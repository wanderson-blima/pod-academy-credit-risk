#!/usr/bin/env python
# coding: utf-8

# ## IngestaoArquivos
# 
# New notebook

# In[ ]:


from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp, lit
from datetime import datetime
import uuid
import pandas as pd

# ======================================================================================
# 1. PARÂMETROS DE AMBIENTE
# ======================================================================================
WORKSPACE_ID = "febb8631-d5c0-43d8-bf08-5e89c8f2d17e"
LAKEHOUSE_ID = "b8822164-7b67-4b17-9a01-3d0737dace7e"
ONELAKE_BASE = f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{LAKEHOUSE_ID}"

# ======================================================================================
# 2. CONFIGURAÇÃO DA INGESTÃO (Altere aqui conforme a necessidade)
# ======================================================================================

# # --- EXEMPLO EXCEL ---
params = {
    "source_format": "excel", 
    "source_folder": "Files/meta_dados_analise.xlsx",
    "target_schema": "config",
    "target_table": "metadados_tabelas",
    "options": {
        "dataAddress": "'info'!A1", # Nome da aba
        "header": "true"
    }
}

# --- EXEMPLO CSV (Descomente para usar) ---
# params = {
#     "source_format": "csv", 
#     "source_folder": "Files/bases_recarga/BI_DIM_CANAL_AQUISICAO_CREDITO.csv",
#     "target_schema": "staging",
#     "target_table": "canal_aquisicao_credito",
#     "options": {"header": "true", "delimiter": ",", "inferSchema": "true", "encoding": "UTF-8"}
# }

#--- EXEMPLO PARQUET (Descomente para usar) ---
# params = {
#     "source_format": "parquet", 
#     "source_folder": "Files/base_score_bureau_movel_full",
#     "target_schema": "staging",
#     "target_table": "base_score_bureau_movel_full",
#     "options": {"header": "true", "inferSchema": "true"}
# }

# ======================================================================================
# 3. CONSTRUÇÃO DOS CAMINHOS
# ======================================================================================
SOURCE_PATH = f"{ONELAKE_BASE}/{params['source_folder']}"
LOCAL_PATH  = f"/lakehouse/default/{params['source_folder']}"
TARGET_PATH = f"{ONELAKE_BASE}/Tables/{params['target_schema']}/{params['target_table']}"
LOG_PATH    = f"{ONELAKE_BASE}/Tables/log/log_info"

# ======================================================================================
# 4. FUNÇÕES DE SUPORTE
# ======================================================================================
EXEC_ID = str(uuid.uuid4())
START_TIME = datetime.now()

def log_step(message):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] [STEP]: {message}")

def persist_log(status, rows=0, error=""):
    log_data = [{
        "ExecutionId": EXEC_ID,
        "Schema": params["target_schema"],
        "TableName": params["target_table"],
        "StartTime": START_TIME,
        "EndTime": datetime.now(),
        "Status": status,
        "RowsAffected": rows,
        "ErrorMessage": str(error)
    }]
    spark.createDataFrame(log_data).write.format("delta").mode("append").option("mergeSchema", "true").save(LOG_PATH)

# ======================================================================================
# 5. EXECUÇÃO DO PIPELINE
# ======================================================================================

def run_pipeline():
    log_step(f"Iniciando Ingestão: {params['target_table']} (Formato: {params['source_format']})")
    
    try:
        # A. Otimização
        spark.conf.set("spark.sql.parquet.vorder.enabled", "true")

        # B. Leitura Híbrida (Excel vs Spark Native)
        format_type = params["source_format"].lower()

        if format_type == "excel":
            log_step(f"Lendo via Pandas: {LOCAL_PATH}")
            # Extração da aba (sheet)
            sheet = params["options"].get("dataAddress", "0").split("!")[0].replace("'", "")
            pdf = pd.read_excel(LOCAL_PATH, sheet_name=sheet)
            df_raw = spark.createDataFrame(pdf)
        
        else:
            log_step(f"Lendo via Spark: {SOURCE_PATH}")
            reader = spark.read.format(format_type)
            # Aplica opções dinamicamente (delimiter, header, etc)
            for k, v in params["options"].items():
                reader = reader.option(k, v)
            df_raw = reader.load(SOURCE_PATH)

        # C. Metadados e Auditoria
        log_step("Enriquecendo dados com linhagem...")
        df_final = df_raw.withColumn("_execution_id", lit(EXEC_ID)) \
                         .withColumn("_data_inclusao", current_timestamp())

        # D. Escrita Delta
        log_step(f"Salvando em Delta Lake: {TARGET_PATH}")
        df_final.write.format("delta") \
            .mode("overwrite") \
            .option("overwriteSchema", "true") \
            .save(TARGET_PATH)

        # E. Finalização
        count = df_final.count()
        log_step(f"Concluído! {count} registros processados.")
        persist_log("SUCCESS", rows=count)

    except Exception as e:
        log_step(f"ERRO: {str(e)}")
        persist_log("FAILED", error=e)
        raise e

run_pipeline()

