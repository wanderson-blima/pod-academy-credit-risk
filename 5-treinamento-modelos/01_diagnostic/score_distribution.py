"""
Score Distribution Analysis — Phase 1.3
Per-SAFRA decile tables, calibration plot data, and swap rate analysis.

Usage: Run in OCI Data Science notebook after model training.
"""
import os
import json
import pickle
from datetime import datetime

NCPUS = int(os.environ.get("NOTEBOOK_OCPUS", "10"))
os.environ["OMP_NUM_THREADS"] = str(NCPUS)
os.environ["OPENBLAS_NUM_THREADS"] = str(NCPUS)
os.environ["MKL_NUM_THREADS"] = "1"

import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

import sklearn.utils.validation as _val
_original_check = _val.check_array
def _patched_check(*a, **kw):
    force_val = kw.pop("force_all_finite", None)
    if force_val is not None and "ensure_all_finite" not in kw:
        kw["ensure_all_finite"] = force_val
    return _original_check(*a, **kw)
_val.check_array = _patched_check

ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", "/home/datascience/artifacts")
DIAGNOSTIC_DIR = os.path.join(ARTIFACT_DIR, "diagnostic")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "oci", "model"))
from train_credit_risk import (
    SELECTED_FEATURES, TARGET, TRAIN_SAFRAS, OOT_SAFRAS,
    LOCAL_DATA_PATH, GOLD_PATH, compute_ks,
)


def decile_table_per_safra(y_true, y_prob, safras_series):
    """Generate decile tables for each SAFRA individually."""
    results = {}
    for safra in sorted(safras_series.unique()):
        mask = safras_series == safra
        y_s = y_true[mask]
        prob_s = y_prob[mask]

        if len(y_s) < 100 or y_s.nunique() < 2:
            continue

        df_eval = pd.DataFrame({"target": y_s.values, "prob": prob_s})
        df_eval["decile"] = pd.qcut(df_eval["prob"], q=10, labels=False, duplicates="drop") + 1

        table = df_eval.groupby("decile").agg(
            count=("target", "count"),
            events=("target", "sum"),
            avg_prob=("prob", "mean"),
        ).reset_index()

        table["non_events"] = table["count"] - table["events"]
        table["event_rate"] = table["events"] / table["count"]
        table["cum_events"] = table["events"].cumsum()
        table["cum_non_events"] = table["non_events"].cumsum()
        table["cum_event_pct"] = table["cum_events"] / table["events"].sum()
        table["cum_non_event_pct"] = table["cum_non_events"] / table["non_events"].sum()
        table["ks"] = abs(table["cum_event_pct"] - table["cum_non_event_pct"])
        table["lift"] = table["event_rate"] / (table["events"].sum() / table["count"].sum())

        ks_max = table["ks"].max()
        is_monotonic = table["event_rate"].is_monotonic_increasing

        results[int(safra)] = {
            "table": table,
            "ks_max": round(float(ks_max), 4),
            "monotonic": bool(is_monotonic),
            "n_records": int(len(y_s)),
        }

        print(f"  SAFRA {safra}: KS={ks_max:.4f}, Monotonic={is_monotonic}, n={len(y_s):,}")

    return results


def calibration_analysis(y_true, y_prob, n_bins=10):
    """Compare predicted probabilities vs observed default rates."""
    bins = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.digitize(y_prob, bins) - 1
    bin_indices = np.clip(bin_indices, 0, n_bins - 1)

    cal_data = []
    for k in range(n_bins):
        mask = bin_indices == k
        if mask.sum() == 0:
            continue
        cal_data.append({
            "bin": k + 1,
            "bin_lower": round(bins[k], 3),
            "bin_upper": round(bins[k + 1], 3),
            "mean_predicted": round(float(y_prob[mask].mean()), 4),
            "observed_rate": round(float(y_true[mask].mean()), 4),
            "count": int(mask.sum()),
            "gap": round(float(abs(y_prob[mask].mean() - y_true[mask].mean())), 4),
        })

    cal_df = pd.DataFrame(cal_data)

    # Expected Calibration Error
    total = cal_df["count"].sum()
    ece = sum(row["count"] / total * row["gap"] for _, row in cal_df.iterrows())

    print(f"\n  Calibration Analysis (ECE={ece:.4f}):")
    print(cal_df[["bin", "mean_predicted", "observed_rate", "count", "gap"]].to_string(index=False))

    return cal_df, round(ece, 4)


def swap_analysis_detailed(y_prob, safras_series, safra_pairs=None):
    """Analyze swap rate between SAFRA pairs in detail."""
    if safra_pairs is None:
        safras = sorted(safras_series.unique())
        safra_pairs = [(safras[i], safras[i + 1]) for i in range(len(safras) - 1)]

    swap_results = {}
    for s1, s2 in safra_pairs:
        mask1 = safras_series == s1
        mask2 = safras_series == s2

        if mask1.sum() < 100 or mask2.sum() < 100:
            continue

        prob1 = y_prob[mask1]
        prob2 = y_prob[mask2]

        deciles_1 = pd.qcut(prob1, q=10, labels=False, duplicates="drop") + 1
        deciles_2 = pd.qcut(prob2, q=10, labels=False, duplicates="drop") + 1

        # Top decil swap analysis
        top_decil_1 = set(np.where(mask1)[0][deciles_1 == 10])
        top_decil_2 = set(np.where(mask2)[0][deciles_2 == 10])

        # For OOS/OOT comparison — use scoring rather than individual tracking
        # Report distribution comparison
        swap_results[f"{s1}_vs_{s2}"] = {
            "safra_1_n": int(mask1.sum()),
            "safra_2_n": int(mask2.sum()),
            "safra_1_top_decil_avg_prob": round(float(prob1[deciles_1 == 10].mean()), 4) if (deciles_1 == 10).any() else None,
            "safra_2_top_decil_avg_prob": round(float(prob2[deciles_2 == 10].mean()), 4) if (deciles_2 == 10).any() else None,
            "safra_1_bottom_decil_avg_prob": round(float(prob1[deciles_1 == 1].mean()), 4) if (deciles_1 == 1).any() else None,
            "safra_2_bottom_decil_avg_prob": round(float(prob2[deciles_2 == 1].mean()), 4) if (deciles_2 == 1).any() else None,
        }

        # Score distribution stats
        for label, probs in [("safra_1", prob1), ("safra_2", prob2)]:
            swap_results[f"{s1}_vs_{s2}"][f"{label}_mean"] = round(float(probs.mean()), 4)
            swap_results[f"{s1}_vs_{s2}"][f"{label}_std"] = round(float(probs.std()), 4)

        print(f"  {s1} vs {s2}: top decil prob shift "
              f"{swap_results[f'{s1}_vs_{s2}']['safra_1_top_decil_avg_prob']} -> "
              f"{swap_results[f'{s1}_vs_{s2}']['safra_2_top_decil_avg_prob']}")

    return swap_results


def run_score_distribution():
    """Full score distribution analysis."""
    import pyarrow.parquet as pq
    import glob as glob_mod

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 70)
    print("DIAGNOSTIC: Score Distribution")
    print(f"Run ID: {run_id}")
    print("=" * 70)

    # Load model
    lgbm_files = sorted(glob_mod.glob(f"{ARTIFACT_DIR}/models/lgbm_oci_*.pkl"))
    if not lgbm_files:
        print("[ERROR] No trained LGBM .pkl found.")
        return
    with open(lgbm_files[-1], "rb") as f:
        pipeline = pickle.load(f)

    # Load data
    columns_to_load = SELECTED_FEATURES + [TARGET, "SAFRA", "NUM_CPF"]
    if os.path.exists(LOCAL_DATA_PATH):
        table = pq.read_table(LOCAL_DATA_PATH, columns=columns_to_load)
        df = table.to_pandas(self_destruct=True)
    else:
        df = pd.read_parquet(GOLD_PATH, columns=columns_to_load)

    df = df[df[TARGET].notna()].copy()
    y = df[TARGET].astype(int)
    X = df[SELECTED_FEATURES]
    y_prob = pipeline.predict_proba(X)[:, 1]

    # 1. Decile tables per SAFRA
    print("\n" + "-" * 70)
    print("1. DECILE TABLES PER SAFRA")
    print("-" * 70)

    decile_results = decile_table_per_safra(y, y_prob, df["SAFRA"])

    # 2. Calibration analysis
    print("\n" + "-" * 70)
    print("2. CALIBRATION ANALYSIS")
    print("-" * 70)

    cal_all, ece_all = calibration_analysis(y.values, y_prob)

    # Per-period calibration
    oot_mask = df["SAFRA"].isin(OOT_SAFRAS)
    if oot_mask.sum() > 100:
        print("\n  OOT Calibration:")
        cal_oot, ece_oot = calibration_analysis(y[oot_mask].values, y_prob[oot_mask])
    else:
        cal_oot, ece_oot = None, None

    # 3. Swap analysis
    print("\n" + "-" * 70)
    print("3. SWAP RATE ANALYSIS")
    print("-" * 70)

    swap_results = swap_analysis_detailed(y_prob, df["SAFRA"])

    # Save
    os.makedirs(DIAGNOSTIC_DIR, exist_ok=True)

    report = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "decile_summary": {
            str(s): {"ks_max": r["ks_max"], "monotonic": r["monotonic"], "n": r["n_records"]}
            for s, r in decile_results.items()
        },
        "calibration": {
            "ece_all": ece_all,
            "ece_oot": ece_oot,
        },
        "swap_analysis": swap_results,
    }

    with open(os.path.join(DIAGNOSTIC_DIR, f"score_distribution_{run_id}.json"), "w") as f:
        json.dump(report, f, indent=2, default=str)

    # Save decile CSVs
    for safra, result in decile_results.items():
        result["table"].to_csv(
            os.path.join(DIAGNOSTIC_DIR, f"decile_safra_{safra}_{run_id}.csv"),
            index=False,
        )

    if cal_all is not None:
        cal_all.to_csv(os.path.join(DIAGNOSTIC_DIR, f"calibration_{run_id}.csv"), index=False)

    print(f"\n[SAVE] Score distribution report saved to {DIAGNOSTIC_DIR}/")
    return report


if __name__ == "__main__":
    run_score_distribution()
