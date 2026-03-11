"""
Feature Selection Pipeline v2 — Phase 2.7
Multi-stage selection: IV → L1 → Correlation → Stability → Permutation Importance.
Anti-leakage validation included.

Usage: Run as script or import run_feature_selection(df_train, y_train, df_all).
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

from sklearn.linear_model import LogisticRegression
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", "/home/datascience/artifacts")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "oci", "model"))
from train_credit_risk import compute_psi


# ═════════════════════════════════════════════════════════════════════════
# INFORMATION VALUE
# ═════════════════════════════════════════════════════════════════════════

def compute_iv(feature_values, target, n_bins=10):
    """Compute Information Value for a single feature."""
    try:
        bins = pd.qcut(feature_values.fillna(feature_values.median()), q=n_bins, duplicates="drop")
    except ValueError:
        return 0.0

    total_events = target.sum()
    total_non_events = len(target) - total_events

    if total_events == 0 or total_non_events == 0:
        return 0.0

    iv = 0.0
    for _, group in target.groupby(bins):
        events = group.sum()
        non_events = len(group) - events

        events_pct = (events + 0.5) / (total_events + 1)
        non_events_pct = (non_events + 0.5) / (total_non_events + 1)

        woe = np.log(non_events_pct / events_pct)
        iv += (non_events_pct - events_pct) * woe

    return round(float(iv), 6)


def iv_filter(df, y, features, min_iv=0.02):
    """Filter features by Information Value threshold."""
    iv_results = {}
    for feat in features:
        if feat not in df.columns:
            continue
        iv = compute_iv(df[feat], y)
        iv_results[feat] = iv

    iv_df = pd.DataFrame({
        "feature": iv_results.keys(),
        "iv": iv_results.values(),
    }).sort_values("iv", ascending=False)

    passed = iv_df[iv_df["iv"] >= min_iv]["feature"].tolist()

    print(f"  IV filter: {len(features)} → {len(passed)} features (IV >= {min_iv})")
    print(f"  Rejected: {len(features) - len(passed)} features with IV < {min_iv}")

    return passed, iv_df


# ═════════════════════════════════════════════════════════════════════════
# L1 REGULARIZATION FILTER
# ═════════════════════════════════════════════════════════════════════════

def l1_filter(df, y, features, C=0.1):
    """Filter features using L1 Logistic Regression coefficients."""
    imputer = SimpleImputer(strategy="median")
    scaler = StandardScaler()

    X = pd.DataFrame(
        scaler.fit_transform(imputer.fit_transform(df[features])),
        columns=features,
    )

    lr = LogisticRegression(
        C=C, penalty="l1", solver="liblinear",
        max_iter=2000, random_state=42,
    )
    lr.fit(X, y)

    coef_abs = np.abs(lr.coef_[0])
    nonzero = coef_abs > 0

    passed = [f for f, nz in zip(features, nonzero) if nz]

    print(f"  L1 filter (C={C}): {len(features)} → {len(passed)} features (non-zero coeff)")

    return passed


# ═════════════════════════════════════════════════════════════════════════
# CORRELATION FILTER
# ═════════════════════════════════════════════════════════════════════════

def correlation_filter(df, features, y=None, max_corr=0.95):
    """Remove one of each pair of highly correlated features."""
    corr_matrix = df[features].corr().abs()

    # If target is provided, keep the feature with higher IV
    to_remove = set()
    for i in range(len(features)):
        if features[i] in to_remove:
            continue
        for j in range(i + 1, len(features)):
            if features[j] in to_remove:
                continue
            if corr_matrix.iloc[i, j] > max_corr:
                # Remove the one with lower variance as proxy
                var_i = df[features[i]].var()
                var_j = df[features[j]].var()
                remove = features[j] if var_i >= var_j else features[i]
                to_remove.add(remove)

    passed = [f for f in features if f not in to_remove]

    print(f"  Correlation filter (|r| < {max_corr}): {len(features)} → {len(passed)} features")
    if to_remove:
        print(f"  Removed: {sorted(to_remove)}")

    return passed


# ═════════════════════════════════════════════════════════════════════════
# TEMPORAL STABILITY FILTER
# ═════════════════════════════════════════════════════════════════════════

def stability_filter(df, features, safra_col="SAFRA", max_psi=0.20):
    """Remove features with PSI > threshold between SAFRAs."""
    safras = sorted(df[safra_col].unique())
    if len(safras) < 2:
        print("  [SKIP] Need >= 2 SAFRAs for stability filter")
        return features

    reference_safra = safras[0]
    ref_data = df[df[safra_col] == reference_safra]

    unstable = set()
    for feat in features:
        if feat not in df.columns:
            continue
        ref_vals = ref_data[feat].dropna().values
        if len(ref_vals) < 100:
            continue

        for safra in safras[1:]:
            curr_vals = df[df[safra_col] == safra][feat].dropna().values
            if len(curr_vals) < 100:
                continue
            psi = compute_psi(ref_vals, curr_vals)
            if psi > max_psi:
                unstable.add(feat)
                print(f"    UNSTABLE: {feat} PSI={psi:.4f} (SAFRA {reference_safra} vs {safra})")
                break

    passed = [f for f in features if f not in unstable]

    print(f"  Stability filter (PSI < {max_psi}): {len(features)} → {len(passed)} features")

    return passed


# ═════════════════════════════════════════════════════════════════════════
# ANTI-LEAKAGE VALIDATION
# ═════════════════════════════════════════════════════════════════════════

# Features that should NEVER be in the model (leakage risk)
LEAKAGE_BLACKLIST = [
    "NUM_CPF", "SAFRA", "FPD",
    "TARGET_SCORE_01", "TARGET_SCORE_02",  # Keep — these are bureau scores available at origination
    "_execution_id", "_data_inclusao", "_data_alteracao_silver",
    "DT_PROCESSAMENTO",
]

# Only block true leakage features (identifiers and target)
TRUE_LEAKAGE = ["NUM_CPF", "SAFRA", "FPD", "_execution_id", "_data_inclusao",
                "_data_alteracao_silver", "DT_PROCESSAMENTO"]


def anti_leakage_check(features):
    """Verify no leakage features made it through selection."""
    leaked = [f for f in features if f in TRUE_LEAKAGE]
    if leaked:
        print(f"  LEAKAGE DETECTED: {leaked}")
        features = [f for f in features if f not in TRUE_LEAKAGE]
    else:
        print(f"  Anti-leakage check: PASSED (0 leaked features)")
    return features


# ═════════════════════════════════════════════════════════════════════════
# FULL SELECTION PIPELINE
# ═════════════════════════════════════════════════════════════════════════

def run_feature_selection(df_train, y_train, all_candidate_features,
                          df_full=None, min_iv=0.02, max_corr=0.95, max_psi=0.20):
    """Run the full feature selection pipeline.

    Args:
        df_train: Training DataFrame
        y_train: Target series
        all_candidate_features: List of all candidate feature names
        df_full: Full DataFrame with all SAFRAs (for stability filter)
        min_iv: Minimum IV threshold
        max_corr: Maximum correlation threshold
        max_psi: Maximum PSI threshold

    Returns: (selected_features, selection_report)
    """
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 70)
    print("FEATURE SELECTION PIPELINE v2")
    print(f"Run ID: {run_id}")
    print(f"Candidates: {len(all_candidate_features)}")
    print("=" * 70)

    # Ensure all features exist
    available = [f for f in all_candidate_features if f in df_train.columns]
    print(f"\n  Available in DataFrame: {len(available)} / {len(all_candidate_features)}")

    report = {
        "run_id": run_id,
        "total_candidates": len(all_candidate_features),
        "available": len(available),
        "stages": {},
    }

    # Stage 1: IV filter
    print(f"\n{'─' * 50}")
    print("Stage 1: Information Value")
    print(f"{'─' * 50}")
    passed_iv, iv_df = iv_filter(df_train, y_train, available, min_iv)
    report["stages"]["iv"] = {"in": len(available), "out": len(passed_iv)}

    # Stage 2: L1 filter
    print(f"\n{'─' * 50}")
    print("Stage 2: L1 Regularization")
    print(f"{'─' * 50}")
    passed_l1 = l1_filter(df_train, y_train, passed_iv)
    report["stages"]["l1"] = {"in": len(passed_iv), "out": len(passed_l1)}

    # Stage 3: Correlation filter
    print(f"\n{'─' * 50}")
    print("Stage 3: Correlation Filter")
    print(f"{'─' * 50}")
    passed_corr = correlation_filter(df_train, passed_l1, max_corr=max_corr)
    report["stages"]["correlation"] = {"in": len(passed_l1), "out": len(passed_corr)}

    # Stage 4: Stability filter (if full data available)
    if df_full is not None and "SAFRA" in df_full.columns:
        print(f"\n{'─' * 50}")
        print("Stage 4: Temporal Stability")
        print(f"{'─' * 50}")
        passed_stable = stability_filter(df_full, passed_corr, max_psi=max_psi)
        report["stages"]["stability"] = {"in": len(passed_corr), "out": len(passed_stable)}
    else:
        passed_stable = passed_corr
        print("\n  [SKIP] Stage 4: No full data for stability filter")

    # Stage 5: Anti-leakage
    print(f"\n{'─' * 50}")
    print("Stage 5: Anti-Leakage Validation")
    print(f"{'─' * 50}")
    selected = anti_leakage_check(passed_stable)
    report["stages"]["anti_leakage"] = {"in": len(passed_stable), "out": len(selected)}

    # Final report
    report["selected_features"] = selected
    report["n_selected"] = len(selected)
    report["iv_ranking"] = iv_df.to_dict("records") if iv_df is not None else []

    print(f"\n{'=' * 70}")
    print(f"SELECTED: {len(selected)} features")
    print(f"{'=' * 70}")
    for i, feat in enumerate(selected):
        iv_val = iv_df[iv_df["feature"] == feat]["iv"].values
        iv_str = f"IV={iv_val[0]:.4f}" if len(iv_val) > 0 else "IV=N/A"
        print(f"  {i+1:3d}. {feat:50s} {iv_str}")

    # Save artifacts
    selection_dir = os.path.join(ARTIFACT_DIR, "feature_selection_v2")
    os.makedirs(selection_dir, exist_ok=True)

    with open(os.path.join(selection_dir, f"selected_features_{run_id}.json"), "w") as f:
        json.dump(report, f, indent=2, default=str)

    with open(os.path.join(selection_dir, f"selected_features_{run_id}.pkl"), "wb") as fh:
        pickle.dump(selected, fh)

    if iv_df is not None:
        iv_df.to_csv(os.path.join(selection_dir, f"iv_ranking_{run_id}.csv"), index=False)

    print(f"\n[SAVE] Selection artifacts saved to {selection_dir}/")

    return selected, report


if __name__ == "__main__":
    print("Feature Selection v2 — use run_feature_selection(df_train, y_train, features)")
