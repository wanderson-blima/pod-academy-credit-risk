"""
CatBoost Hyperparameter Optimization — Phase 3.4
Optuna TPE sampler with temporal CV. Native categorical support.

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

try:
    from catboost import CatBoostClassifier, Pool
    CATBOOST_AVAILABLE = True
except ImportError:
    CATBOOST_AVAILABLE = False
    print("[WARN] catboost not installed — pip install catboost")

try:
    import optuna
    from optuna.pruners import MedianPruner
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False

from sklearn.impute import SimpleImputer

ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", "/home/datascience/artifacts")
HPO_DIR = os.path.join(ARTIFACT_DIR, "hpo")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from temporal_cv import TemporalCV, compute_ks

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "oci", "model"))
from train_credit_risk import TARGET, CAT_FEATURES


def build_catboost_params(trial):
    """Build CatBoost parameter space for Optuna."""
    return {
        "iterations": trial.suggest_int("iterations", 100, 1000, step=50),
        "learning_rate": trial.suggest_float("learning_rate", 0.005, 0.3, log=True),
        "depth": trial.suggest_int("depth", 3, 8),
        "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 1e-3, 10.0, log=True),
        "border_count": trial.suggest_int("border_count", 32, 255),
        "bagging_temperature": trial.suggest_float("bagging_temperature", 0.0, 5.0),
        "random_strength": trial.suggest_float("random_strength", 1e-8, 10.0, log=True),
        "min_data_in_leaf": trial.suggest_int("min_data_in_leaf", 5, 100),
        "random_seed": 42,
        "verbose": 0,
        "thread_count": NCPUS,
        "eval_metric": "AUC",
        "auto_class_weights": "Balanced",
    }


def run_hpo_catboost(df, features, n_trials=200):
    """Run CatBoost HPO with Optuna."""
    if not CATBOOST_AVAILABLE:
        print("[ERROR] catboost required — pip install catboost")
        return None
    if not OPTUNA_AVAILABLE:
        print("[ERROR] optuna required — pip install optuna")
        return None

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 70)
    print("HPO: CatBoost (Optuna TPE)")
    print(f"Run ID: {run_id} | Trials: {n_trials}")
    print("=" * 70)

    cat_feats = [f for f in features if f in CAT_FEATURES]
    cat_indices = [features.index(f) for f in cat_feats] if cat_feats else []

    tcv = TemporalCV()
    df_train = df[df["SAFRA"].isin(tcv.train_safras) & df[TARGET].notna()].copy()
    df_train = df_train.reset_index(drop=True)

    # Impute missing for numerical, fill categorical
    imputer = SimpleImputer(strategy="median")
    num_feats = [f for f in features if f not in cat_feats]

    if num_feats:
        df_train[num_feats] = imputer.fit_transform(df_train[num_feats])
    for cf in cat_feats:
        df_train[cf] = df_train[cf].fillna("MISSING").astype(str)

    def objective(trial):
        params = build_catboost_params(trial)

        fold_ks = []
        for fold_idx, train_idx, val_idx, fold_info in tcv.get_folds(df_train):
            X_train = df_train.loc[train_idx, features]
            y_train = df_train.loc[train_idx, TARGET].astype(int)
            X_val = df_train.loc[val_idx, features]
            y_val = df_train.loc[val_idx, TARGET].astype(int)

            train_pool = Pool(X_train, y_train, cat_features=cat_indices)
            val_pool = Pool(X_val, y_val, cat_features=cat_indices)

            model = CatBoostClassifier(**params)
            model.fit(
                train_pool,
                eval_set=val_pool,
                early_stopping_rounds=50,
                verbose=0,
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
        study_name=f"catboost_hpo_{run_id}",
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
        "model": "CatBoost",
        "n_trials": n_trials,
        "best_trial": best.number,
        "best_ks_cv": round(best.value, 5),
        "best_params": best.params,
        "n_features": len(features),
        "cat_features": cat_feats,
    }

    with open(os.path.join(HPO_DIR, f"hpo_catboost_{run_id}.json"), "w") as f:
        json.dump(results, f, indent=2, default=str)

    with open(os.path.join(HPO_DIR, f"hpo_catboost_study_{run_id}.pkl"), "wb") as f:
        pickle.dump(study, f)

    print(f"[SAVE] HPO results saved to {HPO_DIR}/")
    return results, study


if __name__ == "__main__":
    print("CatBoost HPO — run run_hpo_catboost(df, features, n_trials=200)")
