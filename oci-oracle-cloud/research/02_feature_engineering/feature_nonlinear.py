"""
Non-Linear Transformations — Phase 2.5
Log/sqrt transforms, WoE encoding, and binning for non-linear signals.

Usage: Import create_nonlinear_features(df) from pipeline scripts.
"""
import numpy as np
import pandas as pd


# Features with known high skewness (from EDA)
SKEWED_FEATURES = [
    "REC_VLR_REAL_STDDEV",
    "REC_VLR_CREDITO_STDDEV",
    "REC_QTD_RECARGAS_TOTAL",
    "PAG_QTD_PAGAMENTOS_TOTAL",
    "PAG_VLR_PAGAMENTO_FATURA_STDDEV",
    "FAT_DIAS_ATRASO_MEDIO",
    "FAT_DIAS_ATRASO_MIN",
    "REC_COEF_VARIACAO_REAL",
    "PAG_COEF_VARIACAO_PAGAMENTO",
]

# Top features for WoE encoding (used in LR scorecard)
WOE_CANDIDATE_FEATURES = [
    "TARGET_SCORE_02", "REC_SCORE_RISCO", "TARGET_SCORE_01",
    "REC_QTD_PLAT_AUTOC", "REC_DIAS_ENTRE_RECARGAS",
    "REC_VLR_REAL_STDDEV", "REC_TAXA_CARTAO_ONLINE",
    "REC_DIAS_DESDE_ULTIMA_RECARGA", "FAT_QTD_FATURAS_PRIMEIRA",
    "REC_FREQ_RECARGA_DIARIA",
]


def create_nonlinear_features(df, target_col=None):
    """Create non-linear transformation features.

    Args:
        df: DataFrame with feature columns
        target_col: Column name for target (needed for WoE). If None, skip WoE.

    Returns DataFrame with new features appended.
    """
    result = df.copy()

    # ── Log/sqrt transforms for skewed features ─────────────────────────────

    available_skewed = [f for f in SKEWED_FEATURES if f in df.columns]

    for feat in available_skewed:
        vals = df[feat].fillna(0)

        # Log1p transform (handles zeros)
        result[f"{feat}_LOG"] = np.log1p(np.abs(vals)) * np.sign(vals)

        # Sqrt transform
        result[f"{feat}_SQRT"] = np.sqrt(np.abs(vals)) * np.sign(vals)

    # ── Bureau score binning ────────────────────────────────────────────────

    if "TARGET_SCORE_02" in df.columns:
        score = df["TARGET_SCORE_02"].fillna(df["TARGET_SCORE_02"].median())
        result["SCORE_02_QUARTILE"] = pd.qcut(
            score, q=4, labels=False, duplicates="drop"
        )
        result["SCORE_02_DECILE"] = pd.qcut(
            score, q=10, labels=False, duplicates="drop"
        )

    if "TARGET_SCORE_01" in df.columns:
        score = df["TARGET_SCORE_01"].fillna(df["TARGET_SCORE_01"].median())
        result["SCORE_01_QUARTILE"] = pd.qcut(
            score, q=4, labels=False, duplicates="drop"
        )

    # ── WoE encoding for LR scorecard ───────────────────────────────────────

    if target_col is not None and target_col in df.columns:
        y = df[target_col]
        if y.notna().sum() > 1000 and y.nunique() == 2:
            woe_features = compute_woe(df, y, WOE_CANDIDATE_FEATURES)
            for col, vals in woe_features.items():
                result[col] = vals

    new_cols = [c for c in result.columns if c not in df.columns]
    print(f"[NONLINEAR] Created {len(new_cols)} non-linear features")

    return result


def compute_woe(df, y, features, n_bins=10):
    """Compute Weight of Evidence for given features."""
    woe_results = {}
    total_events = y.sum()
    total_non_events = len(y) - total_events

    if total_events == 0 or total_non_events == 0:
        return woe_results

    for feat in features:
        if feat not in df.columns:
            continue

        vals = df[feat].fillna(df[feat].median())

        try:
            bins = pd.qcut(vals, q=n_bins, labels=False, duplicates="drop")
        except ValueError:
            continue

        woe_map = {}
        for bin_id in sorted(bins.unique()):
            mask = bins == bin_id
            events = y[mask].sum()
            non_events = mask.sum() - events

            # Smoothing to avoid log(0)
            events_pct = (events + 0.5) / (total_events + 1)
            non_events_pct = (non_events + 0.5) / (total_non_events + 1)

            woe = np.log(non_events_pct / events_pct)
            woe_map[bin_id] = woe

        woe_col = f"{feat}_WOE"
        woe_results[woe_col] = bins.map(woe_map)

    return woe_results


def get_nonlinear_feature_names():
    """Return list of possible non-linear feature name patterns."""
    names = []
    for feat in SKEWED_FEATURES:
        names.extend([f"{feat}_LOG", f"{feat}_SQRT"])
    names.extend([
        "SCORE_02_QUARTILE", "SCORE_02_DECILE", "SCORE_01_QUARTILE",
    ])
    for feat in WOE_CANDIDATE_FEATURES:
        names.append(f"{feat}_WOE")
    return names


if __name__ == "__main__":
    print("Non-Linear Features Module — use create_nonlinear_features(df, target_col)")
    print(f"Expected output features: {len(get_nonlinear_feature_names())} features")
