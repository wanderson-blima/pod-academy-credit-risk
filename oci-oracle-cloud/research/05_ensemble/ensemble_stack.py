"""
Ensemble Stacking — Phase 5.2
Two-level stacking with out-of-fold predictions and LR meta-learner.

Usage: Run after multi-model training.
"""
import os
import json
import pickle
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from scipy.stats import ks_2samp

ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", "/home/datascience/artifacts")
ENSEMBLE_DIR = os.path.join(ARTIFACT_DIR, "ensemble")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "03_hpo"))
from temporal_cv import TemporalCV, compute_ks

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "oci", "model"))
from train_credit_risk import TARGET, TRAIN_SAFRAS


def generate_oof_predictions(pipelines, df, features, temporal_cv=None):
    """Generate out-of-fold predictions for all base models using temporal CV.

    Returns: DataFrame with OOF predictions for each model + target.
    """
    if temporal_cv is None:
        temporal_cv = TemporalCV()

    model_names = list(pipelines.keys())
    df_train = df[df["SAFRA"].isin(temporal_cv.train_safras) & df[TARGET].notna()].copy()
    df_train = df_train.reset_index(drop=True)

    n = len(df_train)
    oof_preds = {name: np.zeros(n) for name in model_names}
    oof_mask = np.zeros(n, dtype=bool)

    for fold_idx, train_idx, val_idx, fold_info in temporal_cv.get_folds(df_train):
        print(f"  Fold {fold_idx}: Train={fold_info['train_safras']} Val={fold_info['val_safra']}")

        X_train_fold = df_train.loc[train_idx, features]
        y_train_fold = df_train.loc[train_idx, TARGET].astype(int)
        X_val_fold = df_train.loc[val_idx, features]

        for name, pipeline in pipelines.items():
            # Clone pipeline and retrain on fold
            from sklearn.base import clone
            pipe_clone = clone(pipeline)
            pipe_clone.fit(X_train_fold, y_train_fold)
            preds = pipe_clone.predict_proba(X_val_fold)[:, 1]
            oof_preds[name][val_idx] = preds

        oof_mask[val_idx] = True

    # Build OOF DataFrame (only rows that were in validation at some point)
    oof_df = pd.DataFrame(oof_preds)
    oof_df[TARGET] = df_train[TARGET].astype(int)
    oof_df["SAFRA"] = df_train["SAFRA"].values
    oof_df = oof_df[oof_mask]  # Keep only validated rows

    print(f"  OOF predictions: {len(oof_df):,} rows for {len(model_names)} models")

    return oof_df


def train_meta_learner(oof_df, model_names, include_original_features=False,
                        original_features_df=None, top_k_features=5):
    """Train Level-1 meta-learner on OOF predictions.

    Args:
        oof_df: DataFrame with OOF predictions
        model_names: list of base model column names
        include_original_features: whether to include top-K original features
        original_features_df: DataFrame with original features (if including)
        top_k_features: number of original features to include

    Returns: fitted meta-learner, meta-feature names
    """
    meta_features = model_names.copy()

    X_meta = oof_df[model_names].copy()

    if include_original_features and original_features_df is not None:
        top_feats = original_features_df.columns[:top_k_features].tolist()
        for feat in top_feats:
            if feat in original_features_df.columns:
                X_meta[feat] = original_features_df.loc[oof_df.index, feat].values
                meta_features.append(feat)

    y_meta = oof_df[TARGET].astype(int)

    meta_learner = LogisticRegression(
        C=1.0, penalty="l2", solver="lbfgs",
        max_iter=2000, random_state=42,
    )
    meta_learner.fit(X_meta, y_meta)

    # Report weights
    print(f"\n  Meta-learner coefficients:")
    for feat, coef in zip(meta_features, meta_learner.coef_[0]):
        print(f"    {feat:25s}: {coef:.4f}")

    # Evaluate on OOF (in-sample for meta-learner)
    y_prob = meta_learner.predict_proba(X_meta)[:, 1]
    ks = compute_ks(y_meta.values, y_prob)
    auc = roc_auc_score(y_meta, y_prob)
    print(f"  Meta-learner OOF: KS={ks:.5f} AUC={auc:.5f}")

    return meta_learner, meta_features


def evaluate_stacking(pipelines, meta_learner, meta_features, X, y, label=""):
    """Evaluate stacked ensemble on new data."""
    model_names = list(pipelines.keys())

    # Level-0 predictions
    base_preds = {name: pipe.predict_proba(X)[:, 1] for name, pipe in pipelines.items()}
    X_meta = pd.DataFrame(base_preds)[model_names]

    # Add original features if meta_features includes them
    extra_feats = [f for f in meta_features if f not in model_names]
    for feat in extra_feats:
        if feat in X.columns:
            X_meta[feat] = X[feat].values

    y_prob = meta_learner.predict_proba(X_meta[meta_features])[:, 1]
    ks = compute_ks(y.values, y_prob)
    auc = roc_auc_score(y, y_prob)
    gini = (2 * auc - 1) * 100

    print(f"  Stack {label}: KS={ks:.5f} AUC={auc:.5f} Gini={gini:.2f}")

    return {
        f"ks_{label}": round(ks, 5),
        f"auc_{label}": round(auc, 5),
        f"gini_{label}": round(gini, 2),
    }


def run_stacking(pipelines, df, features, X_oos, y_oos, X_oot, y_oot):
    """Full stacking pipeline."""
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 70)
    print("ENSEMBLE: Stacking (2-Level)")
    print(f"Run ID: {run_id} | Base models: {len(pipelines)}")
    print("=" * 70)

    model_names = list(pipelines.keys())

    # 1. Generate OOF predictions
    print(f"\n{'─' * 50}")
    print("1. GENERATING OOF PREDICTIONS")
    print(f"{'─' * 50}")

    oof_df = generate_oof_predictions(pipelines, df, features)

    # 2. Train meta-learner
    print(f"\n{'─' * 50}")
    print("2. TRAINING META-LEARNER")
    print(f"{'─' * 50}")

    meta_learner, meta_features = train_meta_learner(oof_df, model_names)

    # 3. Evaluate on OOS
    print(f"\n{'─' * 50}")
    print("3. STACKING EVALUATION (OOS)")
    print(f"{'─' * 50}")

    oos_metrics = evaluate_stacking(pipelines, meta_learner, meta_features, X_oos, y_oos, "oos")

    # 4. Evaluate on OOT
    print(f"\n{'─' * 50}")
    print("4. STACKING EVALUATION (OOT)")
    print(f"{'─' * 50}")

    oot_metrics = evaluate_stacking(pipelines, meta_learner, meta_features, X_oot, y_oot, "oot")

    # Save
    os.makedirs(ENSEMBLE_DIR, exist_ok=True)

    report = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "n_base_models": len(pipelines),
        "base_models": model_names,
        "meta_features": meta_features,
        "meta_learner_coefs": {
            feat: round(float(coef), 6)
            for feat, coef in zip(meta_features, meta_learner.coef_[0])
        },
        "oos_metrics": oos_metrics,
        "oot_metrics": oot_metrics,
    }

    with open(os.path.join(ENSEMBLE_DIR, f"stack_results_{run_id}.json"), "w") as f:
        json.dump(report, f, indent=2, default=str)

    with open(os.path.join(ENSEMBLE_DIR, f"meta_learner_{run_id}.pkl"), "wb") as f:
        pickle.dump({"meta_learner": meta_learner, "meta_features": meta_features}, f)

    print(f"\n[SAVE] Stacking results saved to {ENSEMBLE_DIR}/")
    return meta_learner, meta_features, report


if __name__ == "__main__":
    print("Ensemble Stacking — run run_stacking(pipelines, df, features, X_oos, y_oos, X_oot, y_oot)")
