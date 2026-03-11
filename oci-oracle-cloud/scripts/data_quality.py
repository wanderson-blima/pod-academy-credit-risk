#!/usr/bin/env python3
"""
Data Quality Validation — OCI Medallion Pipeline
Validates Bronze, Silver, Gold (books), Gold (consolidated), and Gold (final)
layers by checking object existence via OCI CLI and optionally reading parquet
for deeper schema/row-count checks.

Usage:
    python data_quality.py --namespace grlxi07jz1mo --artifact-dir /home/datascience/artifacts

Runs on OCI Data Science notebook session, orchestrator VM, or locally.
"""
import os
import sys
import json
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================
NAMESPACE = "grlxi07jz1mo"

BUCKETS = {
    "landing": "pod-academy-landing",
    "bronze": "pod-academy-bronze",
    "silver": "pod-academy-silver",
    "gold": "pod-academy-gold",
}

MAIN_TABLES = [
    "dados_cadastrais",
    "telco",
    "score_bureau_movel",
    "recarga",
    "pagamento",
    "faturamento",
    "dim_calendario",
]

DIM_TABLES = [
    "dim_canal_aquisicao_credito",
    "dim_forma_pagamento",
    "dim_instituicao",
    "dim_plano_preco",
    "dim_plataforma",
    "dim_promocao_credito",
    "dim_status_plataforma",
    "dim_tecnologia",
    "dim_tipo_credito",
    "dim_tipo_insercao",
    "dim_tipo_recarga",
    "dim_tipo_faturamento",
]

ALL_TABLES = MAIN_TABLES + DIM_TABLES  # 19 total

SAFRAS = [202410, 202411, 202412, 202501, 202502, 202503]

REQUIRED_COLUMNS = ["TARGET_SCORE_01", "TARGET_SCORE_02", "FPD", "NUM_CPF", "SAFRA"]

EXPECTED_PREFIXES = ["REC_", "PAG_", "FAT_"]

GOLD_BOOKS = ["book_recarga_cmv", "book_pagamento", "book_faturamento"]

ARTIFACT_DIR = "/home/datascience/artifacts"


# =============================================================================
# RESULT COLLECTOR
# =============================================================================
results = []


def add_result(layer, check, status, detail=""):
    """Append a validation result (PASS/FAIL/WARN/SKIP)."""
    results.append({
        "layer": layer,
        "check": check,
        "status": status,
        "detail": str(detail),
        "timestamp": datetime.utcnow().isoformat(),
    })


# =============================================================================
# OCI CLI HELPERS
# =============================================================================
def oci_list_objects(bucket, namespace, prefix=None, limit=1000):
    """List objects in an OCI bucket via CLI. Returns list of object names."""
    cmd = [
        "oci", "os", "object", "list",
        "--bucket-name", bucket,
        "--namespace", namespace,
        "--limit", str(limit),
        "--output", "json",
    ]
    if prefix:
        cmd.extend(["--prefix", prefix])

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            return None, proc.stderr.strip()
        data = json.loads(proc.stdout)
        objects = data.get("data", [])
        names = [o["name"] for o in objects]
        return names, None
    except FileNotFoundError:
        return None, "oci CLI not found on PATH"
    except subprocess.TimeoutExpired:
        return None, "oci CLI timed out"
    except Exception as e:
        return None, str(e)


def count_objects_with_prefix(bucket, namespace, prefix):
    """Count objects under a given prefix."""
    names, err = oci_list_objects(bucket, namespace, prefix=prefix)
    if err:
        return -1, err
    return len(names), None


# =============================================================================
# LAYER VALIDATORS
# =============================================================================
def validate_bronze(namespace):
    """Check that all 19 tables exist as prefixes in the bronze bucket."""
    layer = "Bronze"
    bucket = BUCKETS["bronze"]
    found = 0
    missing = []

    for table in ALL_TABLES:
        prefix = f"staging/{table}/"
        count, err = count_objects_with_prefix(bucket, namespace, prefix)
        if err:
            add_result(layer, f"table:{table}", "FAIL", f"CLI error: {err}")
            missing.append(table)
            continue
        if count > 0:
            add_result(layer, f"table:{table}", "PASS", f"{count} objects")
            found += 1
        else:
            add_result(layer, f"table:{table}", "FAIL", "No objects found")
            missing.append(table)

    # Summary
    status = "PASS" if found == len(ALL_TABLES) else "FAIL"
    detail = f"{found}/{len(ALL_TABLES)} tables present"
    if missing:
        detail += f" | missing: {missing}"
    add_result(layer, "all_tables_exist", status, detail)
    return found


def validate_silver(namespace):
    """Check that all 19 tables exist under rawdata/ in the silver bucket."""
    layer = "Silver"
    bucket = BUCKETS["silver"]
    found = 0
    missing = []

    for table in ALL_TABLES:
        prefix = f"rawdata/{table}/"
        count, err = count_objects_with_prefix(bucket, namespace, prefix)
        if err:
            add_result(layer, f"table:{table}", "FAIL", f"CLI error: {err}")
            missing.append(table)
            continue
        if count > 0:
            add_result(layer, f"table:{table}", "PASS", f"{count} objects")
            found += 1
        else:
            add_result(layer, f"table:{table}", "FAIL", "No objects found")
            missing.append(table)

    status = "PASS" if found == len(ALL_TABLES) else "FAIL"
    detail = f"{found}/{len(ALL_TABLES)} tables present"
    if missing:
        detail += f" | missing: {missing}"
    add_result(layer, "all_tables_exist", status, detail)
    return found


def validate_gold_books(namespace):
    """Check that the 3 Gold books exist in the gold bucket."""
    layer = "Gold-Books"
    bucket = BUCKETS["gold"]
    found = 0
    missing = []

    for book in GOLD_BOOKS:
        prefix = f"feature_store/{book}/"
        count, err = count_objects_with_prefix(bucket, namespace, prefix)
        if err:
            add_result(layer, f"book:{book}", "FAIL", f"CLI error: {err}")
            missing.append(book)
            continue
        if count > 0:
            add_result(layer, f"book:{book}", "PASS", f"{count} objects")
            found += 1
        else:
            add_result(layer, f"book:{book}", "FAIL", "No objects found")
            missing.append(book)

    status = "PASS" if found == len(GOLD_BOOKS) else "FAIL"
    detail = f"{found}/{len(GOLD_BOOKS)} books present"
    if missing:
        detail += f" | missing: {missing}"
    add_result(layer, "all_books_exist", status, detail)
    return found


def validate_gold_consolidated(namespace, artifact_dir):
    """Validate clientes_consolidado: existence, SAFRA partitions, schema."""
    layer = "Gold-Consolidated"
    bucket = BUCKETS["gold"]
    prefix = "feature_store/clientes_consolidado/"

    # 1. Check existence
    names, err = oci_list_objects(bucket, namespace, prefix=prefix, limit=5000)
    if err:
        add_result(layer, "exists", "FAIL", f"CLI error: {err}")
        return
    if not names:
        add_result(layer, "exists", "FAIL", "No objects found")
        return
    add_result(layer, "exists", "PASS", f"{len(names)} objects")

    # 2. Check SAFRA partitions by looking for SAFRA=XXXXXX in object names
    found_safras = set()
    for name in names:
        for safra in SAFRAS:
            if f"SAFRA={safra}" in name or f"safra={safra}" in name:
                found_safras.add(safra)

    missing_safras = set(SAFRAS) - found_safras
    if not missing_safras:
        add_result(layer, "safra_partitions", "PASS",
                   f"All {len(SAFRAS)} SAFRAs present: {sorted(found_safras)}")
    else:
        add_result(layer, "safra_partitions", "FAIL",
                   f"Missing SAFRAs: {sorted(missing_safras)} | Found: {sorted(found_safras)}")

    # 3. Deeper schema/row check via local parquet (if available)
    _validate_consolidated_local(layer, artifact_dir)


def _validate_consolidated_local(layer, artifact_dir):
    """Try to read consolidated parquet from local path for deeper checks."""
    try:
        import pandas as pd
    except ImportError:
        add_result(layer, "local_schema_check", "SKIP", "pandas not available")
        return

    # Look for parquet files in common local locations
    candidate_paths = [
        os.path.join(artifact_dir, "clientes_consolidado"),
        os.path.join(artifact_dir, "data", "clientes_consolidado"),
        "/home/opc/data/clientes_consolidado",
        "/home/datascience/data/clientes_consolidado",
    ]

    df = None
    used_path = None
    for path in candidate_paths:
        if os.path.isdir(path):
            try:
                parquet_files = list(Path(path).rglob("*.parquet"))
                if parquet_files:
                    df = pd.read_parquet(path)
                    used_path = path
                    break
            except Exception:
                continue
        elif os.path.isfile(path) and path.endswith(".parquet"):
            try:
                df = pd.read_parquet(path)
                used_path = path
                break
            except Exception:
                continue

    if df is None:
        add_result(layer, "local_schema_check", "SKIP",
                   "No local parquet found; only bucket-level checks done")
        return

    add_result(layer, "local_data_loaded", "PASS", f"Read from {used_path}")

    # Row count
    nrows = len(df)
    if nrows > 0:
        add_result(layer, "row_count", "PASS", f"{nrows:,} rows")
    else:
        add_result(layer, "row_count", "FAIL", "0 rows")

    # Column count
    ncols = len(df.columns)
    add_result(layer, "column_count", "PASS" if ncols >= 100 else "WARN",
               f"{ncols} columns")

    # Required columns
    cols_upper = [c.upper() for c in df.columns]
    missing_req = [c for c in REQUIRED_COLUMNS if c not in cols_upper]
    if not missing_req:
        add_result(layer, "required_columns", "PASS",
                   f"All {len(REQUIRED_COLUMNS)} required columns present")
    else:
        add_result(layer, "required_columns", "FAIL",
                   f"Missing: {missing_req}")

    # Expected prefixes
    for pfx in EXPECTED_PREFIXES:
        count = sum(1 for c in df.columns if c.upper().startswith(pfx))
        if count > 0:
            add_result(layer, f"prefix:{pfx}", "PASS", f"{count} columns")
        else:
            add_result(layer, f"prefix:{pfx}", "FAIL", "No columns with prefix")

    # SAFRA values
    safra_col = None
    for c in df.columns:
        if c.upper() == "SAFRA":
            safra_col = c
            break
    if safra_col:
        found = sorted(df[safra_col].dropna().unique().tolist())
        expected_set = set(SAFRAS)
        found_set = set(int(s) for s in found)
        missing = expected_set - found_set
        if not missing:
            add_result(layer, "safra_values", "PASS", f"SAFRAs: {found}")
        else:
            add_result(layer, "safra_values", "FAIL",
                       f"Missing SAFRAs: {sorted(missing)} | Found: {found}")

    # Null check on key columns
    for col in REQUIRED_COLUMNS:
        matching = [c for c in df.columns if c.upper() == col]
        if matching:
            null_pct = df[matching[0]].isnull().mean() * 100
            status = "PASS" if null_pct < 50 else "WARN"
            add_result(layer, f"null_check:{col}", status,
                       f"{null_pct:.1f}% null")


def validate_gold_final(namespace):
    """Check if clientes_final exists (post feature-selection)."""
    layer = "Gold-Final"
    bucket = BUCKETS["gold"]
    prefix = "feature_store/clientes_final/"

    count, err = count_objects_with_prefix(bucket, namespace, prefix)
    if err:
        add_result(layer, "exists", "FAIL", f"CLI error: {err}")
        return
    if count > 0:
        add_result(layer, "exists", "PASS", f"{count} objects")
    else:
        add_result(layer, "exists", "WARN",
                   "Not found — feature selection may not have run yet")


def validate_cross_layer(namespace):
    """Cross-layer consistency: compare object counts between layers."""
    layer = "Cross-Layer"
    bucket_bronze = BUCKETS["bronze"]
    bucket_silver = BUCKETS["silver"]

    for table in MAIN_TABLES:
        bronze_count, b_err = count_objects_with_prefix(
            bucket_bronze, namespace, f"staging/{table}/")
        silver_count, s_err = count_objects_with_prefix(
            bucket_silver, namespace, f"rawdata/{table}/")

        if b_err or s_err:
            add_result(layer, f"bronze_vs_silver:{table}", "SKIP",
                       f"CLI error (bronze={b_err}, silver={s_err})")
            continue

        if bronze_count > 0 and silver_count > 0:
            add_result(layer, f"bronze_vs_silver:{table}", "PASS",
                       f"Bronze={bronze_count} objs, Silver={silver_count} objs")
        elif bronze_count > 0 and silver_count == 0:
            add_result(layer, f"bronze_vs_silver:{table}", "FAIL",
                       f"Bronze has {bronze_count} objs but Silver is empty")
        elif bronze_count == 0 and silver_count > 0:
            add_result(layer, f"bronze_vs_silver:{table}", "WARN",
                       f"Bronze empty but Silver has {silver_count} objs")
        else:
            add_result(layer, f"bronze_vs_silver:{table}", "FAIL",
                       "Both layers empty")


# =============================================================================
# REPORTING
# =============================================================================
def build_summary():
    """Build summary statistics from results."""
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    warned = sum(1 for r in results if r["status"] == "WARN")
    skipped = sum(1 for r in results if r["status"] == "SKIP")
    return {
        "total_checks": total,
        "passed": passed,
        "failed": failed,
        "warnings": warned,
        "skipped": skipped,
        "pass_rate": f"{passed / total * 100:.1f}%" if total > 0 else "N/A",
        "overall": "PASS" if failed == 0 else "FAIL",
    }


def save_report(artifact_dir):
    """Save JSON report to artifact_dir."""
    os.makedirs(artifact_dir, exist_ok=True)
    summary = build_summary()
    report = {
        "run_timestamp": datetime.utcnow().isoformat(),
        "summary": summary,
        "results": results,
    }
    path = os.path.join(artifact_dir, "data_quality_report.json")
    with open(path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    return path


def print_markdown():
    """Print a markdown-formatted summary to stdout."""
    summary = build_summary()

    print("\n" + "=" * 72)
    print("  DATA QUALITY REPORT — OCI Medallion Pipeline")
    print("=" * 72)
    print(f"  Timestamp : {datetime.utcnow().isoformat()}")
    print(f"  Overall   : {summary['overall']}")
    print(f"  Checks    : {summary['total_checks']} total | "
          f"{summary['passed']} PASS | {summary['failed']} FAIL | "
          f"{summary['warnings']} WARN | {summary['skipped']} SKIP")
    print(f"  Pass Rate : {summary['pass_rate']}")
    print("=" * 72)

    # Group by layer
    layers_seen = []
    layer_results = {}
    for r in results:
        ly = r["layer"]
        if ly not in layer_results:
            layers_seen.append(ly)
            layer_results[ly] = []
        layer_results[ly].append(r)

    for ly in layers_seen:
        print(f"\n## {ly}")
        print(f"{'Check':<40} {'Status':<8} Detail")
        print("-" * 72)
        for r in layer_results[ly]:
            icon = {"PASS": "[OK]", "FAIL": "[!!]", "WARN": "[??]", "SKIP": "[--]"}.get(
                r["status"], "[  ]")
            detail = r["detail"][:80] if r["detail"] else ""
            print(f"  {icon} {r['check']:<36} {r['status']:<8} {detail}")

    # Failed checks summary
    failures = [r for r in results if r["status"] == "FAIL"]
    if failures:
        print(f"\n{'=' * 72}")
        print(f"  FAILURES ({len(failures)})")
        print(f"{'=' * 72}")
        for r in failures:
            print(f"  [{r['layer']}] {r['check']}: {r['detail']}")

    print()


# =============================================================================
# MAIN
# =============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Data Quality Validation for OCI Medallion Pipeline")
    parser.add_argument("--namespace", default=NAMESPACE,
                        help=f"OCI Object Storage namespace (default: {NAMESPACE})")
    parser.add_argument("--artifact-dir", default=ARTIFACT_DIR,
                        help=f"Directory for output report (default: {ARTIFACT_DIR})")
    args = parser.parse_args()

    ns = args.namespace
    artifact_dir = args.artifact_dir

    print(f"[data_quality] Starting validation — namespace={ns}")
    print(f"[data_quality] Artifact dir: {artifact_dir}")
    t0 = datetime.utcnow()

    # ── Run all validators ──────────────────────────────────────────────
    print("\n[1/6] Validating Bronze layer...")
    validate_bronze(ns)

    print("[2/6] Validating Silver layer...")
    validate_silver(ns)

    print("[3/6] Validating Gold books...")
    validate_gold_books(ns)

    print("[4/6] Validating Gold consolidated...")
    validate_gold_consolidated(ns, artifact_dir)

    print("[5/6] Validating Gold final...")
    validate_gold_final(ns)

    print("[6/6] Cross-layer consistency...")
    validate_cross_layer(ns)

    elapsed = (datetime.utcnow() - t0).total_seconds()
    print(f"\n[data_quality] Validation complete in {elapsed:.1f}s")

    # ── Output ──────────────────────────────────────────────────────────
    report_path = save_report(artifact_dir)
    print(f"[data_quality] Report saved to {report_path}")

    print_markdown()

    # Exit code: 1 if any FAIL
    summary = build_summary()
    if summary["overall"] == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    main()
