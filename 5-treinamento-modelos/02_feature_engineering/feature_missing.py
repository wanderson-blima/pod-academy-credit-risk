"""
Missing Data Features — Phase 2.1
Creates features from missing data patterns (nullity as signal).

Usage: Import create_missing_features(df) from pipeline scripts.
"""
import numpy as np
import pandas as pd


# Feature groups by domain prefix
REC_FEATURES = [
    "REC_SCORE_RISCO", "REC_TAXA_STATUS_A", "REC_QTD_LINHAS",
    "REC_DIAS_ENTRE_RECARGAS", "REC_QTD_INST_DIST_REG",
    "REC_DIAS_DESDE_ULTIMA_RECARGA", "REC_TAXA_CARTAO_ONLINE",
    "REC_QTD_STATUS_ZB2", "REC_QTD_CARTAO_ONLINE",
    "REC_COEF_VARIACAO_REAL", "REC_VLR_CREDITO_STDDEV",
    "REC_TAXA_PLAT_PREPG", "REC_VLR_REAL_STDDEV",
    "REC_QTD_CARTAO_CHIPPRE", "REC_QTD_PLANOS", "REC_QTD_PLAT_AUTOC",
    "REC_QTD_STATUS_ZB1", "REC_COEF_VARIACAO_CREDITO",
    "REC_FREQ_RECARGA_DIARIA", "REC_TAXA_PLAT_CONTROLE",
    "REC_QTD_RECARGAS_TOTAL", "REC_QTD_TIPOS_RECARGA",
    "REC_QTD_PLATAFORMAS", "REC_QTD_INSTITUICOES",
]

PAG_FEATURES = [
    "PAG_QTD_PAGAMENTOS_TOTAL", "PAG_TAXA_PAGAMENTOS_COM_JUROS",
    "PAG_DIAS_ENTRE_FATURAS", "PAG_QTD_FATURAS_DISTINTAS",
    "PAG_DIAS_DESDE_ULTIMA_FATURA", "PAG_TAXA_FORMA_PA",
    "PAG_QTD_PAGAMENTOS_COM_JUROS", "PAG_QTD_AREAS",
    "PAG_VLR_PAGAMENTO_FATURA_STDDEV", "PAG_FLAG_ALTO_RISCO",
    "PAG_QTD_STATUS_R", "PAG_COEF_VARIACAO_PAGAMENTO",
]

FAT_FEATURES = [
    "FAT_DIAS_MEDIO_CRIACAO_VENCIMENTO", "FAT_QTD_FATURAS_PRIMEIRA",
    "FAT_TAXA_PRIMEIRA_FAT", "FAT_DIAS_ATRASO_MIN",
    "FAT_DIAS_MAX_CRIACAO_VENCIMENTO", "FAT_DIAS_DESDE_ATIVACAO_CONTA",
    "FAT_DIAS_DESDE_ULTIMA_FAT", "FAT_DIAS_DESDE_PRIMEIRA_FAT",
    "FAT_DIAS_ATRASO_MEDIO", "FAT_QTD_FAT_PREPG",
    "FAT_QTD_FATURAS_ACA", "FAT_QTD_SAFRAS_DISTINTAS",
]


def create_missing_features(df):
    """Create features from missing data patterns.

    Returns DataFrame with new missing-pattern features appended.
    """
    result = df.copy()

    # Domain-level missing counts
    available_rec = [f for f in REC_FEATURES if f in df.columns]
    available_pag = [f for f in PAG_FEATURES if f in df.columns]
    available_fat = [f for f in FAT_FEATURES if f in df.columns]

    if available_rec:
        result["MISSING_REC_COUNT"] = df[available_rec].isna().sum(axis=1)
        result["MISSING_REC_RATIO"] = result["MISSING_REC_COUNT"] / len(available_rec)

    if available_pag:
        result["MISSING_PAG_COUNT"] = df[available_pag].isna().sum(axis=1)
        result["MISSING_PAG_RATIO"] = result["MISSING_PAG_COUNT"] / len(available_pag)

    if available_fat:
        result["MISSING_FAT_COUNT"] = df[available_fat].isna().sum(axis=1)
        result["MISSING_FAT_RATIO"] = result["MISSING_FAT_COUNT"] / len(available_fat)

    # Total missing ratio across all domains
    all_domain_feats = available_rec + available_pag + available_fat
    if all_domain_feats:
        result["MISSING_TOTAL_COUNT"] = df[all_domain_feats].isna().sum(axis=1)
        result["MISSING_TOTAL_RATIO"] = result["MISSING_TOTAL_COUNT"] / len(all_domain_feats)

    # Individual high-impact missing indicators
    # PAG status has ~54% null — strong signal
    if "PAG_QTD_PAGAMENTOS_TOTAL" in df.columns:
        result["PAG_IND_STATUS_MISSING"] = df["PAG_QTD_PAGAMENTOS_TOTAL"].isna().astype(int)

    if "PAG_FLAG_ALTO_RISCO" in df.columns:
        result["PAG_IND_RISCO_MISSING"] = df["PAG_FLAG_ALTO_RISCO"].isna().astype(int)

    if "FAT_DIAS_ATRASO_MIN" in df.columns:
        result["FAT_IND_ATRASO_MISSING"] = df["FAT_DIAS_ATRASO_MIN"].isna().astype(int)

    if "REC_DIAS_ENTRE_RECARGAS" in df.columns:
        result["REC_IND_RECARGA_MISSING"] = df["REC_DIAS_ENTRE_RECARGAS"].isna().astype(int)

    # Multi-domain missing pattern — binary encoding
    if available_rec and available_pag and available_fat:
        result["MISSING_PATTERN"] = (
            (result.get("MISSING_REC_COUNT", 0) > 0).astype(int) * 4 +
            (result.get("MISSING_PAG_COUNT", 0) > 0).astype(int) * 2 +
            (result.get("MISSING_FAT_COUNT", 0) > 0).astype(int) * 1
        )

    new_cols = [c for c in result.columns if c not in df.columns]
    print(f"[MISSING] Created {len(new_cols)} missing-pattern features: {new_cols}")

    return result


def get_missing_feature_names():
    """Return list of all possible missing feature names."""
    return [
        "MISSING_REC_COUNT", "MISSING_REC_RATIO",
        "MISSING_PAG_COUNT", "MISSING_PAG_RATIO",
        "MISSING_FAT_COUNT", "MISSING_FAT_RATIO",
        "MISSING_TOTAL_COUNT", "MISSING_TOTAL_RATIO",
        "PAG_IND_STATUS_MISSING", "PAG_IND_RISCO_MISSING",
        "FAT_IND_ATRASO_MISSING", "REC_IND_RECARGA_MISSING",
        "MISSING_PATTERN",
    ]


if __name__ == "__main__":
    # Test with sample data
    print("Missing Features Module — use create_missing_features(df)")
    print(f"Expected output features: {get_missing_feature_names()}")
