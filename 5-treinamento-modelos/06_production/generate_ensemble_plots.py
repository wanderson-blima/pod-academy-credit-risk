"""
Generate comparative visualization plots for Credit Risk Ensemble v1.
Compares baseline LGBM v1 vs 5 optimized models + ensemble.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os

# ── Output directory ──
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "artifacts", "visualization-plot", "plots_ensemble")
os.makedirs(OUT_DIR, exist_ok=True)

# ── Color palette (dark theme) ──
BG_COLOR = "#1a1a2e"
CARD_COLOR = "#16213e"
TEXT_COLOR = "#e0e0e0"
GRID_COLOR = "#2a2a4a"
ACCENT = "#00d4ff"
COLORS = {
    "Baseline LGBM v1": "#888888",
    "LR L1 v2": "#ff6b6b",
    "RandomForest": "#ffd93d",
    "CatBoost": "#6bcb77",
    "LightGBM v2": "#4d96ff",
    "XGBoost": "#ff922b",
    "Ensemble (avg)": "#00d4ff",
}

# ── Data ──
MODELS = ["Baseline\nLGBM v1", "LR L1 v2", "Random\nForest", "CatBoost", "LightGBM\nv2", "XGBoost", "Ensemble\n(avg)"]
MODELS_SHORT = ["Baseline LGBM v1", "LR L1 v2", "RandomForest", "CatBoost", "LightGBM v2", "XGBoost", "Ensemble (avg)"]
KS_OOT =  [0.3403, 0.3285, 0.3348, 0.3462, 0.3471, 0.3472, 0.3442]
AUC_OOT = [0.7305, 0.7208, 0.7280, 0.7343, 0.7350, 0.7351, 0.7334]
GINI_OOT = [46.11, 44.16, 45.60, 46.87, 47.00, 47.02, 46.68]
PSI =     [0.0005, 0.0007, 0.0012, 0.0005, 0.0008, 0.0008, 0.0006]

KS_TRAIN = [None, 0.3485, 0.3713, 0.3725, 0.3930, 0.3992, None]
KS_OOS =   [None, 0.3400, 0.3656, 0.3653, 0.3887, 0.3959, None]
KS_OOT_ONLY = [None, 0.3285, 0.3348, 0.3462, 0.3471, 0.3472, None]

# HPO data
HPO_MODELS = ["LightGBM", "XGBoost", "CatBoost"]
HPO_BEST_KS = [0.36548, 0.36596, 0.36541]
HPO_TIME_MIN = [151, 143, 200]  # approximate minutes

# Score distribution
SCORE_BANDS = ["CRITICO\n(<300)", "ALTO\n(300-499)", "MEDIO\n(500-699)", "BAIXO\n(>=700)"]
SCORE_COUNTS = [248675, 945485, 1271725, 1434493]
SCORE_PCTS = [6.4, 24.2, 32.6, 36.8]
SCORE_COLORS = ["#ff4444", "#ff8c00", "#ffd700", "#00cc66"]

# Per-SAFRA performance
SAFRAS = ["202410", "202411", "202412", "202501", "202502\n(OOT)", "202503\n(OOT)"]
SAFRA_KS_BASELINE = [0.3692, 0.3728, 0.3498, 0.3528, 0.3342, 0.3464]

# Feature pipeline
FEAT_STAGES = ["Original\n(402)", "Engineered\n(+47=449)", "IV Filter\n(>0.02)", "Corr Filter\n(<0.95)", "PSI Filter\n(<0.20)"]
FEAT_COUNTS = [402, 449, 86, 78, 72]


def apply_dark_theme(fig, axes):
    fig.patch.set_facecolor(BG_COLOR)
    if not hasattr(axes, '__iter__'):
        axes = [axes]
    for ax in axes:
        ax.set_facecolor(CARD_COLOR)
        ax.tick_params(colors=TEXT_COLOR, labelsize=9)
        ax.xaxis.label.set_color(TEXT_COLOR)
        ax.yaxis.label.set_color(TEXT_COLOR)
        ax.title.set_color(TEXT_COLOR)
        for spine in ax.spines.values():
            spine.set_color(GRID_COLOR)
        ax.grid(True, alpha=0.2, color=GRID_COLOR)


# ═══════════════════════════════════════════════════════════════
# PLOT 1: Model Comparison — KS / AUC / Gini (3 subplots)
# ═══════════════════════════════════════════════════════════════
def plot_model_comparison():
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    apply_dark_theme(fig, axes)
    fig.suptitle("Model Comparison — OOT Performance", color=ACCENT,
                 fontsize=16, fontweight="bold", y=0.98)

    metrics = [
        ("KS Statistic (OOT)", KS_OOT, "{:.4f}"),
        ("AUC-ROC (OOT)", AUC_OOT, "{:.4f}"),
        ("Gini Coefficient (OOT)", GINI_OOT, "{:.2f}pp"),
    ]

    for ax, (title, values, fmt) in zip(axes, metrics):
        colors = [COLORS[m] for m in MODELS_SHORT]
        bars = ax.bar(MODELS, values, color=colors, edgecolor="white", linewidth=0.5, width=0.7)
        ax.set_title(title, fontsize=12, fontweight="bold", pad=10)
        ax.set_ylabel(title.split("(")[0].strip(), fontsize=10)

        # Value labels
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.001,
                    fmt.format(val), ha="center", va="bottom", fontsize=8,
                    color=TEXT_COLOR, fontweight="bold")

        # Baseline reference line
        ax.axhline(y=values[0], color="#888888", linestyle="--", alpha=0.5, linewidth=1)
        ax.tick_params(axis='x', labelsize=7.5)

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    path = os.path.join(OUT_DIR, "01_model_comparison_oot.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close(fig)
    print(f"  Saved: {path}")


# ═══════════════════════════════════════════════════════════════
# PLOT 2: KS Improvement vs Baseline (waterfall-style)
# ═══════════════════════════════════════════════════════════════
def plot_ks_improvement():
    fig, ax = plt.subplots(figsize=(12, 6))
    apply_dark_theme(fig, ax)

    baseline_ks = 0.3403
    models = MODELS_SHORT[1:]  # exclude baseline
    ks_vals = KS_OOT[1:]
    improvements = [(v - baseline_ks) * 100 for v in ks_vals]  # in pp

    colors_bar = [COLORS[m] for m in models]
    bars = ax.barh(range(len(models)), improvements, color=colors_bar,
                   edgecolor="white", linewidth=0.5, height=0.6)

    ax.set_yticks(range(len(models)))
    ax.set_yticklabels([m.replace("\n", " ") for m in MODELS[1:]], fontsize=10)
    ax.set_xlabel("KS Improvement vs Baseline (percentage points)", fontsize=11)
    ax.set_title("KS OOT Improvement over Baseline LGBM v1 (KS=0.3403)",
                 color=ACCENT, fontsize=14, fontweight="bold")
    ax.axvline(x=0, color=TEXT_COLOR, linewidth=1, alpha=0.5)

    for bar, imp in zip(bars, improvements):
        x_pos = bar.get_width() + 0.02 if imp >= 0 else bar.get_width() - 0.02
        ha = "left" if imp >= 0 else "right"
        sign = "+" if imp >= 0 else ""
        ax.text(x_pos, bar.get_y() + bar.get_height()/2,
                f"{sign}{imp:.2f}pp", ha=ha, va="center",
                fontsize=10, color=TEXT_COLOR, fontweight="bold")

    plt.tight_layout()
    path = os.path.join(OUT_DIR, "02_ks_improvement_vs_baseline.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close(fig)
    print(f"  Saved: {path}")


# ═══════════════════════════════════════════════════════════════
# PLOT 3: Overfitting Analysis (Train vs OOS vs OOT)
# ═══════════════════════════════════════════════════════════════
def plot_overfitting():
    fig, ax = plt.subplots(figsize=(12, 6))
    apply_dark_theme(fig, ax)

    models_ov = ["LR L1 v2", "RandomForest", "CatBoost", "LightGBM v2", "XGBoost"]
    ks_t = [0.3485, 0.3713, 0.3725, 0.3930, 0.3992]
    ks_o = [0.3400, 0.3656, 0.3653, 0.3887, 0.3959]
    ks_oot = [0.3285, 0.3348, 0.3462, 0.3471, 0.3472]
    gaps = [(t - o) * 100 for t, o in zip(ks_t, ks_oot)]

    x = np.arange(len(models_ov))
    w = 0.25

    bars1 = ax.bar(x - w, ks_t, w, label="Train", color="#4d96ff", edgecolor="white", linewidth=0.5)
    bars2 = ax.bar(x, ks_o, w, label="OOS", color="#ffd93d", edgecolor="white", linewidth=0.5)
    bars3 = ax.bar(x + w, ks_oot, w, label="OOT", color="#00d4ff", edgecolor="white", linewidth=0.5)

    ax.set_xticks(x)
    ax.set_xticklabels(models_ov, fontsize=10)
    ax.set_ylabel("KS Statistic", fontsize=11)
    ax.set_title("Overfitting Analysis — KS across Train / OOS / OOT",
                 color=ACCENT, fontsize=14, fontweight="bold")
    ax.legend(facecolor=CARD_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=10)

    # Gap annotations
    for i, (bar3, gap) in enumerate(zip(bars3, gaps)):
        ax.annotate(f"Gap: {gap:.1f}pp",
                    xy=(bar3.get_x() + bar3.get_width()/2, bar3.get_height()),
                    xytext=(0, 8), textcoords="offset points",
                    ha="center", fontsize=8, color="#ff6b6b", fontweight="bold")

    plt.tight_layout()
    path = os.path.join(OUT_DIR, "03_overfitting_analysis.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close(fig)
    print(f"  Saved: {path}")


# ═══════════════════════════════════════════════════════════════
# PLOT 4: HPO Results
# ═══════════════════════════════════════════════════════════════
def plot_hpo():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    apply_dark_theme(fig, [ax1, ax2])
    fig.suptitle("Hyperparameter Optimization (Optuna TPE, 50 trials)",
                 color=ACCENT, fontsize=14, fontweight="bold", y=0.98)

    hpo_colors = ["#4d96ff", "#ff922b", "#6bcb77"]

    # Best KS(CV)
    bars1 = ax1.bar(HPO_MODELS, HPO_BEST_KS, color=hpo_colors,
                    edgecolor="white", linewidth=0.5, width=0.5)
    ax1.set_ylabel("Best KS (3-Fold CV)", fontsize=11)
    ax1.set_title("Best KS per Model", fontsize=12, fontweight="bold")
    for bar, val in zip(bars1, HPO_BEST_KS):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.0005,
                 f"{val:.5f}", ha="center", va="bottom", fontsize=10,
                 color=TEXT_COLOR, fontweight="bold")
    ax1.set_ylim(0.364, 0.367)

    # Time
    bars2 = ax2.bar(HPO_MODELS, HPO_TIME_MIN, color=hpo_colors,
                    edgecolor="white", linewidth=0.5, width=0.5)
    ax2.set_ylabel("Time (minutes)", fontsize=11)
    ax2.set_title("HPO Duration", fontsize=12, fontweight="bold")
    for bar, val in zip(bars2, HPO_TIME_MIN):
        h, m = divmod(val, 60)
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                 f"{h}h{m:02d}m", ha="center", va="bottom", fontsize=10,
                 color=TEXT_COLOR, fontweight="bold")

    plt.tight_layout(rect=[0, 0, 1, 0.92])
    path = os.path.join(OUT_DIR, "04_hpo_results.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close(fig)
    print(f"  Saved: {path}")


# ═══════════════════════════════════════════════════════════════
# PLOT 5: PSI Stability
# ═══════════════════════════════════════════════════════════════
def plot_psi():
    fig, ax = plt.subplots(figsize=(12, 5))
    apply_dark_theme(fig, ax)

    colors_bar = [COLORS[m] for m in MODELS_SHORT]
    bars = ax.bar(MODELS, PSI, color=colors_bar, edgecolor="white", linewidth=0.5, width=0.6)
    ax.set_ylabel("PSI", fontsize=11)
    ax.set_title("Population Stability Index (PSI) — All Models",
                 color=ACCENT, fontsize=14, fontweight="bold")

    # Threshold lines
    ax.axhline(y=0.10, color="#ffd93d", linestyle="--", alpha=0.7, linewidth=1.5, label="Warning (0.10)")
    ax.axhline(y=0.25, color="#ff4444", linestyle="--", alpha=0.7, linewidth=1.5, label="Retrain (0.25)")
    ax.legend(facecolor=CARD_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=9)

    for bar, val in zip(bars, PSI):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.00005,
                f"{val:.4f}", ha="center", va="bottom", fontsize=9,
                color=TEXT_COLOR, fontweight="bold")

    ax.set_ylim(0, 0.003)
    ax.tick_params(axis='x', labelsize=8)

    # Add "EXCELLENT" badge
    ax.text(0.98, 0.92, "ALL MODELS: EXCELLENT STABILITY",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=11, color="#00cc66", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#00cc6622", edgecolor="#00cc66"))

    plt.tight_layout()
    path = os.path.join(OUT_DIR, "05_psi_stability.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close(fig)
    print(f"  Saved: {path}")


# ═══════════════════════════════════════════════════════════════
# PLOT 6: Score Distribution
# ═══════════════════════════════════════════════════════════════
def plot_score_distribution():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    apply_dark_theme(fig, [ax1, ax2])
    fig.suptitle("Ensemble Score Distribution — 3,900,378 Records",
                 color=ACCENT, fontsize=14, fontweight="bold", y=0.98)

    # Bar chart
    bars = ax1.bar(SCORE_BANDS, [c/1000 for c in SCORE_COUNTS],
                   color=SCORE_COLORS, edgecolor="white", linewidth=0.5, width=0.6)
    ax1.set_ylabel("Count (thousands)", fontsize=11)
    ax1.set_title("Score Band Distribution", fontsize=12, fontweight="bold")
    for bar, pct, cnt in zip(bars, SCORE_PCTS, SCORE_COUNTS):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 15,
                 f"{pct}%\n({cnt:,})", ha="center", va="bottom", fontsize=9,
                 color=TEXT_COLOR, fontweight="bold")

    # Pie chart
    wedges, texts, autotexts = ax2.pie(
        SCORE_PCTS, labels=["CRITICO", "ALTO", "MEDIO", "BAIXO"],
        colors=SCORE_COLORS, autopct="%1.1f%%", startangle=90,
        textprops={"color": TEXT_COLOR, "fontsize": 10},
        wedgeprops={"edgecolor": BG_COLOR, "linewidth": 2}
    )
    for t in autotexts:
        t.set_fontweight("bold")
    ax2.set_title("Risk Distribution", fontsize=12, fontweight="bold", color=TEXT_COLOR)

    # Stats box
    ax2.text(0.0, -0.15, f"Score Mean: 605  |  Median: 627",
             transform=ax2.transAxes, ha="center", fontsize=10,
             color=ACCENT, fontweight="bold")

    plt.tight_layout(rect=[0, 0, 1, 0.92])
    path = os.path.join(OUT_DIR, "06_score_distribution.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close(fig)
    print(f"  Saved: {path}")


# ═══════════════════════════════════════════════════════════════
# PLOT 7: Feature Engineering Pipeline
# ═══════════════════════════════════════════════════════════════
def plot_feature_pipeline():
    fig, ax = plt.subplots(figsize=(14, 5))
    apply_dark_theme(fig, ax)

    colors_feat = ["#4d96ff", "#00d4ff", "#ffd93d", "#ff922b", "#00cc66"]
    bars = ax.bar(FEAT_STAGES, FEAT_COUNTS, color=colors_feat,
                  edgecolor="white", linewidth=0.5, width=0.55)
    ax.set_ylabel("Number of Features", fontsize=11)
    ax.set_title("Feature Engineering & Selection Pipeline",
                 color=ACCENT, fontsize=14, fontweight="bold")

    for bar, val in zip(bars, FEAT_COUNTS):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5,
                str(val), ha="center", va="bottom", fontsize=12,
                color=TEXT_COLOR, fontweight="bold")

    # Arrows between bars
    for i in range(len(FEAT_COUNTS) - 1):
        diff = FEAT_COUNTS[i+1] - FEAT_COUNTS[i]
        sign = "+" if diff > 0 else ""
        color = "#00cc66" if diff > 0 else "#ff6b6b"
        mid_x = (bars[i].get_x() + bars[i].get_width() + bars[i+1].get_x()) / 2
        mid_y = max(FEAT_COUNTS[i], FEAT_COUNTS[i+1]) / 2 + 30
        ax.annotate(f"{sign}{diff}", xy=(mid_x, mid_y), fontsize=10,
                    ha="center", color=color, fontweight="bold")

    ax.tick_params(axis='x', labelsize=9)
    plt.tight_layout()
    path = os.path.join(OUT_DIR, "07_feature_pipeline.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close(fig)
    print(f"  Saved: {path}")


# ═══════════════════════════════════════════════════════════════
# PLOT 8: Comprehensive Dashboard (2x3 grid)
# ═══════════════════════════════════════════════════════════════
def plot_dashboard():
    fig, axes = plt.subplots(2, 3, figsize=(22, 12))
    apply_dark_theme(fig, axes.flat)
    fig.suptitle("Credit Risk Ensemble v1 — Performance Dashboard",
                 color=ACCENT, fontsize=18, fontweight="bold", y=0.98)

    # (0,0) KS OOT comparison
    ax = axes[0, 0]
    colors_bar = [COLORS[m] for m in MODELS_SHORT]
    bars = ax.bar(range(len(MODELS)), KS_OOT, color=colors_bar, edgecolor="white", linewidth=0.5)
    ax.set_xticks(range(len(MODELS)))
    ax.set_xticklabels(MODELS, fontsize=7)
    ax.set_title("KS OOT — All Models", fontsize=11, fontweight="bold")
    ax.axhline(y=0.3403, color="#888888", linestyle="--", alpha=0.5)
    for bar, val in zip(bars, KS_OOT):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.001,
                f"{val:.4f}", ha="center", va="bottom", fontsize=7, color=TEXT_COLOR)

    # (0,1) AUC OOT
    ax = axes[0, 1]
    bars = ax.bar(range(len(MODELS)), AUC_OOT, color=colors_bar, edgecolor="white", linewidth=0.5)
    ax.set_xticks(range(len(MODELS)))
    ax.set_xticklabels(MODELS, fontsize=7)
    ax.set_title("AUC-ROC OOT — All Models", fontsize=11, fontweight="bold")
    for bar, val in zip(bars, AUC_OOT):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.001,
                f"{val:.4f}", ha="center", va="bottom", fontsize=7, color=TEXT_COLOR)

    # (0,2) PSI
    ax = axes[0, 2]
    bars = ax.bar(range(len(MODELS)), PSI, color=colors_bar, edgecolor="white", linewidth=0.5)
    ax.set_xticks(range(len(MODELS)))
    ax.set_xticklabels(MODELS, fontsize=7)
    ax.set_title("PSI — Score Stability", fontsize=11, fontweight="bold")
    ax.axhline(y=0.10, color="#ffd93d", linestyle="--", alpha=0.5)
    ax.set_ylim(0, 0.003)
    for bar, val in zip(bars, PSI):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.00005,
                f"{val:.4f}", ha="center", va="bottom", fontsize=7, color=TEXT_COLOR)

    # (1,0) Overfitting
    ax = axes[1, 0]
    models_ov = ["LR L1", "RF", "CatBoost", "LGBM v2", "XGBoost"]
    x = np.arange(len(models_ov))
    w = 0.25
    ax.bar(x - w, [0.3485, 0.3713, 0.3725, 0.3930, 0.3992], w,
           label="Train", color="#4d96ff", edgecolor="white", linewidth=0.5)
    ax.bar(x, [0.3400, 0.3656, 0.3653, 0.3887, 0.3959], w,
           label="OOS", color="#ffd93d", edgecolor="white", linewidth=0.5)
    ax.bar(x + w, [0.3285, 0.3348, 0.3462, 0.3471, 0.3472], w,
           label="OOT", color="#00d4ff", edgecolor="white", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(models_ov, fontsize=8)
    ax.set_title("Overfitting Check (Train/OOS/OOT)", fontsize=11, fontweight="bold")
    ax.legend(facecolor=CARD_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=8)

    # (1,1) Score Distribution
    ax = axes[1, 1]
    wedges, texts, autotexts = ax.pie(
        SCORE_PCTS, labels=["CRITICO", "ALTO", "MEDIO", "BAIXO"],
        colors=SCORE_COLORS, autopct="%1.1f%%", startangle=90,
        textprops={"color": TEXT_COLOR, "fontsize": 9},
        wedgeprops={"edgecolor": BG_COLOR, "linewidth": 2}
    )
    for t in autotexts:
        t.set_fontweight("bold")
        t.set_fontsize(8)
    ax.set_title("Score Distribution (3.9M)", fontsize=11, fontweight="bold", color=TEXT_COLOR)

    # (1,2) Feature Pipeline
    ax = axes[1, 2]
    stages_short = ["Original", "+47 Eng", "IV>0.02", "Corr<0.95", "PSI<0.20"]
    feat_colors = ["#4d96ff", "#00d4ff", "#ffd93d", "#ff922b", "#00cc66"]
    bars = ax.bar(stages_short, FEAT_COUNTS, color=feat_colors,
                  edgecolor="white", linewidth=0.5, width=0.55)
    ax.set_title("Feature Pipeline", fontsize=11, fontweight="bold")
    for bar, val in zip(bars, FEAT_COUNTS):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5,
                str(val), ha="center", va="bottom", fontsize=9,
                color=TEXT_COLOR, fontweight="bold")

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    path = os.path.join(OUT_DIR, "08_dashboard_overview.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close(fig)
    print(f"  Saved: {path}")


# ═══════════════════════════════════════════════════════════════
# PLOT 9: Ensemble Strategy Comparison
# ═══════════════════════════════════════════════════════════════
def plot_ensemble_strategy():
    fig, ax = plt.subplots(figsize=(10, 5))
    apply_dark_theme(fig, ax)

    strategies = ["Simple Average\n(CHAMPION)", "Weighted Blend\n(SLSQP)", "Stacking\n(LR meta-learner)"]
    ks_values = [0.34417, 0.34417, 0.32763]
    strat_colors = ["#00d4ff", "#ffd93d", "#ff6b6b"]

    bars = ax.bar(strategies, ks_values, color=strat_colors,
                  edgecolor="white", linewidth=0.5, width=0.5)
    ax.set_ylabel("KS OOT", fontsize=11)
    ax.set_title("Ensemble Strategy Comparison",
                 color=ACCENT, fontsize=14, fontweight="bold")

    for bar, val in zip(bars, ks_values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.001,
                f"{val:.5f}", ha="center", va="bottom", fontsize=11,
                color=TEXT_COLOR, fontweight="bold")

    # Champion badge
    ax.text(bars[0].get_x() + bars[0].get_width()/2, bars[0].get_height() - 0.008,
            "CHAMPION", ha="center", va="top", fontsize=10, color=BG_COLOR,
            fontweight="bold", bbox=dict(boxstyle="round,pad=0.3", facecolor="#00cc66"))

    ax.set_ylim(0.32, 0.35)
    plt.tight_layout()
    path = os.path.join(OUT_DIR, "09_ensemble_strategy.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close(fig)
    print(f"  Saved: {path}")


# ═══════════════════════════════════════════════════════════════
# PLOT 10: Quality Gates Summary
# ═══════════════════════════════════════════════════════════════
def plot_quality_gates():
    fig, ax = plt.subplots(figsize=(12, 5))
    apply_dark_theme(fig, ax)

    gates = ["QG-D1\nDiagnostic", "QG-FE\nFeature Eng", "QG-HPO\nOptimization",
             "QG-MM\nMulti-Model", "QG-ENS\nEnsemble", "QG-PROD\nProduction"]
    criteria = [
        ">=3 findings",
        "New features\nIV>0.02, PSI<0.20",
        "KS improvement\n>0.5pp vs defaults",
        ">=3 models\nKS>0.20, AUC>0.65",
        "Ensemble KS>0.34\nPSI<0.10",
        "3.9M scored\n18 artifacts uploaded"
    ]
    statuses = [1, 1, 1, 1, 1, 1]  # all PASS

    for i, (gate, criterion, status) in enumerate(zip(gates, criteria, statuses)):
        color = "#00cc66" if status else "#ff4444"
        rect = mpatches.FancyBboxPatch((i * 1.8 + 0.1, 0.2), 1.5, 0.6,
                                        boxstyle="round,pad=0.1",
                                        facecolor=color + "33", edgecolor=color, linewidth=2)
        ax.add_patch(rect)
        ax.text(i * 1.8 + 0.85, 0.65, gate, ha="center", va="center",
                fontsize=9, color=TEXT_COLOR, fontweight="bold")
        ax.text(i * 1.8 + 0.85, 0.38, "PASS", ha="center", va="center",
                fontsize=14, color=color, fontweight="bold")
        ax.text(i * 1.8 + 0.85, 0.1, criterion, ha="center", va="top",
                fontsize=7, color=TEXT_COLOR, style="italic")

    ax.set_xlim(-0.1, 11)
    ax.set_ylim(-0.15, 1.0)
    ax.set_title("Quality Gates — All PASSED",
                 color="#00cc66", fontsize=14, fontweight="bold")
    ax.axis("off")

    plt.tight_layout()
    path = os.path.join(OUT_DIR, "10_quality_gates.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close(fig)
    print(f"  Saved: {path}")


# ═══════════════════════════════════════════════════════════════
# PLOT 11: Ensemble v1 vs v2 — Feature Artifact Impact
# ═══════════════════════════════════════════════════════════════
def plot_v1_vs_v2():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    apply_dark_theme(fig, [ax1, ax2])
    fig.suptitle("Ensemble v1 (original) vs v2 (reconstructed features) — Feature Artifact Impact",
                 color=ACCENT, fontsize=14, fontweight="bold", y=0.98)

    # Left: KS OOT per model
    models_v = ["LightGBM v2", "XGBoost", "CatBoost", "Ensemble"]
    ks_v1 = [0.3471, 0.3472, 0.3462, 0.3442]
    ks_v2 = [0.3105, 0.2970, 0.2822, 0.3225]
    x = np.arange(len(models_v))
    w = 0.35
    bars1 = ax1.bar(x - w/2, ks_v1, w, label="v1 (original features)", color="#00d4ff", edgecolor="white", linewidth=0.5)
    bars2 = ax1.bar(x + w/2, ks_v2, w, label="v2 (reconstructed PCA)", color="#ff6b6b", edgecolor="white", linewidth=0.5)
    ax1.set_xticks(x)
    ax1.set_xticklabels(models_v, fontsize=10)
    ax1.set_ylabel("KS OOT", fontsize=11)
    ax1.set_title("KS Degradation from Feature Reconstruction", fontsize=12, fontweight="bold")
    ax1.legend(facecolor=CARD_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=9)

    for b1, b2, v1, v2 in zip(bars1, bars2, ks_v1, ks_v2):
        ax1.text(b1.get_x() + b1.get_width()/2, b1.get_height() + 0.002,
                 f"{v1:.4f}", ha="center", fontsize=8, color=TEXT_COLOR)
        diff = (v2 - v1) * 100
        ax1.text(b2.get_x() + b2.get_width()/2, b2.get_height() + 0.002,
                 f"{v2:.4f}\n({diff:+.1f}pp)", ha="center", fontsize=8, color="#ff6b6b")

    # Right: Key Learning box
    ax2.axis("off")
    learning_text = """KEY LEARNING: Feature Artifact Persistence

Problem:
  PCA transformers and StandardScalers
  were NOT saved as artifacts during training.

Impact:
  Reconstructing PCA components at inference
  produced different features → 3-5pp KS drop
  per model.

  LightGBM: -3.66pp
  XGBoost:  -5.02pp
  CatBoost: -6.40pp

Solution (for v2):
  Save scaler.pkl + pca.pkl alongside model PKLs.
  Or use the saved feature_store_engineered.parquet
  (1.3GB, uploaded to OCI).

Official Results:
  Ensemble v1 (5 models): KS = 0.3442
  XGBoost (champion):     KS = 0.3472"""

    ax2.text(0.05, 0.95, learning_text, transform=ax2.transAxes,
             fontsize=10, color=TEXT_COLOR, fontfamily="monospace",
             verticalalignment="top",
             bbox=dict(boxstyle="round,pad=0.5", facecolor=CARD_COLOR, edgecolor=ACCENT, linewidth=2))
    ax2.set_title("Operational Learning", fontsize=12, fontweight="bold", color=TEXT_COLOR)

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    path = os.path.join(OUT_DIR, "11_v1_vs_v2_feature_impact.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close(fig)
    print(f"  Saved: {path}")


# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("Generating Ensemble comparative plots...")
    print(f"Output: {OUT_DIR}\n")
    plot_model_comparison()
    plot_ks_improvement()
    plot_overfitting()
    plot_hpo()
    plot_psi()
    plot_score_distribution()
    plot_feature_pipeline()
    plot_dashboard()
    plot_ensemble_strategy()
    plot_quality_gates()
    plot_v1_vs_v2()
    print(f"\nDone! 11 plots saved to {OUT_DIR}")
