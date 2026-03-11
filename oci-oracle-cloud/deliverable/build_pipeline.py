"""
Build Champion Pipeline PKL — Self-contained scoring artifact.

Creates a single champion_pipeline.pkl that encapsulates:
  1. Feature list (110 selected features)
  2. Training medians (computed on SAFRAs 202410-202501)
  3. Champion ensemble model (top 3: LightGBM + XGBoost + CatBoost)
  4. Score conversion + risk band logic

Usage:
    python build_pipeline.py
    python build_pipeline.py --data-path data/clientes_consolidado.parquet
    python build_pipeline.py --models 5   # use all 5 models instead of top 3

The resulting PKL can be used for scoring without any external JSON/config files:

    pipeline = ScoringPipeline.load("models/champion_pipeline.pkl")
    result = pipeline.score(df_raw)  # DataFrame with scores + risk bands
"""
import os
import sys
import json
import pickle
import argparse
import numpy as np
import pandas as pd

# sklearn compat patch
import sklearn.utils.validation as _val
if not hasattr(_val, '_real_check_array'):
    _val._real_check_array = _val.check_array
def _patched_check(*a, **kw):
    kw.pop("force_all_finite", None)
    kw.pop("ensure_all_finite", None)
    return _val._real_check_array(*a, **kw)
_val.check_array = _patched_check

import warnings
warnings.filterwarnings("ignore")


class _EnsembleModel:
    """Ensemble model wrapper."""
    def __init__(self, mode, base_models, weights=None, meta_model=None, feature_names=None):
        self.mode = mode
        self.base_models = base_models
        self.weights = weights
        self.meta_model = meta_model
        self.feature_names = feature_names

    def predict_proba(self, X):
        models = self.base_models.values() if isinstance(self.base_models, dict) else self.base_models
        base_probs = np.column_stack([
            m.predict_proba(X)[:, 1] if hasattr(m, "predict_proba") else m.predict(X)
            for m in models
        ])
        if self.mode == "average":
            p1 = base_probs.mean(axis=1)
        elif self.mode == "blend":
            p1 = base_probs @ self.weights
        elif self.mode == "stacking":
            p1 = self.meta_model.predict_proba(base_probs)[:, 1]
        else:
            raise ValueError(f"Unknown mode: {self.mode}")
        p1 = np.clip(p1, 0.0, 1.0)
        return np.column_stack([1 - p1, p1])


class _SingleModel:
    """Wrapper for individual models to match ensemble interface."""
    def __init__(self, model, name):
        self.mode = "single"
        self.model = model
        self.name = name

    def predict_proba(self, X):
        if hasattr(self.model, "predict_proba"):
            return self.model.predict_proba(X)
        pred = self.model.predict(X)
        return np.column_stack([1 - pred, pred])


class ScoringPipeline:
    """
    Self-contained scoring pipeline.

    Encapsulates feature selection, preprocessing (with training medians),
    ensemble model, score conversion, and risk band classification.
    """

    VERSION = "2.0"

    def __init__(self, features, train_medians, model, model_version="ensemble-v2",
                 train_safras=None, oot_safras=None, base_model_names=None,
                 ensemble_comparison=None):
        self.features = features
        self.train_medians = train_medians
        self.model = model
        self.model_version = model_version
        self.train_safras = train_safras or []
        self.oot_safras = oot_safras or []
        self.base_model_names = base_model_names or []
        self.ensemble_comparison = ensemble_comparison
        self.pipeline_version = self.VERSION

    def preprocess(self, df):
        """
        Apply preprocessing:
          1. Select 110 training features
          2. Replace inf/-inf with NaN
          3. Fill NaN with training medians (NOT runtime medians)
        """
        missing = [f for f in self.features if f not in df.columns]
        if missing:
            print(f"[WARN] {len(missing)} features missing, filling with training median")

        X = pd.DataFrame(index=df.index)
        for feat in self.features:
            if feat in df.columns:
                X[feat] = df[feat].values
            else:
                X[feat] = self.train_medians.get(feat, 0.0)

        X = X.replace([np.inf, -np.inf], np.nan)
        for col in X.columns:
            if X[col].isna().any():
                fill_val = self.train_medians.get(col, 0.0)
                X[col] = X[col].fillna(fill_val)

        return X

    def predict_proba(self, df):
        """Return P(FPD=1) for each row."""
        X = self.preprocess(df)
        raw = self.model.predict_proba(X)
        return raw[:, 1]

    def score(self, df):
        """
        Full scoring pipeline: preprocess -> predict -> score -> risk band.

        Args:
            df: DataFrame with at least the 110 features.
                Optional columns: NUM_CPF, SAFRA.

        Returns:
            DataFrame with columns:
                NUM_CPF, SAFRA, SCORE, FAIXA_RISCO, PROBABILIDADE_FPD, MODELO_VERSAO
        """
        probabilities = self.predict_proba(df)
        scores = ((1 - probabilities) * 1000).astype(int).clip(0, 1000)
        bands = np.where(scores < 300, "CRITICO",
                np.where(scores < 500, "ALTO",
                np.where(scores < 700, "MEDIO", "BAIXO")))

        result = pd.DataFrame({
            "NUM_CPF": df["NUM_CPF"].values if "NUM_CPF" in df.columns else range(len(df)),
            "SAFRA": df["SAFRA"].values if "SAFRA" in df.columns else 0,
            "SCORE": scores,
            "FAIXA_RISCO": bands,
            "PROBABILIDADE_FPD": probabilities.round(6),
            "MODELO_VERSAO": self.model_version,
        })

        return result

    def save(self, path):
        """Save pipeline to PKL."""
        with open(path, "wb") as f:
            pickle.dump(self, f, protocol=4)
        size_mb = os.path.getsize(path) / 1024 / 1024
        print(f"[SAVED] {path} ({size_mb:.1f} MB)")

    @staticmethod
    def load(path):
        """Load pipeline from PKL."""
        class _PipelineUnpickler(pickle.Unpickler):
            def find_class(self, module, name):
                if name == "_EnsembleModel":
                    return _EnsembleModel
                if name == "ScoringPipeline":
                    return ScoringPipeline
                return super().find_class(module, name)

        with open(path, "rb") as f:
            return _PipelineUnpickler(f).load()

    def info(self):
        """Print pipeline info."""
        print(f"ScoringPipeline v{self.pipeline_version}")
        print(f"  Features: {len(self.features)}")
        print(f"  Train medians: {len(self.train_medians)} stored")
        mode = getattr(self.model, "mode", "unknown")
        if mode == "single":
            print(f"  Model: {self.base_model_names[0]} (individual)")
        else:
            print(f"  Model: {mode} ensemble")
            print(f"  Base models: {self.base_model_names}")
        print(f"  Train SAFRAs: {self.train_safras}")
        print(f"  OOT SAFRAs: {self.oot_safras}")
        print(f"  Version: {self.model_version}")


ALL_MODELS = {
    "LightGBM_v2": "credit_risk_lgbm_v2.pkl",
    "XGBoost": "credit_risk_xgboost.pkl",
    "CatBoost": "credit_risk_catboost.pkl",
    "RandomForest": "credit_risk_rf.pkl",
    "LR_L1_v2": "credit_risk_lr_l1_v2.pkl",
}

TOP3_MODELS = {k: ALL_MODELS[k] for k in ["LightGBM_v2", "XGBoost", "CatBoost"]}

# Maps model name -> output filename
MODEL_OUTPUT_NAMES = {
    "LightGBM_v2": "pipeline_lgbm_v2.pkl",
    "XGBoost": "pipeline_xgboost.pkl",
    "CatBoost": "pipeline_catboost.pkl",
    "RandomForest": "pipeline_rf.pkl",
    "LR_L1_v2": "pipeline_lr_l1_v2.pkl",
}


def _resolve_artifacts(args_artifacts_path):
    """Resolve artifacts directory path."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if args_artifacts_path:
        return os.path.abspath(args_artifacts_path)
    elif os.path.isdir(os.path.join(script_dir, "..", "artifacts")):
        return os.path.join(script_dir, "..", "artifacts")
    return "artifacts"


def _load_features(artifacts):
    """Load selected features from JSON."""
    feat_path = os.path.join(artifacts, "selected_features.json")
    with open(feat_path) as f:
        feat_data = json.load(f)
    features = feat_data["selected_features"]
    print(f"  Features: {len(features)} loaded from {feat_path}")
    return features


def _load_raw_models(artifacts, model_selection):
    """Load raw model PKLs from artifacts."""
    raw_models = {}
    for name, fname in model_selection.items():
        path = os.path.join(artifacts, "models", fname)
        with open(path, "rb") as f:
            raw_models[name] = pickle.load(f)
        size = os.path.getsize(path) / 1024 / 1024
        print(f"  {name}: {size:.1f} MB")
    return raw_models


def _compute_train_medians(data_path, features):
    """Compute training medians from parquet data."""
    print(f"\n[MEDIANS] Computing from {data_path}")
    df = pd.read_parquet(data_path, columns=["SAFRA"] + [f for f in features if f != "SAFRA"])
    print(f"  Total: {len(df):,} rows")

    train_safras = [202410, 202411, 202412, 202501]
    df_train = df[df["SAFRA"].isin(train_safras)]
    print(f"  Train rows (SAFRAs {train_safras}): {len(df_train):,}")
    del df

    train_medians = {}
    for feat in features:
        if feat in df_train.columns:
            col = df_train[feat].replace([np.inf, -np.inf], np.nan)
            median_val = col.median()
            train_medians[feat] = float(median_val) if pd.notna(median_val) else 0.0
        else:
            train_medians[feat] = 0.0
    del df_train

    n_nonzero = sum(1 for v in train_medians.values() if v != 0.0)
    print(f"  Medians: {len(train_medians)} features ({n_nonzero} non-zero)")
    return train_medians


def _load_ensemble_comparison(artifacts):
    """Load ensemble comparison metadata from artifacts."""
    comp_json = os.path.join(artifacts, "metrics", "ensemble_comparison.json")
    if os.path.isfile(comp_json):
        with open(comp_json) as f:
            return json.load(f)

    # Fallback: build from training_results + ensemble_results
    tr_json = os.path.join(artifacts, "metrics")
    tr_files = [f for f in os.listdir(tr_json) if f.startswith("training_results_")]
    ens_json = os.path.join(artifacts, "metrics", "ensemble_results.json")

    individual = {}
    if tr_files:
        with open(os.path.join(tr_json, sorted(tr_files)[-1])) as f:
            tr_data = json.load(f)
        for name, m in tr_data.get("model_metrics", {}).items():
            key = {"lr_l1_v2": "LR_L1_v2", "lgbm_v2": "LightGBM_v2",
                   "xgboost": "XGBoost", "catboost": "CatBoost", "rf": "RandomForest"}.get(name, name)
            individual[key] = {
                "ks_train": m["ks_train"], "ks_oot": m["ks_oot"],
                "gap": round(m["ks_train"] - m["ks_oot"], 4),
                "ratio": round(m["ks_train"] / m["ks_oot"], 2) if m["ks_oot"] > 0 else 0,
            }

    ens_metrics = {}
    if os.path.isfile(ens_json):
        with open(ens_json) as f:
            ens_data = json.load(f)
        avg = ens_data.get("strategies", {}).get("average", {})
        ens_metrics = {
            "ks_train": avg.get("ks_train"), "ks_oot": avg.get("ks_oot"),
            "auc_train": avg.get("auc_train"), "auc_oot": avg.get("auc_oot"),
            "gini_oot": avg.get("gini_oot"), "psi": avg.get("psi"),
        }

    return {
        "decision": "top3",
        "rationale": (
            "Top 3 (LightGBM+XGBoost+CatBoost) preferred for delivery: "
            "smaller PKL size, excludes weakest models (LR L1, RF)."
        ),
        "ensemble_metrics": ens_metrics,
        "individual_models": individual,
    }


def _load_individual_metrics(artifacts):
    """Load per-model metrics from training_results JSON."""
    tr_dir = os.path.join(artifacts, "metrics")
    tr_files = [f for f in os.listdir(tr_dir) if f.startswith("training_results_")]
    if not tr_files:
        return {}
    with open(os.path.join(tr_dir, sorted(tr_files)[-1])) as f:
        tr_data = json.load(f)
    name_map = {"lr_l1_v2": "LR_L1_v2", "lgbm_v2": "LightGBM_v2",
                "xgboost": "XGBoost", "catboost": "CatBoost", "rf": "RandomForest"}
    result = {}
    for name, m in tr_data.get("model_metrics", {}).items():
        key = name_map.get(name, name)
        result[key] = m
    return result


def _build_and_save(model, model_version, base_model_names, features, train_medians,
                    output_path, ensemble_comparison=None):
    """Build a ScoringPipeline, save it, and run smoke test."""
    train_safras = [202410, 202411, 202412, 202501]
    oot_safras = [202502, 202503]

    pipeline = ScoringPipeline(
        features=features,
        train_medians=train_medians,
        model=model,
        model_version=model_version,
        train_safras=train_safras,
        oot_safras=oot_safras,
        base_model_names=base_model_names,
        ensemble_comparison=ensemble_comparison,
    )

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    pipeline.save(output_path)

    # Verify round-trip
    loaded = ScoringPipeline.load(output_path)
    loaded.info()

    # Smoke test
    synthetic = pd.DataFrame(np.random.rand(5, len(features)), columns=features)
    result = loaded.score(synthetic)
    print(f"  Smoke test: {len(result)} rows, scores={result['SCORE'].tolist()}")


def main():
    parser = argparse.ArgumentParser(description="Build self-contained scoring pipeline PKL(s)")
    parser.add_argument("--data-path", default="data/clientes_consolidado.parquet",
                        help="Path to parquet with training data")
    parser.add_argument("--artifacts-path", default=None,
                        help="Path to artifacts directory")
    parser.add_argument("--output-dir", default="models",
                        help="Output directory for PKL files (default: models)")
    parser.add_argument("--build-all", action="store_true",
                        help="Build all 6 pipelines: champion (top-3) + 5 individual models")
    parser.add_argument("--models", type=int, default=3, choices=[3, 5],
                        help="Number of models in champion ensemble: 3 (top) or 5 (all)")
    args = parser.parse_args()

    artifacts = _resolve_artifacts(args.artifacts_path)
    output_dir = args.output_dir

    print("=" * 60)
    if args.build_all:
        print("BUILD ALL PIPELINES (champion + 5 individual)")
    else:
        print(f"BUILD CHAMPION PIPELINE (top {args.models} ensemble)")
    print("=" * 60)

    # 1. Load features
    print("\n[1] Loading features")
    features = _load_features(artifacts)

    # 2. Load all raw models
    print(f"\n[2] Loading raw models from {artifacts}/models/")
    model_selection = ALL_MODELS if args.build_all else (TOP3_MODELS if args.models == 3 else ALL_MODELS)
    raw_models = _load_raw_models(artifacts, model_selection)

    # 3. Compute training medians (once, shared by all pipelines)
    train_medians = _compute_train_medians(args.data_path, features)

    # 4. Load metadata
    print("\n[4] Loading metadata")
    ensemble_comparison = _load_ensemble_comparison(artifacts)
    individual_metrics = _load_individual_metrics(artifacts)

    built = []

    # ── Champion ensemble pipeline ──────────────────────────────────
    print("\n" + "=" * 60)
    print("[CHAMPION] Building champion ensemble pipeline")
    print("=" * 60)

    if args.models == 3:
        ens_models = {k: raw_models[k] for k in TOP3_MODELS}
        model_version = "ensemble-top3-v2"
    else:
        ens_models = raw_models.copy()
        model_version = "ensemble-all5-v1"

    ensemble = _EnsembleModel(
        mode="average",
        base_models=ens_models,
        feature_names=features,
    )

    champion_path = os.path.join(output_dir, "champion_pipeline.pkl")
    _build_and_save(
        model=ensemble,
        model_version=model_version,
        base_model_names=list(ens_models.keys()),
        features=features,
        train_medians=train_medians,
        output_path=champion_path,
        ensemble_comparison=ensemble_comparison,
    )
    built.append(("champion", champion_path))

    # ── Individual model pipelines ──────────────────────────────────
    if args.build_all:
        for model_name, raw_model in raw_models.items():
            print(f"\n{'=' * 60}")
            print(f"[INDIVIDUAL] Building pipeline for {model_name}")
            print("=" * 60)

            wrapped = _SingleModel(raw_model, model_name)
            out_name = MODEL_OUTPUT_NAMES[model_name]
            out_path = os.path.join(output_dir, out_name)

            # Attach individual model metrics as metadata
            model_meta = individual_metrics.get(model_name)
            ind_comparison = None
            if model_meta:
                ind_comparison = {
                    "model": model_name,
                    "metrics": model_meta,
                    "note": "Individual model pipeline. Champion is ensemble-top3-v2.",
                }

            _build_and_save(
                model=wrapped,
                model_version=f"{model_name.lower().replace('_', '-')}-v1",
                base_model_names=[model_name],
                features=features,
                train_medians=train_medians,
                output_path=out_path,
                ensemble_comparison=ind_comparison,
            )
            built.append((model_name, out_path))

    # ── Summary ─────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"[DONE] Built {len(built)} pipeline(s):")
    for name, path in built:
        size = os.path.getsize(path) / 1024 / 1024
        print(f"  {name:20s} -> {path} ({size:.1f} MB)")
    print(f"\nUsage:")
    print(f"  pipeline = ScoringPipeline.load('models/champion_pipeline.pkl')")
    print(f"  result = pipeline.score(df)")


if __name__ == "__main__":
    main()
