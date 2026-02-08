"""
Tipagem e Deduplicacao — Silver Layer (Raw Data).

Pipeline que le tabelas do Bronze (staging), aplica casting de tipos baseado
nos metadados e deduplica registros por PK, persistindo o resultado no Silver
(rawdata) via Delta MERGE (UPSERT).

Proposito:
    Transformar dados brutos do Bronze em dados tipados e deduplicados no
    Silver, garantindo qualidade e consistencia para consumo downstream
    (books de variaveis e feature store).

Inputs:
    - Tabelas Bronze.<staging>.<table_name>
    - Metadados de tipos em Bronze.<config>.metadados_tabelas
    - Lista de tabelas a processar: SILVER_TABLES (config/pipeline_config.py)

Outputs:
    - Tabelas Delta em Silver.<rawdata>.<table_name>
    - Log de execucao em Bronze.log.log_info

Ordem de execucao no pipeline:
    1. ingestao-arquivos.py
    2. ajustes-tipagem-deduplicacao.py  (ESTE SCRIPT)
    3. criacao-dimensoes.py

Uso:
    Executar como notebook no Fabric. O script processa todas as tabelas
    definidas em SILVER_TABLES automaticamente.
    Para processar tabelas especificas, passe uma lista para
    run_silver_pipeline().
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp, lit, row_number, to_timestamp
from pyspark.sql.window import Window
from delta.tables import DeltaTable
from datetime import datetime
import uuid
import logging

# =============================================================================
# CONFIG CENTRALIZADO
# =============================================================================
import sys; sys.path.insert(0, "/lakehouse/default/Files/projeto-final")
from config.pipeline_config import (
    BRONZE_BASE, SILVER_BASE,
    PATH_METADATA_TABLE, PATH_LOG,
    SCHEMA_STAGING, SCHEMA_RAWDATA,
    SILVER_TABLES,
)

# =============================================================================
# LOGGING ESTRUTURADO
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("tipagem_dedup")


# =============================================================================
# FUNCOES DE SUPORTE
# =============================================================================

def _persist_log(spark, exec_id, table_name, start_time, status, rows=0, error=""):
    """Persiste registro de log no Bronze.log.log_info."""
    log_data = [{
        "ExecutionId": exec_id,
        "Schema": SCHEMA_RAWDATA,
        "TableName": table_name,
        "StartTime": start_time,
        "EndTime": datetime.now(),
        "Status": status,
        "RowsAffected": rows,
        "ErrorMessage": str(error),
    }]
    spark.createDataFrame(log_data) \
        .write.format("delta") \
        .mode("append") \
        .option("mergeSchema", "true") \
        .save(PATH_LOG)


def _build_cast_expressions(cols_meta):
    """Constroi lista de expressoes SQL de cast baseado nos metadados.

    Args:
        cols_meta: Lista de Rows com nome_coluna e tipo.

    Returns:
        list[str]: Expressoes selectExpr para casting.
    """
    expressions = []
    for c in cols_meta:
        c_name = c["nome_coluna"]
        c_type = c["tipo"].lower()

        if "timestamp" in c_type or "date" in c_type:
            expressions.append(f"to_timestamp({c_name}, 'ddMMMyyyy:HH:mm:ss') as {c_name}")
        else:
            expressions.append(f"cast({c_name} as {c_type}) as {c_name}")

    return expressions


def process_table(spark, df_meta, table_name, exec_id):
    """Processa uma unica tabela: casting + deduplicacao + MERGE.

    Args:
        spark: SparkSession ativa.
        df_meta: DataFrame de metadados (todas as tabelas).
        table_name: Nome da tabela a processar.
        exec_id: ID unico de execucao.

    Returns:
        int: Quantidade de registros processados.

    Raises:
        Exception: Se tabela nao tem PK definida ou erro de processamento.
    """
    start_time = datetime.now()
    logger.info(">>> Processando: %s", table_name)

    try:
        # 1. Filtrar metadados da tabela
        cols_meta = df_meta.filter(col("nome_tabela") == table_name).collect()

        if not cols_meta:
            raise ValueError(f"Tabela '{table_name}' nao encontrada nos metadados.")

        pk_cols = [c["nome_coluna"] for c in cols_meta if c["primary_key"] == "PK"]

        if not pk_cols:
            raise ValueError(f"Tabela '{table_name}' nao possui PK definida nos metadados.")

        # 2. Leitura Bronze
        source_path = f"{BRONZE_BASE}/Tables/{SCHEMA_STAGING}/{table_name}"
        df_bronze = spark.read.format("delta").load(source_path)

        # 3. Casting de tipos
        select_expr = _build_cast_expressions(cols_meta)

        # Preservar coluna de auditoria para deduplicacao (nao faz parte dos metadados)
        existing_targets = [e.split(" as ")[-1].strip() if " as " in e else e for e in select_expr]
        if "_data_inclusao" in df_bronze.columns and "_data_inclusao" not in existing_targets:
            select_expr.append("_data_inclusao")

        df_casted = df_bronze.selectExpr(*select_expr)

        # 4. Deduplicacao por PK (registro mais recente por _data_inclusao)
        window_spec = Window.partitionBy(*pk_cols).orderBy(col("_data_inclusao").desc())

        df_silver_ready = df_casted \
            .withColumn("_row_num", row_number().over(window_spec)) \
            .filter(col("_row_num") == 1) \
            .drop("_row_num") \
            .withColumn("_execution_id", lit(exec_id)) \
            .withColumn("_data_alteracao_silver", current_timestamp())

        # 5. Escrita / MERGE na Silver
        target_path = f"{SILVER_BASE}/Tables/{SCHEMA_RAWDATA}/{table_name}"

        if DeltaTable.isDeltaTable(spark, target_path):
            logger.info("MERGE (tabela existente). PKs: %s", pk_cols)
            dt_target = DeltaTable.forPath(spark, target_path)
            join_condition = " AND ".join([f"target.{c} = source.{c}" for c in pk_cols])

            dt_target.alias("target").merge(
                df_silver_ready.alias("source"),
                join_condition,
            ).whenMatchedUpdateAll() \
             .whenNotMatchedInsertAll() \
             .execute()
        else:
            logger.info("Criando tabela pela primeira vez: %s", target_path)
            df_silver_ready.write.format("delta").mode("overwrite").save(target_path)

        rows_affected = df_silver_ready.count()

        # 6. Validacao pos-processamento
        df_check = spark.read.format("delta").load(target_path)
        null_pks = df_check.filter(
            " OR ".join([f"{c} IS NULL" for c in pk_cols])
        ).count()

        if null_pks > 0:
            logger.warning("ATENCAO: %d registros com PK nula em %s", null_pks, table_name)

        logger.info("Sucesso: %s — %d registros", table_name, rows_affected)
        _persist_log(spark, exec_id, table_name, start_time, "SUCCESS", rows=rows_affected)
        return rows_affected

    except Exception as e:
        logger.error("ERRO em %s: %s", table_name, str(e))
        _persist_log(spark, exec_id, table_name, start_time, "FAILED", error=e)
        raise


def run_silver_pipeline(spark, table_list=None):
    """Executa pipeline de tipagem e deduplicacao para todas as tabelas.

    Args:
        spark: SparkSession ativa.
        table_list: Lista de nomes de tabelas. Se None, usa SILVER_TABLES
                    do config centralizado.

    Returns:
        dict: Resumo {table_name: row_count} das tabelas processadas.
    """
    if table_list is None:
        table_list = SILVER_TABLES

    exec_id = str(uuid.uuid4())
    logger.info("Pipeline Silver — %d tabelas para processar (exec: %s)",
                len(table_list), exec_id[:8])

    # Carregar metadados uma unica vez
    df_meta = spark.read.format("delta").load(PATH_METADATA_TABLE)

    # Validar que todas as tabelas existem nos metadados
    available_tables = set(
        row["nome_tabela"]
        for row in df_meta.select("nome_tabela").distinct().collect()
    )
    missing = set(table_list) - available_tables
    if missing:
        logger.warning("Tabelas nao encontradas nos metadados: %s", missing)

    results = {}
    errors = []

    for i, table_name in enumerate(table_list, 1):
        logger.info("[%d/%d] %s", i, len(table_list), table_name)

        try:
            count = process_table(spark, df_meta, table_name, exec_id)
            results[table_name] = count
        except Exception as e:
            errors.append((table_name, str(e)))
            logger.error("Falha em %s — continuando pipeline...", table_name)

    logger.info("=== Pipeline Silver concluido ===")
    logger.info("Sucesso: %d | Falhas: %d", len(results), len(errors))

    for table, count in results.items():
        logger.info("  OK  %s: %d rows", table, count)
    for table, err in errors:
        logger.error("  FAIL %s: %s", table, err)

    return results


# =============================================================================
# EXECUCAO PRINCIPAL
# =============================================================================
run_silver_pipeline(spark)
