"""
Confusion Matrix Analysis — OCI Data Science
Computes confusion matrices at multiple cutoffs, contingency per risk band,
gain/lift analysis, and financial impact simulation.

Outputs:
    artifacts/metrics/confusion_matrix_results.json
    artifacts/plots/confusion_matrix_cutoff700.png
    artifacts/plots/confusion_matrix_multi_threshold.png
    artifacts/plots/confusion_matrix_per_band.png
    artifacts/plots/gain_lift_chart.png
    artifacts/plots/financial_impact_analysis.png

Usage:
    python confusion_matrix_analysis.py
"""
import os
import sys
import json
import pickle
import warnings
from datetime import datetime

# Unbuffered output
sys.stdout.reconfigure(line_buffering=True)
os.environ["PYTHONUNBUFFERED"] = "1"

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
LGD = 44.89  # Loss Given Default proxy (R$)
RISK_BANDS = {
    "CRITICO": (0, 299),
    "ALTO": (300, 499),
    "MEDIO": (500, 699),
    "BAIXO": (700, 1000),
}


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


def mem_usage():
    """Return current RSS in MB (if psutil available)."""
    try:
        import psutil
        return f" [RSS={psutil.Process().memory_info().rss / 1024**2:.0f} MB]"
    except ImportError:
        return ""


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


def prob_to_score(prob, base=600, pdo=20, odds_ref=50):
    """Convert default probability to credit score (0-1000 scale)."""
    prob = np.clip(prob, 1e-10, 1 - 1e-10)
    odds = (1 - prob) / prob
    return np.round(base + pdo * np.log(odds / odds_ref) / np.log(2)).astype(int)


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
# ANALYSIS FUNCTIONS
# =============================================================================

def confusion_at_cutoff(y_true, scores, cutoff):
    """Compute confusion matrix metrics at a given score cutoff.

    Credit risk context:
        approved = score >= cutoff
        TP = approved AND good (FPD=0) — revenue
        FP = approved AND bad  (FPD=1) — loss (most critical)
        TN = rejected AND bad  (FPD=1) — risk avoided
        FN = rejected AND good (FPD=0) — lost revenue

    Returns dict with TP, FP, TN, FN + derived metrics.
    """
    approved = scores >= cutoff
    rejected = ~approved
    good = y_true == 0
    bad = y_true == 1

    tp = int((approved & good).sum())
    fp = int((approved & bad).sum())
    tn = int((rejected & bad).sum())
    fn = int((rejected & good).sum())

    total = tp + fp + tn + fn
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / total if total > 0 else 0.0

    return {
        "cutoff": cutoff,
        "TP": tp,
        "FP": fp,
        "TN": tn,
        "FN": fn,
        "total": total,
        "approved": int(approved.sum()),
        "rejected": int(rejected.sum()),
        "approval_rate": round(approved.sum() / total * 100, 2) if total > 0 else 0.0,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "specificity": round(specificity, 6),
        "f1": round(f1, 6),
        "accuracy": round(accuracy, 6),
        "fpd_rate_approved": round(fp / (tp + fp) * 100, 4) if (tp + fp) > 0 else 0.0,
        "fpd_rate_rejected": round(tn / (tn + fn) * 100, 4) if (tn + fn) > 0 else 0.0,
    }


def confusion_per_band(y_true, scores, bands=None):
    """Contingency table by risk band.

    Returns list of dicts, one per band, with total, fpd_count, fpd_rate, good_count.
    """
    if bands is None:
        bands = RISK_BANDS

    results = []
    for band_name, (lo, hi) in bands.items():
        mask = (scores >= lo) & (scores <= hi)
        band_y = y_true[mask]
        total = int(mask.sum())
        fpd_count = int((band_y == 1).sum())
        good_count = int((band_y == 0).sum())
        fpd_rate = round(fpd_count / total * 100, 4) if total > 0 else 0.0

        results.append({
            "band": band_name,
            "range": f"{lo}-{hi}",
            "total": total,
            "good_count": good_count,
            "fpd_count": fpd_count,
            "fpd_rate": fpd_rate,
            "pct_of_total": round(total / len(y_true) * 100, 2) if len(y_true) > 0 else 0.0,
        })

    return results


def decile_gain_lift(y_true, y_prob):
    """Compute gain/lift chart data by deciles.

    Sorts by predicted probability of default (descending), splits into 10 deciles,
    and computes cumulative gain and lift per decile.

    Returns DataFrame with decile, n_total, n_bad, bad_rate, cum_bad_pct, cum_total_pct, lift.
    """
    df = pd.DataFrame({"y_true": y_true, "y_prob": y_prob})
    df = df.sort_values("y_prob", ascending=False).reset_index(drop=True)

    n = len(df)
    total_bad = df["y_true"].sum()
    decile_size = n // 10

    rows = []
    cum_bad = 0
    cum_total = 0

    for i in range(10):
        start = i * decile_size
        end = start + decile_size if i < 9 else n
        decile_df = df.iloc[start:end]

        n_total = len(decile_df)
        n_bad = int(decile_df["y_true"].sum())
        bad_rate = n_bad / n_total if n_total > 0 else 0.0

        cum_bad += n_bad
        cum_total += n_total

        cum_bad_pct = cum_bad / total_bad if total_bad > 0 else 0.0
        cum_total_pct = cum_total / n

        # Lift = (cumulative bad rate in top deciles) / (overall bad rate)
        cum_bad_rate = cum_bad / cum_total if cum_total > 0 else 0.0
        overall_bad_rate = total_bad / n if n > 0 else 0.0
        lift = cum_bad_rate / overall_bad_rate if overall_bad_rate > 0 else 0.0

        rows.append({
            "decile": i + 1,
            "n_total": n_total,
            "n_bad": n_bad,
            "bad_rate": round(bad_rate, 6),
            "cum_bad": cum_bad,
            "cum_bad_pct": round(cum_bad_pct, 6),
            "cum_total_pct": round(cum_total_pct, 6),
            "lift": round(lift, 4),
        })

    return pd.DataFrame(rows)


def financial_impact(cutoff_data_list, lgd=LGD):
    """Financial simulation per cutoff.

    Revenue per approved good customer = lgd (same ticket proxy).
    Loss per approved bad customer = lgd.
    Net impact = revenue_good - loss_bad.
    Baseline = all approved (no model).

    Returns list of dicts with financial metrics per cutoff.
    """
    # Baseline: all approved
    baseline_entry = cutoff_data_list[0]  # We'll compute from totals
    total_good = sum(e["TP"] + e["FN"] for e in cutoff_data_list[:1])
    total_bad = sum(e["FP"] + e["TN"] for e in cutoff_data_list[:1])

    # Recalculate from first entry (all cutoff entries share same total)
    total_good = cutoff_data_list[0]["TP"] + cutoff_data_list[0]["FN"]
    total_bad = cutoff_data_list[0]["FP"] + cutoff_data_list[0]["TN"]
    baseline_revenue = total_good * lgd
    baseline_loss = total_bad * lgd
    baseline_net = baseline_revenue - baseline_loss

    results = []
    for entry in cutoff_data_list:
        revenue_good = entry["TP"] * lgd
        loss_bad = entry["FP"] * lgd
        net_impact = revenue_good - loss_bad
        avoided_loss = entry["TN"] * lgd
        lost_revenue = entry["FN"] * lgd
        net_vs_baseline = net_impact - baseline_net

        results.append({
            "cutoff": entry["cutoff"],
            "approved": entry["approved"],
            "approval_rate": entry["approval_rate"],
            "revenue_good": round(revenue_good, 2),
            "loss_bad": round(loss_bad, 2),
            "net_impact": round(net_impact, 2),
            "avoided_loss": round(avoided_loss, 2),
            "lost_revenue": round(lost_revenue, 2),
            "net_vs_baseline": round(net_vs_baseline, 2),
            "net_vs_baseline_pct": round(
                net_vs_baseline / abs(baseline_net) * 100, 2
            ) if baseline_net != 0 else 0.0,
        })

    # Prepend baseline
    baseline = {
        "cutoff": 0,
        "approved": total_good + total_bad,
        "approval_rate": 100.0,
        "revenue_good": round(baseline_revenue, 2),
        "loss_bad": round(baseline_loss, 2),
        "net_impact": round(baseline_net, 2),
        "avoided_loss": 0.0,
        "lost_revenue": 0.0,
        "net_vs_baseline": 0.0,
        "net_vs_baseline_pct": 0.0,
    }

    return [baseline] + results


# =============================================================================
# PLOT FUNCTIONS
# =============================================================================

def plot_confusion_heatmap(cm_dict, title, save_path):
    """2x2 confusion matrix heatmap using matplotlib (no seaborn).

    Layout:
                    Predicted
                Aprovado   Rejeitado
    Actual  Adimplente   TP        FN
            Inadimplente FP        TN
    """
    tp, fp, tn, fn = cm_dict["TP"], cm_dict["FP"], cm_dict["TN"], cm_dict["FN"]
    total = tp + fp + tn + fn
    matrix = np.array([[tp, fn], [fp, tn]])
    pct_matrix = matrix / total * 100 if total > 0 else matrix * 0.0

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(matrix, cmap="RdYlGn", aspect="auto", interpolation="nearest")

    # Annotate cells with count + percentage
    for i in range(2):
        for j in range(2):
            color = "white" if matrix[i, j] > matrix.max() * 0.7 or matrix[i, j] < matrix.max() * 0.3 else "black"
            ax.text(j, i, f"{matrix[i, j]:,}\n({pct_matrix[i, j]:.1f}%)",
                    ha="center", va="center", fontsize=14, fontweight="bold", color=color)

    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Aprovado", "Rejeitado"], fontsize=12)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["Adimplente\n(FPD=0)", "Inadimplente\n(FPD=1)"], fontsize=12)
    ax.set_xlabel("Predicted (Decisao do Modelo)", fontsize=12, labelpad=10)
    ax.set_ylabel("Actual (Resultado Real)", fontsize=12, labelpad=10)
    ax.set_title(title, fontsize=13, fontweight="bold", pad=15)

    plt.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_multi_threshold(df_thresholds, save_path):
    """Precision/Recall/F1/Specificity curves + stacked bar TP/FP/TN/FN vs cutoff.

    2 subplots side by side.
    """
    cutoffs = [e["cutoff"] for e in df_thresholds]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # Subplot 1: Metric curves
    ax1.plot(cutoffs, [e["precision"] for e in df_thresholds], "o-",
             color="#1976d2", linewidth=2, label="Precision")
    ax1.plot(cutoffs, [e["recall"] for e in df_thresholds], "s-",
             color="#388e3c", linewidth=2, label="Recall")
    ax1.plot(cutoffs, [e["f1"] for e in df_thresholds], "^-",
             color="#f57c00", linewidth=2, label="F1-Score")
    ax1.plot(cutoffs, [e["specificity"] for e in df_thresholds], "D-",
             color="#d32f2f", linewidth=2, label="Specificity")
    ax1.set_xlabel("Score Cutoff", fontsize=11)
    ax1.set_ylabel("Metrica", fontsize=11)
    ax1.set_title("Metricas por Cutoff", fontsize=12, fontweight="bold")
    ax1.legend(loc="best")
    ax1.set_ylim(0, 1.05)
    ax1.grid(True, alpha=0.3)

    # Subplot 2: Stacked bar TP/FP/TN/FN
    tp_vals = [e["TP"] for e in df_thresholds]
    fp_vals = [e["FP"] for e in df_thresholds]
    tn_vals = [e["TN"] for e in df_thresholds]
    fn_vals = [e["FN"] for e in df_thresholds]

    x = np.arange(len(cutoffs))
    width = 0.6

    ax2.bar(x, tp_vals, width, label="TP (Bom Aprovado)", color="#388e3c")
    ax2.bar(x, fp_vals, width, bottom=tp_vals, label="FP (Mau Aprovado)", color="#d32f2f")
    bottom_2 = [t + f for t, f in zip(tp_vals, fp_vals)]
    ax2.bar(x, tn_vals, width, bottom=bottom_2, label="TN (Mau Rejeitado)", color="#f57c00")
    bottom_3 = [b + t for b, t in zip(bottom_2, tn_vals)]
    ax2.bar(x, fn_vals, width, bottom=bottom_3, label="FN (Bom Rejeitado)", color="#fbc02d")

    ax2.set_xlabel("Score Cutoff", fontsize=11)
    ax2.set_ylabel("Quantidade", fontsize=11)
    ax2.set_title("Composicao da Matriz por Cutoff", fontsize=12, fontweight="bold")
    ax2.set_xticks(x)
    ax2.set_xticklabels([str(c) for c in cutoffs])
    ax2.legend(loc="upper right", fontsize=9)
    ax2.grid(True, alpha=0.3, axis="y")

    fig.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_per_band_contingency(df_bands, save_path):
    """Grouped bars FPD=0 vs FPD=1 per risk band.

    Green = adimplente, Red = inadimplente.
    FPD rate labels on bars.
    """
    bands = [e["band"] for e in df_bands]
    good_counts = [e["good_count"] for e in df_bands]
    fpd_counts = [e["fpd_count"] for e in df_bands]
    fpd_rates = [e["fpd_rate"] for e in df_bands]

    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(bands))
    width = 0.35

    bars_good = ax.bar(x - width / 2, good_counts, width,
                       label="Adimplente (FPD=0)", color="#388e3c", edgecolor="white")
    bars_bad = ax.bar(x + width / 2, fpd_counts, width,
                      label="Inadimplente (FPD=1)", color="#d32f2f", edgecolor="white")

    # Add FPD rate labels above bad bars
    for i, (bar, rate) in enumerate(zip(bars_bad, fpd_rates)):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(fpd_counts) * 0.02,
                f"FPD: {rate:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold",
                color="#d32f2f")

    # Add count labels on good bars
    for bar, count in zip(bars_good, good_counts):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(good_counts) * 0.01,
                f"{count:,}", ha="center", va="bottom", fontsize=8, color="#388e3c")

    ax.set_xlabel("Faixa de Risco", fontsize=11)
    ax.set_ylabel("Quantidade de Clientes", fontsize=11)
    ax.set_title("Contingencia por Faixa de Risco", fontsize=13, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{b}\n({df_bands[i]['range']})" for i, b in enumerate(bands)], fontsize=10)
    ax.legend(loc="upper left", fontsize=10)
    ax.grid(True, alpha=0.3, axis="y")

    fig.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_gain_lift(decile_df, save_path):
    """Gain curve + Lift chart (1x2 subplots).

    Left: cumulative gain curve with diagonal reference + shaded area.
    Right: lift per decile as bars.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Left: Cumulative Gain Curve
    cum_total_pct = [0.0] + decile_df["cum_total_pct"].tolist()
    cum_bad_pct = [0.0] + decile_df["cum_bad_pct"].tolist()

    ax1.plot(cum_total_pct, cum_bad_pct, "o-", color="#1976d2", linewidth=2,
             markersize=6, label="Modelo (Champion Ensemble)")
    ax1.plot([0, 1], [0, 1], "--", color="#999999", linewidth=1.5, label="Modelo Aleatorio")
    ax1.fill_between(cum_total_pct, cum_bad_pct, cum_total_pct, alpha=0.15, color="#1976d2")
    ax1.set_xlabel("% Populacao Analisada (Cumulativo)", fontsize=11)
    ax1.set_ylabel("% Inadimplentes Capturados (Cumulativo)", fontsize=11)
    ax1.set_title("Curva de Ganho (Gain Chart)", fontsize=12, fontweight="bold")
    ax1.legend(loc="lower right")
    ax1.set_xlim(0, 1)
    ax1.set_ylim(0, 1.05)
    ax1.grid(True, alpha=0.3)

    # Right: Lift per Decile
    deciles = decile_df["decile"].values
    lifts = decile_df["lift"].values

    colors = ["#d32f2f" if l > 1.5 else "#f57c00" if l > 1.0 else "#388e3c" for l in lifts]
    bars = ax2.bar(deciles, lifts, color=colors, edgecolor="white")
    ax2.axhline(y=1.0, color="#999999", linestyle="--", linewidth=1.5, label="Baseline (lift=1)")

    # Label bars
    for bar, lift in zip(bars, lifts):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                 f"{lift:.2f}", ha="center", va="bottom", fontsize=9, fontweight="bold")

    ax2.set_xlabel("Decil (1 = maior risco)", fontsize=11)
    ax2.set_ylabel("Lift Cumulativo", fontsize=11)
    ax2.set_title("Lift por Decil", fontsize=12, fontweight="bold")
    ax2.set_xticks(deciles)
    ax2.legend(loc="upper right")
    ax2.grid(True, alpha=0.3, axis="y")

    fig.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_financial_impact(df_financial, save_path):
    """Revenue vs Loss bars + net revenue line.

    Twin axes: bars for gross revenue and loss, line for net.
    """
    # Skip baseline (index 0) for the bar chart, but include it as reference
    entries = df_financial  # includes baseline at index 0
    cutoff_labels = [str(e["cutoff"]) if e["cutoff"] > 0 else "Sem\nModelo" for e in entries]
    revenues = [e["revenue_good"] for e in entries]
    losses = [e["loss_bad"] for e in entries]
    nets = [e["net_impact"] for e in entries]

    fig, ax1 = plt.subplots(figsize=(12, 6))

    x = np.arange(len(entries))
    width = 0.35

    bars_rev = ax1.bar(x - width / 2, [r / 1000 for r in revenues], width,
                       label="Receita Clientes Bons (R$ mil)", color="#388e3c", alpha=0.8)
    bars_loss = ax1.bar(x + width / 2, [l / 1000 for l in losses], width,
                        label="Perda Clientes Maus (R$ mil)", color="#d32f2f", alpha=0.8)

    ax1.set_xlabel("Score Cutoff", fontsize=11)
    ax1.set_ylabel("Valor (R$ mil)", fontsize=11)
    ax1.set_xticks(x)
    ax1.set_xticklabels(cutoff_labels, fontsize=10)
    ax1.legend(loc="upper left", fontsize=9)
    ax1.grid(True, alpha=0.3, axis="y")

    # Net impact line on twin axis
    ax2 = ax1.twinx()
    ax2.plot(x, [n / 1000 for n in nets], "D-", color="#1976d2", linewidth=2.5,
             markersize=8, label="Resultado Liquido (R$ mil)")
    ax2.set_ylabel("Resultado Liquido (R$ mil)", fontsize=11, color="#1976d2")
    ax2.tick_params(axis="y", labelcolor="#1976d2")

    # Mark baseline
    ax2.axhline(y=nets[0] / 1000, color="#999999", linestyle=":", linewidth=1,
                label=f"Baseline (sem modelo): R$ {nets[0]/1000:.1f}k")

    lines2, labels2 = ax2.get_legend_handles_labels()
    ax2.legend(lines2, labels2, loc="upper right", fontsize=9)

    ax1.set_title("Impacto Financeiro por Cutoff (LGD = R$ {:.2f})".format(LGD),
                  fontsize=13, fontweight="bold")

    fig.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# =============================================================================
# MAIN
# =============================================================================

def main():
    import pyarrow.parquet as pq

    print("=" * 70)
    print("  CONFUSION MATRIX ANALYSIS — OCI Data Science")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    log(f"Starting confusion matrix analysis{mem_usage()}")

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
        champion_path = os.path.join(ARTIFACT_DIR, "models", "ensemble_model.pkl")
    if not os.path.exists(champion_path):
        champion_path = os.path.join(ARTIFACT_DIR, "ensemble_model.pkl")

    if not os.path.exists(champion_path):
        print(f"[ERROR] No champion ensemble found. Searched in {ARTIFACT_DIR}")
        exit(1)

    log(f"Loading champion model: {champion_path}")
    with open(champion_path, "rb") as f:
        champion_model = pickle.load(f)
    log(f"Champion loaded (mode={getattr(champion_model, 'mode', 'pipeline')}){mem_usage()}")

    # ── Load Gold data ────────────────────────────────────────────────────
    log(f"Loading Gold data from {DATA_PATH}")
    columns_to_load = selected_features + [TARGET, "SAFRA", "NUM_CPF"]
    if os.path.isdir(DATA_PATH):
        table = pq.read_table(DATA_PATH, columns=columns_to_load)
        df = table.to_pandas(self_destruct=True)
    else:
        df = pd.read_parquet(DATA_PATH, columns=columns_to_load)
    log(f"Loaded {len(df):,} records, {len(df['SAFRA'].unique())} SAFRAs{mem_usage()}")

    # Replace inf with NaN globally
    df[selected_features] = df[selected_features].replace([np.inf, -np.inf], np.nan)

    # ── Score the base ────────────────────────────────────────────────────
    log("Scoring entire base...")
    scores, probabilities = score_population(champion_model, df, selected_features)
    df["SCORE"] = scores
    df["PROBABILIDADE_FPD"] = probabilities
    df["FAIXA_RISCO"] = [risk_band(s) for s in scores]
    log(f"Scoring complete: mean={scores.mean():.0f}, min={scores.min()}, max={scores.max()}{mem_usage()}")

    # ── Filter to labeled (FPD not null) ──────────────────────────────────
    labeled_mask = df[TARGET].notna() & ~df[TARGET].isna()
    df_labeled = df[labeled_mask].copy()
    df_labeled[TARGET] = df_labeled[TARGET].astype(int)
    log(f"Labeled records: {len(df_labeled):,} (filtered from {len(df):,})")
    log(f"FPD distribution: 0={int((df_labeled[TARGET]==0).sum()):,}, 1={int((df_labeled[TARGET]==1).sum()):,}")

    y_true = df_labeled[TARGET].values
    y_scores = df_labeled["SCORE"].values
    y_prob = df_labeled["PROBABILIDADE_FPD"].values

    # ── Create output directories ─────────────────────────────────────────
    metrics_dir = os.path.join(ARTIFACT_DIR, "metrics")
    plots_dir = os.path.join(ARTIFACT_DIR, "plots")
    os.makedirs(metrics_dir, exist_ok=True)
    os.makedirs(plots_dir, exist_ok=True)

    # ═════════════════════════════════════════════════════════════════════
    # PART 1 — Confusion Matrix at each cutoff
    # ═════════════════════════════════════════════════════════════════════
    log("Part 1 — Confusion matrices at multiple cutoffs")
    cutoff_results = []
    for cutoff in CUTOFFS:
        cm = confusion_at_cutoff(y_true, y_scores, cutoff)
        cutoff_results.append(cm)
        log(f"  Cutoff {cutoff}: TP={cm['TP']:,} FP={cm['FP']:,} "
            f"TN={cm['TN']:,} FN={cm['FN']:,} | "
            f"Prec={cm['precision']:.4f} Rec={cm['recall']:.4f} "
            f"F1={cm['f1']:.4f} Spec={cm['specificity']:.4f}")

    # Print summary table
    print(f"\n{'='*80}")
    print("  CONFUSION MATRIX SUMMARY — Multiple Cutoffs")
    print(f"{'='*80}")
    print(f"  {'Cutoff':>8} {'TP':>10} {'FP':>8} {'TN':>8} {'FN':>10} "
          f"{'Prec':>7} {'Recall':>7} {'F1':>7} {'Spec':>7} {'Appr%':>7}")
    print(f"  {'-'*90}")
    for cm in cutoff_results:
        print(f"  {cm['cutoff']:>8} {cm['TP']:>10,} {cm['FP']:>8,} {cm['TN']:>8,} "
              f"{cm['FN']:>10,} {cm['precision']:>7.4f} {cm['recall']:>7.4f} "
              f"{cm['f1']:>7.4f} {cm['specificity']:>7.4f} {cm['approval_rate']:>6.1f}%")

    # ═════════════════════════════════════════════════════════════════════
    # PART 2 — Per-band contingency
    # ═════════════════════════════════════════════════════════════════════
    log("Part 2 — Contingency per risk band")
    band_results = confusion_per_band(y_true, y_scores)

    print(f"\n{'='*70}")
    print("  CONTINGENCY PER RISK BAND")
    print(f"{'='*70}")
    print(f"  {'Band':<12} {'Range':<10} {'Total':>10} {'Good':>10} "
          f"{'Bad':>8} {'FPD%':>8} {'Pop%':>7}")
    print(f"  {'-'*68}")
    for b in band_results:
        print(f"  {b['band']:<12} {b['range']:<10} {b['total']:>10,} "
              f"{b['good_count']:>10,} {b['fpd_count']:>8,} "
              f"{b['fpd_rate']:>7.2f}% {b['pct_of_total']:>6.1f}%")

    # ═════════════════════════════════════════════════════════════════════
    # PART 3 — Gain / Lift
    # ═════════════════════════════════════════════════════════════════════
    log("Part 3 — Decile gain/lift analysis")
    decile_df = decile_gain_lift(y_true, y_prob)

    print(f"\n{'='*70}")
    print("  GAIN / LIFT TABLE")
    print(f"{'='*70}")
    print(f"  {'Decil':>6} {'Total':>8} {'Bad':>8} {'BadRate':>8} "
          f"{'CumBad%':>8} {'CumPop%':>8} {'Lift':>7}")
    print(f"  {'-'*56}")
    for _, row in decile_df.iterrows():
        print(f"  {int(row['decile']):>6} {int(row['n_total']):>8,} "
              f"{int(row['n_bad']):>8,} {row['bad_rate']:>8.4f} "
              f"{row['cum_bad_pct']:>8.4f} {row['cum_total_pct']:>8.4f} "
              f"{row['lift']:>7.2f}")

    # ═════════════════════════════════════════════════════════════════════
    # PART 4 — Financial impact
    # ═════════════════════════════════════════════════════════════════════
    log(f"Part 4 — Financial impact simulation (LGD=R$ {LGD:.2f})")
    financial_results = financial_impact(cutoff_results, lgd=LGD)

    print(f"\n{'='*80}")
    print(f"  FINANCIAL IMPACT (LGD = R$ {LGD:.2f})")
    print(f"{'='*80}")
    print(f"  {'Cutoff':>8} {'Aprovados':>10} {'Receita':>14} {'Perda':>14} "
          f"{'Liquido':>14} {'vs Base':>12}")
    print(f"  {'-'*76}")
    for fi in financial_results:
        label = "Sem Modelo" if fi["cutoff"] == 0 else str(fi["cutoff"])
        print(f"  {label:>8} {fi['approved']:>10,} "
              f"R$ {fi['revenue_good']:>10,.2f} R$ {fi['loss_bad']:>10,.2f} "
              f"R$ {fi['net_impact']:>10,.2f} {fi['net_vs_baseline_pct']:>+10.1f}%")

    # ═════════════════════════════════════════════════════════════════════
    # PART 5 — Save JSON results
    # ═════════════════════════════════════════════════════════════════════
    log("Saving JSON results...")

    overall_fpd_rate = float(y_true.mean())
    summary = {
        "timestamp": datetime.now().isoformat(),
        "run_id": "20260311_015100",
        "total_records": int(len(df)),
        "labeled_records": int(len(df_labeled)),
        "overall_fpd_rate": round(overall_fpd_rate, 6),
        "fpd_count": int(y_true.sum()),
        "good_count": int((y_true == 0).sum()),
        "lgd_proxy": LGD,
        "cutoffs_analyzed": CUTOFFS,
        "confusion_matrices": cutoff_results,
        "risk_band_contingency": band_results,
        "decile_gain_lift": decile_df.to_dict(orient="records"),
        "financial_impact": financial_results,
        "score_stats": {
            "mean": round(float(y_scores.mean()), 2),
            "median": int(np.median(y_scores)),
            "std": round(float(y_scores.std()), 2),
            "min": int(y_scores.min()),
            "max": int(y_scores.max()),
        },
    }

    json_path = os.path.join(metrics_dir, "confusion_matrix_results.json")
    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    log(f"Saved {json_path}")

    # ═════════════════════════════════════════════════════════════════════
    # PART 6 — Generate plots
    # ═════════════════════════════════════════════════════════════════════
    log("Generating plots...")

    # Plot 1: Confusion matrix heatmap for cutoff 700 (recommended)
    cm_700 = [c for c in cutoff_results if c["cutoff"] == 700][0]
    plot_confusion_heatmap(
        cm_700,
        title="Matriz de Confusao — Cutoff 700 (Recomendado)",
        save_path=os.path.join(plots_dir, "confusion_matrix_cutoff700.png"),
    )
    log("  Saved confusion_matrix_cutoff700.png")

    # Plot 2: Multi-threshold metrics
    plot_multi_threshold(
        cutoff_results,
        save_path=os.path.join(plots_dir, "confusion_matrix_multi_threshold.png"),
    )
    log("  Saved confusion_matrix_multi_threshold.png")

    # Plot 3: Per-band contingency
    plot_per_band_contingency(
        band_results,
        save_path=os.path.join(plots_dir, "confusion_matrix_per_band.png"),
    )
    log("  Saved confusion_matrix_per_band.png")

    # Plot 4: Gain/Lift chart
    plot_gain_lift(
        decile_df,
        save_path=os.path.join(plots_dir, "gain_lift_chart.png"),
    )
    log("  Saved gain_lift_chart.png")

    # Plot 5: Financial impact
    plot_financial_impact(
        financial_results,
        save_path=os.path.join(plots_dir, "financial_impact_analysis.png"),
    )
    log("  Saved financial_impact_analysis.png")

    # ═════════════════════════════════════════════════════════════════════
    # FINAL SUMMARY
    # ═════════════════════════════════════════════════════════════════════
    print(f"\n{'='*70}")
    print("  CONFUSION MATRIX ANALYSIS COMPLETE")
    print(f"{'='*70}")
    print(f"  Total records:       {len(df):>10,}")
    print(f"  Labeled records:     {len(df_labeled):>10,}")
    print(f"  Overall FPD rate:    {overall_fpd_rate:.4f}")
    print(f"  Cutoffs analyzed:    {CUTOFFS}")
    print(f"  LGD proxy:           R$ {LGD:.2f}")
    print(f"\n  Best F1 cutoff:      {max(cutoff_results, key=lambda x: x['f1'])['cutoff']} "
          f"(F1={max(cutoff_results, key=lambda x: x['f1'])['f1']:.4f})")
    print(f"  Best precision cutoff: {max(cutoff_results, key=lambda x: x['precision'])['cutoff']} "
          f"(Prec={max(cutoff_results, key=lambda x: x['precision'])['precision']:.4f})")
    print(f"  Gain top decile:     {decile_df.iloc[0]['cum_bad_pct']:.1%} of defaults captured in top 10%")
    print(f"  Lift top decile:     {decile_df.iloc[0]['lift']:.2f}x")
    print(f"\n  Outputs saved to:")
    print(f"    - {metrics_dir}/confusion_matrix_results.json")
    print(f"    - {plots_dir}/confusion_matrix_cutoff700.png")
    print(f"    - {plots_dir}/confusion_matrix_multi_threshold.png")
    print(f"    - {plots_dir}/confusion_matrix_per_band.png")
    print(f"    - {plots_dir}/gain_lift_chart.png")
    print(f"    - {plots_dir}/financial_impact_analysis.png")
    print(f"{'='*70}")
    log(f"Done.{mem_usage()}")

    return summary


if __name__ == "__main__":
    main()
