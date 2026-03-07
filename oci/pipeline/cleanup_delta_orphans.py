#!/usr/bin/env python3
"""
Cleanup Delta Lake Orphan Parquet Files from OCI Object Storage
===============================================================

ADW External Tables read ALL Parquet files in a prefix (no Delta log awareness).
This script removes orphan Parquet files that are not tracked by the current
Delta Lake transaction log, preventing duplicate/stale data in ADW queries.

Targets:
  - Gold: 102 orphan files from v5 (hash 712998fb, 104 cols — superseded by v7, 402 cols)
  - Silver book/ass_recarga_cmv: ~167 orphans from v0 (overwritten by v1)
  - Silver book/pagamento: ~4 orphans
  - Silver book/faturamento: ~5 orphans

Prerequisites:
  - OCI CLI configured (`oci session authenticate` or API key in ~/.oci/config)
  - Delta log JSON files in project root (downloaded from OCI _delta_log/)
  - Python 3.8+

Usage:
  python cleanup_delta_orphans.py --dry-run    # Preview only (default)
  python cleanup_delta_orphans.py --execute     # Actually delete orphans
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


# ── OCI Constants ──────────────────────────────────────────────────────────
NAMESPACE = "grlxi07jz1mo"
REGION = "sa-saopaulo-1"

# Bucket → prefix → delta log files mapping
CLEANUP_TARGETS = {
    "gold": {
        "bucket": "pod-academy-gold",
        "prefix": "feature_store/clientes_consolidado/",
        "delta_logs": ["gold_delta_log_v0.json"],
        "description": "Gold clientes_consolidado (v7, 402 cols)",
    },
    "book_recarga": {
        "bucket": "pod-academy-silver",
        "prefix": "book/ass_recarga_cmv/",
        # v1 is an Overwrite of v0 — only v1 adds are current
        "delta_logs": ["delta_ass_recarga_cmv_v0.json", "delta_recarga_v1.json"],
        "description": "Silver book ass_recarga_cmv (v1, 93 cols)",
    },
    "book_pagamento": {
        "bucket": "pod-academy-silver",
        "prefix": "book/pagamento/",
        "delta_logs": ["delta_pagamento_v0.json"],
        "description": "Silver book pagamento (v0, 97 cols)",
    },
    "book_faturamento": {
        "bucket": "pod-academy-silver",
        "prefix": "book/faturamento/",
        "delta_logs": ["delta_faturamento_v0.json"],
        "description": "Silver book faturamento (v0, 117 cols)",
    },
}


def parse_delta_logs(delta_log_paths: list[str], project_root: Path) -> set[str]:
    """
    Parse Delta Lake transaction log JSON files and compute the current set
    of tracked Parquet file paths.

    Delta semantics for Overwrite:
    - Each log version may contain "add" and "remove" entries
    - For a single-version table (v0 only), all "add" entries are current
    - For multi-version (v0 + v1 Overwrite), v1's adds replace v0's adds
      (v0 adds become implicitly removed)

    Returns:
        Set of relative Parquet paths (e.g., "SAFRA=202410/part-00000-xxx.parquet")
    """
    adds = set()
    removes = set()
    last_is_overwrite = False

    for log_path in delta_log_paths:
        full_path = project_root / log_path
        if not full_path.exists():
            print(f"  WARNING: Delta log not found: {full_path}")
            continue

        version_adds = set()
        version_removes = set()
        is_overwrite = False

        with open(full_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)

                if "commitInfo" in entry:
                    op_params = entry["commitInfo"].get("operationParameters", {})
                    if op_params.get("mode") == "Overwrite":
                        is_overwrite = True

                if "add" in entry:
                    version_adds.add(entry["add"]["path"])

                if "remove" in entry:
                    version_removes.add(entry["remove"]["path"])

        # For Overwrite mode with readVersion, the new version completely
        # replaces the previous state — previous adds become orphans
        if is_overwrite and len(delta_log_paths) > 1:
            # This version's adds are the only current files
            adds = version_adds
            removes = set()  # Previous adds are implicitly removed
            last_is_overwrite = True
        else:
            adds.update(version_adds)
            adds -= version_removes
            removes.update(version_removes)

    return adds


def list_bucket_parquets(bucket: str, prefix: str) -> list[str]:
    """
    List all .parquet files in an OCI bucket prefix using OCI CLI.

    Returns:
        List of full object names (e.g., "feature_store/clientes_consolidado/SAFRA=202410/part-xxx.parquet")
    """
    cmd = [
        "oci", "os", "object", "list",
        "--bucket-name", bucket,
        "--namespace-name", NAMESPACE,
        "--prefix", prefix,
        "--all",
        "--output", "json",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)

    parquets = []
    for obj in data.get("data", []):
        name = obj["name"]
        if name.endswith(".parquet"):
            parquets.append(name)

    return parquets


def delete_object(bucket: str, object_name: str, dry_run: bool) -> bool:
    """Delete a single object from OCI Object Storage."""
    if dry_run:
        return True

    cmd = [
        "oci", "os", "object", "delete",
        "--bucket-name", bucket,
        "--namespace-name", NAMESPACE,
        "--name", object_name,
        "--force",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def cleanup_target(target_key: str, config: dict, project_root: Path, dry_run: bool) -> dict:
    """
    Clean orphan Parquet files for a single target.

    Returns:
        Summary dict with counts.
    """
    bucket = config["bucket"]
    prefix = config["prefix"]
    delta_logs = config["delta_logs"]
    description = config["description"]

    print(f"\n{'='*70}")
    print(f"Target: {description}")
    print(f"Bucket: {bucket} | Prefix: {prefix}")
    print(f"{'='*70}")

    # Step 1: Parse delta logs → tracked files
    tracked_files = parse_delta_logs(delta_logs, project_root)
    print(f"  Delta tracked files: {len(tracked_files)}")

    # Step 2: List all Parquets in bucket
    all_parquets = list_bucket_parquets(bucket, prefix)
    print(f"  Total Parquets in bucket: {len(all_parquets)}")

    # Step 3: Compute orphans
    # tracked_files are relative paths (SAFRA=.../part-xxx.parquet)
    # all_parquets are full paths (feature_store/clientes_consolidado/SAFRA=.../part-xxx.parquet)
    tracked_full = {prefix + f for f in tracked_files}

    orphans = [p for p in all_parquets if p not in tracked_full]
    # Also exclude _delta_log/ entries (not parquet data files)
    orphans = [p for p in orphans if "/_delta_log/" not in p]

    print(f"  Orphan files to delete: {len(orphans)}")

    if not orphans:
        print("  No orphans found — skipping.")
        return {"target": target_key, "tracked": len(tracked_files),
                "total": len(all_parquets), "orphans": 0, "deleted": 0, "failed": 0}

    # Step 4: Delete orphans
    deleted = 0
    failed = 0
    for i, orphan in enumerate(orphans, 1):
        action = "WOULD DELETE" if dry_run else "DELETING"
        print(f"  [{i}/{len(orphans)}] {action}: {orphan}")
        if delete_object(bucket, orphan, dry_run):
            deleted += 1
        else:
            failed += 1
            print(f"    FAILED to delete: {orphan}")

    return {"target": target_key, "tracked": len(tracked_files),
            "total": len(all_parquets), "orphans": len(orphans),
            "deleted": deleted, "failed": failed}


def main():
    parser = argparse.ArgumentParser(
        description="Cleanup orphan Parquet files from OCI Object Storage (Delta Lake aware)"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True,
                      help="Preview only, do not delete (default)")
    mode.add_argument("--execute", action="store_true",
                      help="Actually delete orphan files")
    parser.add_argument("--target", choices=list(CLEANUP_TARGETS.keys()),
                        help="Clean only a specific target (default: all)")
    args = parser.parse_args()

    dry_run = not args.execute

    # Project root = 4 levels up from this script
    project_root = Path(__file__).resolve().parent.parent.parent.parent.parent

    print("Delta Lake Orphan Cleanup — OCI Object Storage")
    print(f"Mode: {'DRY RUN (preview only)' if dry_run else 'EXECUTE (will delete files!)'}")
    print(f"Project root: {project_root}")

    # Verify delta logs exist
    targets = {args.target: CLEANUP_TARGETS[args.target]} if args.target else CLEANUP_TARGETS
    missing_logs = []
    for key, config in targets.items():
        for log_file in config["delta_logs"]:
            if not (project_root / log_file).exists():
                missing_logs.append(log_file)

    if missing_logs:
        print(f"\nERROR: Missing delta log files: {missing_logs}")
        print("Download them from OCI _delta_log/ first:")
        print("  oci os object get --bucket-name <bucket> --name <prefix>/_delta_log/00000000000000000000.json ...")
        sys.exit(1)

    # Run cleanup
    results = []
    for key, config in targets.items():
        result = cleanup_target(key, config, project_root, dry_run)
        results.append(result)

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    total_orphans = 0
    total_deleted = 0
    total_failed = 0
    for r in results:
        status = "DRY RUN" if dry_run else ("OK" if r["failed"] == 0 else "ERRORS")
        print(f"  {r['target']:20s} | tracked: {r['tracked']:4d} | total: {r['total']:4d} | "
              f"orphans: {r['orphans']:4d} | deleted: {r['deleted']:4d} | [{status}]")
        total_orphans += r["orphans"]
        total_deleted += r["deleted"]
        total_failed += r["failed"]

    print(f"\n  Total orphans: {total_orphans} | Deleted: {total_deleted} | Failed: {total_failed}")

    if dry_run and total_orphans > 0:
        print("\n  Run with --execute to actually delete these files.")

    # Post-cleanup verification reminder
    if not dry_run and total_deleted > 0:
        print("\n  POST-CLEANUP VERIFICATION:")
        print("  Re-run with --dry-run to confirm 0 orphans remain.")
        for r in results:
            if r["deleted"] > 0:
                config = CLEANUP_TARGETS[r["target"]]
                expected = r["tracked"]
                print(f"  Expected {config['prefix']}: {expected} Parquet files")

    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
