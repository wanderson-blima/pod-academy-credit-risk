"""
Normalized Ratio Features — Phase 2.3
Creates ratio/proportion features within each domain.

Usage: Import create_ratio_features(df) from pipeline scripts.
"""
import numpy as np
import pandas as pd


def safe_divide(a, b, fill=0.0):
    """Division with zero/nan protection."""
    return np.where((b == 0) | b.isna() | a.isna(), fill, a / b)


def create_ratio_features(df):
    """Create normalized ratio features within domains.

    Returns DataFrame with ~10-15 new ratio features appended.
    """
    result = df.copy()

    # ── Recharge ratios ─────────────────────────────────────────────────────

    # Online recharge ratio
    if "REC_QTD_CARTAO_ONLINE" in df.columns and "REC_QTD_RECARGAS_TOTAL" in df.columns:
        result["REC_ONLINE_RATIO"] = safe_divide(
            df["REC_QTD_CARTAO_ONLINE"], df["REC_QTD_RECARGAS_TOTAL"]
        )

    # Platform diversity ratio
    if "REC_QTD_PLATAFORMAS" in df.columns and "REC_QTD_RECARGAS_TOTAL" in df.columns:
        result["REC_PLATFORM_DIVERSITY"] = safe_divide(
            df["REC_QTD_PLATAFORMAS"], df["REC_QTD_RECARGAS_TOTAL"]
        )

    # Chip prepaid ratio
    if "REC_QTD_CARTAO_CHIPPRE" in df.columns and "REC_QTD_RECARGAS_TOTAL" in df.columns:
        result["REC_CHIPPRE_RATIO"] = safe_divide(
            df["REC_QTD_CARTAO_CHIPPRE"], df["REC_QTD_RECARGAS_TOTAL"]
        )

    # Recharge value stability (CV is already a ratio, but normalize)
    if "REC_VLR_REAL_STDDEV" in df.columns and "REC_VLR_CREDITO_STDDEV" in df.columns:
        result["REC_VALUE_STABILITY"] = safe_divide(
            df["REC_VLR_REAL_STDDEV"], df["REC_VLR_CREDITO_STDDEV"]
        )

    # ── Payment ratios ──────────────────────────────────────────────────────

    # Payment with interest ratio
    if "PAG_QTD_PAGAMENTOS_COM_JUROS" in df.columns and "PAG_QTD_PAGAMENTOS_TOTAL" in df.columns:
        result["PAG_JUROS_RATIO"] = safe_divide(
            df["PAG_QTD_PAGAMENTOS_COM_JUROS"], df["PAG_QTD_PAGAMENTOS_TOTAL"]
        )

    # Open invoice ratio (status R = rejected/pending)
    if "PAG_QTD_STATUS_R" in df.columns and "PAG_QTD_PAGAMENTOS_TOTAL" in df.columns:
        result["PAG_OPEN_INVOICE_RATIO"] = safe_divide(
            df["PAG_QTD_STATUS_R"], df["PAG_QTD_PAGAMENTOS_TOTAL"]
        )

    # PA payment form ratio
    if "PAG_TAXA_FORMA_PA" in df.columns:
        # Already a rate — clip to [0, 1]
        result["PAG_PA_RATIO_CLIPPED"] = df["PAG_TAXA_FORMA_PA"].clip(0, 1).fillna(0)

    # ── Billing ratios ──────────────────────────────────────────────────────

    # First invoice ratio
    if "FAT_QTD_FATURAS_PRIMEIRA" in df.columns and "FAT_QTD_SAFRAS_DISTINTAS" in df.columns:
        result["FAT_FIRST_RATIO"] = safe_divide(
            df["FAT_QTD_FATURAS_PRIMEIRA"], df["FAT_QTD_SAFRAS_DISTINTAS"]
        )

    # Prepaid invoice ratio
    if "FAT_QTD_FAT_PREPG" in df.columns and "FAT_QTD_SAFRAS_DISTINTAS" in df.columns:
        result["FAT_PREPG_RATIO"] = safe_divide(
            df["FAT_QTD_FAT_PREPG"], df["FAT_QTD_SAFRAS_DISTINTAS"]
        )

    # ACA invoice ratio
    if "FAT_QTD_FATURAS_ACA" in df.columns and "FAT_QTD_SAFRAS_DISTINTAS" in df.columns:
        result["FAT_ACA_RATIO"] = safe_divide(
            df["FAT_QTD_FATURAS_ACA"], df["FAT_QTD_SAFRAS_DISTINTAS"]
        )

    # Delay ratio (atraso medio / dias desde ativacao)
    if "FAT_DIAS_ATRASO_MEDIO" in df.columns and "FAT_DIAS_DESDE_ATIVACAO_CONTA" in df.columns:
        result["FAT_DELAY_RATIO"] = safe_divide(
            df["FAT_DIAS_ATRASO_MEDIO"], df["FAT_DIAS_DESDE_ATIVACAO_CONTA"]
        )

    # Billing creation to due ratio
    if "FAT_DIAS_MEDIO_CRIACAO_VENCIMENTO" in df.columns and "FAT_DIAS_MAX_CRIACAO_VENCIMENTO" in df.columns:
        result["FAT_DUE_CONSISTENCY"] = safe_divide(
            df["FAT_DIAS_MEDIO_CRIACAO_VENCIMENTO"],
            df["FAT_DIAS_MAX_CRIACAO_VENCIMENTO"],
        )

    new_cols = [c for c in result.columns if c not in df.columns]
    print(f"[RATIOS] Created {len(new_cols)} ratio features: {new_cols}")

    return result


def get_ratio_feature_names():
    """Return list of all possible ratio feature names."""
    return [
        "REC_ONLINE_RATIO", "REC_PLATFORM_DIVERSITY",
        "REC_CHIPPRE_RATIO", "REC_VALUE_STABILITY",
        "PAG_JUROS_RATIO", "PAG_OPEN_INVOICE_RATIO", "PAG_PA_RATIO_CLIPPED",
        "FAT_FIRST_RATIO", "FAT_PREPG_RATIO", "FAT_ACA_RATIO",
        "FAT_DELAY_RATIO", "FAT_DUE_CONSISTENCY",
    ]


if __name__ == "__main__":
    print("Ratio Features Module — use create_ratio_features(df)")
    print(f"Expected output features: {get_ratio_feature_names()}")
