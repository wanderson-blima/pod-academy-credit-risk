"""
Ensemble Evaluation Suite — Phase 6.1
Comprehensive evaluation of ensemble model: decile tables, swap analysis,
feature PSI, calibration, and backtesting across SAFRAs.

Usage: Run after ensemble is selected.
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

from sklearn.metrics import roc_auc_score
from scipy.stats import ks_2samp

ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", "/home/datascience/artifacts")
EVAL_DIR = os.path.join(ARTIFACT_DIR, "evaluation_ensemble")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "oci", "model"))
from train_credit_risk import (
    TARGET, TRAIN_SAFRAS, OOS_SAFRA, OOT_SAFRAS,
    LOCAL_DATA_PATH, GOLD_PATH,
    compute_ks, compute_gini, compute_psi,
)
from evaluate_model import generate_decile_table, swap_analysis


def evaluate_per_safra(ensemble_model, df, features):
    """Evaluate ensemble per individual SAFRA."""
    results = {}
    for safra in sorted(df["SAFRA"].unique()):
        df_s = df[(df["SAFRA"] == safra) & (df[TARGET].notna())]
        if len(df_s) < 100:
            continue

        X_s = df_s[features]
        y_s = df_s[TARGET].astype(int)
        y_prob = ensemble_model.predict_proba(X_s)[:, 1]

        ks = compute_ks(y_s.values, y_prob)
        auc = roc_auc_score(y_s, y_prob)
        gini = compute_gini(auc)

        results[int(safra)] = {
            "n": int(len(df_s)),
            "fpd_rate": round(float(y_s.mean()), 4),
            "ks": round(float(ks), 5),
            "auc": round(float(auc), 5),
            "gini": round(float(gini), 2),
        }

        print(f"  SAFRA {safra}: n={len(df_s):,} KS={ks:.4f} AUC={auc:.4f} Gini={gini:.2f}")

    return results


def calibration_plot_data(y_true, y_prob, n_bins=10):
    """Generate calibration data: predicted vs observed."""
    bins = np.linspace(0, 1, n_bins + 1)
    bin_idx = np.digitize(y_prob, bins) - 1
    bin_idx = np.clip(bin_idx, 0, n_bins - 1)

    cal_data = []
    for k in range(n_bins):
        mask = bin_idx == k
        if mask.sum() == 0:
            continue
        cal_data.append({
            "bin": k + 1,
            "mean_predicted": round(float(y_prob[mask].mean()), 4),
            "observed_rate": round(float(y_true[mask].mean()), 4),
            "count": int(mask.sum()),
        })

    return pd.DataFrame(cal_data)


def backtesting(ensemble_model, baseline_pipeline, df, features):
    """Compare ensemble vs baseline across all SAFRAs (would ensemble have performed better?)."""
    print(f"\n{'─' * 50}")
    print("BACKTESTING: Ensemble vs LGBM Baseline")
    print(f"{'─' * 50}")

    backtest_results = {}
    for safra in sorted(df["SAFRA"].unique()):
        df_s = df[(df["SAFRA"] == safra) & (df[TARGET].notna())]
        if len(df_s) < 100:
            continue

        X_s = df_s[features]
        y_s = df_s[TARGET].astype(int)

        ens_prob = ensemble_model.predict_proba(X_s)[:, 1]
        ens_ks = compute_ks(y_s.values, ens_prob)

        try:
            base_features = list(baseline_pipeline.named_steps["prep"].transformers[0][2])
            if len(baseline_pipeline.named_steps["prep"].transformers) > 1:
                base_features += list(baseline_pipeline.named_steps["prep"].transformers[1][2])
            base_prob = baseline_pipeline.predict_proba(df_s[base_features])[:, 1]
            base_ks = compute_ks(y_s.values, base_prob)
        except Exception:
            base_ks = None

        improvement = round(float(ens_ks - base_ks), 5) if base_ks is not None else None

        backtest_results[int(safra)] = {
            "ensemble_ks": round(float(ens_ks), 5),
            "baseline_ks": round(float(base_ks), 5) if base_ks is not None else None,
            "improvement": improvement,
        }

        base_str = f"{base_ks:.4f}" if base_ks is not None else "N/A"
        imp_str = f"{improvement:+.4f}" if improvement is not None else "N/A"
        print(f"  SAFRA {safra}: Ensemble={ens_ks:.4f} Baseline={base_str} Improvement={imp_str}")

    return backtest_results


def run_ensemble_evaluation(ensemble_model, df, features, baseline_pipeline=None):
    """Full ensemble evaluation suite."""
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 70)
    print("ENSEMBLE EVALUATION SUITE")
    print(f"Run ID: {run_id}")
    print("=" * 70)

    df = df[df[TARGET].notna()].copy()

    df_train = df[df["SAFRA"].isin(TRAIN_SAFRAS)]
    df_oos = df[df["SAFRA"].isin(OOS_SAFRA)]
    df_oot = df[df["SAFRA"].isin(OOT_SAFRAS)]

    X_train, y_train = df_train[features], df_train[TARGET].astype(int)
    X_oos, y_oos = df_oos[features], df_oos[TARGET].astype(int)
    X_oot, y_oot = df_oot[features], df_oot[TARGET].astype(int)

    # 1. Per-SAFRA metrics
    print(f"\n{'─' * 50}")
    print("1. PER-SAFRA METRICS")
    print(f"{'─' * 50}")

    safra_metrics = evaluate_per_safra(ensemble_model, df, features)

    # 2. Decile tables (OOS + OOT)
    print(f"\n{'─' * 50}")
    print("2. DECILE TABLES")
    print(f"{'─' * 50}")

    oos_prob = ensemble_model.predict_proba(X_oos)[:, 1]
    oot_prob = ensemble_model.predict_proba(X_oot)[:, 1]

    decile_oos, mono_oos = generate_decile_table(y_oos, oos_prob, "Ensemble OOS")
    decile_oot, mono_oot = generate_decile_table(y_oot, oot_prob, "Ensemble OOT")

    # 3. PSI
    print(f"\n{'─' * 50}")
    print("3. SCORE PSI")
    print(f"{'─' * 50}")

    train_prob = ensemble_model.predict_proba(X_train)[:, 1]
    psi = compute_psi(train_prob, oot_prob)
    psi_status = "OK" if psi < 0.10 else ("WARNING" if psi < 0.25 else "RETRAIN")
    print(f"  Ensemble PSI (Train vs OOT): {psi:.6f} [{psi_status}]")

    # 4. Calibration
    print(f"\n{'─' * 50}")
    print("4. CALIBRATION")
    print(f"{'─' * 50}")

    cal_oot = calibration_plot_data(y_oot.values, oot_prob)
    print(cal_oot.to_string(index=False))

    # 5. Backtesting
    backtest = None
    if baseline_pipeline is not None:
        backtest = backtesting(ensemble_model, baseline_pipeline, df, features)

    # 6. Summary metrics
    ens_ks_oot = compute_ks(y_oot.values, oot_prob)
    ens_auc_oot = roc_auc_score(y_oot, oot_prob)
    ens_gini_oot = compute_gini(ens_auc_oot)

    print(f"\n{'=' * 70}")
    print("ENSEMBLE EVALUATION SUMMARY")
    print(f"  KS OOT:  {ens_ks_oot:.5f}")
    print(f"  AUC OOT: {ens_auc_oot:.5f}")
    print(f"  Gini OOT: {ens_gini_oot:.2f}")
    print(f"  PSI:     {psi:.6f}")
    print(f"  OOS Monotonic: {mono_oos}")
    print(f"  OOT Monotonic: {mono_oot}")
    print(f"{'=' * 70}")

    # Save
    os.makedirs(EVAL_DIR, exist_ok=True)

    report = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "ensemble_mode": getattr(ensemble_model, "mode", "unknown"),
        "safra_metrics": safra_metrics,
        "oot_summary": {
            "ks": round(ens_ks_oot, 5),
            "auc": round(ens_auc_oot, 5),
            "gini": round(ens_gini_oot, 2),
            "psi": psi,
            "monotonic_oos": mono_oos,
            "monotonic_oot": mono_oot,
        },
        "backtesting": backtest,
    }

    with open(os.path.join(EVAL_DIR, f"evaluation_ensemble_{run_id}.json"), "w") as f:
        json.dump(report, f, indent=2, default=str)

    decile_oos.to_csv(os.path.join(EVAL_DIR, f"decile_ensemble_oos_{run_id}.csv"), index=False)
    decile_oot.to_csv(os.path.join(EVAL_DIR, f"decile_ensemble_oot_{run_id}.csv"), index=False)
    cal_oot.to_csv(os.path.join(EVAL_DIR, f"calibration_ensemble_{run_id}.csv"), index=False)

    print(f"\n[SAVE] Evaluation saved to {EVAL_DIR}/")
    return report


if __name__ == "__main__":
    print("Ensemble Evaluation — run run_ensemble_evaluation(ensemble_model, df, features)")
