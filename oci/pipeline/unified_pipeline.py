"""
Unified Pipeline — OCI Data Flow
Executes Bronze -> Silver -> Gold in a single SparkSession.
Eliminates 3x bootstrap overhead (saves 6-12 min per run).

Usage:
    oci data-flow run submit --application-id $APP_OCID \
      --arguments '["--start-phase", "bronze"]'

    Phases: bronze, silver, gold
    Default: runs all phases (bronze -> silver -> gold)
"""
import sys
import argparse
import json
from datetime import datetime
from pyspark.sql import SparkSession

# Phase imports - core logic from individual scripts
from ingest_bronze import ingest, SPARK_DELTA_CONFIG as BRONZE_DELTA_CONFIG
from transform_silver import (
    type_cast, deduplicate, read_table, write_table,
    TYPE_CONFIG, TABLES_MAIN, DIMENSION_TABLES,
    STORAGE_FORMAT as SILVER_STORAGE_FORMAT,
    SPARK_DELTA_CONFIG as SILVER_DELTA_CONFIG,
)
from engineer_gold import (
    SAFRAS, SPARK_CONFIG as GOLD_SPARK_CONFIG,
    STORAGE_FORMAT as GOLD_STORAGE_FORMAT,
    SILVER_READ_FORMAT,
)

# =============================================================================
# CONFIGURATION
# =============================================================================
NAMESPACE = "grlxi07jz1mo"
BUCKETS = {
    "landing": "pod-academy-landing",
    "bronze": "pod-academy-bronze",
    "silver": "pod-academy-silver",
    "gold": "pod-academy-gold",
    "logs": "pod-academy-logs",
    "scripts": "pod-academy-scripts",
}

PHASES = ["bronze", "silver", "gold"]


def get_checkpoint_path(phase):
    """Return OCI path for phase checkpoint file."""
    return f"oci://{BUCKETS['logs']}@{NAMESPACE}/checkpoints/{phase}.done"


def check_phase_done(spark, phase):
    """Check if a phase checkpoint exists."""
    try:
        path = get_checkpoint_path(phase)
        # Try to read the checkpoint file
        spark.read.text(path)
        return True
    except Exception:
        return False


def write_checkpoint(spark, phase):
    """Write a checkpoint file after successful phase completion."""
    path = get_checkpoint_path(phase)
    timestamp = datetime.now().isoformat()
    data = [{"phase": phase, "completed_at": timestamp, "status": "SUCCESS"}]
    df = spark.createDataFrame(data)
    df.write.mode("overwrite").json(path)
    print(f"[CHECKPOINT] {phase} completed at {timestamp}")


def clear_checkpoints(spark):
    """Clear all checkpoints for a fresh run."""
    for phase in PHASES:
        try:
            path = get_checkpoint_path(phase)
            # Overwrite with empty marker
            spark._jvm.org.apache.hadoop.fs.FileSystem.get(
                spark._jsc.hadoopConfiguration()
            ).delete(
                spark._jvm.org.apache.hadoop.fs.Path(path), True
            )
        except Exception:
            pass


# =============================================================================
# INCREMENTAL HELPERS
# =============================================================================

def check_partition_exists(spark, path, safra):
    """Check if a SAFRA partition already exists at the given path."""
    try:
        partition_path = f"{path}/SAFRA={safra}"
        df = spark.read.format("delta").load(partition_path)
        count = df.count()
        if count > 0:
            return True
    except Exception:
        pass
    return False


def check_book_done(spark, gold_bucket, namespace, book_name):
    """Check if a Gold book already exists and has data."""
    try:
        path = f"oci://{gold_bucket}@{namespace}/books/{book_name}/"
        df = spark.read.format("delta").load(path)
        count = df.count()
        if count > 0:
            print(f"[GOLD] Book {book_name} already exists ({count} rows). Skipping.")
            return True
    except Exception:
        pass
    return False


# =============================================================================
# PHASE RUNNERS
# =============================================================================

def run_bronze(spark):
    """Execute Bronze ingestion phase."""
    print("\n" + "=" * 70)
    print("PHASE: BRONZE INGESTION")
    print("=" * 70)

    from ingest_bronze import run_bronze as _run_bronze
    total = _run_bronze(spark, NAMESPACE, BUCKETS["landing"], BUCKETS["bronze"])
    return total


def run_silver(spark):
    """Execute Silver transformation phase."""
    print("\n" + "=" * 70)
    print("PHASE: SILVER TRANSFORMATION")
    print("=" * 70)

    from transform_silver import run_silver as _run_silver
    _run_silver(spark, NAMESPACE, BUCKETS["bronze"], BUCKETS["silver"])

    # Break DAG: unpersist all cached DataFrames after Silver
    spark.catalog.clearCache()
    print("[SILVER] Cache cleared — DAG break before Gold")


def run_gold(spark):
    """Execute Gold feature engineering phase.

    Delegates to engineer_gold module's run_gold function.
    The Gold script uses spark.sql() with registered temp views,
    so we pass the existing SparkSession.
    """
    print("\n" + "=" * 70)
    print("PHASE: GOLD FEATURE ENGINEERING")
    print("=" * 70)

    from engineer_gold import run_gold as _run_gold
    _run_gold(spark, NAMESPACE, BUCKETS["silver"], BUCKETS["gold"], BUCKETS["landing"])

    print("[GOLD] Feature engineering complete")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Unified Pipeline — OCI Data Flow")
    parser.add_argument(
        "--start-phase",
        choices=PHASES,
        default="bronze",
        help="Phase to start from (default: bronze). Skips earlier phases."
    )
    parser.add_argument(
        "--end-phase",
        choices=PHASES,
        default="gold",
        help="Phase to end at (default: gold). Stops after this phase."
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Clear all checkpoints and start fresh"
    )
    args = parser.parse_args()

    # Build SparkSession with merged config (covers all phases)
    builder = SparkSession.builder.appName("unified-pipeline")
    for key, value in GOLD_SPARK_CONFIG.items():
        builder = builder.config(key, value)
    spark = builder.getOrCreate()

    print("=" * 70)
    print("UNIFIED PIPELINE — OCI Data Flow")
    print(f"Start phase: {args.start_phase}")
    print(f"End phase: {args.end_phase}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 70)

    if args.fresh:
        clear_checkpoints(spark)

    start_idx = PHASES.index(args.start_phase)
    end_idx = PHASES.index(args.end_phase)
    phases_to_run = PHASES[start_idx:end_idx + 1]

    for phase in phases_to_run:
        if check_phase_done(spark, phase) and not args.fresh:
            print(f"\n[SKIP] {phase} already completed (checkpoint found)")
            continue

        if phase == "bronze":
            run_bronze(spark)
        elif phase == "silver":
            run_silver(spark)
        elif phase == "gold":
            run_gold(spark)

        write_checkpoint(spark, phase)

        # Memory cleanup between phases
        spark.catalog.clearCache()
        print(f"[CLEANUP] Cache cleared after {phase}")

    print("\n" + "=" * 70)
    print("UNIFIED PIPELINE COMPLETE")
    print(f"Phases executed: {phases_to_run}")
    print(f"Completed at: {datetime.now().isoformat()}")
    print("=" * 70)

    spark.stop()


if __name__ == "__main__":
    main()
