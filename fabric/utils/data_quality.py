"""
Validacao de Qualidade de Dados — Pipeline Credit Risk (Hackathon PoD Academy).

Modulo de validacao end-to-end para o pipeline medallion (Bronze -> Silver -> Gold).
Executa checagens automatizadas em cada camada e gera relatorio consolidado
com status PASS/FAIL por tabela e por verificacao individual.

Funcoes principais:
    validate_bronze_to_silver(spark, table_name)
        Valida a transicao Bronze->Silver para uma tabela:
        existencia, contagem, PKs nulas, tipos, colunas de auditoria.

    validate_book(spark, book_name, expected_features=None)
        Valida um book de variaveis (Silver.book):
        existencia, contagem de features, tipo SAFRA, leakage, duplicatas, range SAFRA.

    validate_feature_store(spark)
        Valida a feature store consolidada (Gold):
        todos os checks de book + prefixos, targets, distribuicao SAFRA, volume.

    run_full_validation(spark)
        Orquestra todas as validacoes (Silver tables + books + feature store).

    generate_report(results, output_path=None)
        Gera relatorio Markdown com sumario e detalhes por tabela.

Inputs:
    - SparkSession ativa (disponivel no ambiente Fabric como `spark`)
    - Configuracoes importadas de config.pipeline_config

Outputs:
    - Dicts estruturados com {table/book, status, checks: [{name, passed, detail}]}
    - Relatorio Markdown (stdout ou arquivo)

Uso:
    Executar como notebook no Fabric:

        from utils.data_quality import run_full_validation, generate_report
        results = run_full_validation(spark)
        generate_report(results)

    Ou via bloco __main__:

        # No Fabric, basta executar a celula — usa `spark` global
        results = run_full_validation(spark)
        generate_report(results)
"""

from datetime import datetime
import logging

# =============================================================================
# CONFIG CENTRALIZADO
# =============================================================================
import sys; sys.path.insert(0, "/lakehouse/default/Files/projeto-final")
from config.pipeline_config import (
    BRONZE_BASE, SILVER_BASE, GOLD_BASE,
    SCHEMA_STAGING, SCHEMA_RAWDATA, SCHEMA_BOOK, SCHEMA_FEATURE_STORE,
    PATH_METADATA_TABLE, PATH_FEATURE_STORE,
    PATH_BOOK_RECARGA_CMV, PATH_BOOK_PAGAMENTO, PATH_BOOK_FATURAMENTO,
    SAFRAS, SILVER_TABLES,
    LEAKAGE_BLACKLIST, TARGET_COLUMNS, EXPECTED_FEATURES,
    get_staging_path, get_rawdata_path, get_book_path,
)

# =============================================================================
# LOGGING ESTRUTURADO
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("data_quality")

# =============================================================================
# CONSTANTES INTERNAS
# =============================================================================
AUDIT_COLUMNS_SILVER = ["_execution_id", "_data_inclusao", "_data_alteracao_silver"]

BOOK_PATHS = {
    "ass_recarga_cmv": PATH_BOOK_RECARGA_CMV,
    "pagamento": PATH_BOOK_PAGAMENTO,
    "faturamento": PATH_BOOK_FATURAMENTO,
}

# Approximate expected total records in feature store
FEATURE_STORE_EXPECTED_RECORDS = 3_900_000
FEATURE_STORE_TOLERANCE = 0.30  # warn if > 30% deviation

# If a SAFRA has less than this fraction of the max SAFRA count, flag it
SAFRA_IMBALANCE_THRESHOLD = 0.10


# =============================================================================
# HELPER: check builder
# =============================================================================

def _check(name, passed, detail=""):
    """Cria um dict padrao de resultado de check."""
    return {"name": name, "passed": bool(passed), "detail": str(detail)}


def _overall_status(checks):
    """Retorna 'PASS' se todos os checks passaram, senao 'FAIL'."""
    return "PASS" if all(c["passed"] for c in checks) else "FAIL"


def _is_delta_table(spark, path):
    """Verifica se o path e uma tabela Delta valida."""
    from delta.tables import DeltaTable
    try:
        return DeltaTable.isDeltaTable(spark, path)
    except Exception:
        return False


# =============================================================================
# 1. VALIDATE BRONZE TO SILVER
# =============================================================================

def validate_bronze_to_silver(spark, table_name):
    """Valida a transicao Bronze->Silver para uma tabela.

    Checagens:
        - Tabela Silver existe como Delta
        - Tabela Bronze (staging) existe como Delta
        - Row count: Silver <= Bronze (deduplicacao reduz ou mantem)
        - PKs sem nulos (NUM_CPF onde aplicavel)
        - Tipos reais conferem com metadados (config.metadados_tabelas)
        - Colunas de auditoria presentes

    Args:
        spark: SparkSession ativa.
        table_name: Nome da tabela (ex: "score_bureau_movel_full").

    Returns:
        dict: {table, status, checks: [{name, passed, detail}]}
    """
    logger.info("Validando Bronze->Silver: %s", table_name)
    checks = []

    staging_path = get_staging_path(table_name)
    rawdata_path = get_rawdata_path(table_name)

    # --- Check: Silver table exists ---
    try:
        silver_exists = _is_delta_table(spark, rawdata_path)
        checks.append(_check(
            "silver_table_exists",
            silver_exists,
            f"Path: {rawdata_path}" if silver_exists else f"Delta table not found at {rawdata_path}",
        ))
    except Exception as e:
        checks.append(_check("silver_table_exists", False, f"Error: {e}"))

    # --- Check: Bronze table exists ---
    try:
        bronze_exists = _is_delta_table(spark, staging_path)
        checks.append(_check(
            "bronze_table_exists",
            bronze_exists,
            f"Path: {staging_path}" if bronze_exists else f"Delta table not found at {staging_path}",
        ))
    except Exception as e:
        checks.append(_check("bronze_table_exists", False, f"Error: {e}"))

    # If either table is missing, skip remaining checks
    if not all(c["passed"] for c in checks):
        logger.warning("Tabelas nao encontradas para %s — pulando checks restantes", table_name)
        return {"table": table_name, "status": _overall_status(checks), "checks": checks}

    # --- Check: Row count comparison ---
    try:
        df_bronze = spark.read.format("delta").load(staging_path)
        df_silver = spark.read.format("delta").load(rawdata_path)
        bronze_count = df_bronze.count()
        silver_count = df_silver.count()
        # Silver should have <= Bronze rows (deduplication removes duplicates)
        passed = silver_count <= bronze_count and silver_count > 0
        checks.append(_check(
            "row_count_comparison",
            passed,
            f"Bronze: {bronze_count:,} | Silver: {silver_count:,}",
        ))
    except Exception as e:
        checks.append(_check("row_count_comparison", False, f"Error: {e}"))

    # --- Check: Null PKs ---
    try:
        df_meta = spark.read.format("delta").load(PATH_METADATA_TABLE)
        cols_meta = df_meta.filter(
            df_meta["nome_tabela"] == table_name
        ).collect()

        pk_cols = [c["nome_coluna"] for c in cols_meta if c["primary_key"] == "PK"]

        if pk_cols:
            df_silver = spark.read.format("delta").load(rawdata_path)
            null_filter = " OR ".join([f"{c} IS NULL" for c in pk_cols])
            null_count = df_silver.filter(null_filter).count()
            checks.append(_check(
                "pk_no_nulls",
                null_count == 0,
                f"PKs: {pk_cols} | Null rows: {null_count:,}",
            ))
        else:
            checks.append(_check(
                "pk_no_nulls",
                False,
                f"No PK defined in metadados for {table_name}",
            ))
    except Exception as e:
        checks.append(_check("pk_no_nulls", False, f"Error: {e}"))

    # --- Check: Type validation against metadados ---
    try:
        df_meta = spark.read.format("delta").load(PATH_METADATA_TABLE)
        cols_meta = df_meta.filter(
            df_meta["nome_tabela"] == table_name
        ).collect()

        df_silver = spark.read.format("delta").load(rawdata_path)
        actual_types = {f.name: f.dataType.simpleString() for f in df_silver.schema.fields}

        mismatches = []
        for c in cols_meta:
            col_name = c["nome_coluna"]
            expected_type = c["tipo"].lower().strip()

            if col_name not in actual_types:
                # Audit columns or extra columns are acceptable
                if not col_name.startswith("_"):
                    mismatches.append(f"{col_name}: MISSING")
                continue

            actual = actual_types[col_name]

            # Normalize type names for comparison
            type_ok = _types_compatible(expected_type, actual)
            if not type_ok:
                mismatches.append(f"{col_name}: expected={expected_type}, actual={actual}")

        checks.append(_check(
            "type_validation",
            len(mismatches) == 0,
            f"Mismatches: {mismatches}" if mismatches else "All column types match metadados",
        ))
    except Exception as e:
        checks.append(_check("type_validation", False, f"Error: {e}"))

    # --- Check: Audit columns exist ---
    try:
        df_silver = spark.read.format("delta").load(rawdata_path)
        silver_cols = set(df_silver.columns)
        missing_audit = [c for c in AUDIT_COLUMNS_SILVER if c not in silver_cols]
        checks.append(_check(
            "audit_columns_present",
            len(missing_audit) == 0,
            f"Missing: {missing_audit}" if missing_audit else "All audit columns present",
        ))
    except Exception as e:
        checks.append(_check("audit_columns_present", False, f"Error: {e}"))

    result = {
        "table": table_name,
        "status": _overall_status(checks),
        "checks": checks,
    }
    logger.info("Bronze->Silver %s: %s", table_name, result["status"])
    return result


def _types_compatible(expected, actual):
    """Compara tipo esperado (metadados) com tipo real (Spark).

    Faz normalizacao basica para lidar com diferencas de nomenclatura
    entre metadados (varchar, int, timestamp) e Spark (string, int, timestamp).

    Args:
        expected: Tipo do metadados (ex: "varchar", "int", "timestamp").
        actual: Tipo simpleString do Spark (ex: "string", "int", "timestamp").

    Returns:
        bool: True se os tipos sao compativeis.
    """
    # Normalize expected
    expected = expected.lower().strip()
    actual = actual.lower().strip()

    # Direct match
    if expected == actual:
        return True

    # Equivalences
    equivalences = {
        "varchar": "string",
        "varchar(2048)": "string",
        "varchar(8000)": "string",
        "integer": "int",
        "long": "bigint",
        "bigint": "bigint",
        "float": "float",
        "double": "double",
        "decimal": "decimal",
        "boolean": "boolean",
        "date": "date",
        "timestamp": "timestamp",
    }

    # Strip size specifier from varchar(N)
    normalized_expected = expected
    if expected.startswith("varchar"):
        normalized_expected = "varchar"

    mapped = equivalences.get(normalized_expected, normalized_expected)

    if mapped == actual:
        return True

    # Handle numeric widening: int -> bigint is acceptable
    numeric_hierarchy = ["int", "bigint", "float", "double"]
    if mapped in numeric_hierarchy and actual in numeric_hierarchy:
        return numeric_hierarchy.index(actual) >= numeric_hierarchy.index(mapped)

    # Timestamp/date flexibility
    if normalized_expected in ("timestamp", "date") and actual in ("timestamp", "date"):
        return True

    # Handle decimal with precision/scale: decimal(10,2) matches decimal
    if actual.startswith("decimal") and normalized_expected.startswith("decimal"):
        return True

    return False


# =============================================================================
# 2. VALIDATE BOOK
# =============================================================================

def validate_book(spark, book_name, expected_features=None):
    """Valida um book de variaveis (Silver.book).

    Checagens:
        - Tabela existe como Delta
        - Contagem de features confere com esperado
        - SAFRA eh tipo INT (IntegerType ou LongType), nao StringType
        - Nenhuma coluna de leakage presente (LEAKAGE_BLACKLIST)
        - Sem duplicatas em (NUM_CPF, SAFRA)
        - Valores de SAFRA dentro do range esperado (SAFRAS)
        - Row count > 0

    Args:
        spark: SparkSession ativa.
        book_name: Nome do book (ex: "ass_recarga_cmv", "pagamento", "faturamento").
        expected_features: Numero esperado de features. Se None, usa EXPECTED_FEATURES.

    Returns:
        dict: {book, status, checks: [{name, passed, detail}]}
    """
    logger.info("Validando book: %s", book_name)
    checks = []

    if expected_features is None:
        expected_features = EXPECTED_FEATURES.get(book_name)

    book_path = BOOK_PATHS.get(book_name, get_book_path(book_name))

    # --- Check: Table exists ---
    try:
        exists = _is_delta_table(spark, book_path)
        checks.append(_check(
            "table_exists",
            exists,
            f"Path: {book_path}" if exists else f"Delta table not found at {book_path}",
        ))
    except Exception as e:
        checks.append(_check("table_exists", False, f"Error: {e}"))

    if not checks[0]["passed"]:
        logger.warning("Book %s nao encontrado — pulando checks restantes", book_name)
        return {"book": book_name, "status": _overall_status(checks), "checks": checks}

    # Load the book once for subsequent checks
    try:
        df = spark.read.format("delta").load(book_path)
    except Exception as e:
        checks.append(_check("table_readable", False, f"Error reading table: {e}"))
        return {"book": book_name, "status": _overall_status(checks), "checks": checks}

    # --- Check: Row count > 0 ---
    try:
        row_count = df.count()
        checks.append(_check(
            "row_count_positive",
            row_count > 0,
            f"Rows: {row_count:,}",
        ))
    except Exception as e:
        checks.append(_check("row_count_positive", False, f"Error: {e}"))

    # --- Check: Feature count ---
    try:
        actual_features = len(df.columns)
        if expected_features is not None:
            passed = actual_features == expected_features
            detail = f"Expected: {expected_features} | Actual: {actual_features}"
        else:
            passed = actual_features > 0
            detail = f"Actual: {actual_features} (no expected value configured)"
        checks.append(_check("feature_count", passed, detail))
    except Exception as e:
        checks.append(_check("feature_count", False, f"Error: {e}"))

    # --- Check: SAFRA column type is INT ---
    try:
        safra_field = None
        for field in df.schema.fields:
            if field.name == "SAFRA":
                safra_field = field
                break

        if safra_field is None:
            checks.append(_check("safra_type_int", False, "SAFRA column not found"))
        else:
            type_name = safra_field.dataType.simpleString()
            is_int_type = type_name in ("int", "bigint")
            checks.append(_check(
                "safra_type_int",
                is_int_type,
                f"SAFRA type: {type_name}" + (" (expected int or bigint)" if not is_int_type else ""),
            ))
    except Exception as e:
        checks.append(_check("safra_type_int", False, f"Error: {e}"))

    # --- Check: No leakage columns ---
    try:
        book_cols = set(df.columns)
        leakage_found = [c for c in LEAKAGE_BLACKLIST if c in book_cols]
        checks.append(_check(
            "no_leakage_columns",
            len(leakage_found) == 0,
            f"Leakage columns found: {leakage_found}" if leakage_found else "No leakage columns detected",
        ))
    except Exception as e:
        checks.append(_check("no_leakage_columns", False, f"Error: {e}"))

    # --- Check: No duplicate (NUM_CPF, SAFRA) ---
    try:
        total = df.count()
        distinct = df.select("NUM_CPF", "SAFRA").distinct().count()
        has_dupes = total != distinct
        checks.append(_check(
            "no_duplicate_pk",
            not has_dupes,
            f"Total: {total:,} | Distinct (NUM_CPF, SAFRA): {distinct:,}"
            + (f" | Duplicates: {total - distinct:,}" if has_dupes else ""),
        ))
    except Exception as e:
        checks.append(_check("no_duplicate_pk", False, f"Error: {e}"))

    # --- Check: SAFRA values in expected range ---
    try:
        actual_safras = sorted([
            row["SAFRA"] for row in df.select("SAFRA").distinct().collect()
        ])
        unexpected = [s for s in actual_safras if s not in SAFRAS]
        missing = [s for s in SAFRAS if s not in actual_safras]
        passed = len(unexpected) == 0
        detail_parts = [f"Found: {actual_safras}"]
        if unexpected:
            detail_parts.append(f"Unexpected: {unexpected}")
        if missing:
            detail_parts.append(f"Missing: {missing}")
        checks.append(_check("safra_range_valid", passed, " | ".join(detail_parts)))
    except Exception as e:
        checks.append(_check("safra_range_valid", False, f"Error: {e}"))

    result = {
        "book": book_name,
        "status": _overall_status(checks),
        "checks": checks,
    }
    logger.info("Book %s: %s", book_name, result["status"])
    return result


# =============================================================================
# 3. VALIDATE FEATURE STORE
# =============================================================================

def validate_feature_store(spark):
    """Valida a feature store consolidada (Gold.feature_store.clientes_consolidado).

    Executa todos os checks de validate_book mais:
        - Prefixos de coluna presentes (REC_*, PAG_*, FAT_*)
        - Colunas target presentes (FPD, TARGET_SCORE_01, TARGET_SCORE_02)
        - Distribuicao de SAFRA equilibrada (nenhuma SAFRA com <10% do max)
        - Volume total proximo de 3.9M registros
        - Tabela particionada por SAFRA

    Args:
        spark: SparkSession ativa.

    Returns:
        dict: {table, status, checks: [{name, passed, detail}]}
    """
    logger.info("Validando Feature Store: clientes_consolidado")
    checks = []

    book_name = "clientes_consolidado"
    fs_path = PATH_FEATURE_STORE

    # --- Check: Table exists ---
    try:
        exists = _is_delta_table(spark, fs_path)
        checks.append(_check(
            "table_exists",
            exists,
            f"Path: {fs_path}" if exists else f"Delta table not found at {fs_path}",
        ))
    except Exception as e:
        checks.append(_check("table_exists", False, f"Error: {e}"))

    if not checks[0]["passed"]:
        logger.warning("Feature store nao encontrada — pulando checks restantes")
        return {"table": book_name, "status": _overall_status(checks), "checks": checks}

    # Load once
    try:
        df = spark.read.format("delta").load(fs_path)
    except Exception as e:
        checks.append(_check("table_readable", False, f"Error reading table: {e}"))
        return {"table": book_name, "status": _overall_status(checks), "checks": checks}

    columns = df.columns
    columns_set = set(columns)
    _cached_count = None

    # --- Check: Row count > 0 ---
    try:
        row_count = df.count()
        _cached_count = row_count
        checks.append(_check(
            "row_count_positive",
            row_count > 0,
            f"Rows: {row_count:,}",
        ))
    except Exception as e:
        checks.append(_check("row_count_positive", False, f"Error: {e}"))

    # --- Check: Feature count ---
    try:
        expected = EXPECTED_FEATURES.get(book_name)
        actual = len(columns)
        if expected is not None:
            passed = actual == expected
            detail = f"Expected: {expected} | Actual: {actual}"
        else:
            passed = actual > 0
            detail = f"Actual: {actual} (no expected value configured)"
        checks.append(_check("feature_count", passed, detail))
    except Exception as e:
        checks.append(_check("feature_count", False, f"Error: {e}"))

    # --- Check: SAFRA column type is INT ---
    try:
        safra_field = None
        for field in df.schema.fields:
            if field.name == "SAFRA":
                safra_field = field
                break

        if safra_field is None:
            checks.append(_check("safra_type_int", False, "SAFRA column not found"))
        else:
            type_name = safra_field.dataType.simpleString()
            is_int_type = type_name in ("int", "bigint")
            checks.append(_check(
                "safra_type_int",
                is_int_type,
                f"SAFRA type: {type_name}" + (" (expected int or bigint)" if not is_int_type else ""),
            ))
    except Exception as e:
        checks.append(_check("safra_type_int", False, f"Error: {e}"))

    # --- Check: No leakage columns ---
    try:
        leakage_found = [c for c in LEAKAGE_BLACKLIST if c in columns_set]
        checks.append(_check(
            "no_leakage_columns",
            len(leakage_found) == 0,
            f"Leakage columns found: {leakage_found}" if leakage_found else "No leakage columns detected",
        ))
    except Exception as e:
        checks.append(_check("no_leakage_columns", False, f"Error: {e}"))

    # --- Check: No duplicate (NUM_CPF, SAFRA) ---
    try:
        total = _cached_count if _cached_count is not None else df.count()
        distinct = df.select("NUM_CPF", "SAFRA").distinct().count()
        has_dupes = total != distinct
        checks.append(_check(
            "no_duplicate_pk",
            not has_dupes,
            f"Total: {total:,} | Distinct (NUM_CPF, SAFRA): {distinct:,}"
            + (f" | Duplicates: {total - distinct:,}" if has_dupes else ""),
        ))
    except Exception as e:
        checks.append(_check("no_duplicate_pk", False, f"Error: {e}"))

    # --- Check: SAFRA values in expected range ---
    try:
        actual_safras = sorted([
            row["SAFRA"] for row in df.select("SAFRA").distinct().collect()
        ])
        unexpected = [s for s in actual_safras if s not in SAFRAS]
        missing = [s for s in SAFRAS if s not in actual_safras]
        passed = len(unexpected) == 0
        detail_parts = [f"Found: {actual_safras}"]
        if unexpected:
            detail_parts.append(f"Unexpected: {unexpected}")
        if missing:
            detail_parts.append(f"Missing: {missing}")
        checks.append(_check("safra_range_valid", passed, " | ".join(detail_parts)))
    except Exception as e:
        checks.append(_check("safra_range_valid", False, f"Error: {e}"))

    # --- Check: Column prefix validation (REC_*, PAG_*, FAT_*) ---
    try:
        rec_cols = [c for c in columns if c.startswith("REC_")]
        pag_cols = [c for c in columns if c.startswith("PAG_")]
        fat_cols = [c for c in columns if c.startswith("FAT_")]

        all_present = len(rec_cols) > 0 and len(pag_cols) > 0 and len(fat_cols) > 0
        checks.append(_check(
            "column_prefixes_present",
            all_present,
            f"REC_: {len(rec_cols)} | PAG_: {len(pag_cols)} | FAT_: {len(fat_cols)}",
        ))
    except Exception as e:
        checks.append(_check("column_prefixes_present", False, f"Error: {e}"))

    # --- Check: Target columns present ---
    try:
        missing_targets = [c for c in TARGET_COLUMNS if c not in columns_set]
        checks.append(_check(
            "target_columns_present",
            len(missing_targets) == 0,
            f"Missing: {missing_targets}" if missing_targets else f"All targets present: {TARGET_COLUMNS}",
        ))
    except Exception as e:
        checks.append(_check("target_columns_present", False, f"Error: {e}"))

    # --- Check: SAFRA distribution balance ---
    try:
        from pyspark.sql.functions import count as spark_count
        safra_counts = df.groupBy("SAFRA").agg(
            spark_count("*").alias("cnt")
        ).collect()

        safra_dict = {row["SAFRA"]: row["cnt"] for row in safra_counts}
        max_count = max(safra_dict.values()) if safra_dict else 0
        threshold = max_count * SAFRA_IMBALANCE_THRESHOLD

        imbalanced = {s: cnt for s, cnt in safra_dict.items() if cnt < threshold}
        checks.append(_check(
            "safra_distribution_balanced",
            len(imbalanced) == 0,
            f"Counts per SAFRA: {safra_dict}"
            + (f" | Imbalanced (<{SAFRA_IMBALANCE_THRESHOLD:.0%} of max): {imbalanced}" if imbalanced else ""),
        ))
    except Exception as e:
        checks.append(_check("safra_distribution_balanced", False, f"Error: {e}"))

    # --- Check: Total record volume ---
    try:
        total = _cached_count if _cached_count is not None else df.count()
        deviation = abs(total - FEATURE_STORE_EXPECTED_RECORDS) / FEATURE_STORE_EXPECTED_RECORDS
        within_tolerance = deviation <= FEATURE_STORE_TOLERANCE
        checks.append(_check(
            "record_volume",
            within_tolerance,
            f"Total: {total:,} | Expected: ~{FEATURE_STORE_EXPECTED_RECORDS:,} | "
            f"Deviation: {deviation:.1%} (tolerance: {FEATURE_STORE_TOLERANCE:.0%})",
        ))
    except Exception as e:
        checks.append(_check("record_volume", False, f"Error: {e}"))

    # --- Check: Partitioned by SAFRA ---
    try:
        from delta.tables import DeltaTable
        dt = DeltaTable.forPath(spark, fs_path)
        detail_df = dt.detail()
        partition_cols = detail_df.select("partitionColumns").collect()[0][0]
        is_partitioned = "SAFRA" in partition_cols
        checks.append(_check(
            "partitioned_by_safra",
            is_partitioned,
            f"Partition columns: {list(partition_cols)}" if partition_cols else "No partitioning detected",
        ))
    except Exception as e:
        checks.append(_check("partitioned_by_safra", False, f"Error: {e}"))

    result = {
        "table": book_name,
        "status": _overall_status(checks),
        "checks": checks,
    }
    logger.info("Feature Store: %s", result["status"])
    return result


# =============================================================================
# 4. RUN FULL VALIDATION
# =============================================================================

def run_full_validation(spark):
    """Orquestra todas as validacoes do pipeline.

    Executa:
        1. validate_bronze_to_silver para cada tabela em SILVER_TABLES
        2. validate_book para cada book (ass_recarga_cmv, pagamento, faturamento)
        3. validate_feature_store

    Args:
        spark: SparkSession ativa.

    Returns:
        list[dict]: Lista de resultados de validacao (um por tabela/book).
    """
    logger.info("=" * 60)
    logger.info("VALIDACAO COMPLETA DO PIPELINE — Inicio")
    logger.info("=" * 60)

    results = []

    # --- Silver tables ---
    logger.info("--- Fase 1: Bronze -> Silver ---")
    for table_name in SILVER_TABLES:
        try:
            result = validate_bronze_to_silver(spark, table_name)
            results.append(result)
        except Exception as e:
            logger.error("Erro fatal validando %s: %s", table_name, e)
            results.append({
                "table": table_name,
                "status": "ERROR",
                "checks": [_check("validation_execution", False, f"Fatal error: {e}")],
            })

    # --- Books ---
    logger.info("--- Fase 2: Books ---")
    for book_name in BOOK_PATHS:
        try:
            result = validate_book(spark, book_name)
            results.append(result)
        except Exception as e:
            logger.error("Erro fatal validando book %s: %s", book_name, e)
            results.append({
                "book": book_name,
                "status": "ERROR",
                "checks": [_check("validation_execution", False, f"Fatal error: {e}")],
            })

    # --- Feature Store ---
    logger.info("--- Fase 3: Feature Store ---")
    try:
        result = validate_feature_store(spark)
        results.append(result)
    except Exception as e:
        logger.error("Erro fatal validando feature store: %s", e)
        results.append({
            "table": "clientes_consolidado",
            "status": "ERROR",
            "checks": [_check("validation_execution", False, f"Fatal error: {e}")],
        })

    logger.info("=" * 60)
    logger.info("VALIDACAO COMPLETA — Fim")
    logger.info("=" * 60)

    return results


# =============================================================================
# 5. GENERATE REPORT
# =============================================================================

def generate_report(results, output_path=None):
    """Gera relatorio Markdown com resultados de validacao.

    Formato:
        - Header com timestamp
        - Tabela sumario: PASS/FAIL/ERROR por entidade
        - Detalhes por entidade com resultado de cada check individual

    Args:
        results: Lista de dicts retornados pelas funcoes de validacao.
        output_path: Caminho para salvar o relatorio. Se None, imprime no stdout.

    Returns:
        str: Conteudo do relatorio em Markdown.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []

    lines.append("# Data Quality Validation Report")
    lines.append("")
    lines.append(f"**Generated**: {now}")
    lines.append(f"**Pipeline**: Hackathon PoD Academy — Credit Risk")
    lines.append(f"**Entities validated**: {len(results)}")
    lines.append("")

    # --- Summary table ---
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    error_count = sum(1 for r in results if r["status"] == "ERROR")
    total_checks = sum(len(r["checks"]) for r in results)
    passed_checks = sum(sum(1 for c in r["checks"] if c["passed"]) for r in results)

    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Entities PASS | {pass_count} |")
    lines.append(f"| Entities FAIL | {fail_count} |")
    lines.append(f"| Entities ERROR | {error_count} |")
    lines.append(f"| Total checks | {total_checks} |")
    lines.append(f"| Checks passed | {passed_checks} |")
    lines.append(f"| Checks failed | {total_checks - passed_checks} |")
    lines.append("")

    # --- Entity overview ---
    lines.append("## Entity Results")
    lines.append("")
    lines.append("| Entity | Status | Passed | Failed |")
    lines.append("|--------|--------|--------|--------|")

    for r in results:
        name = r.get("table") or r.get("book", "unknown")
        status = r["status"]
        n_passed = sum(1 for c in r["checks"] if c["passed"])
        n_failed = sum(1 for c in r["checks"] if not c["passed"])
        lines.append(f"| {name} | {status} | {n_passed} | {n_failed} |")

    lines.append("")

    # --- Detailed results per entity ---
    lines.append("## Detailed Results")
    lines.append("")

    for r in results:
        name = r.get("table") or r.get("book", "unknown")
        status = r["status"]
        lines.append(f"### {name} [{status}]")
        lines.append("")
        lines.append("| Check | Result | Detail |")
        lines.append("|-------|--------|--------|")

        for c in r["checks"]:
            result_text = "PASS" if c["passed"] else "FAIL"
            # Escape pipes in detail text for Markdown table
            detail = c["detail"].replace("|", "\\|") if c["detail"] else ""
            lines.append(f"| {c['name']} | {result_text} | {detail} |")

        lines.append("")

    # --- Footer ---
    lines.append("---")
    lines.append(f"*Report generated by utils/data_quality.py at {now}*")
    lines.append("")

    report = "\n".join(lines)

    if output_path is not None:
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report)
            logger.info("Relatorio salvo em: %s", output_path)
        except Exception as e:
            logger.error("Erro ao salvar relatorio: %s", e)
            print(report)
    else:
        print(report)

    return report


# =============================================================================
# EXECUCAO PRINCIPAL
# =============================================================================
if __name__ == "__main__":
    # `spark` is available as a global in Fabric notebook environment
    results = run_full_validation(spark)  # noqa: F821
    generate_report(results)
