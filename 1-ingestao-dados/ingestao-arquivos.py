"""
Ingestao de Arquivos — Bronze Layer (Staging).

Pipeline de ingestao batch que carrega arquivos fonte (Excel, CSV, Parquet)
para o Lakehouse Bronze no Microsoft Fabric via Delta Lake.

Proposito:
    Ler arquivos de diversas fontes e formatos, enriquecer com colunas de
    auditoria (_execution_id, _data_inclusao) e persistir como tabelas Delta
    no schema staging ou config do Bronze Lakehouse.

Inputs:
    - Lista de dicionarios de parametros (INGESTION_PARAMS) definida em
      config/pipeline_config.py. Cada dict contem:
        source_format : str   — "excel", "csv" ou "parquet"
        source_folder : str   — caminho relativo no Lakehouse (Files/...)
        target_schema : str   — schema destino ("staging" ou "config")
        target_table  : str   — nome da tabela destino
        options       : dict  — opcoes do reader (header, delimiter, etc.)

Outputs:
    - Tabelas Delta em Bronze.<target_schema>.<target_table>
    - Log de execucao em Bronze.log.log_info

Ordem de execucao no pipeline:
    1. ingestao-arquivos.py  (ESTE SCRIPT)
    2. ajustes-tipagem-deduplicacao.py
    3. criacao-dimensoes.py

Uso:
    Executar como notebook no Fabric. O script processa todas as tabelas
    definidas em INGESTION_PARAMS automaticamente (batch).
    Para processar tabelas especificas, passe uma lista filtrada para
    run_ingestion_pipeline().
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp, lit
from datetime import datetime
import uuid
import logging
import pandas as pd

# =============================================================================
# CONFIG CENTRALIZADO
# =============================================================================
import sys; sys.path.insert(0, "/lakehouse/default/Files/projeto-final")
from config.pipeline_config import BRONZE_BASE, PATH_LOG, INGESTION_PARAMS

# =============================================================================
# LOGGING ESTRUTURADO
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ingestao")


# =============================================================================
# FUNCOES DE SUPORTE
# =============================================================================

def _persist_log(spark, exec_id, params, start_time, status, rows=0, error=""):
    """Persiste registro de log no Bronze.log.log_info."""
    log_data = [{
        "ExecutionId": exec_id,
        "Schema": params["target_schema"],
        "TableName": params["target_table"],
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


def _read_source(spark, params):
    """Le arquivo fonte usando Pandas (Excel) ou Spark (CSV/Parquet)."""
    source_path = f"{BRONZE_BASE}/{params['source_folder']}"
    local_path = f"/lakehouse/default/{params['source_folder']}"
    fmt = params["source_format"].lower()

    if fmt == "excel":
        logger.info("Lendo via Pandas: %s", local_path)
        sheet = params["options"].get("dataAddress", "0").split("!")[0].replace("'", "")
        pdf = pd.read_excel(local_path, sheet_name=sheet)
        return spark.createDataFrame(pdf)

    logger.info("Lendo via Spark (%s): %s", fmt, source_path)
    reader = spark.read.format(fmt)
    for k, v in params["options"].items():
        reader = reader.option(k, v)
    return reader.load(source_path)


def ingest_table(spark, params):
    """Ingere uma unica tabela conforme dicionario de parametros.

    Args:
        spark: SparkSession ativa.
        params: Dicionario com source_format, source_folder, target_schema,
                target_table e options.

    Returns:
        int: Quantidade de registros ingeridos.

    Raises:
        Exception: Propaga erro apos registrar no log.
    """
    exec_id = str(uuid.uuid4())
    start_time = datetime.now()
    table_name = params["target_table"]

    logger.info("=== Iniciando ingestao: %s (formato: %s) ===",
                table_name, params["source_format"])

    try:
        spark.conf.set("spark.sql.parquet.vorder.enabled", "true")

        df_raw = _read_source(spark, params)

        logger.info("Enriquecendo com colunas de auditoria...")
        df_final = df_raw \
            .withColumn("_execution_id", lit(exec_id)) \
            .withColumn("_data_inclusao", current_timestamp())

        target_path = f"{BRONZE_BASE}/Tables/{params['target_schema']}/{table_name}"
        logger.info("Salvando em Delta: %s", target_path)

        df_final.write.format("delta") \
            .mode("overwrite") \
            .option("overwriteSchema", "true") \
            .save(target_path)

        count = df_final.count()
        logger.info("Concluido: %s — %d registros", table_name, count)
        _persist_log(spark, exec_id, params, start_time, "SUCCESS", rows=count)
        return count

    except Exception as e:
        logger.error("ERRO em %s: %s", table_name, str(e))
        _persist_log(spark, exec_id, params, start_time, "FAILED", error=e)
        raise


def run_ingestion_pipeline(spark, params_list=None):
    """Executa ingestao batch para todas as tabelas.

    Args:
        spark: SparkSession ativa.
        params_list: Lista de dicts de parametros. Se None, usa INGESTION_PARAMS
                     do config centralizado.

    Returns:
        dict: Resumo {table_name: row_count} das tabelas processadas.
    """
    if params_list is None:
        params_list = INGESTION_PARAMS

    logger.info("Pipeline de ingestao — %d tabelas para processar", len(params_list))

    results = {}
    errors = []

    for i, params in enumerate(params_list, 1):
        table_name = params["target_table"]
        logger.info("[%d/%d] Processando: %s", i, len(params_list), table_name)

        try:
            count = ingest_table(spark, params)
            results[table_name] = count
        except Exception as e:
            errors.append((table_name, str(e)))
            logger.error("Falha em %s — continuando pipeline...", table_name)

    logger.info("=== Pipeline concluido ===")
    logger.info("Sucesso: %d | Falhas: %d", len(results), len(errors))

    for table, count in results.items():
        logger.info("  OK  %s: %d rows", table, count)
    for table, err in errors:
        logger.error("  FAIL %s: %s", table, err)

    if errors:
        logger.warning("Tabelas com erro: %s", [t for t, _ in errors])

    return results


# =============================================================================
# EXECUCAO PRINCIPAL
# =============================================================================
run_ingestion_pipeline(spark)
