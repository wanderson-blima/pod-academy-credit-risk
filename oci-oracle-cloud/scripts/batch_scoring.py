"""
Batch Scoring — OCI Data Science
Scores all customers using champion ensemble or fallback model.
Output: clientes_scores table (8 columns) in Gold bucket.
Also generates decile analysis, plots, and scoring summary JSON.

Scoring is segmented by population:
  - TRAIN (SAFRAs 202410-202501): scored for monitoring/comparison only
  - PRODUCTION (SAFRAs 202502+): scored for actual decisioning (unseen data)

Preprocessing: The sklearn Pipeline inside each .pkl already contains
SimpleImputer (training medians) + StandardScaler. Do NOT apply manual
fillna — let the pipeline handle it to avoid data leakage.

Usage:
    Run in OCI Data Science notebook after training and evaluation.
    Loads champion_ensemble.pkl (preferred) or any model from ARTIFACT_DIR.
"""
import os
import json
import pickle
import uuid
import glob
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime

# Threading
NCPUS = int(os.environ.get("NOTEBOOK_OCPUS", "10"))
os.environ["OMP_NUM_THREADS"] = str(NCPUS)
os.environ["OPENBLAS_NUM_THREADS"] = str(NCPUS)
os.environ["MKL_NUM_THREADS"] = "1"

# sklearn compat patch
import sklearn.utils.validation as _val
_original_check = _val.check_array
def _patched_check(*a, **kw):
    kw.pop("force_all_finite", None)
    kw.pop("ensure_all_finite", None)
    return _original_check(*a, **kw)
_val.check_array = _patched_check

import warnings
warnings.filterwarnings("ignore")

from train_credit_risk import (
    SELECTED_FEATURES as _DEFAULT_FEATURES, TARGET, ARTIFACT_DIR,
    GOLD_PATH, LOCAL_DATA_PATH,
    NAMESPACE, GOLD_BUCKET,
    TRAIN_SAFRAS, OOT_SAFRAS,
)
# Import ensemble class so pickle can deserialize champion_ensemble.pkl
try:
    from ensemble import _EnsembleModel
except ImportError:
    pass

# Try loading dynamically selected features
features_path = os.path.join(ARTIFACT_DIR, "selected_features.json")
if os.path.exists(features_path):
    with open(features_path) as f:
        feat_data = json.load(f)
    SELECTED_FEATURES = feat_data.get("selected_features", feat_data.get("features", []))
    print(f"[FEATURES] Loaded {len(SELECTED_FEATURES)} from selected_features.json")
else:
    SELECTED_FEATURES = _DEFAULT_FEATURES
    print(f"[FEATURES] Using {len(SELECTED_FEATURES)} default features from train_credit_risk")

# ═══════════════════════════════════════════════════════════════════════════
# SCORING
# ═══════════════════════════════════════════════════════════════════════════

SCORES_OUTPUT_PATH = f"oci://{GOLD_BUCKET}@{NAMESPACE}/clientes_scores/"
MODEL_VERSION = "ensemble-v1"

# Priority: champion ensemble > individual model
CHAMPION_PATH = os.path.join(ARTIFACT_DIR, "models", "champion_ensemble.pkl")
# Legacy ensemble path (backward compat)
LEGACY_ENSEMBLE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "artifacts", "ensemble", "ensemble_model.pkl"
)
# Fallback: single model from models/ directory
FALLBACK_MODEL_VERSION = "lgbm-oci-v1"


def risk_band(score):
    """Classify score into risk band (0-1000 scale)."""
    if score < 300:
        return "CRITICO"
    elif score < 500:
        return "ALTO"
    elif score < 700:
        return "MEDIO"
    else:
        return "BAIXO"


def decile_table(y_true, y_prob):
    """Decile analysis with lift."""
    df = pd.DataFrame({"y_true": y_true, "y_prob": y_prob})
    df["decile"] = pd.qcut(df["y_prob"], 10, labels=False, duplicates="drop")
    df["decile"] = 10 - df["decile"]
    summary = df.groupby("decile").agg(
        n=("y_true", "count"),
        n_bad=("y_true", "sum"),
        mean_prob=("y_prob", "mean"),
    ).sort_index()
    summary["n_good"] = summary["n"] - summary["n_bad"]
    summary["bad_rate"] = summary["n_bad"] / summary["n"]
    summary["cum_bad"] = summary["n_bad"].cumsum()
    summary["cum_good"] = summary["n_good"].cumsum()
    summary["cum_bad_pct"] = summary["cum_bad"] / summary["n_bad"].sum()
    summary["cum_good_pct"] = summary["cum_good"] / summary["n_good"].sum()
    summary["ks"] = (summary["cum_bad_pct"] - summary["cum_good_pct"]).abs()
    summary["lift"] = summary["bad_rate"] / (summary["n_bad"].sum() / summary["n"].sum())
    return summary


def score_batch(pipeline, df):
    """Score all customers and generate clientes_scores output.

    IMPORTANT: Does NOT apply manual fillna. The sklearn Pipeline inside the
    model already contains SimpleImputer with training-time medians. Applying
    fillna here would override training preprocessing and cause data leakage.
    Only inf→NaN conversion is needed (SimpleImputer handles NaN, not inf).
    """
    execution_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"[SCORE] Scoring {len(df):,} records...")
    X = df[SELECTED_FEATURES].copy()

    # Only convert inf to NaN — the pipeline's SimpleImputer handles NaN
    # using training-time medians (frozen at fit time, no leakage)
    X = X.replace([np.inf, -np.inf], np.nan)

    # Generate probabilities — handle both ensemble (nx2) and pipeline models
    raw_proba = pipeline.predict_proba(X)
    if raw_proba.ndim == 2 and raw_proba.shape[1] >= 2:
        probabilities = raw_proba[:, 1]
    else:
        probabilities = raw_proba.ravel()

    # Convert to 0-1000 score (higher = lower risk)
    scores = ((1 - probabilities) * 1000).astype(int).clip(0, 1000)

    # Build output DataFrame — matches Gold.clientes_scores schema (8 columns)
    result = pd.DataFrame({
        "NUM_CPF": df["NUM_CPF"].values,
        "SAFRA": df["SAFRA"].values,
        "SCORE": scores,
        "FAIXA_RISCO": [risk_band(s) for s in scores],
        "PROBABILIDADE_FPD": probabilities.round(6),
        "MODELO_VERSAO": MODEL_VERSION,
        "DATA_SCORING": timestamp,
        "EXECUTION_ID": execution_id,
    })

    # Distribution summary
    print(f"\n[SCORE] Distribution:")
    for band in ["CRITICO", "ALTO", "MEDIO", "BAIXO"]:
        count = (result["FAIXA_RISCO"] == band).sum()
        pct = count / len(result) * 100
        print(f"  {band:10s}: {count:>8,} ({pct:.1f}%)")

    print(f"\n[SCORE] Score stats: mean={scores.mean():.0f}, "
          f"median={int(np.median(scores))}, "
          f"min={scores.min()}, max={scores.max()}")

    return result


def save_scores(scores_df, output_path=None):
    """Write scores locally and optionally to OCI Object Storage."""
    if output_path is None:
        output_path = SCORES_OUTPUT_PATH

    # Save local copy first (always works)
    local_path = f"{ARTIFACT_DIR}/scoring"
    os.makedirs(local_path, exist_ok=True)
    scores_df.to_parquet(f"{local_path}/clientes_scores_all.parquet", index=False)
    print(f"[SAVE] Local copy: {local_path}/clientes_scores_all.parquet")

    # Save production-only scores (unseen data) for downstream consumption
    prod_only = scores_df[scores_df.get("POPULACAO", "PRODUCAO") == "PRODUCAO"]
    if len(prod_only) > 0:
        prod_only.to_parquet(f"{local_path}/clientes_scores_production.parquet", index=False)
        print(f"[SAVE] Production-only: {local_path}/clientes_scores_production.parquet ({len(prod_only):,} records)")

    # Save partitioned by SAFRA locally
    for safra in sorted(scores_df["SAFRA"].unique()):
        safra_df = scores_df[scores_df["SAFRA"] == safra]
        safra_dir = f"{local_path}/SAFRA={safra}"
        os.makedirs(safra_dir, exist_ok=True)
        safra_df.drop(columns=["SAFRA"]).to_parquet(
            f"{safra_dir}/scores.parquet", index=False
        )
        print(f"  SAFRA {safra}: {len(safra_df):,} records")

    # Try uploading to OCI Object Storage
    try:
        print(f"\n[SAVE] Uploading to {output_path}...")
        for safra in sorted(scores_df["SAFRA"].unique()):
            safra_df = scores_df[scores_df["SAFRA"] == safra]
            safra_path = f"{output_path}SAFRA={safra}/scores.parquet"
            safra_df.drop(columns=["SAFRA"]).to_parquet(safra_path, index=False)
        print("[SAVE] OCI upload complete")
    except Exception as e:
        print(f"[SAVE] OCI upload failed (non-critical): {e}")
        print("[SAVE] Scores saved locally — upload manually with OCI CLI")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import pyarrow.parquet as pq

    print("=" * 70)
    print("BATCH SCORING — OCI Data Science")
    print("=" * 70)

    # Priority: champion ensemble > legacy ensemble > any model in models/
    model_version = MODEL_VERSION
    if os.path.exists(CHAMPION_PATH):
        print(f"[LOAD] Champion ensemble: {CHAMPION_PATH}")
        with open(CHAMPION_PATH, "rb") as f:
            lgbm_pipeline = pickle.load(f)
        model_version = MODEL_VERSION
        print(f"[LOAD] Champion loaded (mode={getattr(lgbm_pipeline, 'mode', 'pipeline')})")
    elif os.path.exists(LEGACY_ENSEMBLE_PATH):
        print(f"[LOAD] Legacy ensemble: {LEGACY_ENSEMBLE_PATH}")
        with open(LEGACY_ENSEMBLE_PATH, "rb") as f:
            lgbm_pipeline = pickle.load(f)
        model_version = MODEL_VERSION
        print(f"[LOAD] Legacy ensemble loaded (mode={getattr(lgbm_pipeline, 'mode', 'pipeline')})")
    else:
        model_files = sorted(glob.glob(f"{ARTIFACT_DIR}/models/*.pkl"))
        if not model_files:
            print("[ERROR] No trained model .pkl found. Run train_credit_risk.py first.")
            exit(1)
        print(f"[LOAD] Fallback to individual model: {model_files[-1]}")
        with open(model_files[-1], "rb") as f:
            lgbm_pipeline = pickle.load(f)
        model_version = FALLBACK_MODEL_VERSION

    # Load all data
    columns_to_load = SELECTED_FEATURES + [TARGET, "SAFRA", "NUM_CPF"]
    if os.path.exists(LOCAL_DATA_PATH):
        table = pq.read_table(LOCAL_DATA_PATH, columns=columns_to_load)
        df = table.to_pandas(self_destruct=True)
    else:
        df = pd.read_parquet(GOLD_PATH, columns=columns_to_load)

    print(f"[DATA] Loaded {len(df):,} records, {len(df['SAFRA'].unique())} SAFRAs")
    all_safras = sorted(df["SAFRA"].unique())
    print(f"[DATA] SAFRAs: {all_safras}")

    # Override MODEL_VERSION based on what was loaded
    MODEL_VERSION = model_version

    # ── Segment populations ──────────────────────────────────────────
    train_safras_set = set(TRAIN_SAFRAS)
    production_safras = [s for s in all_safras if s not in train_safras_set]

    print(f"\n[POPULATION] Train SAFRAs: {TRAIN_SAFRAS} ({len(df[df['SAFRA'].isin(TRAIN_SAFRAS)]):,} records)")
    print(f"[POPULATION] Production SAFRAs: {production_safras} ({len(df[~df['SAFRA'].isin(TRAIN_SAFRAS)]):,} records)")

    # Score ALL records (for monitoring comparison)
    scores_df = score_batch(lgbm_pipeline, df)

    # Tag each record with its population
    scores_df["POPULACAO"] = scores_df["SAFRA"].apply(
        lambda s: "TREINO" if s in train_safras_set else "PRODUCAO"
    )

    # Validate output schema
    expected_cols = {"NUM_CPF", "SAFRA", "SCORE", "FAIXA_RISCO",
                     "PROBABILIDADE_FPD", "MODELO_VERSAO", "DATA_SCORING",
                     "EXECUTION_ID", "POPULACAO"}
    assert set(scores_df.columns) == expected_cols, f"Schema mismatch: {set(scores_df.columns)}"
    print(f"\n[VALIDATE] Output schema: {len(scores_df.columns)} columns — OK")

    # Save to Gold
    save_scores(scores_df)

    # ── Per-SAFRA metrics ─────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("METRICS PER SAFRA")
    print("=" * 70)

    labeled = scores_df.merge(df[["NUM_CPF", "SAFRA", TARGET]], on=["NUM_CPF", "SAFRA"])
    safra_metrics = {}

    for safra in sorted(scores_df["SAFRA"].unique()):
        safra_data = labeled[labeled["SAFRA"] == safra]
        pop = "TREINO" if safra in train_safras_set else "PRODUCAO"
        n_total = len(safra_data)
        n_labeled = safra_data[TARGET].notna().sum()
        n_fpd = int(safra_data[TARGET].sum()) if n_labeled > 0 else 0
        fpd_rate = n_fpd / n_labeled if n_labeled > 0 else None

        safra_scores = safra_data["SCORE"]
        safra_proba = safra_data["PROBABILIDADE_FPD"]
        risk_dist_safra = safra_data["FAIXA_RISCO"].value_counts().to_dict()

        metrics = {
            "safra": int(safra),
            "population": pop,
            "total_records": n_total,
            "labeled_records": int(n_labeled),
            "fpd_count": n_fpd,
            "fpd_rate": round(fpd_rate, 4) if fpd_rate is not None else None,
            "score_mean": round(float(safra_scores.mean()), 1),
            "score_median": int(safra_scores.median()),
            "score_std": round(float(safra_scores.std()), 1),
            "risk_distribution": {str(k): int(v) for k, v in risk_dist_safra.items()},
        }

        # KS and AUC only for labeled data
        if n_labeled > 100 and safra_data[TARGET].nunique() == 2:
            from sklearn.metrics import roc_auc_score
            y_true = safra_data[TARGET].dropna().values
            y_prob = safra_data.loc[safra_data[TARGET].notna(), "PROBABILIDADE_FPD"].values
            auc = roc_auc_score(y_true, y_prob)
            # KS
            from scipy.stats import ks_2samp
            good_probs = y_prob[y_true == 0]
            bad_probs = y_prob[y_true == 1]
            ks_stat = ks_2samp(bad_probs, good_probs).statistic
            metrics["ks"] = round(float(ks_stat), 4)
            metrics["auc"] = round(float(auc), 4)
            metrics["gini"] = round(float((2 * auc - 1) * 100), 2)

        safra_metrics[str(safra)] = metrics

        # Print
        ks_str = f"KS={metrics.get('ks', 'N/A')}" if 'ks' in metrics else "KS=N/A (unlabeled)"
        print(f"\n  SAFRA {safra} [{pop}]:")
        print(f"    Records: {n_total:,} | Labeled: {n_labeled:,} | FPD: {n_fpd:,} ({fpd_rate*100:.2f}%)" if fpd_rate else f"    Records: {n_total:,} | Labeled: {n_labeled:,}")
        print(f"    Score: mean={metrics['score_mean']}, median={metrics['score_median']}, std={metrics['score_std']}")
        print(f"    {ks_str}")
        print(f"    Risk bands: {risk_dist_safra}")

    # ── Decile analysis — PRODUCTION population only ──────────────────
    prod_labeled = labeled[(~labeled["SAFRA"].isin(TRAIN_SAFRAS)) & (labeled[TARGET].notna())]
    if len(prod_labeled) > 0 and prod_labeled[TARGET].nunique() == 2:
        deciles_prod = decile_table(prod_labeled[TARGET].values, prod_labeled["PROBABILIDADE_FPD"].values)
        print("\n[DECILE] Production Population (OOT SAFRAs):")
        print(deciles_prod.to_string())
    else:
        deciles_prod = None
        print("\n[DECILE] No labeled production records — skipping decile analysis")

    # Also compute train deciles for comparison
    train_labeled = labeled[(labeled["SAFRA"].isin(TRAIN_SAFRAS)) & (labeled[TARGET].notna())]
    if len(train_labeled) > 0 and train_labeled[TARGET].nunique() == 2:
        deciles_train = decile_table(train_labeled[TARGET].values, train_labeled["PROBABILIDADE_FPD"].values)
        print("\n[DECILE] Training Population (for comparison):")
        print(deciles_train.to_string())
    else:
        deciles_train = None

    # ── Plots ──────────────────────────────────────────────────────────
    plots_dir = os.path.join(ARTIFACT_DIR, "plots")
    os.makedirs(plots_dir, exist_ok=True)
    colors_map = {"CRITICO": "#d32f2f", "ALTO": "#f57c00", "MEDIO": "#fbc02d", "BAIXO": "#388e3c"}

    # 1. Score histogram by risk band — PRODUCTION only
    fig, axes = plt.subplots(1, 2, figsize=(16, 5))
    for ax, (pop_name, pop_df) in zip(axes, [
        ("Production (OOT)", scores_df[scores_df["POPULACAO"] == "PRODUCAO"]),
        ("Training (baseline)", scores_df[scores_df["POPULACAO"] == "TREINO"]),
    ]):
        for band in ["CRITICO", "ALTO", "MEDIO", "BAIXO"]:
            subset = pop_df[pop_df["FAIXA_RISCO"] == band]["SCORE"]
            if len(subset) > 0:
                ax.hist(subset, bins=50, alpha=0.7, label=band, color=colors_map[band])
        ax.set_xlabel("Score (0-1000)")
        ax.set_ylabel("Count")
        ax.set_title(f"Score Distribution — {pop_name}")
        ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(plots_dir, "scoring_histogram.png"), dpi=150)
    plt.close(fig)
    print(f"\n[PLOT] Saved scoring_histogram.png")

    # 2. Score distribution per SAFRA (overlay)
    fig, ax = plt.subplots(figsize=(12, 5))
    safra_colors = {202410: "#90caf9", 202411: "#64b5f6", 202412: "#42a5f5",
                    202501: "#1e88e5", 202502: "#e53935", 202503: "#c62828"}
    for safra in sorted(scores_df["SAFRA"].unique()):
        subset = scores_df[scores_df["SAFRA"] == safra]["SCORE"]
        pop = "TREINO" if safra in train_safras_set else "PROD"
        ax.hist(subset, bins=50, alpha=0.4, label=f"{safra} [{pop}]",
                color=safra_colors.get(safra, "#888888"), density=True)
    ax.set_xlabel("Score (0-1000)")
    ax.set_ylabel("Density")
    ax.set_title("Score Distribution per SAFRA (Train vs Production)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(plots_dir, "scoring_by_safra.png"), dpi=150)
    plt.close(fig)
    print(f"[PLOT] Saved scoring_by_safra.png")

    # 3. Risk band pie chart — Production only
    prod_scores = scores_df[scores_df["POPULACAO"] == "PRODUCAO"]
    fig, ax = plt.subplots(figsize=(7, 7))
    band_counts = prod_scores["FAIXA_RISCO"].value_counts()
    band_order = [b for b in ["CRITICO", "ALTO", "MEDIO", "BAIXO"] if b in band_counts.index]
    pie_colors = [colors_map[b] for b in band_order]
    ax.pie(band_counts[band_order], labels=band_order, colors=pie_colors,
           autopct="%1.1f%%", startangle=90)
    ax.set_title("Risk Band Distribution — Production Population")
    fig.tight_layout()
    fig.savefig(os.path.join(plots_dir, "scoring_pie.png"), dpi=150)
    plt.close(fig)
    print(f"[PLOT] Saved scoring_pie.png")

    # 4. Lift by decile (production)
    if deciles_prod is not None:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(deciles_prod.index.astype(str), deciles_prod["lift"], color="#1976d2", edgecolor="white")
        ax.axhline(y=1.0, color="red", linestyle="--", label="Baseline (lift=1)")
        ax.set_xlabel("Decile")
        ax.set_ylabel("Lift")
        ax.set_title("Lift by Decile — Production Population (OOT)")
        ax.legend()
        fig.tight_layout()
        fig.savefig(os.path.join(plots_dir, "scoring_lift.png"), dpi=150)
        plt.close(fig)
        print(f"[PLOT] Saved scoring_lift.png")

    # ── Scoring summary JSON ──────────────────────────────────────────
    scoring_dir = os.path.join(ARTIFACT_DIR, "scoring")
    os.makedirs(scoring_dir, exist_ok=True)

    risk_dist_all = scores_df["FAIXA_RISCO"].value_counts().to_dict()
    risk_dist_prod = prod_scores["FAIXA_RISCO"].value_counts().to_dict()
    safra_counts = scores_df.groupby("SAFRA").size().to_dict()

    def _score_stats(sdf):
        return {
            "mean": round(float(sdf["SCORE"].mean()), 2),
            "median": float(sdf["SCORE"].median()),
            "min": int(sdf["SCORE"].min()),
            "max": int(sdf["SCORE"].max()),
            "std": round(float(sdf["SCORE"].std()), 2),
        }

    summary = {
        "total_records": int(len(scores_df)),
        "train_records": int(len(scores_df[scores_df["POPULACAO"] == "TREINO"])),
        "production_records": int(len(prod_scores)),
        "train_safras": TRAIN_SAFRAS,
        "production_safras": production_safras,
        "records_per_safra": {str(k): int(v) for k, v in safra_counts.items()},
        "safra_metrics": safra_metrics,
        "score_stats_all": _score_stats(scores_df),
        "score_stats_production": _score_stats(prod_scores),
        "score_stats_train": _score_stats(scores_df[scores_df["POPULACAO"] == "TREINO"]),
        "risk_distribution_all": {str(k): int(v) for k, v in risk_dist_all.items()},
        "risk_distribution_production": {str(k): int(v) for k, v in risk_dist_prod.items()},
        "model_version": model_version,
        "preprocessing_note": "Pipeline includes SimpleImputer (training medians) + StandardScaler. No manual fillna applied.",
        "timestamp": datetime.now().isoformat(),
    }
    summary_path = os.path.join(scoring_dir, "scoring_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n[SUMMARY] Saved {summary_path}")

    print(f"\n[DONE] Batch scoring complete:")
    print(f"  Total:      {len(scores_df):,} records")
    print(f"  Training:   {summary['train_records']:,} records (for monitoring)")
    print(f"  Production: {summary['production_records']:,} records (unseen data)")
