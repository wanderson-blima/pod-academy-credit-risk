"""
Credit Risk Model Training — OCI Data Science
Phase 5: Model Training with Dynamic Feature Selection

Trains dual models (LR L1 Scorecard + LightGBM GBDT) for FPD prediction.
Supports both hardcoded features (legacy mode) and dynamic multi-stage
feature selection from Gold consolidated data (402 columns).

Architecture: VM.Standard.E4.Flex — 4-10 OCPUs, 64-160 GB RAM
Threading: OMP_NUM_THREADS=N, LightGBM num_threads=N

Usage:
    Run as OCI Data Science Job or in notebook session.
    Requires: scikit-learn, lightgbm, category-encoders, pyarrow

    Dynamic mode: set FEATURE_SELECTION_MODE=dynamic (default)
    Legacy mode: set FEATURE_SELECTION_MODE=legacy (uses 59 hardcoded features)
"""
import os
import json
import time
from datetime import datetime

# ── Threading config (BEFORE any numpy/sklearn import) ─────────────────────
NCPUS = int(os.environ.get("JOB_OCPUS", os.environ.get("NOTEBOOK_OCPUS", str(os.cpu_count() or 4))))
os.environ["OMP_NUM_THREADS"] = str(NCPUS)
os.environ["OPENBLAS_NUM_THREADS"] = str(NCPUS)
os.environ["MKL_NUM_THREADS"] = "1"  # Disable MKL to avoid OpenMP conflicts

import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

# -- sklearn/LightGBM compatibility patch --
# category_encoders passes deprecated 'force_all_finite' to check_array.
# In sklearn >=1.4, only 'ensure_all_finite' is accepted.
# We convert force_all_finite to ensure_all_finite instead of dropping both.
import sklearn.utils.validation as _val
_original_check = _val.check_array
def _patched_check(*a, **kw):
    force_val = kw.pop("force_all_finite", None)
    if force_val is not None and "ensure_all_finite" not in kw:
        kw["ensure_all_finite"] = force_val
    return _original_check(*a, **kw)
_val.check_array = _patched_check

from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.metrics import roc_auc_score
from scipy.stats import ks_2samp
import lightgbm as lgb

try:
    from category_encoders import CountEncoder
except ImportError:
    from category_encoders.count import CountEncoder

# ── OCI Authentication ─────────────────────────────────────────────────────
try:
    import ads
    ads.set_auth("resource_principal")
    OCI_MODE = True
except Exception:
    OCI_MODE = False
    print("[WARN] ADS not available — running in local mode")

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

# Object Storage paths
NAMESPACE = os.environ.get("OCI_NAMESPACE", "grlxi07jz1mo")
GOLD_BUCKET = os.environ.get("GOLD_BUCKET", "pod-academy-gold")
GOLD_PATH = f"oci://{GOLD_BUCKET}@{NAMESPACE}/feature_store/clientes_consolidado/"

# Local path (if pre-copied to block volume for faster I/O)
LOCAL_DATA_PATH = os.environ.get("DATA_PATH", "/home/datascience/data/clientes_consolidado/")

# Artifact output directory
ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", "/home/datascience/artifacts")

# Feature selection mode: "dynamic" (run selection on new data) or "legacy" (use 59 hardcoded)
FEATURE_SELECTION_MODE = os.environ.get("FEATURE_SELECTION_MODE", "dynamic")

# Target variable
TARGET = "FPD"

# 59 selected features — exact match with Fabric v6 model
SELECTED_FEATURES = [
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

# Feature type split (from Fabric ColumnTransformer)
CAT_FEATURES = ["var_34", "var_67"]
NUM_FEATURES = [f for f in SELECTED_FEATURES if f not in CAT_FEATURES]

# Temporal split
TRAIN_SAFRAS = [202410, 202411, 202412, 202501]  # Train + OOS combined (Fabric v6)
OOS_SAFRA = [202501]                               # OOS evaluated separately
OOT_SAFRAS = [202502, 202503]                      # Out-of-time

# Fabric baseline metrics (for parity validation)
FABRIC_BASELINE = {
    "lgbm": {
        "ks_oot": 0.33974, "auc_oot": 0.73032, "gini_oot": 46.064,
        "ks_oos_202501": 0.34971, "auc_oos_202501": 0.73805,
    },
    "lr_l1": {
        "ks_oot": 0.32767, "auc_oot": 0.72073, "gini_oot": 44.146,
        "ks_oos_202501": 0.33846, "auc_oos_202501": 0.72902,
    },
}

# ═══════════════════════════════════════════════════════════════════════════
# METRICS
# ═══════════════════════════════════════════════════════════════════════════

def compute_ks(y_true, y_prob):
    """KS statistic — max separation between cumulative distributions."""
    prob_good = y_prob[y_true == 0]
    prob_bad = y_prob[y_true == 1]
    ks_stat, _ = ks_2samp(prob_good, prob_bad)
    return ks_stat

def compute_gini(auc):
    """Gini coefficient from AUC."""
    return (2 * auc - 1) * 100

def evaluate_model(pipeline, X, y, label=""):
    """Evaluate model pipeline and return metrics dict."""
    y_prob = pipeline.predict_proba(X)[:, 1]
    auc = roc_auc_score(y, y_prob)
    ks = compute_ks(y.values, y_prob)
    gini = compute_gini(auc)
    metrics = {
        f"ks_{label}": round(ks, 5),
        f"auc_{label}": round(auc, 5),
        f"gini_{label}": round(gini, 2),
    }
    return metrics

def compute_psi(expected, actual, bins=10):
    """Population Stability Index between two score distributions."""
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

# ═══════════════════════════════════════════════════════════════════════════
# DYNAMIC FEATURE SELECTION (multi-stage funnel)
# ═══════════════════════════════════════════════════════════════════════════

def compute_iv(df, feature, target, bins=10):
    """Information Value for a single feature."""
    try:
        x = pd.to_numeric(df[feature], errors="coerce")
        y = df[target].astype(int)
        mask = x.notna() & y.notna()
        x, y = x[mask], y[mask]
        if len(x) < 100 or y.nunique() < 2:
            return 0.0
        try:
            x_binned = pd.qcut(x, q=bins, duplicates="drop")
        except ValueError:
            x_binned = pd.cut(x, bins=min(bins, x.nunique()), duplicates="drop")
        grouped = pd.DataFrame({"x": x_binned, "y": y})
        ct = grouped.groupby("x")["y"].agg(["sum", "count"])
        ct["good"] = ct["count"] - ct["sum"]
        ct["bad"] = ct["sum"]
        total_good = ct["good"].sum()
        total_bad = ct["bad"].sum()
        if total_good == 0 or total_bad == 0:
            return 0.0
        ct["pct_good"] = (ct["good"] + 0.5) / (total_good + 0.5 * len(ct))
        ct["pct_bad"] = (ct["bad"] + 0.5) / (total_bad + 0.5 * len(ct))
        ct["woe"] = np.log(ct["pct_good"] / ct["pct_bad"])
        ct["iv"] = (ct["pct_good"] - ct["pct_bad"]) * ct["woe"]
        return ct["iv"].sum()
    except Exception:
        return 0.0


def run_feature_selection(data_path, target_col):
    """Memory-efficient multi-stage feature selection funnel.

    Reads parquet column-by-column for IV computation (Stage 1),
    then loads only IV-passing features for L1/Correlation/PSI.
    Peak memory: ~4 GB instead of ~12 GB.
    """
    import pyarrow.parquet as pq
    import gc

    print("\n" + "=" * 70)
    print("DYNAMIC FEATURE SELECTION (memory-efficient)")
    print("=" * 70)

    # Get schema without loading data
    ds = pq.ParquetDataset(data_path)
    all_columns = ds.schema.names

    exclude = {"NUM_CPF", "SAFRA", "FPD", "FLAG_INSTALACAO", "DT_PROCESSAMENTO",
               "_execution_id", "_data_inclusao", "_data_alteracao_silver",
               "DATADENASCIMENTO", "PROD", "flag_mig2", "STATUSRF"}
    candidates = sorted([c for c in all_columns if c not in exclude])
    print(f"  Total columns: {len(all_columns)} → Candidates: {len(candidates)}")

    # Load only target + SAFRA for reference (tiny: 2 cols × 3.9M rows)
    df_ref = pq.read_table(data_path, columns=[target_col, "SAFRA"]).to_pandas()
    train_mask = df_ref["SAFRA"].isin(TRAIN_SAFRAS) & df_ref[target_col].notna()
    y_train = df_ref.loc[train_mask, target_col].astype(int)
    safra_train = df_ref.loc[train_mask, "SAFRA"]
    train_idx = train_mask[train_mask].index
    print(f"  Train rows: {len(train_idx):,}")

    # Stage 1: IV > 0.02 — read ONE column at a time
    print("  Stage 1: Information Value (IV > 0.02) — column-by-column...")
    iv_scores = {}
    numeric_candidates = []
    for i, feat in enumerate(candidates):
        if (i + 1) % 50 == 0:
            print(f"    ... processed {i + 1}/{len(candidates)} columns")
        try:
            col_data = pq.read_table(data_path, columns=[feat]).to_pandas()[feat]
            col_train = col_data.iloc[train_idx]
            del col_data
            vals = pd.to_numeric(col_train, errors="coerce")
            if vals.notna().sum() < 100:
                del col_train, vals
                continue
            numeric_candidates.append(feat)
            # Compute IV inline
            x = vals
            y = y_train
            mask = x.notna()
            x_m, y_m = x[mask], y[mask]
            if len(x_m) < 100:
                iv_scores[feat] = 0.0
            else:
                try:
                    x_binned = pd.qcut(x_m, q=10, duplicates="drop")
                except ValueError:
                    x_binned = pd.cut(x_m, bins=min(10, x_m.nunique()), duplicates="drop")
                ct = pd.DataFrame({"x": x_binned, "y": y_m}).groupby("x")["y"].agg(["sum", "count"])
                ct["good"] = ct["count"] - ct["sum"]
                ct["bad"] = ct["sum"]
                tg, tb = ct["good"].sum(), ct["bad"].sum()
                if tg == 0 or tb == 0:
                    iv_scores[feat] = 0.0
                else:
                    ct["pg"] = (ct["good"] + 0.5) / (tg + 0.5 * len(ct))
                    ct["pb"] = (ct["bad"] + 0.5) / (tb + 0.5 * len(ct))
                    ct["woe"] = np.log(ct["pg"] / ct["pb"])
                    iv_scores[feat] = ((ct["pg"] - ct["pb"]) * ct["woe"]).sum()
            del col_train, vals
        except Exception:
            pass

    features_iv = [f for f in numeric_candidates if iv_scores.get(f, 0) > 0.02]
    features_iv.sort(key=lambda f: iv_scores[f], reverse=True)
    print(f"  Candidates: {len(candidates)} → Numeric: {len(numeric_candidates)}")
    print(f"    After IV: {len(features_iv)} features")
    gc.collect()

    # Stage 2: L1 regularization — memory-efficient: subsample from full dataset
    L1_SAMPLE = min(300_000, len(train_idx))
    # Use top-80 IV features to keep matrix small
    top_iv = features_iv[:min(80, len(features_iv))]
    print(f"  Stage 2: L1 Regularization (top {len(top_iv)} IV cols, {L1_SAMPLE} sample)...")
    rng = np.random.RandomState(42)
    # Read only the columns we need (not all rows are avoidable with parquet)
    table = pq.read_table(data_path, columns=top_iv + [target_col])
    df_l1 = table.to_pandas(self_destruct=True)
    del table; gc.collect()
    # Take only train rows and drop NaN target
    df_l1 = df_l1.iloc[train_idx].reset_index(drop=True)
    mask = df_l1[target_col].notna()
    df_l1 = df_l1[mask].reset_index(drop=True)
    print(f"    Train rows (no NaN): {len(df_l1):,}")
    # Subsample for speed and memory
    if len(df_l1) > L1_SAMPLE:
        idx = rng.choice(len(df_l1), size=L1_SAMPLE, replace=False)
        df_l1 = df_l1.iloc[idx].reset_index(drop=True)
    y_sample = df_l1[target_col].values.astype(np.float32)
    X_sel = df_l1[top_iv].apply(pd.to_numeric, errors="coerce")
    del df_l1; gc.collect()
    X_sel = X_sel.fillna(X_sel.median()).astype(np.float32)
    from sklearn.preprocessing import StandardScaler as SS
    scaler = SS()
    X_scaled = scaler.fit_transform(X_sel).astype(np.float32)
    del X_sel; gc.collect()
    print(f"    Memory before L1 fit: {X_scaled.nbytes / 1e6:.0f} MB")
    lr_sel = LogisticRegression(C=0.1, penalty="l1", solver="liblinear",
                                max_iter=300, random_state=42)
    lr_sel.fit(X_scaled, y_sample)
    nonzero_mask = np.abs(lr_sel.coef_[0]) > 0
    # Features that survive L1, plus remaining IV features not tested
    features_l1 = [f for f, nz in zip(top_iv, nonzero_mask) if nz]
    # Also keep features ranked 81+ from IV (they weren't tested by L1 but passed IV)
    features_l1_extra = features_iv[min(80, len(features_iv)):]
    features_l1 = features_l1 + list(features_l1_extra)
    del X_scaled, lr_sel, y_sample, scaler; gc.collect()
    print(f"    After L1: {len(features_l1)} features ({len([f for f, nz in zip(top_iv, nonzero_mask) if nz])} from L1 + {len(features_l1_extra)} untested)")

    # Stage 3: Correlation filter (|r| < 0.90) — column-pair approach for memory
    CORR_SAMPLE = min(50_000, len(train_idx))
    print(f"  Stage 3: Correlation (|r| < 0.90, {len(features_l1)} features)...")
    # Read a small sample to compute correlations (50K rows × N features)
    # Read in chunks to avoid OOM: 50K × 186 × 4 bytes = ~36 MB
    sample_rows = sorted(rng.choice(train_idx, size=CORR_SAMPLE, replace=False).tolist())
    # Build correlation matrix by reading features in batches of 30
    batch_size = 30
    all_corr_data = {}
    for b_start in range(0, len(features_l1), batch_size):
        batch_feats = features_l1[b_start:b_start + batch_size]
        tbl = pq.read_table(data_path, columns=batch_feats)
        batch_df = tbl.to_pandas(self_destruct=True)
        del tbl
        batch_df = batch_df.iloc[sample_rows].apply(pd.to_numeric, errors="coerce").fillna(0).astype(np.float32)
        for f in batch_feats:
            all_corr_data[f] = batch_df[f].values
        del batch_df; gc.collect()
    # Build correlation matrix from vectors
    corr_df = pd.DataFrame(all_corr_data).astype(np.float32)
    del all_corr_data; gc.collect()
    corr = corr_df.corr().abs()
    del corr_df; gc.collect()
    upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
    to_drop = set()
    for col in upper.columns:
        for row in upper.index:
            if upper.loc[row, col] > 0.90:
                to_drop.add(col if iv_scores.get(col, 0) < iv_scores.get(row, 0) else row)
    features_corr = [f for f in features_l1 if f not in to_drop]
    del corr, upper; gc.collect()
    print(f"    After Corr: {len(features_corr)} features (dropped {len(to_drop)})")

    # Stage 4: PSI < 0.25 (train vs OOT stability)
    print("  Stage 4: PSI stability (< 0.25)...")
    all_safra = df_ref["SAFRA"]
    features_psi = []
    for feat in features_corr:
        try:
            col = pq.read_table(data_path, columns=[feat]).to_pandas()[feat]
            train_vals = pd.to_numeric(col[all_safra.isin([202410, 202411, 202412])],
                                       errors="coerce").dropna().values
            oot_vals = pd.to_numeric(col[all_safra.isin([202502, 202503])],
                                     errors="coerce").dropna().values
            del col
            if len(train_vals) > 0 and len(oot_vals) > 0:
                psi = compute_psi(train_vals, oot_vals)
                features_psi.append(feat) if psi < 0.25 else None
            else:
                features_psi.append(feat)
        except Exception:
            features_psi.append(feat)
    print(f"    After PSI: {len(features_psi)} features")

    # Stage 5: Anti-leakage
    print("  Stage 5: Anti-leakage...")
    leakage_patterns = ["VLR_FPD", "TARGET_FPD", "_LEAKAGE"]
    features_final = []
    for feat in features_psi:
        if any(p in feat.upper() for p in leakage_patterns):
            print(f"    REMOVED (leakage): {feat}")
            continue
        features_final.append(feat)
    print(f"    Final: {len(features_final)} features")

    print(f"\n  FUNNEL: {len(candidates)} → {len(numeric_candidates)} → "
          f"{len(features_iv)} → {len(features_l1)} → {len(features_corr)} → "
          f"{len(features_psi)} → {len(features_final)}")

    # Memory-aware feature cap: on low-memory instances (<32 GB), limit features
    import psutil
    total_mem_gb = psutil.virtual_memory().total / 1e9
    if total_mem_gb < 32 and len(features_final) > 60:
        print(f"  [MEM] Low memory ({total_mem_gb:.0f} GB) — capping features from {len(features_final)} to 60")
        features_final = features_final[:60]

    # Save selection artifact
    selection_artifact = {
        "n_features": len(features_final),
        "features": features_final,
        "funnel": {
            "total_columns": len(candidates),
            "numeric_candidates": len(numeric_candidates),
            "after_iv": len(features_iv),
            "after_l1": len(features_l1),
            "after_corr": len(features_corr),
            "after_psi": len(features_psi),
            "after_leakage": len(features_final),
        },
        "top_iv": {f: round(iv_scores[f], 4) for f in features_final[:20]},
    }
    os.makedirs(f"{ARTIFACT_DIR}/metrics", exist_ok=True)
    with open(f"{ARTIFACT_DIR}/metrics/selected_features.json", "w") as f:
        json.dump(selection_artifact, f, indent=2)

    del df_ref; gc.collect()
    return features_final


# ═══════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════

def get_data_path():
    """Return the best data path (local preferred)."""
    if os.path.exists(LOCAL_DATA_PATH):
        return LOCAL_DATA_PATH
    return GOLD_PATH


def load_data(features_to_load=None):
    """Load Gold feature store with only the needed columns.

    Args:
        features_to_load: list of feature columns. If None, uses SELECTED_FEATURES.
    """
    import pyarrow.parquet as pq
    import gc

    t0 = time.time()
    data_path = get_data_path()
    cols = features_to_load or SELECTED_FEATURES
    columns_to_load = list(set(cols + [TARGET, "SAFRA"]))

    print(f"[DATA] Source: {data_path}")
    print(f"[DATA] Loading {len(columns_to_load)} columns ({len(cols)} features + keys)...")

    table = pq.read_table(data_path, columns=columns_to_load)
    df = table.to_pandas(self_destruct=True)
    del table; gc.collect()

    # Downcast float64 to float32 to save memory
    float_cols = df.select_dtypes(include=["float64"]).columns
    if len(float_cols) > 0:
        print(f"[DATA] Downcasting {len(float_cols)} float64 → float32")
        df[float_cols] = df[float_cols].astype(np.float32)
    gc.collect()

    elapsed = time.time() - t0
    print(f"[DATA] Loaded: {len(df):,} rows, {df.shape[1]} columns in {elapsed:.1f}s")
    print(f"[DATA] Memory: {df.memory_usage(deep=True).sum() / 1e9:.2f} GB")
    print(f"[DATA] SAFRAs: {sorted(df['SAFRA'].unique())}")
    print(f"[DATA] FPD rate: {df[TARGET].mean():.4f} ({df[TARGET].sum():,} defaults)")

    non_null_fpd = df[TARGET].dropna()
    assert non_null_fpd.isin([0, 1, 0.0, 1.0]).all(), "FPD must be binary (0/1)"
    print(f"[DATA] FPD null: {df[TARGET].isna().sum():,} | non-null: {len(non_null_fpd):,}")

    return df

# ═══════════════════════════════════════════════════════════════════════════
# TEMPORAL SPLIT
# ═══════════════════════════════════════════════════════════════════════════

def temporal_split(df, features):
    """Split by SAFRA — replicates Fabric v6 temporal boundaries."""
    df_train = df[df["SAFRA"].isin(TRAIN_SAFRAS) & df[TARGET].notna()].copy()
    df_oos = df[df["SAFRA"].isin(OOS_SAFRA) & df[TARGET].notna()].copy()
    df_oot = df[df["SAFRA"].isin(OOT_SAFRAS) & df[TARGET].notna()].copy()

    print(f"\n[SPLIT] Train: {len(df_train):,} rows | SAFRAs {TRAIN_SAFRAS}")
    print(f"[SPLIT] OOS:   {len(df_oos):,} rows | SAFRAs {OOS_SAFRA}")
    print(f"[SPLIT] OOT:   {len(df_oot):,} rows | SAFRAs {OOT_SAFRAS}")
    print(f"[SPLIT] FPD rates — Train: {df_train[TARGET].mean():.4f}, "
          f"OOS: {df_oos[TARGET].mean():.4f}, OOT: {df_oot[TARGET].mean():.4f}")

    # Validate no temporal leakage
    train_safras_set = set(df_train["SAFRA"].unique())
    oot_safras_set = set(df_oot["SAFRA"].unique())
    assert train_safras_set.isdisjoint(oot_safras_set), "SAFRA leak: train/OOT overlap!"

    X_train = df_train[features]
    y_train = df_train[TARGET].astype(int)
    X_oos = df_oos[features]
    y_oos = df_oos[TARGET].astype(int)
    X_oot = df_oot[features]
    y_oot = df_oot[TARGET].astype(int)

    return X_train, y_train, X_oos, y_oos, X_oot, y_oot

# ═══════════════════════════════════════════════════════════════════════════
# PREPROCESSING PIPELINES (exact Fabric v6 replication)
# ═══════════════════════════════════════════════════════════════════════════

def build_lr_pipeline(num_features, cat_features):
    """LR L1 Scorecard pipeline."""
    transformers = [
        ("num", Pipeline(steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]), num_features),
    ]
    if cat_features:
        transformers.append(
            ("cat", Pipeline(steps=[
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("encoder", CountEncoder(
                    combine_min_nan_groups=True,
                    normalize=True,
                    handle_missing=0,
                    handle_unknown=0,
                )),
            ]), cat_features),
        )
    preprocessor = ColumnTransformer(transformers=transformers)

    pipeline = Pipeline(steps=[
        ("prep", preprocessor),
        ("model", LogisticRegression(
            C=0.5,
            penalty="l1",
            solver="liblinear",
            max_iter=2000,
            tol=0.001,
            class_weight="balanced",
            random_state=42,
        )),
    ])
    return pipeline

def build_lgbm_pipeline(num_features, cat_features):
    """LightGBM GBDT pipeline."""
    transformers = [
        ("num", Pipeline(steps=[
            ("imputer", SimpleImputer(strategy="median")),
        ]), num_features),
    ]
    if cat_features:
        transformers.append(
            ("cat", Pipeline(steps=[
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("encoder", CountEncoder(
                    combine_min_nan_groups=True,
                    normalize=True,
                    handle_missing=0,
                    handle_unknown=0,
                )),
            ]), cat_features),
        )
    preprocessor = ColumnTransformer(transformers=transformers)

    pipeline = Pipeline(steps=[
        ("prep", preprocessor),
        ("model", lgb.LGBMClassifier(
            objective="binary",
            n_estimators=250,
            learning_rate=0.05,
            max_depth=4,
            colsample_bytree=0.8,
            n_jobs=NCPUS,
            num_threads=NCPUS,
            random_state=42,
            verbosity=-1,
        )),
    ])
    return pipeline

# ═══════════════════════════════════════════════════════════════════════════
# TRAINING
# ═══════════════════════════════════════════════════════════════════════════

def train_and_evaluate():
    """Full training pipeline: load → select features → split → train → evaluate."""
    global SELECTED_FEATURES, CAT_FEATURES, NUM_FEATURES
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 1. Load data
    print("=" * 70)
    print("PHASE 5 — MODEL TRAINING (OCI Data Science)")
    print(f"Run ID: {run_id} | OCPUs: {NCPUS}")
    print(f"Feature selection: {FEATURE_SELECTION_MODE}")
    print("=" * 70)

    # 2. Feature selection (if dynamic mode)
    if FEATURE_SELECTION_MODE == "dynamic":
        data_path = get_data_path()
        selected = run_feature_selection(data_path, TARGET)
        SELECTED_FEATURES = selected
        # All dynamically selected features are numeric (IV requires numeric)
        CAT_FEATURES = []
        NUM_FEATURES = list(SELECTED_FEATURES)
        print(f"\n[FEATURES] Selected: {len(SELECTED_FEATURES)} "
              f"({len(NUM_FEATURES)} numeric, {len(CAT_FEATURES)} categorical)")
    else:
        print(f"\n[FEATURES] Using {len(SELECTED_FEATURES)} legacy features")

    # 3. Load ONLY selected features (memory efficient)
    df = load_data(SELECTED_FEATURES)

    # 4. Temporal split
    X_train, y_train, X_oos, y_oos, X_oot, y_oot = temporal_split(df, SELECTED_FEATURES)
    del df  # Free memory
    import gc; gc.collect()

    # 5. Train LR L1 Scorecard
    print("\n" + "-" * 70)
    print("MODEL 1: LR L1 Scorecard")
    print("-" * 70)
    t0 = time.time()

    lr_pipeline = build_lr_pipeline(NUM_FEATURES, CAT_FEATURES)
    lr_pipeline.fit(X_train, y_train)

    lr_time = time.time() - t0
    print(f"[LR] Training completed in {lr_time:.1f}s")

    lr_metrics_train = evaluate_model(lr_pipeline, X_train, y_train, "train")
    lr_metrics_oos = evaluate_model(lr_pipeline, X_oos, y_oos, "oos_202501")
    lr_metrics_oot = evaluate_model(lr_pipeline, X_oot, y_oot, "oot")
    lr_metrics = {**lr_metrics_train, **lr_metrics_oos, **lr_metrics_oot}

    print(f"[LR] KS  — Train: {lr_metrics['ks_train']:.4f} | "
          f"OOS: {lr_metrics['ks_oos_202501']:.4f} | OOT: {lr_metrics['ks_oot']:.4f}")
    print(f"[LR] AUC — Train: {lr_metrics['auc_train']:.4f} | "
          f"OOS: {lr_metrics['auc_oos_202501']:.4f} | OOT: {lr_metrics['auc_oot']:.4f}")
    print(f"[LR] Gini — OOT: {lr_metrics['gini_oot']:.2f}")

    # 4. Train LightGBM GBDT
    print("\n" + "-" * 70)
    print(f"MODEL 2: LightGBM GBDT (num_threads={NCPUS})")
    print("-" * 70)
    t0 = time.time()

    lgbm_pipeline = build_lgbm_pipeline(NUM_FEATURES, CAT_FEATURES)
    lgbm_pipeline.fit(X_train, y_train)

    lgbm_time = time.time() - t0
    print(f"[LGBM] Training completed in {lgbm_time:.1f}s")

    lgbm_metrics_train = evaluate_model(lgbm_pipeline, X_train, y_train, "train")
    lgbm_metrics_oos = evaluate_model(lgbm_pipeline, X_oos, y_oos, "oos_202501")
    lgbm_metrics_oot = evaluate_model(lgbm_pipeline, X_oot, y_oot, "oot")
    lgbm_metrics = {**lgbm_metrics_train, **lgbm_metrics_oos, **lgbm_metrics_oot}

    print(f"[LGBM] KS  — Train: {lgbm_metrics['ks_train']:.4f} | "
          f"OOS: {lgbm_metrics['ks_oos_202501']:.4f} | OOT: {lgbm_metrics['ks_oot']:.4f}")
    print(f"[LGBM] AUC — Train: {lgbm_metrics['auc_train']:.4f} | "
          f"OOS: {lgbm_metrics['auc_oos_202501']:.4f} | OOT: {lgbm_metrics['auc_oot']:.4f}")
    print(f"[LGBM] Gini — OOT: {lgbm_metrics['gini_oot']:.2f}")

    # 5. PSI — Score stability (train vs OOT)
    print("\n" + "-" * 70)
    print("STABILITY: PSI Analysis")
    print("-" * 70)

    lr_train_scores = lr_pipeline.predict_proba(X_train)[:, 1]
    lr_oot_scores = lr_pipeline.predict_proba(X_oot)[:, 1]
    lgbm_train_scores = lgbm_pipeline.predict_proba(X_train)[:, 1]
    lgbm_oot_scores = lgbm_pipeline.predict_proba(X_oot)[:, 1]

    lr_psi = compute_psi(lr_train_scores, lr_oot_scores)
    lgbm_psi = compute_psi(lgbm_train_scores, lgbm_oot_scores)

    print(f"[PSI] LR scorecard:  {lr_psi:.6f} {'(STABLE)' if lr_psi < 0.10 else '(SHIFT!)'}")
    print(f"[PSI] LightGBM:      {lgbm_psi:.6f} {'(STABLE)' if lgbm_psi < 0.10 else '(SHIFT!)'}")

    # 6. Fabric Parity Comparison
    print("\n" + "-" * 70)
    print("PARITY: OCI vs Fabric Baseline")
    print("-" * 70)

    parity_results = {}
    for model_name, oci_metrics, baseline in [
        ("LR L1", lr_metrics, FABRIC_BASELINE["lr_l1"]),
        ("LightGBM", lgbm_metrics, FABRIC_BASELINE["lgbm"]),
    ]:
        print(f"\n  {model_name}:")
        model_parity = {}
        for metric_key in baseline:
            fabric_val = baseline[metric_key]
            oci_val = oci_metrics.get(metric_key, 0)
            diff = abs(oci_val - fabric_val)
            # KS/Gini tolerance: 2pp, AUC tolerance: 0.005
            if "ks" in metric_key:
                tolerance = 0.02
                pct_label = f"{diff*100:.2f}pp"
            elif "auc" in metric_key:
                tolerance = 0.005
                pct_label = f"{diff:.4f}"
            else:
                tolerance = 2.0
                pct_label = f"{diff:.2f}pp"

            passed = diff <= tolerance
            status = "PASS" if passed else "FAIL"
            model_parity[metric_key] = {"oci": oci_val, "fabric": fabric_val, "diff": diff, "status": status}
            print(f"    {metric_key:25s} Fabric: {fabric_val:.5f} | OCI: {oci_val:.5f} | "
                  f"Diff: {pct_label} [{status}]")

        parity_results[model_name] = model_parity

    # 7. Quality Gate QG-05
    print("\n" + "=" * 70)
    print("QUALITY GATE QG-05 — Pre-Deployment Validation")
    print("=" * 70)

    gates = [
        ("KS OOT > 0.20 (LR)",   lr_metrics["ks_oot"] > 0.20),
        ("KS OOT > 0.20 (LGBM)", lgbm_metrics["ks_oot"] > 0.20),
        ("AUC OOT > 0.65 (LR)",  lr_metrics["auc_oot"] > 0.65),
        ("AUC OOT > 0.65 (LGBM)", lgbm_metrics["auc_oot"] > 0.65),
        ("Gini OOT > 30 (LR)",   lr_metrics["gini_oot"] > 30),
        ("Gini OOT > 30 (LGBM)", lgbm_metrics["gini_oot"] > 30),
        ("PSI < 0.25 (LR)",      lr_psi < 0.25),
        ("PSI < 0.25 (LGBM)",    lgbm_psi < 0.25),
    ]

    all_passed = True
    for gate_name, passed in gates:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"  [{status}] {gate_name}")

    print(f"\n  Quality Gate QG-05: {'PASSED' if all_passed else 'FAILED'}")

    # 8. Save artifacts
    os.makedirs(f"{ARTIFACT_DIR}/models", exist_ok=True)
    os.makedirs(f"{ARTIFACT_DIR}/metrics", exist_ok=True)

    import pickle
    with open(f"{ARTIFACT_DIR}/models/lr_l1_oci_{run_id}.pkl", "wb") as f:
        pickle.dump(lr_pipeline, f)
    with open(f"{ARTIFACT_DIR}/models/lgbm_oci_{run_id}.pkl", "wb") as f:
        pickle.dump(lgbm_pipeline, f)
    print(f"\n[SAVE] Models saved to {ARTIFACT_DIR}/models/")

    # Save metrics
    results = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "platform": "OCI Data Science",
        "shape": f"VM.Standard.E4.Flex ({NCPUS} OCPUs)",
        "training_time_seconds": {"lr": round(lr_time, 1), "lgbm": round(lgbm_time, 1)},
        "n_features": len(SELECTED_FEATURES),
        "feature_selection_mode": FEATURE_SELECTION_MODE,
        "feature_names": SELECTED_FEATURES,
        "cat_features": CAT_FEATURES,
        "num_features": NUM_FEATURES,
        "train_safras": TRAIN_SAFRAS,
        "oot_safras": OOT_SAFRAS,
        "lr_metrics": lr_metrics,
        "lgbm_metrics": lgbm_metrics,
        "lr_psi": lr_psi,
        "lgbm_psi": lgbm_psi,
        "fabric_baseline": FABRIC_BASELINE,
        "parity_results": {k: {mk: {"status": mv["status"]} for mk, mv in v.items()}
                           for k, v in parity_results.items()},
        "quality_gate_qg05": "PASSED" if all_passed else "FAILED",
    }

    with open(f"{ARTIFACT_DIR}/metrics/training_results_{run_id}.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"[SAVE] Metrics saved to {ARTIFACT_DIR}/metrics/training_results_{run_id}.json")

    # 9. Feature importance (LightGBM)
    lgbm_model = lgbm_pipeline.named_steps["model"]
    prep = lgbm_pipeline.named_steps["prep"]
    transformed_feature_names = (
        [f"num__{f}" for f in NUM_FEATURES] +
        [f"cat__{f}" for f in CAT_FEATURES]
    )
    importance_df = pd.DataFrame({
        "feature": transformed_feature_names,
        "importance": lgbm_model.feature_importances_,
    }).sort_values("importance", ascending=False)
    importance_df.to_csv(f"{ARTIFACT_DIR}/metrics/feature_importance_{run_id}.csv", index=False)
    print(f"[SAVE] Feature importance saved")
    print(f"\n[TOP 10 Features]")
    print(importance_df.head(10).to_string(index=False))

    return lr_pipeline, lgbm_pipeline, results


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    lr_pipeline, lgbm_pipeline, results = train_and_evaluate()

    print("\n" + "=" * 70)
    print(f"TRAINING COMPLETE — Run ID: {results['run_id']}")
    print(f"Quality Gate QG-05: {results['quality_gate_qg05']}")
    print(f"LR  KS OOT: {results['lr_metrics']['ks_oot']:.4f} | "
          f"AUC: {results['lr_metrics']['auc_oot']:.4f}")
    print(f"LGBM KS OOT: {results['lgbm_metrics']['ks_oot']:.4f} | "
          f"AUC: {results['lgbm_metrics']['auc_oot']:.4f}")
    print("=" * 70)
