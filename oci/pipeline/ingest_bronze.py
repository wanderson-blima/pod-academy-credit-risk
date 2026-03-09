"""
Bronze Ingestion — OCI Data Flow
Reads raw files from landing bucket and writes to bronze bucket.
Storage: Delta Lake (ACID transactions, schema evolution, time travel)
Equivalent to Fabric: 1-ingestao-dados/ingestao-arquivos.py

Tables: 19 total (7 main + 12 dimensions)
Strategy: Overwrite (delete + reload for each table)

Usage: oci data-flow run submit --application-id $APP_OCID --arguments '["landing-bucket", "bronze-bucket", "namespace"]'
"""
import sys
import re
import uuid
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import lit, current_timestamp

# =============================================================================
# STORAGE FORMAT — Delta Lake for production lakehouse
# =============================================================================
STORAGE_FORMAT = "delta"  # "delta" or "parquet"

SPARK_DELTA_CONFIG = {
    "spark.oracle.deltalake.version": "3.1.0",
    "spark.delta.logStore.oci.impl": "io.delta.storage.OracleCloudLogStore",
    "spark.sql.extensions": "io.delta.sql.DeltaSparkSessionExtension",
    "spark.sql.catalog.spark_catalog": "org.apache.spark.sql.delta.catalog.DeltaCatalog",
}

def ingest(spark, source_uri, target_uri, source_format, table_name, safra=None):
    """Ingest a single source file/folder into bronze layer."""
    execution_id = str(uuid.uuid4())

    # Read source
    if source_format == "csv":
        df = spark.read.csv(source_uri, header=True, inferSchema=True, sep=";")
    elif source_format == "parquet":
        df = spark.read.parquet(source_uri)
    elif source_format == "excel":
        df = spark.read.format("com.crealytics.spark.excel") \
            .option("header", "true") \
            .option("inferSchema", "true") \
            .load(source_uri)
    else:
        raise ValueError(f"Unsupported format: {source_format}")

    # Sanitize column names for Delta Lake compatibility
    for c in df.columns:
        clean = re.sub(r'[ ,;{}()\n\t=]', '_', c)
        if clean != c:
            df = df.withColumnRenamed(c, clean)

    # Add audit columns
    df = df.withColumn("_execution_id", lit(execution_id)) \
           .withColumn("_data_inclusao", current_timestamp())

    # Cache and count before write
    df.cache()
    row_count = df.count()

    # Write to bronze in configured format
    target_path = f"{target_uri}/{table_name}/"
    writer = df.write.mode("overwrite")
    if safra:
        writer = writer.partitionBy("SAFRA")
    if STORAGE_FORMAT == "delta":
        writer.format("delta").option("mergeSchema", "true").save(target_path)
    else:
        writer.parquet(target_path)

    df.unpersist()
    print(f"[BRONZE] {table_name}: {row_count} rows ingested. Execution: {execution_id}")
    return row_count


def run_bronze(spark, namespace="grlxi07jz1mo", landing_bucket="pod-academy-landing", bronze_bucket="pod-academy-bronze"):
    """Run full bronze ingestion — 19 tables (7 main + 12 dimensions).
    Strategy: overwrite (delete + reload) for each table.
    Importable entry point for unified pipeline.
    """
    # 7 main tables (from parquet/csv in Landing root folders)
    main_sources = [
        {"name": "dados_cadastrais", "format": "parquet", "path": "dados_cadastrais/"},
        {"name": "telco", "format": "parquet", "path": "telco/"},
        {"name": "score_bureau_movel", "format": "parquet", "path": "score_bureau_movel/"},
        {"name": "recarga", "format": "parquet", "path": "recarga/"},
        {"name": "pagamento", "format": "parquet", "path": "pagamento/"},
        {"name": "faturamento", "format": "parquet", "path": "faturamento/"},
        {"name": "dim_calendario", "format": "csv", "path": "dim_calendario/dim_calendario.csv"},
    ]

    # 12 dimension tables (individual CSVs from recarga_dim/ and faturamento_dim/)
    dimension_sources = [
        {"name": "dim_canal_aquisicao_credito", "format": "csv", "path": "recarga_dim/BI_DIM_CANAL_AQUISICAO_CREDITO.csv"},
        {"name": "dim_forma_pagamento",         "format": "csv", "path": "recarga_dim/BI_DIM_FORMA_PAGAMENTO.csv"},
        {"name": "dim_instituicao",             "format": "csv", "path": "recarga_dim/BI_DIM_INSTITUICAO.csv"},
        {"name": "dim_plano_preco",             "format": "csv", "path": "recarga_dim/BI_DIM_PLANO_PRECO.csv"},
        {"name": "dim_plataforma",              "format": "csv", "path": "recarga_dim/BI_DIM_PLATAFORMA.csv"},
        {"name": "dim_promocao_credito",        "format": "csv", "path": "recarga_dim/BI_DIM_PROMOCAO_CREDITO.csv"},
        {"name": "dim_status_plataforma",       "format": "csv", "path": "recarga_dim/BI_DIM_STATUS_PLATAFORMA.csv"},
        {"name": "dim_tecnologia",              "format": "csv", "path": "recarga_dim/BI_DIM_TECNOLOGIA.csv"},
        {"name": "dim_tipo_credito",            "format": "csv", "path": "recarga_dim/BI_DIM_TIPO_CREDITO.csv"},
        {"name": "dim_tipo_insercao",           "format": "csv", "path": "recarga_dim/BI_DIM_TIPO_INSERCAO.csv"},
        {"name": "dim_tipo_recarga",            "format": "csv", "path": "recarga_dim/BI_DIM_TIPO_RECARGA.csv"},
        {"name": "dim_tipo_faturamento",        "format": "csv", "path": "faturamento_dim/BI_DIM_TIPO_FATURAMENTO.csv"},
    ]

    all_sources = main_sources + dimension_sources
    total = 0
    success = 0
    for src in all_sources:
        source_uri = f"oci://{landing_bucket}@{namespace}/{src['path']}"
        target_uri = f"oci://{bronze_bucket}@{namespace}"
        try:
            count = ingest(spark, source_uri, target_uri, src["format"], src["name"])
            total += count
            success += 1
        except Exception as e:
            print(f"[BRONZE] ERROR ingesting {src['name']}: {e}")

    print(f"[BRONZE] Total: {total} rows ingested across {success}/{len(all_sources)} tables")
    return total


if __name__ == "__main__":
    builder = SparkSession.builder.appName("ingest-bronze")
    if STORAGE_FORMAT == "delta":
        for key, value in SPARK_DELTA_CONFIG.items():
            builder = builder.config(key, value)
    spark = builder.getOrCreate()

    landing_bucket = sys.argv[1] if len(sys.argv) > 1 else "pod-academy-landing"
    bronze_bucket = sys.argv[2] if len(sys.argv) > 2 else "pod-academy-bronze"
    namespace = sys.argv[3] if len(sys.argv) > 3 else "grlxi07jz1mo"

    run_bronze(spark, namespace, landing_bucket, bronze_bucket)
    spark.stop()
