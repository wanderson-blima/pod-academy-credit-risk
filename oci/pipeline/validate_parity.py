"""
Worker Script: validate-parity (OCI-T-010) — Data Quality & Fabric Parity Checks
Created: Story 4 — End-to-end validation of OCI pipeline vs Fabric baseline.
Updated: Delta Lake format support for reading lakehouse tables.
Classification: VALIDATION_WORKER

Parity Validation — OCI Data Flow
Checks Bronze/Silver/Gold layer counts, schemas, and data quality against Fabric baseline.
Generates markdown report with PASS/FAIL per check.
Storage: Reads Delta Lake tables (auto-detects format).

Usage: oci data-flow run submit --application-id $APP_OCID --arguments '["bronze-bucket", "silver-bucket", "gold-bucket", "namespace"]'
"""
import sys
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, isnan, isnull, when, lit

# =============================================================================
# STORAGE FORMAT — Must match pipeline output format per layer
# =============================================================================
BRONZE_FORMAT = "delta"   # All layers now use Delta Lake
SILVER_FORMAT = "delta"   # All layers now use Delta Lake
GOLD_FORMAT = "delta"     # All layers now use Delta Lake

SPARK_DELTA_CONFIG = {
    "spark.oracle.deltalake.version": "3.1.0",
    "spark.delta.logStore.oci.impl": "io.delta.storage.OracleCloudLogStore",
    "spark.sql.extensions": "io.delta.sql.DeltaSparkSessionExtension",
    "spark.sql.catalog.spark_catalog": "org.apache.spark.sql.delta.catalog.DeltaCatalog",
}


def read_table(spark, uri, fmt="delta"):
    """Read table in specified storage format."""
    if fmt == "delta":
        return spark.read.format("delta").load(uri)
    return spark.read.parquet(uri)


# =============================================================================
# FABRIC BASELINE (ground truth from Microsoft Fabric pipeline)
# =============================================================================
FABRIC_BASELINE = {
    "bronze_tables": 9,
    "silver_rawdata_tables": 19,  # 7 main + 12 dims (incl dim_calendario)
    "silver_book_tables": 3,
    "gold_tables": 1,

    # Row counts (exact from Fabric)
    "row_counts": {
        "dados_cadastrais": 3_900_378,
        "telco": 3_900_378,
        "score_bureau_movel": 3_900_378,
        "recarga": 99_896_314,
        "pagamento": 27_948_583,
        "faturamento": 32_687_219,
        "clientes_consolidado": 3_900_378,
    },

    # Column counts (exact from Fabric DDL)
    "column_counts": {
        "book_recarga_cmv": 93,     # Silver book (after aggregation)
        "book_pagamento": 97,       # Silver book (after aggregation)
        "book_faturamento": 117,    # Silver book (after aggregation)
        "clientes_consolidado": 402,  # Gold feature store
    },

    # SAFRAs expected
    "safras": [202410, 202411, 202412, 202501, 202502, 202503],

    # Leakage column that MUST be absent
    "leakage_blacklist": ["FAT_VLR_FPD"],

    # Required target columns
    "required_columns": ["TARGET_SCORE_01", "TARGET_SCORE_02", "FPD", "NUM_CPF", "SAFRA"],

    # Column prefixes expected in Gold
    "expected_prefixes": ["REC_", "PAG_", "FAT_"],
}

# Tolerance for row count comparison
ROW_COUNT_TOLERANCE = 0.001  # 0.1%
NULL_RATE_TOLERANCE_PP = 5   # 5 percentage points


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================
class ValidationResult:
    def __init__(self, check_name, layer, expected, actual, status, detail=""):
        self.check_name = check_name
        self.layer = layer
        self.expected = expected
        self.actual = actual
        self.status = status  # "PASS" or "FAIL"
        self.detail = detail

    def __str__(self):
        icon = "PASS" if self.status == "PASS" else "FAIL"
        return f"[{icon}] {self.layer}/{self.check_name}: expected={self.expected}, actual={self.actual} {self.detail}"


def check_row_count(name, actual, expected, tolerance=ROW_COUNT_TOLERANCE):
    """Check if row count is within tolerance of expected."""
    if expected == 0:
        return ValidationResult(f"{name}_row_count", "Silver", expected, actual,
                                "PASS" if actual == 0 else "FAIL")
    diff_pct = abs(actual - expected) / expected
    status = "PASS" if diff_pct <= tolerance else "FAIL"
    return ValidationResult(f"{name}_row_count", "Silver", expected, actual, status,
                            f"(diff={diff_pct:.4%})")


def check_column_count(name, actual, expected, layer="Silver"):
    """Check exact column count match."""
    status = "PASS" if actual == expected else "FAIL"
    return ValidationResult(f"{name}_col_count", layer, expected, actual, status)


def check_leakage(columns, blacklist):
    """Check that leakage columns are absent."""
    found = [c for c in columns if any(bl in c for bl in blacklist)]
    status = "PASS" if not found else "FAIL"
    detail = f"found={found}" if found else ""
    return ValidationResult("leakage_check", "Gold", "absent", "absent" if not found else found, status, detail)


def check_required_columns(columns, required):
    """Check that all required columns are present."""
    missing = [c for c in required if c not in columns]
    status = "PASS" if not missing else "FAIL"
    detail = f"missing={missing}" if missing else ""
    return ValidationResult("required_columns", "Gold", len(required), len(required) - len(missing), status, detail)


def check_prefixes(columns, expected_prefixes):
    """Check that expected column prefixes exist."""
    results = []
    for prefix in expected_prefixes:
        matching = [c for c in columns if c.startswith(prefix)]
        status = "PASS" if len(matching) > 0 else "FAIL"
        results.append(ValidationResult(
            f"prefix_{prefix.rstrip('_')}", "Gold",
            f">0 cols", len(matching), status
        ))
    return results


def check_no_duplicates(spark, df, key_cols, name):
    """Check for duplicate rows on key columns."""
    from pyspark.sql.functions import count as spark_count
    dup_count = df.groupBy(*key_cols).agg(spark_count("*").alias("cnt")) \
                  .filter(col("cnt") > 1).count()
    status = "PASS" if dup_count == 0 else "FAIL"
    return ValidationResult(f"{name}_no_duplicates", "Gold", 0, dup_count, status)


def check_safra_count(df, expected_safras):
    """Check SAFRA partition count."""
    actual_safras = sorted([row.SAFRA for row in df.select("SAFRA").distinct().collect()])
    status = "PASS" if actual_safras == expected_safras else "FAIL"
    return ValidationResult("safra_partitions", "Gold", expected_safras, actual_safras, status)


def compute_null_rates(df):
    """Compute null rate per column."""
    total = df.count()
    if total == 0:
        return {}
    null_rates = {}
    for c in df.columns:
        null_count = df.filter(col(c).isNull() | isnan(col(c))).count() \
            if str(df.schema[c].dataType) in ("DoubleType()", "FloatType()") \
            else df.filter(col(c).isNull()).count()
        null_rates[c] = round(null_count / total * 100, 2)
    return null_rates


# =============================================================================
# REPORT GENERATOR
# =============================================================================
def generate_report(results, output_uri=None):
    """Generate markdown parity report."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    total = len(results)

    lines = [
        f"# OCI vs Fabric Parity Report",
        f"",
        f"**Generated**: {now}",
        f"**Result**: {'ALL PASS' if failed == 0 else f'{failed} FAILURES'} ({passed}/{total} checks passed)",
        f"",
        f"## Summary",
        f"",
        f"| # | Layer | Check | Expected | Actual | Status |",
        f"|---|-------|-------|----------|--------|--------|",
    ]

    for i, r in enumerate(results, 1):
        icon = "PASS" if r.status == "PASS" else "**FAIL**"
        lines.append(f"| {i} | {r.layer} | {r.check_name} | {r.expected} | {r.actual} | {icon} |")

    lines.append("")

    # Detail failures
    failures = [r for r in results if r.status == "FAIL"]
    if failures:
        lines.append("## Failures Detail")
        lines.append("")
        for r in failures:
            lines.append(f"- **{r.layer}/{r.check_name}**: expected={r.expected}, actual={r.actual} {r.detail}")
        lines.append("")

    lines.append("---")
    lines.append(f"*Validation script: validate_parity.py | {total} checks*")

    report = "\n".join(lines)
    print(report)
    return report


# =============================================================================
# MAIN EXECUTION
# =============================================================================
if __name__ == "__main__":
    builder = SparkSession.builder.appName("validate-parity")
    if "delta" in (BRONZE_FORMAT, SILVER_FORMAT, GOLD_FORMAT):
        for key, value in SPARK_DELTA_CONFIG.items():
            builder = builder.config(key, value)
    spark = builder.getOrCreate()

    bronze_bucket = sys.argv[1] if len(sys.argv) > 1 else "pod-academy-bronze"
    silver_bucket = sys.argv[2] if len(sys.argv) > 2 else "pod-academy-silver"
    gold_bucket = sys.argv[3] if len(sys.argv) > 3 else "pod-academy-gold"
    namespace = sys.argv[4] if len(sys.argv) > 4 else "grlxi07jz1mo"

    results = []
    baseline = FABRIC_BASELINE

    # =========================================================================
    # CHECK 1: Bronze table count
    # =========================================================================
    print("[VALIDATE] Checking Bronze tables...")
    bronze_tables = []
    for table_name in ["dados_cadastrais", "telco", "score_bureau_movel",
                       "recarga", "pagamento", "faturamento",
                       "dim_calendario", "recarga_dim", "faturamento_dim"]:
        try:
            uri = f"oci://{bronze_bucket}@{namespace}/{table_name}/"
            read_table(spark, uri, fmt=BRONZE_FORMAT).limit(1).count()
            bronze_tables.append(table_name)
        except Exception:
            pass

    results.append(ValidationResult(
        "table_count", "Bronze", baseline["bronze_tables"], len(bronze_tables),
        "PASS" if len(bronze_tables) >= baseline["bronze_tables"] else "FAIL"
    ))

    # =========================================================================
    # CHECK 2: Silver rawdata — row counts for main tables
    # =========================================================================
    print("[VALIDATE] Checking Silver rawdata row counts...")
    for table_name, expected_rows in baseline["row_counts"].items():
        if table_name == "clientes_consolidado":
            continue  # Gold check
        try:
            uri = f"oci://{silver_bucket}@{namespace}/rawdata/{table_name}/"
            df = read_table(spark, uri, fmt=SILVER_FORMAT)
            actual_rows = df.count()
            results.append(check_row_count(table_name, actual_rows, expected_rows))
        except Exception as e:
            results.append(ValidationResult(
                f"{table_name}_row_count", "Silver", expected_rows, f"ERROR: {e}", "FAIL"
            ))

    # =========================================================================
    # CHECK 3: Silver rawdata — dimension table presence
    # =========================================================================
    print("[VALIDATE] Checking Silver dimension tables...")
    dim_names = ["canal_aquisicao_credito", "forma_pagamento", "instituicao",
                 "plano_preco", "plataforma", "promocao_credito", "status_plataforma",
                 "tecnologia", "tipo_credito", "tipo_insercao", "tipo_recarga",
                 "tipo_faturamento"]

    dim_present = 0
    for dim_name in dim_names:
        try:
            uri = f"oci://{silver_bucket}@{namespace}/rawdata/{dim_name}/"
            read_table(spark, uri, fmt=SILVER_FORMAT).limit(1).count()
            dim_present += 1
        except Exception:
            pass

    results.append(ValidationResult(
        "dimension_tables", "Silver", len(dim_names), dim_present,
        "PASS" if dim_present == len(dim_names) else "FAIL"
    ))

    # =========================================================================
    # CHECK 4: Silver books — column counts
    # =========================================================================
    print("[VALIDATE] Checking Silver book column counts...")
    book_map = {
        "book_recarga_cmv": "ass_recarga_cmv",
        "book_pagamento": "pagamento",
        "book_faturamento": "faturamento",
    }
    for book_key, book_path in book_map.items():
        expected_cols = baseline["column_counts"].get(book_key)
        if expected_cols is None:
            continue
        try:
            uri = f"oci://{silver_bucket}@{namespace}/book/{book_path}/"
            df = read_table(spark, uri, fmt=GOLD_FORMAT)  # books written by Gold script
            actual_cols = len(df.columns)
            results.append(check_column_count(book_key, actual_cols, expected_cols, "Silver"))
        except Exception as e:
            results.append(ValidationResult(
                f"{book_key}_col_count", "Silver", expected_cols, f"ERROR: {e}", "FAIL"
            ))

    # =========================================================================
    # CHECK 5: Gold — clientes_consolidado
    # =========================================================================
    print("[VALIDATE] Checking Gold clientes_consolidado...")
    try:
        gold_uri = f"oci://{gold_bucket}@{namespace}/feature_store/clientes_consolidado/"
        df_gold = read_table(spark, gold_uri, fmt=GOLD_FORMAT)
        gold_cols = df_gold.columns
        gold_rows = df_gold.count()
        gold_col_count = len(gold_cols)

        # 5a. Row count
        expected_rows = baseline["row_counts"]["clientes_consolidado"]
        results.append(check_row_count("clientes_consolidado", gold_rows, expected_rows))

        # 5b. Column count (exact)
        expected_cols = baseline["column_counts"]["clientes_consolidado"]
        results.append(check_column_count("clientes_consolidado", gold_col_count, expected_cols, "Gold"))

        # 5c. SAFRA partitions
        results.append(check_safra_count(df_gold, baseline["safras"]))

        # 5d. Leakage check (FAT_VLR_FPD must be absent)
        results.append(check_leakage(gold_cols, baseline["leakage_blacklist"]))

        # 5e. Required columns (TARGET_SCORE_01/02, FPD, etc.)
        results.append(check_required_columns(gold_cols, baseline["required_columns"]))

        # 5f. Column prefix check (REC_*, PAG_*, FAT_*)
        prefix_results = check_prefixes(gold_cols, baseline["expected_prefixes"])
        results.extend(prefix_results)

        # 5g. No duplicates on (NUM_CPF, SAFRA)
        results.append(check_no_duplicates(spark, df_gold, ["NUM_CPF", "SAFRA"], "clientes_consolidado"))

        # 5h. Null rate summary (informational, not PASS/FAIL)
        print("[VALIDATE] Computing null rates (sample)...")
        # Sample 10% for speed
        df_sample = df_gold.sample(fraction=0.1, seed=42)
        null_rates = compute_null_rates(df_sample)
        high_null = {k: v for k, v in null_rates.items() if v > 50}
        if high_null:
            print(f"[VALIDATE] High null rate columns (>50%): {high_null}")

    except Exception as e:
        results.append(ValidationResult(
            "gold_access", "Gold", "accessible", f"ERROR: {e}", "FAIL"
        ))

    # =========================================================================
    # GENERATE REPORT
    # =========================================================================
    print("\n" + "=" * 60)
    report = generate_report(results)

    # Write report to Gold bucket
    try:
        report_uri = f"oci://{gold_bucket}@{namespace}/validation/"
        report_df = spark.createDataFrame(
            [(datetime.now().isoformat(), report, sum(1 for r in results if r.status == "PASS"),
              sum(1 for r in results if r.status == "FAIL"))],
            ["timestamp", "report_md", "passed", "failed"]
        )
        writer = report_df.write.mode("overwrite")
        if GOLD_FORMAT == "delta":
            writer.format("delta").save(report_uri)
        else:
            writer.parquet(report_uri)
        print(f"[VALIDATE] Report saved to {report_uri}")
    except Exception as e:
        print(f"[VALIDATE] Could not save report: {e}")

    spark.stop()
