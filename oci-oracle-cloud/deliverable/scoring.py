"""
Standalone Scoring Script — Credit Risk Model
Scores customers using the champion pipeline (champion_pipeline.pkl).
Outputs CSV with scores/risk bands and JSON summary.

Usage:
    python scoring.py --data-path /path/to/data.parquet
    python scoring.py --data-path /path/to/data.parquet --pipeline-path models/champion_pipeline.pkl
"""
import os
import sys
import json
import pickle
import argparse
import numpy as np
import pandas as pd
from datetime import datetime

# sklearn compat patch — must be applied before any sklearn import
import sklearn.utils.validation as _val
if not hasattr(_val, '_real_check_array'):
    _val._real_check_array = _val.check_array
def _patched_check(*a, **kw):
    kw.pop("force_all_finite", None)
    kw.pop("ensure_all_finite", None)
    return _val._real_check_array(*a, **kw)
_val.check_array = _patched_check

from sklearn.metrics import roc_auc_score

import warnings
warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# Inline classes required for pickle deserialization
# ---------------------------------------------------------------------------

class _EnsembleModel:
    """Ensemble model wrapper supporting average, blend, and stacking modes."""

    def __init__(self, mode, base_models, weights=None, meta_model=None, feature_names=None):
        self.mode = mode
        self.base_models = base_models
        self.weights = weights
        self.meta_model = meta_model
        self.feature_names = feature_names

    def predict_proba(self, X):
        models = self.base_models.values() if isinstance(self.base_models, dict) else self.base_models
        base_probs = np.column_stack([
            m.predict_proba(X)[:, 1] if hasattr(m, "predict_proba")
            else m.predict(X)
            for m in models
        ])
        if self.mode == "average":
            p1 = base_probs.mean(axis=1)
        elif self.mode == "blend":
            p1 = base_probs @ self.weights
        elif self.mode == "stacking":
            p1 = self.meta_model.predict_proba(base_probs)[:, 1]
        else:
            raise ValueError(f"Unknown ensemble mode: {self.mode}")
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
    """Stub for pickle deserialization."""
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def compute_ks(y_true, y_prob):
    """Compute KS statistic."""
    from scipy.stats import ks_2samp
    pos = y_prob[y_true == 1]
    neg = y_prob[y_true == 0]
    if len(pos) == 0 or len(neg) == 0:
        return 0.0
    ks_stat, _ = ks_2samp(pos, neg)
    return float(ks_stat)


def load_pipeline(path):
    """Load ScoringPipeline from PKL with custom unpickler."""
    class _PipelineUnpickler(pickle.Unpickler):
        def find_class(self, module, name):
            if name == "_EnsembleModel":
                return _EnsembleModel
            if name == "_SingleModel":
                return _SingleModel
            if name == "ScoringPipeline":
                try:
                    from build_pipeline import ScoringPipeline as SP
                    return SP
                except ImportError:
                    pass
                return ScoringPipeline
            return super().find_class(module, name)

    with open(path, "rb") as f:
        return _PipelineUnpickler(f).load()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Credit Risk Standalone Scoring")
    parser.add_argument("--data-path", required=True, help="Path to parquet file or directory")
    parser.add_argument("--pipeline-path", default=None,
                        help="Path to champion_pipeline.pkl (default: models/champion_pipeline.pkl)")
    parser.add_argument("--output-path", default="output", help="Path to output directory (default: output)")
    args = parser.parse_args()

    # Resolve pipeline path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if args.pipeline_path:
        pipeline_path = os.path.abspath(args.pipeline_path)
    else:
        pipeline_path = os.path.join(script_dir, "models", "champion_pipeline.pkl")

    print("=" * 70)
    print("STANDALONE SCORING — Credit Risk Model")
    print("=" * 70)
    print(f"  Data path:     {args.data_path}")
    print(f"  Pipeline path: {pipeline_path}")
    print(f"  Output path:   {args.output_path}")
    print()

    # ── Load pipeline ──────────────────────────────────────────────────
    print(f"[PIPELINE] Loading from {pipeline_path}...")
    if not os.path.exists(pipeline_path):
        print(f"[ERROR] Pipeline file not found: {pipeline_path}")
        sys.exit(1)

    pipeline = load_pipeline(pipeline_path)
    model_version = getattr(pipeline, "model_version", "unknown")
    base_models = getattr(pipeline, "base_model_names", [])
    n_features = len(pipeline.features) if hasattr(pipeline, "features") else 0
    print(f"[PIPELINE] Loaded: {model_version}, {len(base_models)} models, {n_features} features")
    print(f"[PIPELINE] Models: {base_models}")

    # ── Load data ──────────────────────────────────────────────────────
    print(f"\n[DATA] Reading parquet from {args.data_path}...")
    df = pd.read_parquet(args.data_path)
    print(f"[DATA] Loaded {len(df):,} records, {df.shape[1]} columns")

    if "SAFRA" in df.columns:
        safras = sorted(df["SAFRA"].unique())
        print(f"[DATA] SAFRAs: {safras}")

    # ── Score using pipeline ───────────────────────────────────────────
    print(f"\n[SCORE] Running pipeline.score()...")
    result = pipeline.score(df)
    scores = result["SCORE"].values

    # ── Print distribution ─────────────────────────────────────────────
    print(f"\n[SCORE] Risk Distribution:")
    for band in ["CRITICO", "ALTO", "MEDIO", "BAIXO"]:
        count = (result["FAIXA_RISCO"] == band).sum()
        pct = count / len(result) * 100
        print(f"  {band:10s}: {count:>8,} ({pct:.1f}%)")

    print(f"\n[SCORE] Score stats: mean={scores.mean():.0f}, "
          f"median={int(np.median(scores))}, "
          f"min={scores.min()}, max={scores.max()}")

    # ── Performance metrics (if FPD column exists) ─────────────────────
    perf_metrics = None
    if "FPD" in df.columns:
        labeled = df["FPD"].notna()
        if labeled.sum() > 0:
            y_true = df.loc[labeled, "FPD"].values.astype(int)
            y_prob = result.loc[labeled.values, "PROBABILIDADE_FPD"].values
            if len(np.unique(y_true)) >= 2:
                auc = float(roc_auc_score(y_true, y_prob))
                ks = compute_ks(y_true, y_prob)
                gini = 2 * auc - 1
                perf_metrics = {
                    "KS": round(ks, 4),
                    "AUC": round(auc, 4),
                    "Gini": round(gini * 100, 2),
                    "labeled_records": int(labeled.sum()),
                }
                print(f"\n[PERF] KS={ks:.4f}, AUC={auc:.4f}, Gini={gini*100:.2f}%")

    # ── Save outputs ───────────────────────────────────────────────────
    os.makedirs(args.output_path, exist_ok=True)

    csv_path = os.path.join(args.output_path, "clientes_scores.csv")
    result.to_csv(csv_path, index=False)
    print(f"\n[OUTPUT] CSV saved: {csv_path} ({len(result):,} rows)")

    # Build summary JSON
    risk_dist = result["FAIXA_RISCO"].value_counts().to_dict()
    summary = {
        "total_records": int(len(result)),
        "risk_distribution": {str(k): int(v) for k, v in risk_dist.items()},
        "score_stats": {
            "mean": float(result["SCORE"].mean()),
            "median": float(result["SCORE"].median()),
            "min": int(result["SCORE"].min()),
            "max": int(result["SCORE"].max()),
            "std": float(result["SCORE"].std()),
        },
        "model_version": model_version,
        "base_models": base_models,
        "timestamp": datetime.now().isoformat(),
    }
    if perf_metrics:
        summary["performance_metrics"] = perf_metrics

    json_path = os.path.join(args.output_path, "scoring_summary.json")
    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"[OUTPUT] JSON saved: {json_path}")

    print(f"\n[DONE] Scoring complete: {len(result):,} records scored")


if __name__ == "__main__":
    main()
