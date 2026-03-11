"""
Cross-Domain Interaction Features — Phase 2.2
Creates features from interactions between REC_, PAG_, FAT_ domains.

Usage: Import create_interaction_features(df) from pipeline scripts.
"""
import numpy as np
import pandas as pd


def safe_divide(a, b, fill=0.0):
    """Division with zero/nan protection."""
    return np.where((b == 0) | b.isna() | a.isna(), fill, a / b)


def create_interaction_features(df):
    """Create cross-domain interaction features.

    Returns DataFrame with ~20-30 new interaction features appended.
    """
    result = df.copy()

    # ── Cross-domain ratios ─────────────────────────────────────────────────

    # Recharge vs Payment patterns
    if "REC_QTD_RECARGAS_TOTAL" in df.columns and "PAG_QTD_PAGAMENTOS_TOTAL" in df.columns:
        result["RATIO_REC_PAG"] = safe_divide(
            df["REC_QTD_RECARGAS_TOTAL"], df["PAG_QTD_PAGAMENTOS_TOTAL"]
        )

    # Billing vs Payment patterns
    if "FAT_QTD_FATURAS_PRIMEIRA" in df.columns and "PAG_QTD_PAGAMENTOS_TOTAL" in df.columns:
        result["RATIO_FAT_PAG"] = safe_divide(
            df["FAT_QTD_FATURAS_PRIMEIRA"], df["PAG_QTD_PAGAMENTOS_TOTAL"]
        )

    # Bureau score difference
    if "TARGET_SCORE_02" in df.columns and "TARGET_SCORE_01" in df.columns:
        result["DIFF_SCORE_BUREAU"] = df["TARGET_SCORE_02"] - df["TARGET_SCORE_01"]
        result["RATIO_SCORE_BUREAU"] = safe_divide(
            df["TARGET_SCORE_02"], df["TARGET_SCORE_01"]
        )

    # ── Risk combination features ───────────────────────────────────────────

    # Bureau score x Recharge risk
    if "TARGET_SCORE_02" in df.columns and "REC_SCORE_RISCO" in df.columns:
        result["SCORE_X_REC_RISK"] = df["TARGET_SCORE_02"] * df["REC_SCORE_RISCO"]
        result["SCORE_MINUS_REC_RISK"] = df["TARGET_SCORE_02"] - df["REC_SCORE_RISCO"]

    # Bureau score x Payment risk flag
    if "TARGET_SCORE_02" in df.columns and "PAG_FLAG_ALTO_RISCO" in df.columns:
        result["SCORE_X_PAG_RISK"] = df["TARGET_SCORE_02"] * df["PAG_FLAG_ALTO_RISCO"].fillna(0)

    # ── Behavioral gap features ─────────────────────────────────────────────

    # Recharge vs Payment timing gap
    if "REC_DIAS_DESDE_ULTIMA_RECARGA" in df.columns and "PAG_DIAS_DESDE_ULTIMA_FATURA" in df.columns:
        result["REC_PAG_GAP"] = (
            df["REC_DIAS_DESDE_ULTIMA_RECARGA"].fillna(0) -
            df["PAG_DIAS_DESDE_ULTIMA_FATURA"].fillna(0)
        )

    # Billing load: faturas / recharges (high = billing-heavy customer)
    if "FAT_QTD_FATURAS_PRIMEIRA" in df.columns and "REC_QTD_RECARGAS_TOTAL" in df.columns:
        result["BILLING_LOAD"] = safe_divide(
            df["FAT_QTD_FATURAS_PRIMEIRA"], df["REC_QTD_RECARGAS_TOTAL"]
        )

    # ── High risk combinations ──────────────────────────────────────────────

    # High risk combo: low bureau + high recharge risk + payment issues
    if all(c in df.columns for c in ["TARGET_SCORE_02", "REC_SCORE_RISCO", "PAG_FLAG_ALTO_RISCO"]):
        low_bureau = (df["TARGET_SCORE_02"].fillna(500) < 400).astype(int)
        high_rec_risk = (df["REC_SCORE_RISCO"].fillna(0) > df["REC_SCORE_RISCO"].quantile(0.75)).astype(int)
        pag_risk = df["PAG_FLAG_ALTO_RISCO"].fillna(0).astype(int)
        result["HIGH_RISK_COMBO"] = low_bureau + high_rec_risk + pag_risk

    # ── Variability interactions ────────────────────────────────────────────

    # Recharge variability x Payment variability
    if "REC_COEF_VARIACAO_REAL" in df.columns and "PAG_COEF_VARIACAO_PAGAMENTO" in df.columns:
        result["CV_REC_X_PAG"] = (
            df["REC_COEF_VARIACAO_REAL"].fillna(0) *
            df["PAG_COEF_VARIACAO_PAGAMENTO"].fillna(0)
        )
        result["CV_REC_PLUS_PAG"] = (
            df["REC_COEF_VARIACAO_REAL"].fillna(0) +
            df["PAG_COEF_VARIACAO_PAGAMENTO"].fillna(0)
        )

    # ── Platform/channel diversity ──────────────────────────────────────────

    # Recharge platform diversity x payment areas
    if "REC_QTD_PLATAFORMAS" in df.columns and "PAG_QTD_AREAS" in df.columns:
        result["PLATFORM_X_AREAS"] = (
            df["REC_QTD_PLATAFORMAS"].fillna(0) *
            df["PAG_QTD_AREAS"].fillna(0)
        )

    # ── Delinquency signals ─────────────────────────────────────────────────

    # Late payment frequency x billing delay
    if "PAG_TAXA_PAGAMENTOS_COM_JUROS" in df.columns and "FAT_DIAS_ATRASO_MEDIO" in df.columns:
        result["DELINQUENCY_SIGNAL"] = (
            df["PAG_TAXA_PAGAMENTOS_COM_JUROS"].fillna(0) *
            df["FAT_DIAS_ATRASO_MEDIO"].fillna(0)
        )

    # Payment with interest x recharge frequency
    if "PAG_QTD_PAGAMENTOS_COM_JUROS" in df.columns and "REC_FREQ_RECARGA_DIARIA" in df.columns:
        result["JUROS_X_FREQ_RECARGA"] = (
            df["PAG_QTD_PAGAMENTOS_COM_JUROS"].fillna(0) *
            df["REC_FREQ_RECARGA_DIARIA"].fillna(0)
        )

    # ── Score quartile interactions ─────────────────────────────────────────

    if "TARGET_SCORE_02" in df.columns:
        score_q = pd.qcut(
            df["TARGET_SCORE_02"].fillna(df["TARGET_SCORE_02"].median()),
            q=4, labels=False, duplicates="drop"
        )
        result["SCORE_QUARTILE"] = score_q

        if "REC_QTD_RECARGAS_TOTAL" in df.columns:
            result["SCORE_Q_X_RECARGAS"] = score_q * df["REC_QTD_RECARGAS_TOTAL"].fillna(0)

    # ── Dias patterns ───────────────────────────────────────────────────────

    if "FAT_DIAS_DESDE_ATIVACAO_CONTA" in df.columns and "REC_DIAS_DESDE_ULTIMA_RECARGA" in df.columns:
        result["DAYS_ACTIVE_RATIO"] = safe_divide(
            df["REC_DIAS_DESDE_ULTIMA_RECARGA"],
            df["FAT_DIAS_DESDE_ATIVACAO_CONTA"],
        )

    if "FAT_DIAS_DESDE_PRIMEIRA_FAT" in df.columns and "FAT_DIAS_DESDE_ULTIMA_FAT" in df.columns:
        result["FAT_SPAN"] = (
            df["FAT_DIAS_DESDE_PRIMEIRA_FAT"].fillna(0) -
            df["FAT_DIAS_DESDE_ULTIMA_FAT"].fillna(0)
        )

    new_cols = [c for c in result.columns if c not in df.columns]
    print(f"[INTERACTIONS] Created {len(new_cols)} interaction features: {new_cols}")

    return result


def get_interaction_feature_names():
    """Return list of all possible interaction feature names."""
    return [
        "RATIO_REC_PAG", "RATIO_FAT_PAG",
        "DIFF_SCORE_BUREAU", "RATIO_SCORE_BUREAU",
        "SCORE_X_REC_RISK", "SCORE_MINUS_REC_RISK", "SCORE_X_PAG_RISK",
        "REC_PAG_GAP", "BILLING_LOAD",
        "HIGH_RISK_COMBO",
        "CV_REC_X_PAG", "CV_REC_PLUS_PAG",
        "PLATFORM_X_AREAS",
        "DELINQUENCY_SIGNAL", "JUROS_X_FREQ_RECARGA",
        "SCORE_QUARTILE", "SCORE_Q_X_RECARGAS",
        "DAYS_ACTIVE_RATIO", "FAT_SPAN",
    ]


if __name__ == "__main__":
    print("Interaction Features Module — use create_interaction_features(df)")
    print(f"Expected output features: {get_interaction_feature_names()}")
