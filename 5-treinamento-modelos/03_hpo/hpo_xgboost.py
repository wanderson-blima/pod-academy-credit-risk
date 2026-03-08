"""
XGBoost Hyperparameter Optimization — Phase 3.3
Optuna TPE sampler with temporal CV.

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

try:
    from xgboost import XGBClassifier
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False
    print("[WARN] xgboost not installed — pip install xgboost")

try:
    import optuna
    from optuna.pruners import MedianPruner
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False

from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer

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
from train_credit_risk import TARGET, CAT_FEATURES


def build_xgb_params(trial):
    """Build XGBoost parameter space for Optuna."""
    return {
        "objective": "binary:logistic",
        "n_estimators": trial.suggest_int("n_estimators", 100, 1000, step=50),
        "learning_rate": trial.suggest_float("learning_rate", 0.005, 0.3, log=True),
        "max_depth": trial.suggest_int("max_depth", 3, 8),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 20),
        "gamma": trial.suggest_float("gamma", 1e-8, 1.0, log=True),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.4, 1.0),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "scale_pos_weight": trial.suggest_float("scale_pos_weight", 1.0, 5.0),
        "n_jobs": NCPUS,
        "random_state": 42,
        "verbosity": 0,
        "eval_metric": "auc",
        "use_label_encoder": False,
    }


def build_preprocessor(num_features, cat_features):
    """Build preprocessing pipeline."""
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


def run_hpo_xgboost(df, features, n_trials=200):
    """Run XGBoost HPO with Optuna."""
    if not XGB_AVAILABLE:
        print("[ERROR] xgboost required — pip install xgboost")
        return None
    if not OPTUNA_AVAILABLE:
        print("[ERROR] optuna required — pip install optuna")
        return None

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 70)
    print("HPO: XGBoost (Optuna TPE)")
    print(f"Run ID: {run_id} | Trials: {n_trials}")
    print("=" * 70)

    cat_feats = [f for f in features if f in CAT_FEATURES]
    num_feats = [f for f in features if f not in cat_feats]

    preprocessor = build_preprocessor(num_feats, cat_feats)

    tcv = TemporalCV()
    df_train = df[df["SAFRA"].isin(tcv.train_safras) & df[TARGET].notna()].copy()
    df_train = df_train.reset_index(drop=True)

    preprocessor.fit(df_train[features])

    def objective(trial):
        params = build_xgb_params(trial)

        fold_ks = []
        for fold_idx, train_idx, val_idx, fold_info in tcv.get_folds(df_train):
            X_train = preprocessor.transform(df_train.loc[train_idx, features])
            y_train = df_train.loc[train_idx, TARGET].astype(int)
            X_val = preprocessor.transform(df_train.loc[val_idx, features])
            y_val = df_train.loc[val_idx, TARGET].astype(int)

            model = XGBClassifier(**params)
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                verbose=False,
            )

            y_prob = model.predict_proba(X_val)[:, 1]
            ks = compute_ks(y_val.values, y_prob)
            fold_ks.append(ks)

            trial.report(np.mean(fold_ks), fold_idx)
            if trial.should_prune():
                raise optuna.TrialPruned()

        return np.mean(fold_ks)

    study = optuna.create_study(
        direction="maximize",
        study_name=f"xgboost_hpo_{run_id}",
        pruner=MedianPruner(n_startup_trials=10, n_warmup_steps=1),
    )

    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

    best = study.best_trial
    print(f"\n{'=' * 70}")
    print(f"BEST TRIAL: #{best.number}")
    print(f"  Mean KS (CV): {best.value:.5f}")
    print(f"  Parameters:")
    for k, v in best.params.items():
        print(f"    {k}: {v}")

    os.makedirs(HPO_DIR, exist_ok=True)

    results = {
        "run_id": run_id,
        "model": "XGBoost",
        "n_trials": n_trials,
        "best_trial": best.number,
        "best_ks_cv": round(best.value, 5),
        "best_params": best.params,
        "n_features": len(features),
    }

    with open(os.path.join(HPO_DIR, f"hpo_xgboost_{run_id}.json"), "w") as f:
        json.dump(results, f, indent=2, default=str)

    with open(os.path.join(HPO_DIR, f"hpo_xgboost_study_{run_id}.pkl"), "wb") as f:
        pickle.dump(study, f)

    print(f"[SAVE] HPO results saved to {HPO_DIR}/")
    return results, study


if __name__ == "__main__":
    print("XGBoost HPO — run run_hpo_xgboost(df, features, n_trials=200)")
