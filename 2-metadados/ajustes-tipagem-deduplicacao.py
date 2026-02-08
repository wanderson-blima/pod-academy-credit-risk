#!/usr/bin/env python
# coding: utf-8

# ## TipagemDeduplicacao
# 
# New notebook

# In[1]:


from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp, lit, row_number, to_timestamp
from pyspark.sql.window import Window
from delta.tables import DeltaTable
from datetime import datetime
import uuid

# ======================================================================================
# 1. PARÂMETROS DE AMBIENTE
# ======================================================================================
WORKSPACE_ID = "febb8631-d5c0-43d8-bf08-5e89c8f2d17e"
BRONZE_ID    = "b8822164-7b67-4b17-9a01-3d0737dace7e" 
SILVER_ID    = "5f8a4808-6f65-401b-a427-b0dd9d331b35" 

BRONZE_BASE = f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{BRONZE_ID}"
SILVER_BASE = f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{SILVER_ID}"

METADATA_TABLE_PATH = f"{BRONZE_BASE}/Tables/config/metadados_tabelas"
LOG_PATH            = f"{BRONZE_BASE}/Tables/log/log_info"

SOURCE_SCHEMA = "staging"
TARGET_SCHEMA = "rawdata"

# ======================================================================================
# 2. FUNÇÕES DE APOIO E LOG
# ======================================================================================
EXEC_ID = str(uuid.uuid4())

def persist_log(table_name, status, rows=0, error=""):
    log_data = [{
        "ExecutionId": EXEC_ID,
        "Schema": TARGET_SCHEMA,
        "TableName": table_name,
        "StartTime": datetime.now(),
        "EndTime": datetime.now(),
        "Status": status,
        "RowsAffected": rows,
        "ErrorMessage": str(error)
    }]
    spark.createDataFrame(log_data).write.format("delta").mode("append").option("mergeSchema", "true").save(LOG_PATH)

# ======================================================================================
# 3. EXECUÇÃO DO PIPELINE
# ======================================================================================

def run_silver_migration():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Iniciando processamento da Camada Silver...")
    
    df_meta = spark.read.format("delta").load(METADATA_TABLE_PATH)

    # Lista de tabelas únicas para processar
    # tabelas = df_meta.select("nome_tabela").distinct().collect()  # Fazer o loop em todas as tabelas, sem filtrar a tabela de metadados

    # # Lista de tabelas desejadas
    lista_tabelas = ["score_bureau_movel_full"]

    tabelas = df_meta.filter(col("nome_tabela").isin(lista_tabelas)) \
                    .select("nome_tabela") \
                    .distinct() \
                    .collect()

    for row in tabelas:
        table_name = row["nome_tabela"]
        print(f"\n>>> Processando Tabela: {table_name}")
        
        try:
            # 2. Filtra metadados da tabela
            cols_meta = df_meta.filter(col("nome_tabela") == table_name)
            list_cols = cols_meta.collect()
            pk_cols = [c["nome_coluna"] for c in list_cols if c["primary_key"] == "PK"]
            
            if not pk_cols:
                raise Exception(f"Tabela {table_name} não possui PK definida nos metadados.")

            # 3. Leitura Bronze
            source_path = f"{BRONZE_BASE}/Tables/{SOURCE_SCHEMA}/{table_name}"
            df_bronze = spark.read.format("delta").load(source_path)

            # 4. Casting e Preparação com tratamento de Data Customizada
            # ----------------------------------------------------------------------------------
            select_expr = []
            for c in list_cols:
                c_name = c['nome_coluna']
                c_type = c['tipo'].lower()
                
                # Tratamento especial para o formato 01MAY2024:00:00:00
                if "timestamp" in c_type or "date" in c_type:
                    expr = f"to_timestamp({c_name}, 'ddMMMyyyy:HH:mm:ss') as {c_name}"
                else:
                    expr = f"cast({c_name} as {c_type}) as {c_name}"
                
                select_expr.append(expr)
            
            df_casted = df_bronze.selectExpr(*select_expr)
            # ----------------------------------------------------------------------------------

            # 5. Lógica de Deduplicação
            # ----------------------------------------------------------------------------------
            # Ordenamos pela data de inclusão técnica para pegar o registro mais recente
            window_spec = Window.partitionBy(*pk_cols).orderBy(col("_data_inclusao").desc())
            
            df_silver_ready = df_casted \
                .withColumn("row_num", row_number().over(window_spec)) \
                .filter(col("row_num") == 1) \
                .drop("row_num") \
                .withColumn("_execution_id", lit(EXEC_ID)) \
                .withColumn("_data_alteracao_silver", current_timestamp())

            # 6. Escrita / Merge na Silver
            # ----------------------------------------------------------------------------------
            target_path = f"{SILVER_BASE}/Tables/{TARGET_SCHEMA}/{table_name}"
            
            if DeltaTable.isDeltaTable(spark, target_path):
                print(f"Executando MERGE (Tabela existente). PKs: {pk_cols}")
                dt_target = DeltaTable.forPath(spark, target_path)
                
                join_condition = " AND ".join([f"target.{c} = source.{c}" for c in pk_cols])
                
                dt_target.alias("target").merge(
                    df_silver_ready.alias("source"),
                    join_condition
                ).whenMatchedUpdateAll() \
                 .whenNotMatchedInsertAll() \
                 .execute()
                
                rows_affected = df_silver_ready.count()
            else:
                print(f"Criando tabela pela primeira vez. Local: {target_path}")
                df_silver_ready.write.format("delta").mode("overwrite").save(target_path)
                rows_affected = df_silver_ready.count()

            persist_log(table_name, "SUCCESS", rows=rows_affected)
            print(f"Sucesso: {table_name} processada com sucesso.")

        except Exception as e:
            print(f"ERRO na tabela {table_name}: {str(e)}")
            persist_log(table_name, "FAILED", error=e)

run_silver_migration()

