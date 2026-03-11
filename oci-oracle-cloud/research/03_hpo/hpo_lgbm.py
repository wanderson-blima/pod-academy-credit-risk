"""
LightGBM Hyperparameter Optimization — Phase 3.2
Optuna TPE sampler with temporal CV and early stopping.

Usage: Run in OCI Data Science notebook.
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

import lightgbm as lgb
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer

try:
    import optuna
    from optuna.pruners import MedianPruner
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False
    print("[WARN] optuna not installed — pip install optuna")

try:
    from category_encoders import CountEncoder
except ImportError:
    from category_encoders.count import CountEncoder

ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", "/home/datascience/artifacts")
HPO_DIR = os.path.join(ARTIFACT_DIR, "hpo")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from temporal_cv import TemporalCV, compute_ks

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "oci", "model"))
from train_credit_risk import (
    TARGET, CAT_FEATURES, LOCAL_DATA_PATH, GOLD_PATH,
)


def build_lgbm_params(trial):
    """Build LightGBM parameter space for Optuna."""
    return {
        "objective": "binary",
        "n_estimators": trial.suggest_int("n_estimators", 100, 1000, step=50),
        "learning_rate": trial.suggest_float("learning_rate", 0.005, 0.3, log=True),
        "max_depth": trial.suggest_int("max_depth", 3, 8),
        "num_leaves": trial.suggest_int("num_leaves", 15, 127),
        "min_child_samples": trial.suggest_int("min_child_samples", 20, 200),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.4, 1.0),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "subsample_freq": trial.suggest_int("subsample_freq", 1, 7),
        "scale_pos_weight": trial.suggest_float("scale_pos_weight", 1.0, 5.0),
        "n_jobs": NCPUS,
        "num_threads": NCPUS,
        "random_state": 42,
        "verbosity": -1,
    }


def build_preprocessor(num_features, cat_features):
    """Build preprocessing pipeline matching existing pattern."""
    transformers = [
        ("num", Pipeline(steps=[
            ("imputer", SimpleImputer(strategy="median")),
        ]), num_features),
    ]
    if cat_features:
        transformers.append(
            ("cat", Pipeline(steps=[
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("encoder", CountEncoder(
                    combine_min_nan_groups=True,
                    normalize=True,
                    handle_missing=0,
                    handle_unknown=0,
                )),
            ]), cat_features),
        )
    return ColumnTransformer(transformers=transformers)


def run_hpo_lgbm(df, features, n_trials=200):
    """Run LightGBM HPO with Optuna."""
    if not OPTUNA_AVAILABLE:
        print("[ERROR] optuna required — pip install optuna")
        return None

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 70)
    print("HPO: LightGBM (Optuna TPE)")
    print(f"Run ID: {run_id} | Trials: {n_trials}")
    print("=" * 70)

    # Separate feature types
    cat_feats = [f for f in features if f in CAT_FEATURES]
    num_feats = [f for f in features if f not in cat_feats]

    # Build preprocessor
    preprocessor = build_preprocessor(num_feats, cat_feats)

    # Temporal CV
    tcv = TemporalCV()

    # Filter to train SAFRAs only (OOT is holdout)
    df_train = df[df["SAFRA"].isin(tcv.train_safras) & df[TARGET].notna()].copy()
    df_train = df_train.reset_index(drop=True)

    # Fit preprocessor on all training data
    preprocessor.fit(df_train[features])

    def objective(trial):
        params = build_lgbm_params(trial)

        fold_ks = []
        for fold_idx, train_idx, val_idx, fold_info in tcv.get_folds(df_train):
            X_train = preprocessor.transform(df_train.loc[train_idx, features])
            y_train = df_train.loc[train_idx, TARGET].astype(int)
            X_val = preprocessor.transform(df_train.loc[val_idx, features])
            y_val = df_train.loc[val_idx, TARGET].astype(int)

            model = lgb.LGBMClassifier(**params)
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                callbacks=[lgb.early_stopping(50, verbose=False)],
            )

            y_prob = model.predict_proba(X_val)[:, 1]
            ks = compute_ks(y_val.values, y_prob)
            fold_ks.append(ks)

            # Pruning
            trial.report(np.mean(fold_ks), fold_idx)
            if trial.should_prune():
                raise optuna.TrialPruned()

        return np.mean(fold_ks)

    study = optuna.create_study(
        direction="maximize",
        study_name=f"lgbm_hpo_{run_id}",
        pruner=MedianPruner(n_startup_trials=10, n_warmup_steps=1),
    )

    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

    # Results
    best = study.best_trial
    print(f"\n{'=' * 70}")
    print(f"BEST TRIAL: #{best.number}")
    print(f"  Mean KS (CV): {best.value:.5f}")
    print(f"  Parameters:")
    for k, v in best.params.items():
        print(f"    {k}: {v}")
    print(f"{'=' * 70}")

    # Save
    os.makedirs(HPO_DIR, exist_ok=True)

    results = {
        "run_id": run_id,
        "model": "LightGBM",
        "n_trials": n_trials,
        "best_trial": best.number,
        "best_ks_cv": round(best.value, 5),
        "best_params": best.params,
        "n_features": len(features),
        "features": features,
    }

    with open(os.path.join(HPO_DIR, f"hpo_lgbm_{run_id}.json"), "w") as f:
        json.dump(results, f, indent=2, default=str)

    with open(os.path.join(HPO_DIR, f"hpo_lgbm_study_{run_id}.pkl"), "wb") as f:
        pickle.dump(study, f)

    print(f"[SAVE] HPO results saved to {HPO_DIR}/")

    return results, study


if __name__ == "__main__":
    print("LightGBM HPO — run run_hpo_lgbm(df, features, n_trials=200)")
