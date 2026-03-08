"""
LR Scorecard v2 — Phase 6.5
Updated L1 Logistic Regression scorecard with WoE features.
Regulatory requirement: interpretable scoring model.

Usage: Run after feature engineering (Phase 2).
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
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.metrics import roc_auc_score
from scipy.stats import ks_2samp

ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", "/home/datascience/artifacts")
SCORECARD_DIR = os.path.join(ARTIFACT_DIR, "scorecard_v2")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "oci", "model"))
from train_credit_risk import (
    TARGET, TRAIN_SAFRAS, OOS_SAFRA, OOT_SAFRAS,
    compute_ks, compute_gini,
)


def compute_woe_iv(df, feature, target, n_bins=10):
    """Compute WoE and IV for a single feature."""
    vals = df[feature].fillna(df[feature].median())
    y = df[target]

    try:
        bins = pd.qcut(vals, q=n_bins, labels=False, duplicates="drop")
    except ValueError:
        return None, None, 0.0

    total_events = y.sum()
    total_non_events = len(y) - total_events

    if total_events == 0 or total_non_events == 0:
        return None, None, 0.0

    woe_table = []
    iv_total = 0.0

    for bin_id in sorted(bins.unique()):
        mask = bins == bin_id
        events = y[mask].sum()
        non_events = mask.sum() - events

        events_pct = (events + 0.5) / (total_events + 1)
        non_events_pct = (non_events + 0.5) / (total_non_events + 1)

        woe = np.log(non_events_pct / events_pct)
        iv_bin = (non_events_pct - events_pct) * woe
        iv_total += iv_bin

        bin_min = vals[mask].min()
        bin_max = vals[mask].max()

        woe_table.append({
            "bin": int(bin_id),
            "bin_min": round(float(bin_min), 4),
            "bin_max": round(float(bin_max), 4),
            "count": int(mask.sum()),
            "events": int(events),
            "event_rate": round(float(events / mask.sum()), 4),
            "woe": round(float(woe), 6),
            "iv": round(float(iv_bin), 6),
        })

    return pd.DataFrame(woe_table), woe, round(iv_total, 6)


def build_scorecard(pipeline, features, base_score=600, pdo=50):
    """Generate scorecard points from fitted LR pipeline.

    Args:
        pipeline: fitted Pipeline with StandardScaler + LogisticRegression
        features: feature names
        base_score: score at odds 1:1
        pdo: points to double the odds

    Returns: DataFrame with feature points
    """
    model = pipeline.named_steps["model"]
    scaler = pipeline.named_steps["prep"]

    intercept = model.intercept_[0]
    coefs = model.coef_[0]

    # Factor and offset for scorecard
    factor = pdo / np.log(2)
    offset = base_score - factor * np.log(1)  # odds at base_score

    scorecard_rows = []
    for i, (feat, coef) in enumerate(zip(features, coefs)):
        if abs(coef) < 1e-6:
            continue
        points = -coef * factor
        scorecard_rows.append({
            "feature": feat,
            "coefficient": round(float(coef), 6),
            "points": round(float(points), 2),
            "direction": "protective" if coef < 0 else "risk",
        })

    scorecard_df = pd.DataFrame(scorecard_rows)
    scorecard_df = scorecard_df.sort_values("points", ascending=True)

    print(f"\n  Scorecard (base={base_score}, PDO={pdo}):")
    print(f"  Intercept: {intercept:.6f}")
    print(f"  Non-zero features: {len(scorecard_df)}/{len(features)}")
    print(scorecard_df.to_string(index=False))

    return scorecard_df


def train_lr_scorecard_v2(df, features, woe_features=None):
    """Train LR v2 scorecard with WoE features."""
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 70)
    print("LR SCORECARD v2 (Regulatory Interpretable Model)")
    print(f"Run ID: {run_id}")
    print("=" * 70)

    # Use WoE features if available, otherwise use raw features
    use_features = woe_features if woe_features else features
    use_features = [f for f in use_features if f in df.columns]

    df_train = df[df["SAFRA"].isin(TRAIN_SAFRAS) & df[TARGET].notna()].copy()
    df_oos = df[df["SAFRA"].isin(OOS_SAFRA) & df[TARGET].notna()].copy()
    df_oot = df[df["SAFRA"].isin(OOT_SAFRAS) & df[TARGET].notna()].copy()

    X_train, y_train = df_train[use_features], df_train[TARGET].astype(int)
    X_oos, y_oos = df_oos[use_features], df_oos[TARGET].astype(int)
    X_oot, y_oot = df_oot[use_features], df_oot[TARGET].astype(int)

    # Build pipeline
    pipeline = Pipeline([
        ("prep", Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ])),
        ("model", LogisticRegression(
            C=0.5, penalty="l1", solver="liblinear",
            max_iter=2000, tol=0.001,
            class_weight="balanced", random_state=42,
        )),
    ])

    pipeline.fit(X_train, y_train)

    # Evaluate
    for label, X, y in [("Train", X_train, y_train), ("OOS", X_oos, y_oos), ("OOT", X_oot, y_oot)]:
        y_prob = pipeline.predict_proba(X)[:, 1]
        ks = compute_ks(y.values, y_prob)
        auc = roc_auc_score(y, y_prob)
        print(f"  {label}: KS={ks:.4f} AUC={auc:.4f} Gini={compute_gini(auc):.2f}")

    # Generate scorecard
    print(f"\n{'─' * 50}")
    print("SCORECARD")
    print(f"{'─' * 50}")

    scorecard = build_scorecard(pipeline, use_features)

    # Save
    os.makedirs(SCORECARD_DIR, exist_ok=True)

    with open(os.path.join(SCORECARD_DIR, f"lr_scorecard_v2_{run_id}.pkl"), "wb") as f:
        pickle.dump(pipeline, f)

    scorecard.to_csv(os.path.join(SCORECARD_DIR, f"scorecard_points_{run_id}.csv"), index=False)

    report = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "n_features": len(use_features),
        "n_nonzero": len(scorecard),
        "features": use_features,
    }

    with open(os.path.join(SCORECARD_DIR, f"scorecard_report_{run_id}.json"), "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\n[SAVE] Scorecard saved to {SCORECARD_DIR}/")
    return pipeline, scorecard


if __name__ == "__main__":
    print("LR Scorecard v2 — run train_lr_scorecard_v2(df, features)")
