"""
Feature Selection — 5-Stage Funnel for Credit Risk Model
=========================================================
Standalone script for OCI Data Science.
Reads Gold consolidated parquet, runs multi-stage feature selection,
generates diagnostic plots and saves artifacts.

Stages:
  1. Information Value (IV > 0.02)
  2. L1 LogisticRegression (keep coef != 0)
  3. Correlation filter (|r| > 0.90, prefer reference features, tie-break by IV)
  4. PSI < 0.25 (train vs OOT stability)
  5. Anti-leakage (VLR_FPD, TARGET_FPD, _LEAKAGE patterns + corr > 0.95 with target)

Usage:
  python feature_selection.py

Environment variables (optional):
  DATA_PATH     — local path to consolidated parquet (default: /home/datascience/data/clientes_consolidado/)
  ARTIFACT_DIR  — output directory for artifacts (default: /home/datascience/artifacts)
  OCI_NAMESPACE — OCI namespace (default: grlxi07jz1mo)

Hackathon PoD Academy (Claro + Oracle)
"""

import json
import os
import re
import sys
import time
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

# =============================================================================
# CONFIGURATION
# =============================================================================
NAMESPACE = os.environ.get("OCI_NAMESPACE", "grlxi07jz1mo")
GOLD_BUCKET = "pod-academy-gold"
TARGET = "FPD"

TRAIN_SAFRAS = [202410, 202411, 202412, 202501]
OOT_SAFRAS = [202502, 202503]

LOCAL_DATA_PATH = os.environ.get(
    "DATA_PATH", "/home/datascience/data/clientes_consolidado/"
)
ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", "/home/datascience/artifacts")

# Reference features from previous Fabric selection (used for correlation tie-breaking)
SELECTED_FEATURES_REF = [
    "TARGET_SCORE_02", "TARGET_SCORE_01",
    "REC_SCORE_RISCO", "REC_TAXA_STATUS_A", "REC_QTD_LINHAS",
    "REC_DIAS_ENTRE_RECARGAS", "REC_QTD_INST_DIST_REG",
    "REC_DIAS_DESDE_ULTIMA_RECARGA", "REC_TAXA_CARTAO_ONLINE",
    "REC_QTD_STATUS_ZB2", "REC_QTD_CARTAO_ONLINE",
    "REC_COEF_VARIACAO_REAL", "var_26",
    "FAT_DIAS_MEDIO_CRIACAO_VENCIMENTO", "REC_VLR_CREDITO_STDDEV",
    "REC_TAXA_PLAT_PREPG", "REC_VLR_REAL_STDDEV",
    "REC_QTD_CARTAO_CHIPPRE", "REC_QTD_PLANOS", "REC_QTD_PLAT_AUTOC",
    "PAG_QTD_PAGAMENTOS_TOTAL", "FAT_QTD_FATURAS_PRIMEIRA", "var_73",
    "REC_QTD_STATUS_ZB1", "FAT_TAXA_PRIMEIRA_FAT", "FAT_DIAS_ATRASO_MIN",
    "PAG_TAXA_PAGAMENTOS_COM_JUROS", "FAT_DIAS_MAX_CRIACAO_VENCIMENTO",
    "REC_COEF_VARIACAO_CREDITO", "PAG_DIAS_ENTRE_FATURAS",
    "FAT_DIAS_DESDE_ATIVACAO_CONTA", "var_85", "REC_FREQ_RECARGA_DIARIA",
    "FAT_DIAS_DESDE_ULTIMA_FAT", "FAT_DIAS_DESDE_PRIMEIRA_FAT",
    "PAG_QTD_FATURAS_DISTINTAS", "var_82", "PAG_DIAS_DESDE_ULTIMA_FATURA",
    "REC_TAXA_PLAT_CONTROLE", "var_90", "PAG_TAXA_FORMA_PA",
    "PAG_QTD_PAGAMENTOS_COM_JUROS", "PAG_QTD_AREAS",
    "FAT_DIAS_ATRASO_MEDIO", "REC_QTD_RECARGAS_TOTAL", "var_28", "var_44",
    "PAG_VLR_PAGAMENTO_FATURA_STDDEV", "REC_QTD_TIPOS_RECARGA",
    "var_34", "FAT_QTD_FAT_PREPG", "PAG_FLAG_ALTO_RISCO", "var_67",
    "REC_QTD_PLATAFORMAS", "PAG_QTD_STATUS_R",
    "PAG_COEF_VARIACAO_PAGAMENTO", "FAT_QTD_FATURAS_ACA",
    "REC_QTD_INSTITUICOES", "FAT_QTD_SAFRAS_DISTINTAS",
]

# Columns to exclude from feature candidates
ID_COLS = ["NUM_CPF", "SAFRA", "FLAG_INSTALACAO", "PROD", "flag_mig2", "STATUSRF",
           "DATADENASCIMENTO", "CEP_3_digitos", "_execution_id", "_data_inclusao",
           "_data_alteracao_silver", "DT_PROCESSAMENTO"]

# Leakage patterns
LEAKAGE_PATTERNS = [r"VLR_FPD", r"TARGET_FPD", r"_LEAKAGE"]

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

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


def psi_alert(psi_value):
    """PSI traffic-light classification."""
    if psi_value < 0.10:
        return "GREEN"
    elif psi_value < 0.25:
        return "YELLOW"
    else:
        return "RED"


def compute_iv(feature_series, target_series, bins=10):
    """
    Information Value for a single numeric feature against binary target.
    Uses equal-frequency binning with 10 bins.
    """
    df_temp = pd.DataFrame({"feat": feature_series, "target": target_series}).dropna()
    if df_temp.empty or df_temp["target"].nunique() < 2:
        return 0.0

    n_good = (df_temp["target"] == 0).sum()
    n_bad = (df_temp["target"] == 1).sum()
    if n_good == 0 or n_bad == 0:
        return 0.0

    try:
        df_temp["bin"] = pd.qcut(df_temp["feat"], q=bins, duplicates="drop")
    except ValueError:
        return 0.0

    grouped = df_temp.groupby("bin", observed=True)["target"]
    stats = grouped.agg(["sum", "count"])
    stats.columns = ["bad", "total"]
    stats["good"] = stats["total"] - stats["bad"]

    # Add smoothing to avoid log(0)
    stats["bad_pct"] = (stats["bad"] + 0.5) / (n_bad + 0.5 * len(stats))
    stats["good_pct"] = (stats["good"] + 0.5) / (n_good + 0.5 * len(stats))

    stats["woe"] = np.log(stats["good_pct"] / stats["bad_pct"])
    stats["iv_bin"] = (stats["good_pct"] - stats["bad_pct"]) * stats["woe"]

    iv = stats["iv_bin"].sum()
    return round(iv, 6)


# =============================================================================
# DATA LOADING
# =============================================================================

def get_data_path():
    """Return validated data path."""
    local_path = Path(LOCAL_DATA_PATH)
    if local_path.exists():
        return local_path
    print(f"[ERROR] Data path not found: {local_path}")
    print("[ERROR] Set DATA_PATH env var to a local parquet directory.")
    sys.exit(1)


def load_columns(columns):
    """Load specific columns from parquet dataset (memory-efficient)."""
    data_path = get_data_path()
    table = pq.read_table(data_path, columns=columns)
    return table.to_pandas()


def load_data():
    """Load Gold consolidated parquet — only metadata columns for initial inspection."""
    data_path = get_data_path()
    print(f"[DATA] Using data path: {data_path}")

    # Read schema to get column names without loading data
    ds = pq.ParquetDataset(data_path)
    all_columns = ds.schema.names
    print(f"[DATA] Schema has {len(all_columns)} columns")

    # Load only SAFRA + TARGET for split and summary
    df_meta = load_columns(["SAFRA", TARGET])
    n_rows = len(df_meta)
    print(f"[DATA] {n_rows:,} rows")
    print(f"[DATA] SAFRAs present: {sorted(df_meta['SAFRA'].unique())}")
    print(f"[DATA] Target '{TARGET}' distribution:\n{df_meta[TARGET].value_counts().to_string()}")

    return df_meta, all_columns


# =============================================================================
# FEATURE CANDIDATE SELECTION
# =============================================================================

def get_candidate_features(all_columns):
    """Identify numeric feature candidates from parquet schema, excluding IDs, target, and metadata."""
    import pyarrow as pa
    data_path = get_data_path()
    ds = pq.ParquetDataset(data_path)
    schema = ds.schema

    exclude = set(ID_COLS + [TARGET])
    numeric_types = (pa.int8(), pa.int16(), pa.int32(), pa.int64(),
                     pa.float16(), pa.float32(), pa.float64())
    candidates = []
    for i in range(len(schema)):
        field = schema.field(i)
        if field.name in exclude:
            continue
        if any(field.type == t for t in numeric_types):
            candidates.append(field.name)
    print(f"[CANDIDATES] {len(candidates)} numeric feature candidates identified")
    return sorted(candidates)


# =============================================================================
# STAGE 1: INFORMATION VALUE (IV > 0.02)
# =============================================================================

def stage_1_iv(train_safras, candidates, threshold=0.02):
    """Filter features by Information Value > threshold. Loads columns one-by-one."""
    print("\n" + "=" * 70)
    print("STAGE 1: Information Value (IV > {:.2f})".format(threshold))
    print("=" * 70)

    # Load target for train rows
    df_meta = load_columns(["SAFRA", TARGET])
    train_mask = df_meta["SAFRA"].isin(train_safras)
    target_train = df_meta.loc[train_mask, TARGET].values
    del df_meta

    iv_scores = {}
    data_path = get_data_path()
    for i, col in enumerate(candidates):
        col_data = pq.read_table(data_path, columns=[col]).to_pandas()[col].values
        col_train = col_data[train_mask.values]
        del col_data
        iv = compute_iv(pd.Series(col_train), pd.Series(target_train), bins=10)
        iv_scores[col] = iv
        if (i + 1) % 50 == 0:
            print(f"  ... computed IV for {i + 1}/{len(candidates)} features")

    iv_df = pd.DataFrame([
        {"feature": k, "iv": v} for k, v in iv_scores.items()
    ]).sort_values("iv", ascending=False).reset_index(drop=True)

    passed = iv_df[iv_df["iv"] > threshold]["feature"].tolist()
    removed = iv_df[iv_df["iv"] <= threshold]["feature"].tolist()

    print(f"  Passed: {len(passed)} | Removed: {len(removed)}")
    print(f"  Top-5 IV: {iv_df.head(5)[['feature', 'iv']].to_string(index=False)}")
    if removed:
        bottom = iv_df[iv_df["iv"] <= threshold].tail(5)
        print(f"  Bottom-5 removed: {bottom[['feature', 'iv']].to_string(index=False)}")

    return passed, iv_scores, iv_df


# =============================================================================
# STAGE 2: L1 LOGISTIC REGRESSION (coef != 0)
# =============================================================================

def stage_2_l1(train_safras, features, C=1.0, subsample=50000):
    """Keep features with non-zero L1 coefficients. Uses subsampling for memory."""
    print("\n" + "=" * 70)
    print(f"STAGE 2: L1 LogisticRegression (C={C}, liblinear, balanced)")
    print("=" * 70)

    # Load target + SAFRA to get train mask
    df_meta = load_columns(["SAFRA", TARGET])
    train_mask = df_meta["SAFRA"].isin(train_safras)
    y_full = df_meta.loc[train_mask, TARGET].values
    train_indices = np.where(train_mask.values)[0]
    del df_meta

    # Drop rows with NaN target
    valid_mask = ~np.isnan(y_full)
    train_indices = train_indices[valid_mask]
    y_full = y_full[valid_mask]
    print(f"  Train rows with valid target: {len(train_indices):,}")

    # Subsample for L1 to save memory
    if len(train_indices) > subsample:
        rng = np.random.RandomState(42)
        sample_idx = rng.choice(len(train_indices), subsample, replace=False)
        sample_idx.sort()
        row_indices = train_indices[sample_idx]
        y = y_full[sample_idx]
        print(f"  Subsampled {subsample:,} rows from {len(train_indices):,} train rows")
    else:
        row_indices = train_indices
        y = y_full

    # Load features in batches of 30
    data_path = get_data_path()
    batch_size = 30
    all_data = {}
    for b_start in range(0, len(features), batch_size):
        batch_feats = features[b_start:b_start + batch_size]
        tbl = pq.read_table(data_path, columns=batch_feats)
        df_batch = tbl.to_pandas()
        for col in batch_feats:
            all_data[col] = df_batch[col].values[row_indices]
        del tbl, df_batch
        print(f"  ... loaded {min(b_start + batch_size, len(features))}/{len(features)} features")

    X = pd.DataFrame(all_data, columns=features)
    del all_data

    # Fill missing with median and replace inf
    for col in X.columns:
        X[col] = X[col].replace([np.inf, -np.inf], np.nan)
        median_val = X[col].median()
        if np.isnan(median_val):
            median_val = 0.0
        X[col] = X[col].fillna(median_val)

    # Standardize
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    del X

    # Fit L1
    lr = LogisticRegression(
        penalty="l1", C=C, solver="liblinear",
        class_weight="balanced", max_iter=1000, random_state=42
    )
    lr.fit(X_scaled, y)

    coefs = pd.Series(lr.coef_[0], index=features)
    nonzero_mask = coefs.abs() > 0
    passed = coefs[nonzero_mask].index.tolist()
    removed = coefs[~nonzero_mask].index.tolist()

    print(f"  Non-zero coefs: {nonzero_mask.sum()} | Zero coefs: {(~nonzero_mask).sum()}")
    print(f"  Passed: {len(passed)} | Removed: {len(removed)}")
    top_coefs = coefs.abs().sort_values(ascending=False).head(10)
    print(f"  Top-10 |coef|:\n    {top_coefs.to_string()}")

    return passed


# =============================================================================
# STAGE 3: CORRELATION FILTER (|r| > 0.90)
# =============================================================================

def stage_3_correlation(train_safras, features, iv_scores, threshold=0.90):
    """
    Remove highly correlated features. Loads train data for correlation.
    When |r| > threshold, prefer:
      1. Feature in SELECTED_FEATURES_REF (reference from Fabric)
      2. Higher IV score (tie-break)
    """
    print("\n" + "=" * 70)
    print(f"STAGE 3: Correlation filter (|r| > {threshold})")
    print("=" * 70)

    # Load features + SAFRA to filter train rows
    cols_to_load = features + ["SAFRA"]
    data_path = get_data_path()

    # Load in batches to manage memory, but we need all features for correlation matrix
    df_meta = load_columns(["SAFRA"])
    train_mask = df_meta["SAFRA"].isin(train_safras).values
    del df_meta

    batch_size = 30
    all_data = {}
    for b_start in range(0, len(features), batch_size):
        batch_feats = features[b_start:b_start + batch_size]
        tbl = pq.read_table(data_path, columns=batch_feats)
        df_batch = tbl.to_pandas()
        for col in batch_feats:
            all_data[col] = df_batch[col].values[train_mask]
        del tbl, df_batch
        print(f"  ... loaded {min(b_start + batch_size, len(features))}/{len(features)} features for correlation")

    X = pd.DataFrame(all_data, columns=features).fillna(0)
    del all_data
    corr_matrix = X.corr().abs()
    del X

    ref_set = set(SELECTED_FEATURES_REF)
    to_drop = set()

    for i in range(len(features)):
        if features[i] in to_drop:
            continue
        for j in range(i + 1, len(features)):
            if features[j] in to_drop:
                continue
            if corr_matrix.iloc[i, j] > threshold:
                fi, fj = features[i], features[j]
                iv_i = iv_scores.get(fi, 0)
                iv_j = iv_scores.get(fj, 0)

                fi_in_ref = fi in ref_set
                fj_in_ref = fj in ref_set

                if fi_in_ref and not fj_in_ref:
                    drop = fj
                elif fj_in_ref and not fi_in_ref:
                    drop = fi
                else:
                    drop = fj if iv_i >= iv_j else fi

                to_drop.add(drop)
                print(f"  Corr({fi}, {fj}) = {corr_matrix.iloc[i, j]:.3f} -> drop '{drop}'")

    passed = [f for f in features if f not in to_drop]
    print(f"\n  Passed: {len(passed)} | Removed: {len(to_drop)}")

    return passed, corr_matrix


# =============================================================================
# STAGE 4: PSI < 0.25 (Train vs OOT stability)
# =============================================================================

def stage_4_psi(train_safras, oot_safras, features, threshold=0.25):
    """Remove features with PSI >= threshold. Loads columns one-by-one."""
    print("\n" + "=" * 70)
    print(f"STAGE 4: PSI < {threshold} (train vs OOT stability)")
    print("=" * 70)

    df_meta = load_columns(["SAFRA"])
    train_mask = df_meta["SAFRA"].isin(train_safras).values
    oot_mask = df_meta["SAFRA"].isin(oot_safras).values
    del df_meta

    data_path = get_data_path()
    psi_scores = {}
    for i, col in enumerate(features):
        col_data = pq.read_table(data_path, columns=[col]).to_pandas()[col].values
        train_vals = col_data[train_mask]
        oot_vals = col_data[oot_mask]
        del col_data

        # Drop NaN
        train_vals = train_vals[~np.isnan(train_vals)] if train_vals.dtype.kind == 'f' else train_vals
        oot_vals = oot_vals[~np.isnan(oot_vals)] if oot_vals.dtype.kind == 'f' else oot_vals

        if len(train_vals) < 10 or len(oot_vals) < 10:
            psi_scores[col] = 0.0
            continue

        psi_val = compute_psi(train_vals, oot_vals, bins=10)
        psi_scores[col] = psi_val

        if (i + 1) % 20 == 0:
            print(f"  ... computed PSI for {i + 1}/{len(features)} features")

    psi_df = pd.DataFrame([
        {"feature": k, "psi": v, "alert": psi_alert(v)}
        for k, v in psi_scores.items()
    ]).sort_values("psi", ascending=False).reset_index(drop=True)

    passed = psi_df[psi_df["psi"] < threshold]["feature"].tolist()
    removed = psi_df[psi_df["psi"] >= threshold]["feature"].tolist()

    print(f"  Distribution: GREEN={sum(1 for v in psi_scores.values() if v < 0.10)}, "
          f"YELLOW={sum(1 for v in psi_scores.values() if 0.10 <= v < 0.25)}, "
          f"RED={sum(1 for v in psi_scores.values() if v >= 0.25)}")
    print(f"  Passed: {len(passed)} | Removed: {len(removed)}")
    if removed:
        print(f"  Removed features (PSI >= {threshold}):")
        for f in removed:
            print(f"    {f}: PSI={psi_scores[f]:.4f} [{psi_alert(psi_scores[f])}]")

    return passed, psi_scores, psi_df


# =============================================================================
# STAGE 5: ANTI-LEAKAGE
# =============================================================================

def stage_5_antileakage(train_safras, features, target_corr_threshold=0.95):
    """
    Remove features that leak target information. Loads columns one-by-one.
      - Name matches VLR_FPD, TARGET_FPD, or _LEAKAGE patterns
      - |correlation with target| > 0.95
    """
    print("\n" + "=" * 70)
    print(f"STAGE 5: Anti-leakage (patterns + |corr with target| > {target_corr_threshold})")
    print("=" * 70)

    pattern_removed = []
    corr_removed = []

    # Check name patterns
    for col in features:
        for pat in LEAKAGE_PATTERNS:
            if re.search(pat, col, re.IGNORECASE):
                pattern_removed.append(col)
                print(f"  Pattern match: '{col}' matches '{pat}'")
                break

    remaining = [f for f in features if f not in pattern_removed]

    # Load target for train rows
    df_meta = load_columns(["SAFRA", TARGET])
    train_mask = df_meta["SAFRA"].isin(train_safras).values
    target_vals = df_meta.loc[train_mask, TARGET].values
    del df_meta

    # Check correlation with target - load one column at a time
    data_path = get_data_path()
    for col in remaining:
        col_data = pq.read_table(data_path, columns=[col]).to_pandas()[col].values
        vals = col_data[train_mask]
        del col_data
        vals = np.nan_to_num(vals, nan=0.0)
        corr = np.corrcoef(vals, target_vals)[0, 1]
        if abs(corr) > target_corr_threshold:
            corr_removed.append(col)
            print(f"  High target corr: '{col}' corr={corr:.4f}")

    all_removed = set(pattern_removed + corr_removed)
    passed = [f for f in features if f not in all_removed]

    print(f"\n  Pattern removed: {len(pattern_removed)} | Corr removed: {len(corr_removed)}")
    print(f"  Passed: {len(passed)} | Total removed: {len(all_removed)}")

    return passed


# =============================================================================
# PLOTS
# =============================================================================

def plot_iv_top30(iv_df, plot_dir):
    """Bar chart of top-30 features by IV."""
    top30 = iv_df.head(30).copy()
    fig, ax = plt.subplots(figsize=(12, 8))
    colors = ["#2ecc71" if v > 0.3 else "#f39c12" if v > 0.1 else "#e74c3c" if v > 0.02 else "#95a5a6"
              for v in top30["iv"]]
    ax.barh(range(len(top30)), top30["iv"].values, color=colors)
    ax.set_yticks(range(len(top30)))
    ax.set_yticklabels(top30["feature"].values, fontsize=8)
    ax.set_xlabel("Information Value")
    ax.set_title("Top-30 Features by Information Value")
    ax.invert_yaxis()
    ax.axvline(x=0.02, color="red", linestyle="--", alpha=0.7, label="IV=0.02 threshold")
    ax.axvline(x=0.1, color="orange", linestyle="--", alpha=0.5, label="IV=0.10 (medium)")
    ax.axvline(x=0.3, color="green", linestyle="--", alpha=0.5, label="IV=0.30 (strong)")
    ax.legend(fontsize=8)
    plt.tight_layout()
    path = os.path.join(plot_dir, "iv_top30.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  Saved: {path}")
    return path


def plot_correlation_heatmap(corr_matrix, selected_features, plot_dir, max_features=40):
    """Correlation heatmap for selected features."""
    feats = selected_features[:max_features]
    sub = corr_matrix.loc[feats, feats] if all(f in corr_matrix.index for f in feats) else None
    if sub is None or sub.empty:
        print("  [WARN] Could not generate correlation heatmap (missing features in matrix)")
        return None

    fig, ax = plt.subplots(figsize=(14, 12))
    im = ax.imshow(sub.values, cmap="RdYlBu_r", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(len(feats)))
    ax.set_yticks(range(len(feats)))
    ax.set_xticklabels(feats, rotation=90, fontsize=6)
    ax.set_yticklabels(feats, fontsize=6)
    ax.set_title(f"Correlation Heatmap (top {len(feats)} selected features)")
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    plt.tight_layout()
    path = os.path.join(plot_dir, "correlation_heatmap.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  Saved: {path}")
    return path


def plot_psi_bar(psi_df, plot_dir):
    """PSI bar chart for all features evaluated in Stage 4."""
    if psi_df.empty:
        return None

    top = psi_df.head(40).copy()
    fig, ax = plt.subplots(figsize=(12, 8))
    colors = ["#2ecc71" if a == "GREEN" else "#f39c12" if a == "YELLOW" else "#e74c3c"
              for a in top["alert"]]
    ax.barh(range(len(top)), top["psi"].values, color=colors)
    ax.set_yticks(range(len(top)))
    ax.set_yticklabels(top["feature"].values, fontsize=8)
    ax.set_xlabel("PSI")
    ax.set_title("Population Stability Index (top 40 by PSI)")
    ax.invert_yaxis()
    ax.axvline(x=0.10, color="orange", linestyle="--", alpha=0.7, label="PSI=0.10 (YELLOW)")
    ax.axvline(x=0.25, color="red", linestyle="--", alpha=0.7, label="PSI=0.25 (RED)")
    ax.legend(fontsize=8)
    plt.tight_layout()
    path = os.path.join(plot_dir, "psi_bar.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  Saved: {path}")
    return path


# =============================================================================
# MAIN
# =============================================================================

def main():
    t0 = time.time()
    print("=" * 70)
    print("FEATURE SELECTION — 5-Stage Funnel (Memory-Efficient)")
    print("Hackathon PoD Academy (Claro + Oracle)")
    print("=" * 70)

    # ── Setup artifact directories ──────────────────────────────────────
    artifact_dir = Path(ARTIFACT_DIR)
    plot_dir = artifact_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    # ── Check if pre-computed selected_features.json exists ─────────────
    # If it exists and has features, skip the full funnel (saves ~30-60 min)
    # To force re-computation, delete the file before running.
    precomputed_path = artifact_dir / "selected_features.json"
    force_rerun = os.environ.get("FORCE_FEATURE_SELECTION", "").lower() in ("1", "true", "yes")
    if precomputed_path.exists() and not force_rerun:
        with open(precomputed_path) as f:
            existing = json.load(f)
        existing_features = existing.get("selected_features", existing.get("features", []))
        if len(existing_features) > 0:
            print(f"\n[SKIP] Pre-computed selected_features.json found: {len(existing_features)} features")
            print(f"  Path: {precomputed_path}")
            print(f"  To force re-computation: export FORCE_FEATURE_SELECTION=1")
            print(f"\n[DONE] Using existing feature selection (elapsed: 0.0s)")
            return existing_features

    # ── Load metadata (only SAFRA + TARGET) ─────────────────────────────
    df_meta, all_columns = load_data()

    # ── Split info ──────────────────────────────────────────────────────
    train_count = df_meta["SAFRA"].isin(TRAIN_SAFRAS).sum()
    oot_count = df_meta["SAFRA"].isin(OOT_SAFRAS).sum()
    print(f"\n[SPLIT] Train: {train_count:,} rows (SAFRAs {TRAIN_SAFRAS})")
    print(f"[SPLIT] OOT:   {oot_count:,} rows (SAFRAs {OOT_SAFRAS})")
    del df_meta

    if train_count == 0:
        print("[ERROR] No training data found. Check SAFRA values.")
        sys.exit(1)

    # ── Get candidates (from parquet schema) ────────────────────────────
    candidates = get_candidate_features(all_columns)
    funnel = {"initial_candidates": len(candidates)}

    # ── Stage 1: IV (column-by-column) ──────────────────────────────────
    s1_features, iv_scores, iv_df = stage_1_iv(TRAIN_SAFRAS, candidates, threshold=0.02)
    funnel["stage_1_iv"] = len(s1_features)

    # ── Stage 2: L1 (subsampled, batch-loaded) ──────────────────────────
    s2_features = stage_2_l1(TRAIN_SAFRAS, s1_features, C=1.0)
    funnel["stage_2_l1"] = len(s2_features)

    # ── Stage 3: Correlation (batch-loaded) ─────────────────────────────
    s3_features, corr_matrix = stage_3_correlation(TRAIN_SAFRAS, s2_features, iv_scores, threshold=0.90)
    funnel["stage_3_corr"] = len(s3_features)

    # ── Stage 4: PSI (column-by-column) ─────────────────────────────────
    if oot_count == 0:
        print("\n[WARN] No OOT data available. Skipping PSI stage.")
        s4_features = s3_features
        psi_scores = {}
        psi_df = pd.DataFrame()
    else:
        s4_features, psi_scores, psi_df = stage_4_psi(TRAIN_SAFRAS, OOT_SAFRAS, s3_features, threshold=0.25)
    funnel["stage_4_psi"] = len(s4_features)

    # ── Stage 5: Anti-leakage (column-by-column) ───────────────────────
    s5_features = stage_5_antileakage(TRAIN_SAFRAS, s4_features, target_corr_threshold=0.95)
    funnel["stage_5_antileakage"] = len(s5_features)

    # ── Final selected features ─────────────────────────────────────────
    selected = s5_features
    funnel["final_selected"] = len(selected)

    # ── Generate plots ──────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("GENERATING PLOTS")
    print("=" * 70)
    plot_iv_top30(iv_df, str(plot_dir))
    plot_correlation_heatmap(corr_matrix, selected, str(plot_dir))
    if not psi_df.empty:
        plot_psi_bar(psi_df, str(plot_dir))

    # ── Save artifacts ──────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("SAVING ARTIFACTS")
    print("=" * 70)

    # 1. selected_features.json
    features_path = artifact_dir / "selected_features.json"
    with open(features_path, "w") as f:
        json.dump({
            "selected_features": selected,
            "count": len(selected),
            "target": TARGET,
            "train_safras": TRAIN_SAFRAS,
            "oot_safras": OOT_SAFRAS,
            "iv_scores": {feat: iv_scores.get(feat, 0) for feat in selected},
            "psi_scores": {feat: psi_scores.get(feat, 0) for feat in selected},
        }, f, indent=2)
    print(f"  Saved: {features_path}")

    # 2. Funnel summary
    funnel_path = artifact_dir / "funnel_summary.json"
    with open(funnel_path, "w") as f:
        json.dump(funnel, f, indent=2)
    print(f"  Saved: {funnel_path}")

    # 3. IV scores (full)
    iv_path = artifact_dir / "iv_scores.csv"
    iv_df.to_csv(iv_path, index=False)
    print(f"  Saved: {iv_path}")

    # 4. PSI scores (if available)
    if not psi_df.empty:
        psi_path = artifact_dir / "psi_scores.csv"
        psi_df.to_csv(psi_path, index=False)
        print(f"  Saved: {psi_path}")

    # ── Print summary ───────────────────────────────────────────────────
    elapsed = time.time() - t0
    print("\n" + "=" * 70)
    print("FUNNEL SUMMARY")
    print("=" * 70)
    print(f"  Initial candidates:      {funnel['initial_candidates']:>5}")
    print(f"  Stage 1 (IV > 0.02):     {funnel['stage_1_iv']:>5}  (-{funnel['initial_candidates'] - funnel['stage_1_iv']})")
    print(f"  Stage 2 (L1 coef != 0):  {funnel['stage_2_l1']:>5}  (-{funnel['stage_1_iv'] - funnel['stage_2_l1']})")
    print(f"  Stage 3 (|r| < 0.90):    {funnel['stage_3_corr']:>5}  (-{funnel['stage_2_l1'] - funnel['stage_3_corr']})")
    print(f"  Stage 4 (PSI < 0.25):    {funnel['stage_4_psi']:>5}  (-{funnel['stage_3_corr'] - funnel['stage_4_psi']})")
    print(f"  Stage 5 (anti-leakage):  {funnel['stage_5_antileakage']:>5}  (-{funnel['stage_4_psi'] - funnel['stage_5_antileakage']})")
    print(f"  ─────────────────────────────────")
    print(f"  FINAL SELECTED:          {funnel['final_selected']:>5}")
    print(f"\n  Elapsed: {elapsed:.1f}s")
    print(f"  Artifacts: {artifact_dir}")
    print(f"  Plots:     {plot_dir}")

    print("\n[SELECTED FEATURES]")
    for i, feat in enumerate(selected, 1):
        iv = iv_scores.get(feat, 0)
        psi = psi_scores.get(feat, 0)
        alert = psi_alert(psi) if psi > 0 else "N/A"
        print(f"  {i:>3}. {feat:<45} IV={iv:.4f}  PSI={psi:.4f} [{alert}]")

    print("\n" + "=" * 70)
    print("DONE — Feature selection complete.")
    print("=" * 70)

    return selected


if __name__ == "__main__":
    selected = main()
