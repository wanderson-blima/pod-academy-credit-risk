"""
Error Analysis — Phase 1.1
Segments false positives/negatives by SAFRA, risk band, and bureau score.
Brier score decomposition for reliability and resolution assessment.

Usage: Run in OCI Data Science notebook after model training.
"""
import os
import json
import pickle
import time
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

from sklearn.metrics import brier_score_loss

# ── Paths ────────────────────────────────────────────────────────────────
ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", "/home/datascience/artifacts")
DIAGNOSTIC_DIR = os.path.join(ARTIFACT_DIR, "diagnostic")

# Import shared config
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "oci", "model"))
from train_credit_risk import (
    SELECTED_FEATURES, TARGET, TRAIN_SAFRAS, OOT_SAFRAS,
    LOCAL_DATA_PATH, GOLD_PATH, compute_ks,
)

# ═════════════════════════════════════════════════════════════════════════
# ERROR SEGMENTATION
# ═════════════════════════════════════════════════════════════════════════

def segment_errors(y_true, y_prob, df_meta, threshold=0.5):
    """Classify predictions into TP/TN/FP/FN and segment by metadata."""
    y_pred = (y_prob >= threshold).astype(int)

    segments = pd.DataFrame({
        "y_true": y_true.values,
        "y_prob": y_prob,
        "y_pred": y_pred,
        "SAFRA": df_meta["SAFRA"].values,
    })

    # Add bureau score buckets if available
    if "TARGET_SCORE_02" in df_meta.columns:
        segments["BUREAU_SCORE"] = df_meta["TARGET_SCORE_02"].values
        segments["BUREAU_BUCKET"] = pd.cut(
            segments["BUREAU_SCORE"],
            bins=[-np.inf, 300, 500, 700, np.inf],
            labels=["LOW_0_300", "MED_300_500", "HIGH_500_700", "VERY_HIGH_700+"],
        )

    # Classify error types
    segments["error_type"] = "TN"
    segments.loc[(segments["y_true"] == 1) & (segments["y_pred"] == 1), "error_type"] = "TP"
    segments.loc[(segments["y_true"] == 0) & (segments["y_pred"] == 1), "error_type"] = "FP"
    segments.loc[(segments["y_true"] == 1) & (segments["y_pred"] == 0), "error_type"] = "FN"

    # Risk band from probability
    scores = ((1 - y_prob) * 1000).astype(int).clip(0, 1000)
    segments["FAIXA_RISCO"] = pd.cut(
        scores, bins=[-1, 300, 500, 700, 1001],
        labels=["CRITICO", "ALTO", "MEDIO", "BAIXO"],
    )

    return segments


def error_profile_by_safra(segments):
    """Error distribution per SAFRA."""
    profile = segments.groupby(["SAFRA", "error_type"]).size().unstack(fill_value=0)
    profile["total"] = profile.sum(axis=1)
    for col in ["TP", "FP", "TN", "FN"]:
        if col in profile.columns:
            profile[f"{col}_pct"] = (profile[col] / profile["total"] * 100).round(2)

    print("\n  Error Profile by SAFRA:")
    print(profile.to_string())
    return profile


def error_profile_by_risk_band(segments):
    """Error distribution per risk band."""
    profile = segments.groupby(["FAIXA_RISCO", "error_type"]).size().unstack(fill_value=0)
    profile["total"] = profile.sum(axis=1)
    for col in ["TP", "FP", "TN", "FN"]:
        if col in profile.columns:
            profile[f"{col}_pct"] = (profile[col] / profile["total"] * 100).round(2)

    print("\n  Error Profile by Risk Band:")
    print(profile.to_string())
    return profile


def high_bureau_defaulters(segments):
    """Analyze clients with high bureau scores who defaulted (FN — model misses)."""
    if "BUREAU_BUCKET" not in segments.columns:
        print("  [SKIP] No bureau score available")
        return None

    fn_high = segments[
        (segments["error_type"] == "FN") &
        (segments["BUREAU_BUCKET"].isin(["HIGH_500_700", "VERY_HIGH_700+"]))
    ]

    total_fn = (segments["error_type"] == "FN").sum()
    high_fn = len(fn_high)

    print(f"\n  High Bureau Score Defaulters (FN):")
    print(f"    Total FN: {total_fn:,}")
    print(f"    High bureau FN: {high_fn:,} ({high_fn/max(total_fn,1)*100:.1f}%)")

    if len(fn_high) > 0:
        print(f"    Mean predicted prob: {fn_high['y_prob'].mean():.4f}")
        print(f"    SAFRA distribution:")
        print(fn_high.groupby("SAFRA").size().to_string())

    return fn_high


# ═════════════════════════════════════════════════════════════════════════
# BRIER SCORE DECOMPOSITION
# ═════════════════════════════════════════════════════════════════════════

def brier_decomposition(y_true, y_prob, n_bins=10):
    """Decompose Brier score into reliability, resolution, and uncertainty."""
    brier = brier_score_loss(y_true, y_prob)
    base_rate = y_true.mean()
    uncertainty = base_rate * (1 - base_rate)

    # Bin predictions
    bins = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.digitize(y_prob, bins) - 1
    bin_indices = np.clip(bin_indices, 0, n_bins - 1)

    reliability = 0.0
    resolution = 0.0

    for k in range(n_bins):
        mask = bin_indices == k
        n_k = mask.sum()
        if n_k == 0:
            continue
        o_k = y_true[mask].mean()  # observed frequency
        f_k = y_prob[mask].mean()  # forecast probability
        reliability += n_k * (f_k - o_k) ** 2
        resolution += n_k * (o_k - base_rate) ** 2

    reliability /= len(y_true)
    resolution /= len(y_true)

    print(f"\n  Brier Score Decomposition:")
    print(f"    Brier Score:  {brier:.6f}")
    print(f"    Reliability:  {reliability:.6f} (lower=better calibration)")
    print(f"    Resolution:   {resolution:.6f} (higher=better discrimination)")
    print(f"    Uncertainty:  {uncertainty:.6f} (base rate contribution)")
    print(f"    Skill Score:  {(resolution - reliability) / uncertainty:.4f}")

    return {
        "brier_score": round(brier, 6),
        "reliability": round(reliability, 6),
        "resolution": round(resolution, 6),
        "uncertainty": round(uncertainty, 6),
        "skill_score": round((resolution - reliability) / uncertainty, 4),
    }


# ═════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════

def run_error_analysis():
    """Full error analysis pipeline."""
    import pyarrow.parquet as pq
    import glob as glob_mod

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 70)
    print("DIAGNOSTIC: Error Analysis")
    print(f"Run ID: {run_id}")
    print("=" * 70)

    # Load model
    lgbm_files = sorted(glob_mod.glob(f"{ARTIFACT_DIR}/models/lgbm_oci_*.pkl"))
    if not lgbm_files:
        print("[ERROR] No trained LGBM .pkl found.")
        return
    with open(lgbm_files[-1], "rb") as f:
        pipeline = pickle.load(f)
    print(f"[LOAD] Model: {lgbm_files[-1]}")

    # Load data
    columns_to_load = SELECTED_FEATURES + [TARGET, "SAFRA", "NUM_CPF"]
    if os.path.exists(LOCAL_DATA_PATH):
        table = pq.read_table(LOCAL_DATA_PATH, columns=columns_to_load)
        df = table.to_pandas(self_destruct=True)
    else:
        df = pd.read_parquet(GOLD_PATH, columns=columns_to_load)

    # Filter to labeled data
    df = df[df[TARGET].notna()].copy()
    y = df[TARGET].astype(int)
    X = df[SELECTED_FEATURES]
    y_prob = pipeline.predict_proba(X)[:, 1]

    # 1. Error segmentation
    print("\n" + "-" * 70)
    print("1. ERROR SEGMENTATION")
    print("-" * 70)

    segments = segment_errors(y, y_prob, df)

    safra_profile = error_profile_by_safra(segments)
    risk_profile = error_profile_by_risk_band(segments)
    fn_high = high_bureau_defaulters(segments)

    # 2. Error analysis per SAFRA
    print("\n" + "-" * 70)
    print("2. PER-SAFRA METRICS")
    print("-" * 70)

    safra_metrics = {}
    for safra in sorted(df["SAFRA"].unique()):
        mask = df["SAFRA"] == safra
        if mask.sum() < 100:
            continue
        y_s = y[mask]
        prob_s = y_prob[mask]
        ks = compute_ks(y_s.values, prob_s)
        fpd_rate = y_s.mean()
        n_fp = ((prob_s >= 0.5) & (y_s == 0)).sum()
        n_fn = ((prob_s < 0.5) & (y_s == 1)).sum()
        safra_metrics[int(safra)] = {
            "n": int(mask.sum()),
            "fpd_rate": round(float(fpd_rate), 4),
            "ks": round(float(ks), 4),
            "n_fp": int(n_fp),
            "n_fn": int(n_fn),
        }
        print(f"  SAFRA {safra}: n={mask.sum():,}, FPD={fpd_rate:.4f}, KS={ks:.4f}, FP={n_fp:,}, FN={n_fn:,}")

    # 3. Brier decomposition
    print("\n" + "-" * 70)
    print("3. BRIER SCORE DECOMPOSITION")
    print("-" * 70)

    brier_all = brier_decomposition(y.values, y_prob)

    # Per OOS/OOT
    oos_mask = df["SAFRA"].isin([202501])
    oot_mask = df["SAFRA"].isin(OOT_SAFRAS)

    brier_oos = brier_decomposition(y[oos_mask].values, y_prob[oos_mask]) if oos_mask.sum() > 100 else None
    brier_oot = brier_decomposition(y[oot_mask].values, y_prob[oot_mask]) if oot_mask.sum() > 100 else None

    # Save results
    os.makedirs(DIAGNOSTIC_DIR, exist_ok=True)

    report = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "total_records": len(df),
        "safra_metrics": safra_metrics,
        "brier_all": brier_all,
        "brier_oos": brier_oos,
        "brier_oot": brier_oot,
        "error_summary": {
            "total_fp": int((segments["error_type"] == "FP").sum()),
            "total_fn": int((segments["error_type"] == "FN").sum()),
            "total_tp": int((segments["error_type"] == "TP").sum()),
            "total_tn": int((segments["error_type"] == "TN").sum()),
            "high_bureau_fn": int(len(fn_high)) if fn_high is not None else 0,
        },
        "improvement_areas": [],
    }

    # Identify improvement areas
    if brier_all["reliability"] > 0.001:
        report["improvement_areas"].append("Calibration: Brier reliability > 0.001 — consider Platt scaling")
    if fn_high is not None and len(fn_high) > 100:
        report["improvement_areas"].append(f"High bureau defaulters: {len(fn_high)} FN with high bureau — add interaction features")
    for safra, m in safra_metrics.items():
        if m["ks"] < 0.30:
            report["improvement_areas"].append(f"SAFRA {safra} KS={m['ks']:.4f} below 0.30 — investigate drift")

    with open(os.path.join(DIAGNOSTIC_DIR, f"error_analysis_{run_id}.json"), "w") as f:
        json.dump(report, f, indent=2, default=str)

    safra_profile.to_csv(os.path.join(DIAGNOSTIC_DIR, f"error_by_safra_{run_id}.csv"))
    risk_profile.to_csv(os.path.join(DIAGNOSTIC_DIR, f"error_by_risk_{run_id}.csv"))

    print(f"\n[SAVE] Diagnostics saved to {DIAGNOSTIC_DIR}/")
    print(f"\n  Improvement Areas Identified: {len(report['improvement_areas'])}")
    for area in report["improvement_areas"]:
        print(f"    - {area}")

    return report


if __name__ == "__main__":
    run_error_analysis()
