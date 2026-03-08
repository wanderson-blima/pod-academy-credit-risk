"""
Temporal Features — Phase 2.4
Creates temporal/lifecycle features from snapshot-level data.

Usage: Import create_temporal_features(df) from pipeline scripts.
"""
import numpy as np
import pandas as pd


def safe_divide(a, b, fill=0.0):
    """Division with zero/nan protection."""
    return np.where((b == 0) | b.isna() | a.isna(), fill, a / b)


def create_temporal_features(df):
    """Create temporal and lifecycle features.

    Returns DataFrame with ~10-12 new temporal features appended.
    """
    result = df.copy()

    # ── Tenure and lifecycle ────────────────────────────────────────────────

    if "FAT_DIAS_DESDE_ATIVACAO_CONTA" in df.columns:
        # Tenure buckets
        result["TENURE_BUCKET"] = pd.cut(
            df["FAT_DIAS_DESDE_ATIVACAO_CONTA"].fillna(0),
            bins=[-1, 30, 90, 180, 365, 730, float("inf")],
            labels=[0, 1, 2, 3, 4, 5],  # 0=new, 5=mature
        ).astype(float)

        # Lifecycle stage (more granular)
        result["LIFECYCLE_STAGE"] = pd.cut(
            df["FAT_DIAS_DESDE_ATIVACAO_CONTA"].fillna(0),
            bins=[-1, 60, 180, 365, float("inf")],
            labels=[0, 1, 2, 3],  # 0=onboarding, 1=growth, 2=established, 3=mature
        ).astype(float)

    # ── Recency features ────────────────────────────────────────────────────

    if "REC_DIAS_DESDE_ULTIMA_RECARGA" in df.columns:
        # Recency gap — how recently customer recharged relative to typical interval
        if "REC_DIAS_ENTRE_RECARGAS" in df.columns:
            result["RECENCY_GAP"] = (
                df["REC_DIAS_DESDE_ULTIMA_RECARGA"].fillna(0) -
                df["REC_DIAS_ENTRE_RECARGAS"].fillna(0)
            )

        # Recency bucket
        result["RECENCY_BUCKET"] = pd.cut(
            df["REC_DIAS_DESDE_ULTIMA_RECARGA"].fillna(999),
            bins=[-1, 7, 15, 30, 60, float("inf")],
            labels=[0, 1, 2, 3, 4],  # 0=very_recent, 4=dormant
        ).astype(float)

    # ── Velocity changes ────────────────────────────────────────────────────

    if "REC_FREQ_RECARGA_DIARIA" in df.columns and "REC_DIAS_ENTRE_RECARGAS" in df.columns:
        # Recharge velocity: freq / interval (higher = more active)
        result["RECHARGE_VELOCITY"] = safe_divide(
            df["REC_FREQ_RECARGA_DIARIA"],
            df["REC_DIAS_ENTRE_RECARGAS"],
        )

    # ── Activity ratio ──────────────────────────────────────────────────────

    if "FAT_DIAS_DESDE_ATIVACAO_CONTA" in df.columns and "FAT_QTD_SAFRAS_DISTINTAS" in df.columns:
        # How many distinct SAFRAs relative to total time
        result["SAFRA_DENSITY"] = safe_divide(
            df["FAT_QTD_SAFRAS_DISTINTAS"],
            df["FAT_DIAS_DESDE_ATIVACAO_CONTA"] / 30,  # months
        )

    # ── Billing timing patterns ─────────────────────────────────────────────

    if "FAT_DIAS_DESDE_PRIMEIRA_FAT" in df.columns and "FAT_DIAS_DESDE_ULTIMA_FAT" in df.columns:
        # Active billing window
        result["BILLING_WINDOW"] = (
            df["FAT_DIAS_DESDE_PRIMEIRA_FAT"].fillna(0) -
            df["FAT_DIAS_DESDE_ULTIMA_FAT"].fillna(0)
        )

    if "FAT_DIAS_ATRASO_MEDIO" in df.columns and "FAT_DIAS_ATRASO_MIN" in df.columns:
        # Delay trend: avg - min (positive = worsening pattern)
        result["DELAY_TREND"] = (
            df["FAT_DIAS_ATRASO_MEDIO"].fillna(0) -
            df["FAT_DIAS_ATRASO_MIN"].fillna(0)
        )

    # ── Payment timing ──────────────────────────────────────────────────────

    if "PAG_DIAS_ENTRE_FATURAS" in df.columns and "PAG_DIAS_DESDE_ULTIMA_FATURA" in df.columns:
        # Payment regularity: recent interval vs average
        result["PAYMENT_REGULARITY"] = safe_divide(
            df["PAG_DIAS_DESDE_ULTIMA_FATURA"],
            df["PAG_DIAS_ENTRE_FATURAS"],
        )

    new_cols = [c for c in result.columns if c not in df.columns]
    print(f"[TEMPORAL] Created {len(new_cols)} temporal features: {new_cols}")

    return result


def get_temporal_feature_names():
    """Return list of all possible temporal feature names."""
    return [
        "TENURE_BUCKET", "LIFECYCLE_STAGE",
        "RECENCY_GAP", "RECENCY_BUCKET",
        "RECHARGE_VELOCITY",
        "SAFRA_DENSITY",
        "BILLING_WINDOW", "DELAY_TREND",
        "PAYMENT_REGULARITY",
    ]


if __name__ == "__main__":
    print("Temporal Features Module — use create_temporal_features(df)")
    print(f"Expected output features: {get_temporal_feature_names()}")
