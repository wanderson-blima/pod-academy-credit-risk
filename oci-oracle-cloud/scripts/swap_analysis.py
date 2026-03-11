"""
Swap-In / Swap-Out Analysis — OCI Data Science
Analyzes credit risk model behavior at different score cutoffs:
  - Swap-in: good customers rejected (FPD=0, score < cutoff)
  - Swap-out: bad customers approved (FPD=1, score >= cutoff)
  - Population comparison: labeled vs unlabeled score distributions
  - Cutoff impact table with recommended threshold

Usage:
    python swap_analysis.py

Requires:
    - Champion ensemble model in ARTIFACT_DIR/champion_ensemble.pkl
    - Gold final data (Parquet) in DATA_PATH
    - Selected features in ARTIFACT_DIR/selected_features.json
"""
import os
import json
import pickle
import warnings
from datetime import datetime

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Threading
NCPUS = int(os.environ.get("NOTEBOOK_OCPUS", "10"))
os.environ["OMP_NUM_THREADS"] = str(NCPUS)
os.environ["OPENBLAS_NUM_THREADS"] = str(NCPUS)
os.environ["MKL_NUM_THREADS"] = "1"

# sklearn compat patch (same as other oci/model scripts)
import sklearn.utils.validation as _val
_original_check = _val.check_array
def _patched_check(*a, **kw):
    kw.pop("force_all_finite", None)
    kw.pop("ensure_all_finite", None)
    return _original_check(*a, **kw)
_val.check_array = _patched_check

warnings.filterwarnings("ignore")

# =============================================================================
# CONFIGURATION
# =============================================================================
TARGET = "FPD"
TRAIN_SAFRAS = [202410, 202411, 202412, 202501]
OOT_SAFRAS = [202502, 202503]
NAMESPACE = os.environ.get("OCI_NAMESPACE", "grlxi07jz1mo")
GOLD_BUCKET = os.environ.get("GOLD_BUCKET", "pod-academy-gold")
ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", "/home/datascience/artifacts")
DATA_PATH = os.environ.get("DATA_PATH", "/home/datascience/data/clientes_consolidado")
CUTOFFS = [300, 400, 500, 600, 700]


# =============================================================================
# _EnsembleModel class (required for unpickling champion_ensemble.pkl)
# =============================================================================

class _EnsembleModel:
    """Wrapper for ensemble predictions supporting all 3 modes."""

    def __init__(self, mode, base_models, weights=None, meta_model=None,
                 feature_names=None):
        """
        Parameters
        ----------
        mode : str
            One of 'average', 'blend', 'stacking'.
        base_models : dict
            Mapping of model name -> fitted estimator.
        weights : np.ndarray, optional
            Weight vector for blend mode. Must sum to 1.
        meta_model : estimator, optional
            Fitted meta-learner for stacking mode.
        feature_names : list[str], optional
            Feature names used by base models.
        """
        self.mode = mode
        self.base_models = base_models
        self.weights = weights
        self.meta_model = meta_model
        self.feature_names = feature_names

    def predict_proba(self, X):
        """Generate combined probability predictions.

        Returns array of shape (n_samples, 2) with columns [P(0), P(1)].
        """
        base_probs = np.column_stack([
            m.predict_proba(X)[:, 1] for m in self.base_models.values()
        ])

        if self.mode == "average":
            probs = base_probs.mean(axis=1)
        elif self.mode == "blend":
            probs = base_probs @ self.weights
        elif self.mode == "stacking":
            probs = self.meta_model.predict_proba(base_probs)[:, 1]
        else:
            raise ValueError(f"Unknown mode: {self.mode}")

        return np.column_stack([1 - probs, probs])


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def log(msg):
    """Log with timestamp."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


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


def compute_psi(expected, actual, bins=10):
    """Population Stability Index between two distributions."""
    breakpoints = np.percentile(expected, np.linspace(0, 100, bins + 1))
    breakpoints = np.unique(breakpoints)
    breakpoints[0] = -np.inf
    breakpoints[-1] = np.inf
    expected_counts = np.histogram(expected, bins=breakpoints)[0]
    actual_counts = np.histogram(actual, bins=breakpoints)[0]
    expected_pct = (expected_counts + 1) / (len(expected) + len(breakpoints) - 1)
    actual_pct = (actual_counts + 1) / (len(actual) + len(breakpoints) - 1)
    psi = np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct))
    return round(psi, 6)


def score_population(model, df, selected_features):
    """Score a DataFrame using the champion model. Returns 0-1000 integer scores."""
    X = df[selected_features].copy()
    X.replace([np.inf, -np.inf], np.nan, inplace=True)
    X.fillna(X.median(), inplace=True)

    raw_proba = model.predict_proba(X)
    if raw_proba.ndim == 2 and raw_proba.shape[1] >= 2:
        probabilities = raw_proba[:, 1]
    else:
        probabilities = raw_proba.ravel()

    scores = ((1 - probabilities) * 1000).astype(int).clip(0, 1000)
    return scores, probabilities


# =============================================================================
# PART 1 — POPULATION COMPARISON (Labeled vs Unlabeled)
# =============================================================================

def population_comparison(df, selected_features, model, output_dir):
    """Compare score distributions of labeled vs unlabeled populations."""
    log("Part 1 — Population Comparison (Labeled vs Unlabeled)")

    # Divide populations
    labeled_mask = df[TARGET].notna() & ~df[TARGET].isna()
    df_labeled = df[labeled_mask].copy()
    df_unlabeled = df[~labeled_mask].copy()

    log(f"  Labeled:   {len(df_labeled):,} records")
    log(f"  Unlabeled: {len(df_unlabeled):,} records")

    # Score both populations
    scores_labeled, proba_labeled = score_population(model, df_labeled, selected_features)
    scores_unlabeled, proba_unlabeled = score_population(model, df_unlabeled, selected_features)

    df_labeled["SCORE"] = scores_labeled
    df_labeled["PROBABILIDADE_FPD"] = proba_labeled
    df_unlabeled["SCORE"] = scores_unlabeled
    df_unlabeled["PROBABILIDADE_FPD"] = proba_unlabeled

    # Score stats
    labeled_stats = {
        "mean": float(scores_labeled.mean()),
        "median": float(np.median(scores_labeled)),
        "std": float(scores_labeled.std()),
    }
    unlabeled_stats = {
        "mean": float(scores_unlabeled.mean()),
        "median": float(np.median(scores_unlabeled)),
        "std": float(scores_unlabeled.std()),
    } if len(scores_unlabeled) > 0 else {"mean": None, "median": None, "std": None}

    # PSI between labeled vs unlabeled
    psi_val = compute_psi(scores_labeled, scores_unlabeled) if len(scores_unlabeled) > 0 else None

    # Analysis by SAFRA
    by_safra = {}
    for safra in sorted(df["SAFRA"].unique()):
        safra_df = df[df["SAFRA"] == safra]
        safra_labeled = safra_df[safra_df[TARGET].notna()]
        safra_unlabeled = safra_df[safra_df[TARGET].isna()]
        fpd_rate = float(safra_labeled[TARGET].mean()) if len(safra_labeled) > 0 else None
        by_safra[str(int(safra))] = {
            "total": int(len(safra_df)),
            "labeled": int(len(safra_labeled)),
            "unlabeled": int(len(safra_unlabeled)),
            "fpd_rate": round(fpd_rate, 6) if fpd_rate is not None else None,
        }

    # Print summary
    print(f"\n{'='*60}")
    print("  POPULATION COMPARISON — Labeled vs Unlabeled")
    print(f"{'='*60}")
    print(f"  Labeled:   {len(df_labeled):>10,} | Mean score: {labeled_stats['mean']:.0f}")
    if len(df_unlabeled) > 0:
        print(f"  Unlabeled: {len(df_unlabeled):>10,} | Mean score: {unlabeled_stats['mean']:.0f}")
        print(f"  PSI (labeled vs unlabeled): {psi_val:.6f}")
    else:
        print(f"  Unlabeled: {len(df_unlabeled):>10,} | N/A")

    print(f"\n  {'SAFRA':<10} {'Total':>10} {'Labeled':>10} {'Unlabeled':>10} {'FPD Rate':>10}")
    print(f"  {'-'*52}")
    for safra, info in by_safra.items():
        fpd_str = f"{info['fpd_rate']:.4f}" if info['fpd_rate'] is not None else "N/A"
        print(f"  {safra:<10} {info['total']:>10,} {info['labeled']:>10,} "
              f"{info['unlabeled']:>10,} {fpd_str:>10}")

    # ── Plot: Overlay histogram labeled vs unlabeled ──────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Histogram
    ax = axes[0]
    ax.hist(scores_labeled, bins=50, alpha=0.6, color="#1976d2", label="Labeled", density=True)
    if len(scores_unlabeled) > 0:
        ax.hist(scores_unlabeled, bins=50, alpha=0.6, color="#f57c00", label="Unlabeled", density=True)
    ax.set_xlabel("Score (0-1000)")
    ax.set_ylabel("Density")
    ax.set_title("Score Distribution: Labeled vs Unlabeled")
    ax.legend()

    # KDE
    ax = axes[1]
    from scipy.stats import gaussian_kde
    kde_labeled = gaussian_kde(scores_labeled)
    x_range = np.linspace(0, 1000, 200)
    ax.plot(x_range, kde_labeled(x_range), color="#1976d2", linewidth=2, label="Labeled")
    if len(scores_unlabeled) > 0:
        kde_unlabeled = gaussian_kde(scores_unlabeled)
        ax.plot(x_range, kde_unlabeled(x_range), color="#f57c00", linewidth=2, label="Unlabeled")
    ax.set_xlabel("Score (0-1000)")
    ax.set_ylabel("Density")
    ax.set_title("KDE: Labeled vs Unlabeled")
    ax.legend()

    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "swap_distributions.png"), dpi=150)
    plt.close(fig)
    log("  Saved swap_distributions.png")

    # ── Plot: Labeled/Unlabeled breakdown per SAFRA ───────────────────────
    safras = sorted(by_safra.keys())
    labeled_counts = [by_safra[s]["labeled"] for s in safras]
    unlabeled_counts = [by_safra[s]["unlabeled"] for s in safras]

    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(safras))
    width = 0.35
    ax.bar(x - width / 2, labeled_counts, width, label="Labeled", color="#1976d2")
    ax.bar(x + width / 2, unlabeled_counts, width, label="Unlabeled", color="#f57c00")
    ax.set_xlabel("SAFRA")
    ax.set_ylabel("Count")
    ax.set_title("Labeled vs Unlabeled Records per SAFRA")
    ax.set_xticks(x)
    ax.set_xticklabels(safras)
    ax.legend()
    for i, (lc, uc) in enumerate(zip(labeled_counts, unlabeled_counts)):
        ax.text(i - width / 2, lc + max(labeled_counts + unlabeled_counts) * 0.01,
                f"{lc:,}", ha="center", va="bottom", fontsize=7)
        ax.text(i + width / 2, uc + max(labeled_counts + unlabeled_counts) * 0.01,
                f"{uc:,}", ha="center", va="bottom", fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "swap_by_safra.png"), dpi=150)
    plt.close(fig)
    log("  Saved swap_by_safra.png")

    return df_labeled, df_unlabeled, labeled_stats, unlabeled_stats, psi_val, by_safra


# =============================================================================
# PART 2 — SWAP-IN / SWAP-OUT CUTOFF ANALYSIS
# =============================================================================

def cutoff_analysis(df_labeled, df_unlabeled, output_dir):
    """Analyze swap-in / swap-out at each score cutoff."""
    log("Part 2 — Swap-In / Swap-Out Cutoff Analysis")

    fpd_rate_overall = float(df_labeled[TARGET].mean())
    total_labeled = len(df_labeled)

    print(f"\n{'='*70}")
    print("  SWAP-IN / SWAP-OUT ANALYSIS BY CUTOFF")
    print(f"{'='*70}")
    print(f"  Total labeled: {total_labeled:,} | Overall FPD rate: {fpd_rate_overall:.4f}")
    print(f"  {'Cutoff':>8} {'Approved':>10} {'Appr%':>7} {'FPD_Appr':>9} "
          f"{'Rejected':>10} {'FPD_Rej':>8} {'SwapIn':>8} {'SwapOut':>8}")
    print(f"  {'-'*78}")

    cutoff_results = []

    for cutoff in CUTOFFS:
        approved = df_labeled[df_labeled["SCORE"] >= cutoff]
        rejected = df_labeled[df_labeled["SCORE"] < cutoff]

        approved_count = len(approved)
        rejected_count = len(rejected)
        approved_pct = approved_count / total_labeled * 100 if total_labeled > 0 else 0

        approved_fpd_rate = float(approved[TARGET].mean()) if approved_count > 0 else 0.0
        rejected_fpd_rate = float(rejected[TARGET].mean()) if rejected_count > 0 else 0.0

        # Swap-in: good customers among rejected (FPD=0, score < cutoff)
        swap_in_count = int((rejected[TARGET] == 0).sum()) if rejected_count > 0 else 0
        swap_in_pct = swap_in_count / rejected_count * 100 if rejected_count > 0 else 0.0

        # Swap-out: bad customers among approved (FPD=1, score >= cutoff)
        swap_out_count = int((approved[TARGET] == 1).sum()) if approved_count > 0 else 0
        swap_out_pct = swap_out_count / approved_count * 100 if approved_count > 0 else 0.0

        cutoff_results.append({
            "cutoff": cutoff,
            "approved_count": int(approved_count),
            "approved_pct": round(approved_pct, 2),
            "approved_fpd_rate": round(approved_fpd_rate, 6),
            "rejected_count": int(rejected_count),
            "rejected_fpd_rate": round(rejected_fpd_rate, 6),
            "swap_in_count": swap_in_count,
            "swap_in_pct_of_rejected": round(swap_in_pct, 2),
            "swap_out_count": swap_out_count,
            "swap_out_pct_of_approved": round(swap_out_pct, 2),
        })

        print(f"  {cutoff:>8} {approved_count:>10,} {approved_pct:>6.1f}% "
              f"{approved_fpd_rate:>9.4f} {rejected_count:>10,} {rejected_fpd_rate:>8.4f} "
              f"{swap_in_count:>8,} {swap_out_count:>8,}")

    # ── Recommend optimal cutoff ──────────────────────────────────────────
    # Heuristic: maximize approval while keeping FPD rate under 2x overall
    recommended = None
    rationale = ""
    for entry in cutoff_results:
        if entry["approved_fpd_rate"] <= fpd_rate_overall * 2.0 and entry["approved_pct"] >= 30:
            recommended = entry["cutoff"]
            rationale = (
                f"Cutoff {recommended} approves {entry['approved_pct']:.1f}% of population "
                f"with FPD rate {entry['approved_fpd_rate']:.4f} "
                f"(<= 2x overall rate {fpd_rate_overall:.4f}). "
                f"Swap-out: {entry['swap_out_count']:,} bad customers "
                f"({entry['swap_out_pct_of_approved']:.1f}% of approved)."
            )
    if recommended is None:
        # Fallback: pick the cutoff with lowest approved FPD rate that has >= 10% approval
        viable = [e for e in cutoff_results if e["approved_pct"] >= 10]
        if viable:
            best = min(viable, key=lambda e: e["approved_fpd_rate"])
            recommended = best["cutoff"]
            rationale = (
                f"Cutoff {recommended} selected as best trade-off: "
                f"{best['approved_pct']:.1f}% approval, "
                f"FPD rate {best['approved_fpd_rate']:.4f}."
            )
        else:
            recommended = CUTOFFS[-1]
            rationale = "No cutoff meets criteria; defaulting to highest cutoff."

    print(f"\n  Recommended cutoff: {recommended}")
    print(f"  Rationale: {rationale}")

    # ── Unlabeled risk projection ─────────────────────────────────────────
    if len(df_unlabeled) > 0:
        print(f"\n  UNLABELED RISK PROJECTION:")
        for cutoff in CUTOFFS:
            n_above = int((df_unlabeled["SCORE"] >= cutoff).sum())
            n_below = int((df_unlabeled["SCORE"] < cutoff).sum())
            pct_above = n_above / len(df_unlabeled) * 100
            print(f"    Cutoff {cutoff}: {n_above:>8,} ({pct_above:>5.1f}%) would be approved")

    # ── Plot: Approval rate vs FPD rate by cutoff ─────────────────────────
    fig, ax1 = plt.subplots(figsize=(10, 5))
    cutoff_vals = [e["cutoff"] for e in cutoff_results]
    approval_rates = [e["approved_pct"] for e in cutoff_results]
    fpd_rates = [e["approved_fpd_rate"] * 100 for e in cutoff_results]

    color1 = "#1976d2"
    color2 = "#d32f2f"
    ax1.set_xlabel("Score Cutoff")
    ax1.set_ylabel("Approval Rate (%)", color=color1)
    ax1.plot(cutoff_vals, approval_rates, "o-", color=color1, linewidth=2, markersize=8,
             label="Approval Rate (%)")
    ax1.tick_params(axis="y", labelcolor=color1)

    ax2 = ax1.twinx()
    ax2.set_ylabel("FPD Rate of Approved (%)", color=color2)
    ax2.plot(cutoff_vals, fpd_rates, "s--", color=color2, linewidth=2, markersize=8,
             label="FPD Rate (%)")
    ax2.tick_params(axis="y", labelcolor=color2)

    # Mark recommended cutoff
    if recommended in cutoff_vals:
        idx = cutoff_vals.index(recommended)
        ax1.axvline(x=recommended, color="#388e3c", linestyle=":", linewidth=2,
                     label=f"Recommended ({recommended})")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="center left")
    ax1.set_title("Approval Rate vs FPD Rate by Score Cutoff")
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "swap_cutoff_analysis.png"), dpi=150)
    plt.close(fig)
    log("  Saved swap_cutoff_analysis.png")

    # ── Plot: Impact table as visual table ────────────────────────────────
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.axis("off")
    col_labels = ["Cutoff", "Approved", "Appr%", "FPD Rate\n(Approved)",
                  "Rejected", "FPD Rate\n(Rejected)", "Swap-In\n(Good Lost)",
                  "Swap-Out\n(Bad Passed)"]
    table_data = []
    for e in cutoff_results:
        table_data.append([
            str(e["cutoff"]),
            f"{e['approved_count']:,}",
            f"{e['approved_pct']:.1f}%",
            f"{e['approved_fpd_rate']:.4f}",
            f"{e['rejected_count']:,}",
            f"{e['rejected_fpd_rate']:.4f}",
            f"{e['swap_in_count']:,} ({e['swap_in_pct_of_rejected']:.1f}%)",
            f"{e['swap_out_count']:,} ({e['swap_out_pct_of_approved']:.1f}%)",
        ])

    table = ax.table(cellText=table_data, colLabels=col_labels, loc="center",
                     cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.0, 1.6)

    # Color header
    for j in range(len(col_labels)):
        table[0, j].set_facecolor("#1976d2")
        table[0, j].set_text_props(color="white", fontweight="bold")

    # Highlight recommended row
    if recommended in [e["cutoff"] for e in cutoff_results]:
        row_idx = [e["cutoff"] for e in cutoff_results].index(recommended) + 1
        for j in range(len(col_labels)):
            table[row_idx, j].set_facecolor("#e8f5e9")

    ax.set_title("Swap-In / Swap-Out Impact Table", fontsize=12, fontweight="bold", pad=20)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "swap_impact_table.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    log("  Saved swap_impact_table.png")

    return cutoff_results, recommended, rationale


# =============================================================================
# MAIN
# =============================================================================

def main():
    import pyarrow.parquet as pq

    print("=" * 70)
    print("  SWAP-IN / SWAP-OUT ANALYSIS — OCI Data Science")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # ── Load selected features ────────────────────────────────────────────
    features_path = os.path.join(ARTIFACT_DIR, "selected_features.json")
    if os.path.exists(features_path):
        with open(features_path) as f:
            feat_data = json.load(f)
        if isinstance(feat_data, dict):
            selected_features = feat_data.get("features") or feat_data.get("selected_features")
            if selected_features is None:
                print(f"[ERROR] Dict keys found: {list(feat_data.keys())}. Expected 'features' or 'selected_features'.")
                exit(1)
        else:
            selected_features = feat_data
        log(f"Loaded {len(selected_features)} features from selected_features.json")
    else:
        print(f"[ERROR] selected_features.json not found at {features_path}")
        exit(1)

    # ── Load champion ensemble model ──────────────────────────────────────
    champion_path = os.path.join(ARTIFACT_DIR, "models", "champion_ensemble.pkl")
    if not os.path.exists(champion_path):
        champion_path = os.path.join(ARTIFACT_DIR, "champion_ensemble.pkl")
    if not os.path.exists(champion_path):
        # Try ensemble_model.pkl
        champion_path = os.path.join(ARTIFACT_DIR, "models", "ensemble_model.pkl")
    if not os.path.exists(champion_path):
        champion_path = os.path.join(ARTIFACT_DIR, "ensemble_model.pkl")

    if not os.path.exists(champion_path):
        print(f"[ERROR] No champion ensemble found. Searched in {ARTIFACT_DIR}")
        exit(1)

    log(f"Loading champion model: {champion_path}")
    with open(champion_path, "rb") as f:
        champion_model = pickle.load(f)
    log(f"Champion loaded (mode={getattr(champion_model, 'mode', 'pipeline')})")

    # ── Load Gold data ────────────────────────────────────────────────────
    log(f"Loading Gold data from {DATA_PATH}")
    columns_to_load = selected_features + [TARGET, "SAFRA", "NUM_CPF"]
    if os.path.isdir(DATA_PATH):
        table = pq.read_table(DATA_PATH, columns=columns_to_load)
        df = table.to_pandas(self_destruct=True)
    else:
        df = pd.read_parquet(DATA_PATH, columns=columns_to_load)
    log(f"Loaded {len(df):,} records, {len(df['SAFRA'].unique())} SAFRAs")

    # Replace inf with NaN globally
    df[selected_features] = df[selected_features].replace([np.inf, -np.inf], np.nan)

    # ── Create output directory ───────────────────────────────────────────
    output_dir = os.path.join(ARTIFACT_DIR, "swap_analysis")
    os.makedirs(output_dir, exist_ok=True)

    # ── Part 1: Population Comparison ─────────────────────────────────────
    (df_labeled, df_unlabeled,
     labeled_stats, unlabeled_stats,
     psi_val, by_safra) = population_comparison(df, selected_features, champion_model, output_dir)

    # ── Part 2: Cutoff Analysis ───────────────────────────────────────────
    cutoff_results, recommended_cutoff, recommendation_rationale = cutoff_analysis(
        df_labeled, df_unlabeled, output_dir,
    )

    # ── Build and save summary JSON ───────────────────────────────────────
    labeled_fpd_rate = float(df_labeled[TARGET].mean()) if len(df_labeled) > 0 else None
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_records": int(len(df)),
        "labeled_records": int(len(df_labeled)),
        "unlabeled_records": int(len(df_unlabeled)),
        "labeled_fpd_rate": round(labeled_fpd_rate, 6) if labeled_fpd_rate is not None else None,
        "psi_labeled_vs_unlabeled": psi_val,
        "score_stats": {
            "labeled": labeled_stats,
            "unlabeled": unlabeled_stats,
        },
        "by_safra": by_safra,
        "cutoff_analysis": cutoff_results,
        "recommended_cutoff": recommended_cutoff,
        "recommendation_rationale": recommendation_rationale,
    }

    summary_path = os.path.join(output_dir, "swap_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    log(f"Saved {summary_path}")

    # ── Final summary ─────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print("  SWAP ANALYSIS COMPLETE")
    print(f"{'='*70}")
    print(f"  Total records:     {len(df):>10,}")
    print(f"  Labeled:           {len(df_labeled):>10,}")
    print(f"  Unlabeled:         {len(df_unlabeled):>10,}")
    print(f"  Labeled FPD rate:  {labeled_fpd_rate:.4f}" if labeled_fpd_rate else "  Labeled FPD rate:  N/A")
    print(f"  PSI (L vs U):      {psi_val:.6f}" if psi_val is not None else "  PSI (L vs U):      N/A")
    print(f"  Recommended cutoff: {recommended_cutoff}")
    print(f"  Rationale: {recommendation_rationale}")
    print(f"\n  Outputs saved to: {output_dir}/")
    print(f"    - swap_summary.json")
    print(f"    - swap_distributions.png")
    print(f"    - swap_cutoff_analysis.png")
    print(f"    - swap_by_safra.png")
    print(f"    - swap_impact_table.png")
    print(f"{'='*70}")

    return summary


if __name__ == "__main__":
    main()
