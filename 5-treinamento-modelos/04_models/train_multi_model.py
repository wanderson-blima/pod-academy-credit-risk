"""
Multi-Model Training — Phase 4.1
Trains 5 diverse models with optimized hyperparameters and expanded features.

Models: LightGBM v2, XGBoost, CatBoost, Random Forest, LR L1 v2

Usage: Run in OCI Data Science notebook after HPO and Feature Engineering.
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

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.metrics import roc_auc_score
from scipy.stats import ks_2samp
import lightgbm as lgb

try:
    from xgboost import XGBClassifier
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

try:
    from catboost import CatBoostClassifier
    CATBOOST_AVAILABLE = True
except ImportError:
    CATBOOST_AVAILABLE = False

try:
    from category_encoders import CountEncoder
except ImportError:
    from category_encoders.count import CountEncoder

ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", "/home/datascience/artifacts")
MODELS_DIR = os.path.join(ARTIFACT_DIR, "models_v2")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "oci", "model"))
from train_credit_risk import (
    TARGET, CAT_FEATURES, TRAIN_SAFRAS, OOS_SAFRA, OOT_SAFRAS,
    LOCAL_DATA_PATH, GOLD_PATH,
    compute_ks, compute_gini, compute_psi, evaluate_model,
)

# HPO directory for loading best params
HPO_DIR = os.path.join(ARTIFACT_DIR, "hpo")


def load_best_params(model_name):
    """Load best HPO params for a model, or return defaults."""
    defaults = {
        "LightGBM": {
            "objective": "binary", "n_estimators": 500, "learning_rate": 0.03,
            "max_depth": 6, "num_leaves": 63, "min_child_samples": 50,
            "reg_alpha": 0.1, "reg_lambda": 1.0,
            "colsample_bytree": 0.7, "subsample": 0.8, "subsample_freq": 3,
            "n_jobs": NCPUS, "num_threads": NCPUS, "random_state": 42, "verbosity": -1,
        },
        "XGBoost": {
            "objective": "binary:logistic", "n_estimators": 500, "learning_rate": 0.03,
            "max_depth": 6, "min_child_weight": 5, "gamma": 0.01,
            "reg_alpha": 0.1, "reg_lambda": 1.0,
            "colsample_bytree": 0.7, "subsample": 0.8,
            "n_jobs": NCPUS, "random_state": 42, "verbosity": 0,
            "eval_metric": "auc", "use_label_encoder": False,
        },
        "CatBoost": {
            "iterations": 500, "learning_rate": 0.03, "depth": 6,
            "l2_leaf_reg": 3.0, "border_count": 128,
            "bagging_temperature": 1.0,
            "random_seed": 42, "verbose": 0, "thread_count": NCPUS,
            "eval_metric": "AUC", "auto_class_weights": "Balanced",
        },
        "RandomForest": {
            "n_estimators": 500, "max_depth": 12, "min_samples_leaf": 50,
            "max_features": "sqrt", "class_weight": "balanced",
            "n_jobs": NCPUS, "random_state": 42,
        },
        "LR_L1": {
            "C": 0.5, "penalty": "l1", "solver": "liblinear",
            "max_iter": 2000, "tol": 0.001,
            "class_weight": "balanced", "random_state": 42,
        },
    }

    # Try loading HPO results
    hpo_map = {"LightGBM": "hpo_lgbm_", "XGBoost": "hpo_xgboost_", "CatBoost": "hpo_catboost_"}
    prefix = hpo_map.get(model_name)

    if prefix and os.path.exists(HPO_DIR):
        hpo_files = sorted([
            f for f in os.listdir(HPO_DIR)
            if f.startswith(prefix) and f.endswith(".json")
        ])
        if hpo_files:
            with open(os.path.join(HPO_DIR, hpo_files[-1])) as f:
                hpo_data = json.load(f)
            best_params = hpo_data.get("best_params", {})
            if best_params:
                merged = {**defaults.get(model_name, {}), **best_params}
                print(f"  [HPO] Loaded optimized params for {model_name}")
                return merged

    print(f"  [DEFAULT] Using default params for {model_name}")
    return defaults.get(model_name, {})


def build_preprocessor(num_features, cat_features, use_scaler=False):
    """Build preprocessing pipeline."""
    if use_scaler:
        num_pipe = Pipeline(steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ])
    else:
        num_pipe = Pipeline(steps=[
            ("imputer", SimpleImputer(strategy="median")),
        ])

    transformers = [("num", num_pipe, num_features)]

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


def train_all_models(df, features, run_id=None):
    """Train all 5 models and return pipelines + metrics."""
    if run_id is None:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 70)
    print("MULTI-MODEL TRAINING — Phase 4")
    print(f"Run ID: {run_id} | Features: {len(features)}")
    print("=" * 70)

    cat_feats = [f for f in features if f in CAT_FEATURES]
    num_feats = [f for f in features if f not in cat_feats]

    # Temporal split
    df_train = df[df["SAFRA"].isin(TRAIN_SAFRAS) & df[TARGET].notna()].copy()
    df_oos = df[df["SAFRA"].isin(OOS_SAFRA) & df[TARGET].notna()].copy()
    df_oot = df[df["SAFRA"].isin(OOT_SAFRAS) & df[TARGET].notna()].copy()

    X_train, y_train = df_train[features], df_train[TARGET].astype(int)
    X_oos, y_oos = df_oos[features], df_oos[TARGET].astype(int)
    X_oot, y_oot = df_oot[features], df_oot[TARGET].astype(int)

    print(f"\n[DATA] Train: {len(X_train):,} | OOS: {len(X_oos):,} | OOT: {len(X_oot):,}")

    results = {}
    pipelines = {}

    # ── Model 1: LightGBM v2 ───────────────────────────────────────────────
    print(f"\n{'─' * 70}")
    print("MODEL 1: LightGBM v2 (HPO optimized)")
    print(f"{'─' * 70}")

    params = load_best_params("LightGBM")
    prep = build_preprocessor(num_feats, cat_feats)
    pipeline = Pipeline([("prep", prep), ("model", lgb.LGBMClassifier(**params))])

    t0 = time.time()
    pipeline.fit(X_train, y_train)
    train_time = time.time() - t0

    metrics = {
        **evaluate_model(pipeline, X_train, y_train, "train"),
        **evaluate_model(pipeline, X_oos, y_oos, "oos"),
        **evaluate_model(pipeline, X_oot, y_oot, "oot"),
        "train_time": round(train_time, 1),
    }
    results["LightGBM_v2"] = metrics
    pipelines["LightGBM_v2"] = pipeline
    print(f"  KS: Train={metrics['ks_train']:.4f} OOS={metrics['ks_oos']:.4f} OOT={metrics['ks_oot']:.4f} ({train_time:.1f}s)")

    # ── Model 2: XGBoost ────────────────────────────────────────────────────
    if XGB_AVAILABLE:
        print(f"\n{'─' * 70}")
        print("MODEL 2: XGBoost")
        print(f"{'─' * 70}")

        params = load_best_params("XGBoost")
        prep = build_preprocessor(num_feats, cat_feats)
        pipeline = Pipeline([("prep", prep), ("model", XGBClassifier(**params))])

        t0 = time.time()
        pipeline.fit(X_train, y_train)
        train_time = time.time() - t0

        metrics = {
            **evaluate_model(pipeline, X_train, y_train, "train"),
            **evaluate_model(pipeline, X_oos, y_oos, "oos"),
            **evaluate_model(pipeline, X_oot, y_oot, "oot"),
            "train_time": round(train_time, 1),
        }
        results["XGBoost"] = metrics
        pipelines["XGBoost"] = pipeline
        print(f"  KS: Train={metrics['ks_train']:.4f} OOS={metrics['ks_oos']:.4f} OOT={metrics['ks_oot']:.4f} ({train_time:.1f}s)")
    else:
        print("\n  [SKIP] XGBoost not available")

    # ── Model 3: CatBoost ───────────────────────────────────────────────────
    if CATBOOST_AVAILABLE:
        print(f"\n{'─' * 70}")
        print("MODEL 3: CatBoost")
        print(f"{'─' * 70}")

        params = load_best_params("CatBoost")
        # CatBoost with simple imputation (handles categoricals natively)
        prep = build_preprocessor(num_feats, cat_feats)
        pipeline = Pipeline([("prep", prep), ("model", CatBoostClassifier(**params))])

        t0 = time.time()
        pipeline.fit(X_train, y_train)
        train_time = time.time() - t0

        metrics = {
            **evaluate_model(pipeline, X_train, y_train, "train"),
            **evaluate_model(pipeline, X_oos, y_oos, "oos"),
            **evaluate_model(pipeline, X_oot, y_oot, "oot"),
            "train_time": round(train_time, 1),
        }
        results["CatBoost"] = metrics
        pipelines["CatBoost"] = pipeline
        print(f"  KS: Train={metrics['ks_train']:.4f} OOS={metrics['ks_oos']:.4f} OOT={metrics['ks_oot']:.4f} ({train_time:.1f}s)")
    else:
        print("\n  [SKIP] CatBoost not available")

    # ── Model 4: Random Forest ──────────────────────────────────────────────
    print(f"\n{'─' * 70}")
    print("MODEL 4: Random Forest")
    print(f"{'─' * 70}")

    params = load_best_params("RandomForest")
    prep = build_preprocessor(num_feats, cat_feats)
    pipeline = Pipeline([("prep", prep), ("model", RandomForestClassifier(**params))])

    t0 = time.time()
    pipeline.fit(X_train, y_train)
    train_time = time.time() - t0

    metrics = {
        **evaluate_model(pipeline, X_train, y_train, "train"),
        **evaluate_model(pipeline, X_oos, y_oos, "oos"),
        **evaluate_model(pipeline, X_oot, y_oot, "oot"),
        "train_time": round(train_time, 1),
    }
    results["RandomForest"] = metrics
    pipelines["RandomForest"] = pipeline
    print(f"  KS: Train={metrics['ks_train']:.4f} OOS={metrics['ks_oos']:.4f} OOT={metrics['ks_oot']:.4f} ({train_time:.1f}s)")

    # ── Model 5: LR L1 v2 ──────────────────────────────────────────────────
    print(f"\n{'─' * 70}")
    print("MODEL 5: LR L1 v2 (with expanded features)")
    print(f"{'─' * 70}")

    params = load_best_params("LR_L1")
    prep = build_preprocessor(num_feats, cat_feats, use_scaler=True)
    pipeline = Pipeline([("prep", prep), ("model", LogisticRegression(**params))])

    t0 = time.time()
    pipeline.fit(X_train, y_train)
    train_time = time.time() - t0

    metrics = {
        **evaluate_model(pipeline, X_train, y_train, "train"),
        **evaluate_model(pipeline, X_oos, y_oos, "oos"),
        **evaluate_model(pipeline, X_oot, y_oot, "oot"),
        "train_time": round(train_time, 1),
    }
    results["LR_L1_v2"] = metrics
    pipelines["LR_L1_v2"] = pipeline
    print(f"  KS: Train={metrics['ks_train']:.4f} OOS={metrics['ks_oos']:.4f} OOT={metrics['ks_oot']:.4f} ({train_time:.1f}s)")

    # ── PSI for all models ──────────────────────────────────────────────────
    print(f"\n{'─' * 70}")
    print("PSI ANALYSIS")
    print(f"{'─' * 70}")

    for name, pipe in pipelines.items():
        train_scores = pipe.predict_proba(X_train)[:, 1]
        oot_scores = pipe.predict_proba(X_oot)[:, 1]
        psi = compute_psi(train_scores, oot_scores)
        results[name]["psi"] = psi
        status = "STABLE" if psi < 0.10 else ("WARNING" if psi < 0.25 else "RETRAIN")
        print(f"  {name}: PSI={psi:.6f} [{status}]")

    # ── Save artifacts ──────────────────────────────────────────────────────
    os.makedirs(MODELS_DIR, exist_ok=True)

    for name, pipe in pipelines.items():
        with open(os.path.join(MODELS_DIR, f"{name}_{run_id}.pkl"), "wb") as f:
            pickle.dump(pipe, f)

    training_results = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "n_features": len(features),
        "features": features,
        "cat_features": cat_feats,
        "models": results,
    }

    with open(os.path.join(MODELS_DIR, f"multi_model_results_{run_id}.json"), "w") as f:
        json.dump(training_results, f, indent=2, default=str)

    # Summary table
    print(f"\n{'=' * 70}")
    print("MULTI-MODEL COMPARISON")
    print(f"{'=' * 70}")

    comp = []
    for name, m in results.items():
        comp.append({
            "Model": name,
            "KS_Train": m.get("ks_train", 0),
            "KS_OOS": m.get("ks_oos", 0),
            "KS_OOT": m.get("ks_oot", 0),
            "AUC_OOT": m.get("auc_oot", 0),
            "Gini_OOT": m.get("gini_oot", 0),
            "PSI": m.get("psi", 0),
            "Time_s": m.get("train_time", 0),
        })
    print(pd.DataFrame(comp).to_string(index=False))

    print(f"\n[SAVE] Models and results saved to {MODELS_DIR}/")

    return pipelines, results


if __name__ == "__main__":
    print("Multi-Model Training — run train_all_models(df, features)")
