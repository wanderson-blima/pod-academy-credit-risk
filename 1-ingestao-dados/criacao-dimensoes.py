"""
Criacao de Dimensoes — Silver Layer (Raw Data).

Pipeline que cria as tabelas dimensionais (dim_calendario e dim_num_cpf)
no Silver Lakehouse. Ambas as dimensoes sao idempotentes — so recriam
se a tabela nao existir ou se forcado explicitamente.

Proposito:
    Gerar dimensoes auxiliares para o modelo dimensional do pipeline de
    credit risk. dim_calendario fornece atributos temporais e
    dim_num_cpf mapeia CPFs unicos com surrogate keys deterministicas.

Inputs:
    - Parametros de data range (DATA_INICIAL, DATA_FINAL)
    - Silver.rawdata.dados_cadastrais (para dim_num_cpf)

Outputs:
    - Silver.rawdata.dim_calendario
    - Silver.rawdata.dim_num_cpf

Ordem de execucao no pipeline:
    1. ingestao-arquivos.py
    2. ajustes-tipagem-deduplicacao.py
    3. criacao-dimensoes.py  (ESTE SCRIPT)

Uso:
    Executar como notebook no Fabric. Por padrao, so cria dimensoes que
    ainda nao existem. Use force=True para recriar.
"""

from pyspark.sql import SparkSession, functions as F
from pyspark.sql.functions import monotonically_increasing_id
from delta.tables import DeltaTable
from datetime import datetime
import uuid
import logging

# =============================================================================
# CONFIG CENTRALIZADO
# =============================================================================
import sys; sys.path.insert(0, "/lakehouse/default/Files/projeto-final")
from config.pipeline_config import (
    PATH_DIM_CALENDARIO, PATH_DADOS_CADASTRAIS, PATH_DIM_NUM_CPF, PATH_LOG,
)

# =============================================================================
# LOGGING ESTRUTURADO
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("dimensoes")

# =============================================================================
# PARAMETROS
# =============================================================================
DATA_INICIAL = "2010-01-01"
DATA_FINAL = "2035-12-31"


# =============================================================================
# DIMENSAO: CALENDARIO
# =============================================================================

def create_dim_calendario(spark, force=False):
    """Cria a dimensao de calendario no Silver Lakehouse.

    Gera um range de datas de DATA_INICIAL a DATA_FINAL com atributos
    temporais (ano, mes, trimestre, flags de negocio, etc.).

    Args:
        spark: SparkSession ativa.
        force: Se True, recria mesmo se ja existir.

    Returns:
        int: Quantidade de registros na dimensao.
    """
    if not force and DeltaTable.isDeltaTable(spark, PATH_DIM_CALENDARIO):
        count = spark.read.format("delta").load(PATH_DIM_CALENDARIO).count()
        logger.info("dim_calendario ja existe (%d registros). Use force=True para recriar.", count)
        return count

    logger.info("Criando dim_calendario (%s a %s)...", DATA_INICIAL, DATA_FINAL)

    df_datas = (
        spark.range(1)
        .select(
            F.explode(
                F.sequence(
                    F.to_date(F.lit(DATA_INICIAL)),
                    F.to_date(F.lit(DATA_FINAL)),
                    F.expr("interval 1 day"),
                )
            ).alias("Data")
        )
    )

    df_calendario = (
        df_datas
        .withColumn("DataKey", F.date_format("Data", "yyyyMMdd").cast("int"))
        .withColumn("Ano", F.year("Data"))
        .withColumn("Mes", F.month("Data"))
        .withColumn("Dia", F.dayofmonth("Data"))
        .withColumn("DiaSemana", F.dayofweek("Data"))
        .withColumn("DiaAno", F.dayofyear("Data"))
        .withColumn("SemanaAno", F.weekofyear("Data"))
        .withColumn("Trimestre", F.quarter("Data"))
        .withColumn("NomeMes", F.date_format("Data", "MMMM"))
        .withColumn("NomeMesAbrev", F.date_format("Data", "MMM"))
        .withColumn("NomeDiaSemana", F.date_format("Data", "EEEE"))
        .withColumn("AnoMes", F.concat_ws("-", F.col("Ano"), F.lpad(F.col("Mes"), 2, "0")))
        .withColumn("NumAnoMes", (F.col("Ano") * 100 + F.col("Mes")).cast("int"))
        .withColumn("MesAno", F.concat_ws("/", F.lpad(F.col("Mes"), 2, "0"), F.col("Ano")))
        .withColumn("AnoTrimestre", F.concat_ws("T", F.col("Ano"), F.col("Trimestre")))
        .withColumn("EhFimDeSemana", F.col("DiaSemana").isin([1, 7]))
        .withColumn("EhDiaUtil", ~F.col("DiaSemana").isin([1, 7]))
        .withColumn("EhHoje", F.col("Data") == F.current_date())
        .withColumn("EhMesAtual",
                    (F.col("Ano") == F.year(F.current_date())) &
                    (F.col("Mes") == F.month(F.current_date())))
        .withColumn("EhAnoAtual", F.col("Ano") == F.year(F.current_date()))
    )

    df_final = df_calendario.select(
        "DataKey", "Data", "Ano", "AnoMes", "NumAnoMes", "AnoTrimestre",
        "Mes", "NomeMes", "NomeMesAbrev", "MesAno", "Trimestre",
        "SemanaAno", "Dia", "DiaAno", "DiaSemana", "NomeDiaSemana",
        "EhFimDeSemana", "EhDiaUtil", "EhHoje", "EhMesAtual", "EhAnoAtual",
    ).orderBy("Data")

    df_final.write.mode("overwrite").format("delta") \
        .option("overwriteSchema", "true") \
        .save(PATH_DIM_CALENDARIO)

    count = df_final.count()
    logger.info("dim_calendario criada: %d registros", count)
    return count


# =============================================================================
# DIMENSAO: NUM_CPF
# =============================================================================

def create_dim_num_cpf(spark, force=False):
    """Cria a dimensao de CPFs unicos com surrogate key distribuida.

    Le CPFs distintos de dados_cadastrais e atribui CpfKey via
    monotonically_increasing_id() (distribuido, sem gargalo de particao unica).

    Args:
        spark: SparkSession ativa.
        force: Se True, recria mesmo se ja existir.

    Returns:
        int: Quantidade de CPFs unicos na dimensao.
    """
    if not force and DeltaTable.isDeltaTable(spark, PATH_DIM_NUM_CPF):
        count = spark.read.format("delta").load(PATH_DIM_NUM_CPF).count()
        logger.info("dim_num_cpf ja existe (%d registros). Use force=True para recriar.", count)
        return count

    logger.info("Criando dim_num_cpf...")

    df_origem = spark.read.format("delta").load(PATH_DADOS_CADASTRAIS)

    df_cpf = (
        df_origem
        .select(F.col("NUM_CPF").cast("string").alias("NumCPF"))
        .where(F.col("NumCPF").isNotNull())
        .where(F.trim(F.col("NumCPF")) != "")
        .dropDuplicates(["NumCPF"])
    )

    # Surrogate key distribuida via monotonically_increasing_id().
    # Tradeoff: nao e deterministica entre execucoes, mas escala bem com 3.9M+ rows
    # evitando o gargalo de particao unica que row_number() sem partitionBy causa.
    df_final = (
        df_cpf
        .withColumn("CpfKey", (monotonically_increasing_id() + 1).cast("int"))
        .select("CpfKey", "NumCPF")
    )

    df_final.write.mode("overwrite").format("delta") \
        .option("overwriteSchema", "true") \
        .save(PATH_DIM_NUM_CPF)

    count = df_final.count()
    logger.info("dim_num_cpf criada: %d CPFs unicos", count)
    return count


# =============================================================================
# LOG PERSISTENCE
# =============================================================================

def _persist_log(spark, exec_id, dim_name, start_time, status, rows=0, error=""):
    """Persiste registro de log no Bronze.log.log_info."""
    log_data = [{
        "ExecutionId": exec_id,
        "Schema": "rawdata",
        "TableName": dim_name,
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


# =============================================================================
# FUNCAO PRINCIPAL
# =============================================================================

def run_dimensions_pipeline(spark, force=False):
    """Cria todas as dimensoes do pipeline.

    Args:
        spark: SparkSession ativa.
        force: Se True, recria dimensoes mesmo se ja existirem.

    Returns:
        dict: Resumo {dim_name: row_count}.
    """
    exec_id = str(uuid.uuid4())
    logger.info("Pipeline de dimensoes — force=%s (exec: %s)", force, exec_id[:8])

    results = {}
    errors = []

    # --- dim_calendario ---
    start_time = datetime.now()
    try:
        count = create_dim_calendario(spark, force=force)
        results["dim_calendario"] = count
        _persist_log(spark, exec_id, "dim_calendario", start_time, "SUCCESS", rows=count)
    except Exception as e:
        logger.error("ERRO em dim_calendario: %s", str(e))
        errors.append(("dim_calendario", str(e)))
        _persist_log(spark, exec_id, "dim_calendario", start_time, "FAILED", error=e)

    # --- dim_num_cpf ---
    start_time = datetime.now()
    try:
        count = create_dim_num_cpf(spark, force=force)
        results["dim_num_cpf"] = count
        _persist_log(spark, exec_id, "dim_num_cpf", start_time, "SUCCESS", rows=count)
    except Exception as e:
        logger.error("ERRO em dim_num_cpf: %s", str(e))
        errors.append(("dim_num_cpf", str(e)))
        _persist_log(spark, exec_id, "dim_num_cpf", start_time, "FAILED", error=e)

    logger.info("=== Pipeline de dimensoes concluido ===")
    logger.info("Sucesso: %d | Falhas: %d", len(results), len(errors))
    for dim, count in results.items():
        logger.info("  OK  %s: %d registros", dim, count)
    for dim, err in errors:
        logger.error("  FAIL %s: %s", dim, err)

    return results


# =============================================================================
# EXECUCAO PRINCIPAL
# =============================================================================
run_dimensions_pipeline(spark)
