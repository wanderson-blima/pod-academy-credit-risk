"""
Silver Transformation — OCI Data Flow
Type casting (metadata-driven), deduplication, cleansing.
Tables: 19 total (7 main + 12 dimensions) — all read from Bronze (Delta)
Strategy: Overwrite (delete + reload for each table)
Equivalent to Fabric: 2-metadados/ajustes-tipagem-deduplicacao.py
Storage: Delta Lake (ACID transactions, schema evolution, time travel)

Usage: oci data-flow run submit --application-id $APP_OCID --arguments '["bronze-bucket", "silver-bucket", "namespace"]'
"""
import sys
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, trim, upper, to_date, to_timestamp,
    row_number, desc, current_timestamp, regexp_replace
)
from pyspark.sql.window import Window
from pyspark.sql.types import IntegerType, DoubleType, LongType, StringType, DateType

# =============================================================================
# STORAGE FORMAT — Delta Lake for production lakehouse
# =============================================================================
STORAGE_FORMAT = "delta"  # "delta" or "parquet"

# Delta/Spark extensions config
SPARK_DELTA_CONFIG = {
    "spark.oracle.deltalake.version": "3.1.0",
    "spark.delta.logStore.oci.impl": "io.delta.storage.OracleCloudLogStore",
    "spark.sql.extensions": "io.delta.sql.DeltaSparkSessionExtension",
    "spark.sql.catalog.spark_catalog": "org.apache.spark.sql.delta.catalog.DeltaCatalog",
}


# =============================================================================
# TYPE CASTING CONFIG — Ported from Fabric metadados_tabelas (hardcoded)
# Format: {table_name: {column_name: target_type}}
# Types: int, long, double, date, timestamp, string
# Derived from: src/metadata/ajustes-tipagem-deduplicacao.py + enriched metadata JSONs
# =============================================================================
TYPE_CONFIG = {
    "dados_cadastrais": {
        "SAFRA": "int",
        "FLAG_INSTALACAO": "int",
        "FPD": "int",
        "var_02": "int", "var_03": "int", "var_04": "int", "var_05": "int",
        "var_06": "int", "var_07": "int", "var_08": "int", "var_09": "int",
        "var_14": "int", "var_16": "int", "var_17": "int",
        "var_26": "int", "var_27": "int", "var_28": "int",
        "var_29": "double", "var_30": "double", "var_31": "double",
        "DATADENASCIMENTO": "date",
    },
    "telco": {
        "SAFRA": "int",
        "FLAG_INSTALACAO": "int",
        "FPD": "int",
        "flag_mig2": "string",
        "var_32": "double", "var_33": "double", "var_34": "double",
        "var_35": "double", "var_36": "double", "var_37": "double",
        "var_38": "double", "var_39": "double", "var_40": "double",
        "var_41": "double", "var_42": "double", "var_43": "double",
        "var_44": "int", "var_45": "int", "var_46": "int", "var_47": "int",
        "var_48": "int", "var_49": "int", "var_50": "int", "var_51": "int",
        "var_52": "int", "var_53": "int", "var_54": "int", "var_55": "int",
        "var_56": "int", "var_57": "int", "var_58": "double",
        "var_59": "int", "var_60": "int", "var_61": "int",
        "var_62": "double", "var_63": "double", "var_64": "double",
        "var_65": "double", "var_66": "double", "var_67": "double",
        "var_68": "int",
        "var_69": "double", "var_70": "double", "var_71": "double",
        "var_72": "double",
        "var_73": "int", "var_74": "int", "var_75": "int", "var_76": "int",
        "var_77": "int", "var_78": "int", "var_79": "int", "var_80": "int",
        "var_81": "int",
        "var_82": "int", "var_83": "int", "var_84": "int", "var_85": "int",
        "var_86": "int", "var_87": "int", "var_88": "int", "var_89": "int",
        "var_90": "int", "var_91": "int", "var_92": "int", "var_93": "int",
    },
    "score_bureau_movel": {
        "SAFRA": "int",
        "SCORE_01": "int",
        "SCORE_02": "int",
        "FPD": "int",
        "FLAG_INSTALACAO": "int",
    },
    "recarga": {
        "VAL_CREDITO_INSERIDO": "double",
        "VAL_BONUS": "double",
        "VAL_REAL": "double",
        "FLAG_SOS": "int",
        "DAT_INSERCAO_CREDITO": "timestamp_custom",
    },
    "pagamento": {
        "VAL_PAGAMENTO_FATURA": "double",
        "VAL_PAGAMENTO_ITEM": "double",
        "VAL_PAGAMENTO_CREDITO": "double",
        "VAL_ATUAL_PAGAMENTO": "double",
        "VAL_ORIGINAL_PAGAMENTO": "double",
        "VAL_BAIXA_ATIVIDADE": "double",
        "VAL_JUROS_MULTAS_ITEM": "double",
        "VAL_MULTA_EQUIP_ITEM": "double",
        "DAT_STATUS_FATURA": "timestamp_custom",
        "DAT_CRIACAO_DW": "timestamp_custom",
        "DAT_CRIACAO_ATIVIDADE": "timestamp_custom",
        "DAT_BAIXA_ATIVIDADE": "timestamp_custom",
        "DAT_DEPOSITO_ATIVIDADE": "timestamp_custom",
    },
    "faturamento": {
        "VAL_FAT_BRUTO": "double",
        "VAL_FAT_LIQUIDO": "double",
        "VAL_FAT_CREDITO": "double",
        "VAL_FAT_ABERTO": "double",
        "VAL_FAT_ABERTO_LIQ": "double",
        "VAL_FAT_AJUSTE": "double",
        "VAL_FAT_BRUTO_BC": "double",
        "VAL_FAT_PAGAMENTO_BRUTO": "double",
        "VAL_FAT_LIQ_JM_MC": "double",
        "VAL_MULTA_JUROS": "double",
        "VAL_MULTA_CANCELAMENTO": "double",
        "VAL_PARC_APARELHO_LIQ": "double",
        "DAT_REFERENCIA": "timestamp_custom",
        "DAT_CRIACAO_FAT": "timestamp_custom",
        "DAT_VENCIMENTO_FAT": "timestamp_custom",
        "DAT_STATUS_FAT": "timestamp_custom",
        "DAT_ATIVACAO_CONTA_CLI": "timestamp_custom",
    },
    "dim_calendario": {
        "DT_REFERENCIA": "date",
        "SAFRA": "int",
        "ANO": "int",
        "MES": "int",
        "DIA": "int",
        "DIA_SEMANA": "int",
        "TRIMESTRE": "int",
        "SEMESTRE": "int",
    },
}

# =============================================================================
# TABLE CONFIGS: primary keys + dedup strategy
# =============================================================================
TABLES_MAIN = {
    "dados_cadastrais":   {"pk": ["NUM_CPF", "SAFRA"]},
    "telco":              {"pk": ["NUM_CPF", "SAFRA"]},
    "score_bureau_movel": {"pk": ["NUM_CPF", "SAFRA"]},
    "recarga":            {"pk": []},       # transactional — full-row dedup
    "pagamento":          {"pk": []},       # transactional — full-row dedup
    "faturamento":        {"pk": []},       # transactional — full-row dedup
    "dim_calendario":     {"pk": ["DT_REFERENCIA"]},
}

# =============================================================================
# DIMENSION TABLES — now read from Bronze (Delta) instead of Landing CSVs
# Bronze ingestion (ingest_bronze.py) loads each dimension as individual Delta table
# =============================================================================
DIMENSION_TABLES = {
    "dim_canal_aquisicao_credito": {"pk": ["COD_CANAL_AQUISICAO"]},
    "dim_forma_pagamento":         {"pk": ["DW_FORMA_PAGAMENTO"]},
    "dim_instituicao":             {"pk": ["DW_INSTITUICAO"]},
    "dim_plano_preco":             {"pk": ["DW_PLANO"]},
    "dim_plataforma":              {"pk": ["COD_PLATAFORMA"]},
    "dim_promocao_credito":        {"pk": ["DW_PROMOCAO_CREDITO"]},
    "dim_status_plataforma":       {"pk": ["COD_STATUS_PLATAFORMA"]},
    "dim_tecnologia":              {"pk": ["DW_TECNOLOGIA"]},
    "dim_tipo_credito":            {"pk": ["COD_TIPO_CREDITO"]},
    "dim_tipo_insercao":           {"pk": ["DW_TIPO_INSERCAO"]},
    "dim_tipo_recarga":            {"pk": ["DW_TIPO_RECARGA"]},
    "dim_tipo_faturamento":        {"pk": ["DW_TIPO_FATURAMENTO"]},
}


def type_cast(df, table_name, type_config):
    """Apply type casting based on metadata configuration.
    Handles custom date format: 01MAY2024:00:00:00 → to_timestamp via ddMMMyyyy:HH:mm:ss
    """
    if table_name not in type_config:
        return df

    for col_name, target_type in type_config[table_name].items():
        if col_name not in df.columns:
            continue
        if target_type == "int":
            df = df.withColumn(col_name, col(col_name).cast(IntegerType()))
        elif target_type == "long":
            df = df.withColumn(col_name, col(col_name).cast(LongType()))
        elif target_type == "double":
            df = df.withColumn(col_name, col(col_name).cast(DoubleType()))
        elif target_type == "date":
            df = df.withColumn(col_name,
                to_date(regexp_replace(col(col_name), ":00:00:00$", ""), "ddMMMyyyy"))
        elif target_type == "timestamp_custom":
            # Fabric format: 01MAY2024:00:00:00 → to_timestamp(col, 'ddMMMyyyy:HH:mm:ss')
            df = df.withColumn(col_name,
                to_timestamp(col(col_name), "ddMMMyyyy:HH:mm:ss"))
        elif target_type == "string":
            df = df.withColumn(col_name, trim(col(col_name)))

    return df


def deduplicate(df, pk_columns):
    """Remove duplicates keeping most recent _data_inclusao."""
    valid_pks = [c for c in pk_columns if c in df.columns]
    if not valid_pks:
        return df.dropDuplicates()

    if "_data_inclusao" not in df.columns:
        return df.dropDuplicates(valid_pks)

    w = Window.partitionBy(*valid_pks).orderBy(desc("_data_inclusao"))
    return df.withColumn("_rn", row_number().over(w)) \
             .filter(col("_rn") == 1) \
             .drop("_rn")


def read_table(spark, uri):
    """Read table in configured storage format."""
    if STORAGE_FORMAT == "delta":
        return spark.read.format("delta").load(uri)
    return spark.read.parquet(uri)


def write_table(df, uri, partition_by=None):
    """Write table in configured storage format with overwriteSchema for Delta."""
    writer = df.write.mode("overwrite")
    if STORAGE_FORMAT == "delta":
        writer = writer.format("delta").option("overwriteSchema", "true")
    if partition_by:
        writer = writer.partitionBy(partition_by)
    if STORAGE_FORMAT == "delta":
        writer.save(uri)
    else:
        writer.parquet(uri)


def merge_table(spark, df, uri, pk_columns, partition_by=None):
    """Delta MERGE (upsert) for incremental updates."""
    from delta.tables import DeltaTable

    if STORAGE_FORMAT != "delta":
        write_table(df, uri, partition_by)
        return

    try:
        delta_table = DeltaTable.forPath(spark, uri)
        merge_condition = " AND ".join([f"target.{pk} = source.{pk}" for pk in pk_columns])

        merger = delta_table.alias("target").merge(
            df.alias("source"), merge_condition
        )
        merger.whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()
        print(f"  [MERGE] Delta MERGE completed on {uri}")
    except Exception:
        # Table doesn't exist yet — do initial write
        write_table(df, uri, partition_by)
        print(f"  [MERGE] Initial write (table did not exist)")


def run_silver(spark, namespace="grlxi07jz1mo", bronze_bucket="pod-academy-bronze",
               silver_bucket="pod-academy-silver", landing_bucket=None):
    """Run full silver transformation — 19 tables (7 main + 12 dimensions).
    All tables read from Bronze (Delta) → type cast + dedup → write to Silver (Delta).
    Strategy: overwrite (delete + reload) for each table.
    Importable entry point for unified pipeline.
    """
    from pyspark.sql.types import StringType

    # Phase 1: Main tables
    print("=" * 60)
    print("PHASE 1: Main tables (Bronze -> Silver rawdata)")
    print("=" * 60)

    for table_name, config in TABLES_MAIN.items():
        source_uri = f"oci://{bronze_bucket}@{namespace}/{table_name}/"
        target_uri = f"oci://{silver_bucket}@{namespace}/rawdata/{table_name}/"

        print(f"\n[SILVER] Processing {table_name}...")
        df = read_table(spark, source_uri)
        count_before = df.count()
        print(f"[SILVER] {table_name}: {count_before} rows read from Bronze. "
              f"Schema: {len(df.columns)} cols")

        df = type_cast(df, table_name, TYPE_CONFIG)

        for c in [c for c in df.columns if df.schema[c].dataType == StringType()]:
            df = df.withColumn(c, trim(col(c)))

        df = deduplicate(df, config["pk"])
        df = df.withColumn("_data_alteracao_silver", current_timestamp())

        partition_col = "SAFRA" if "SAFRA" in df.columns else None
        write_table(df, target_uri, partition_by=partition_col)

        count_after = df.count()
        print(f"[SILVER] {table_name}: {count_before} -> {count_after} rows "
              f"({count_before - count_after} duplicates removed)")

    # Phase 2: Dimension tables (from Bronze Delta, same flow as main tables)
    print("\n" + "=" * 60)
    print("PHASE 2: Dimension tables (Bronze Delta -> Silver rawdata)")
    print("=" * 60)

    for dim_name, dim_config in DIMENSION_TABLES.items():
        source_uri = f"oci://{bronze_bucket}@{namespace}/{dim_name}/"
        target_uri = f"oci://{silver_bucket}@{namespace}/rawdata/{dim_name}/"

        print(f"\n[SILVER DIM] Processing {dim_name}...")
        try:
            df = read_table(spark, source_uri)
            count_before = df.count()

            for c in [c for c in df.columns if df.schema[c].dataType == StringType()]:
                df = df.withColumn(c, trim(col(c)))

            df = deduplicate(df, dim_config["pk"])
            df = df.withColumn("_data_alteracao_silver", current_timestamp())
            write_table(df, target_uri)

            count_after = df.count()
            print(f"[SILVER DIM] {dim_name}: {count_before} -> {count_after} rows")
        except Exception as e:
            print(f"[SILVER DIM] ERROR processing {dim_name}: {e}")

    # Summary
    total_tables = len(TABLES_MAIN) + len(DIMENSION_TABLES)
    print("\n" + "=" * 60)
    print("SILVER TRANSFORM COMPLETE")
    print("=" * 60)
    print(f"  Main tables: {len(TABLES_MAIN)}")
    print(f"  Dimension tables: {len(DIMENSION_TABLES)}")
    print(f"  Total: {total_tables} tables")
    print(f"  Storage format: {STORAGE_FORMAT}")
    print(f"  Source: oci://{bronze_bucket}@{namespace}/ (all tables from Bronze)")
    print(f"  Output: oci://{silver_bucket}@{namespace}/rawdata/")


if __name__ == "__main__":
    builder = SparkSession.builder.appName("transform-silver")
    if STORAGE_FORMAT == "delta":
        for key, value in SPARK_DELTA_CONFIG.items():
            builder = builder.config(key, value)
    spark = builder.getOrCreate()

    bronze_bucket = sys.argv[1] if len(sys.argv) > 1 else "pod-academy-bronze"
    silver_bucket = sys.argv[2] if len(sys.argv) > 2 else "pod-academy-silver"
    namespace = sys.argv[3] if len(sys.argv) > 3 else "grlxi07jz1mo"
    landing_bucket = sys.argv[4] if len(sys.argv) > 4 else "pod-academy-landing"

    run_silver(spark, namespace, bronze_bucket, silver_bucket, landing_bucket)
    spark.stop()
