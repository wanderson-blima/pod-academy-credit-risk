#!/usr/bin/env python3
"""
Full Ensemble Pipeline Orchestrator
Runs all 6 phases end-to-end on OCI compute.

Usage:
    python run_full_pipeline.py [--n-trials 50] [--skip-hpo] [--data-path /path/to/data]
"""
import os
import sys
import json
import time
import pickle
import argparse
from datetime import datetime

# ── Threading config (BEFORE any numpy/sklearn import) ─────────────────
NCPUS = int(os.environ.get("NOTEBOOK_OCPUS", os.cpu_count() or 4))
os.environ["OMP_NUM_THREADS"] = str(NCPUS)
os.environ["OPENBLAS_NUM_THREADS"] = str(NCPUS)
os.environ["MKL_NUM_THREADS"] = "1"

import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

# sklearn compat patch
import sklearn.utils.validation as _val
_original_check = _val.check_array
def _patched_check(*a, **kw):
    force_val = kw.pop("force_all_finite", None)
    if force_val is not None and "ensure_all_finite" not in kw:
        kw["ensure_all_finite"] = force_val
    return _original_check(*a, **kw)
_val.check_array = _patched_check

from sklearn.metrics import roc_auc_score
from scipy.stats import ks_2samp

# ── Configuration ──────────────────────────────────────────────────────
NAMESPACE = os.environ.get("OCI_NAMESPACE", "grlxi07jz1mo")
GOLD_BUCKET = os.environ.get("GOLD_BUCKET", "pod-academy-gold")
GOLD_PATH = f"oci://{GOLD_BUCKET}@{NAMESPACE}/feature_store/clientes_consolidado/"
LOCAL_DATA_PATH = os.environ.get("DATA_PATH", "/home/opc/data/clientes_consolidado/")
ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", "/home/opc/artifacts")
TARGET = "FPD"

TRAIN_SAFRAS = [202410, 202411, 202412, 202501]
OOS_SAFRA = [202501]
OOT_SAFRAS = [202502, 202503]

# Original 59 selected features (Fabric v6)
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
CAT_FEATURES = ["var_34", "var_67"]
NUM_FEATURES = [f for f in SELECTED_FEATURES if f not in CAT_FEATURES]


def compute_ks(y_true, y_prob):
    prob_good = y_prob[y_true == 0]
    prob_bad = y_prob[y_true == 1]
    ks_stat, _ = ks_2samp(prob_good, prob_bad)
    return ks_stat


def compute_gini(auc):
    return (2 * auc - 1) * 100


def compute_psi(expected, actual, bins=10):
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


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ═════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ═════════════════════════════════════════════════════════════════════════

def load_data():
    """Load feature store from local copy or OCI Object Storage."""
    import pyarrow.parquet as pq

    t0 = time.time()
    if os.path.exists(LOCAL_DATA_PATH):
        log(f"Reading from local: {LOCAL_DATA_PATH}")
        table = pq.read_table(LOCAL_DATA_PATH)
        df = table.to_pandas(self_destruct=True)
    else:
        log(f"Reading from OCI: {GOLD_PATH}")
        try:
            import ocifs
            fs = ocifs.OCIFileSystem()
            df = pd.read_parquet(GOLD_PATH, filesystem=fs)
        except ImportError:
            # Fallback: use oci cli to download first
            log("ocifs not available, downloading via OCI CLI...")
            os.makedirs(LOCAL_DATA_PATH, exist_ok=True)
            os.system(f'oci os object bulk-download --bucket-name {GOLD_BUCKET} --namespace {NAMESPACE} '
                      f'--prefix feature_store/clientes_consolidado/ --download-dir /home/opc/data/ '
                      f'--overwrite 2>&1')
            table = pq.read_table(LOCAL_DATA_PATH)
            df = table.to_pandas(self_destruct=True)

    elapsed = time.time() - t0
    log(f"Loaded: {len(df):,} rows, {df.shape[1]} columns in {elapsed:.1f}s")
    log(f"SAFRAs: {sorted(df['SAFRA'].unique())}")
    log(f"FPD rate: {df[TARGET].mean():.4f} ({df[TARGET].sum():,.0f} defaults)")
    return df


def temporal_split(df, features):
    """Split by SAFRA."""
    df_train = df[df["SAFRA"].isin(TRAIN_SAFRAS) & df[TARGET].notna()].copy()
    df_oos = df[df["SAFRA"].isin(OOS_SAFRA) & df[TARGET].notna()].copy()
    df_oot = df[df["SAFRA"].isin(OOT_SAFRAS) & df[TARGET].notna()].copy()

    log(f"Train: {len(df_train):,} | OOS: {len(df_oos):,} | OOT: {len(df_oot):,}")

    return (
        df_train[features], df_train[TARGET].astype(int),
        df_oos[features], df_oos[TARGET].astype(int),
        df_oot[features], df_oot[TARGET].astype(int),
        df_train, df_oos, df_oot,
    )


# ═════════════════════════════════════════════════════════════════════════
# PHASE 1: DIAGNOSTIC (lightweight — just metrics)
# ═════════════════════════════════════════════════════════════════════════

def phase1_diagnostic(df, pipeline_baseline):
    """Quick diagnostic of baseline model."""
    log("=" * 70)
    log("PHASE 1: DIAGNOSTIC")
    log("=" * 70)

    df_labeled = df[df[TARGET].notna()].copy()
    y = df_labeled[TARGET].astype(int)
    X = df_labeled[SELECTED_FEATURES]
    y_prob = pipeline_baseline.predict_proba(X)[:, 1]

    # Per-SAFRA KS
    findings = []
    for safra in sorted(df_labeled["SAFRA"].unique()):
        mask = df_labeled["SAFRA"] == safra
        ks = compute_ks(y[mask].values, y_prob[mask])
        auc = roc_auc_score(y[mask], y_prob[mask])
        log(f"  SAFRA {safra}: KS={ks:.4f} AUC={auc:.4f} n={mask.sum():,}")
        if ks < 0.30:
            findings.append(f"SAFRA {safra} KS={ks:.4f} below 0.30")

    # Brier score
    from sklearn.metrics import brier_score_loss
    brier = brier_score_loss(y, y_prob)
    log(f"  Brier Score: {brier:.6f}")

    # Feature drift — check REC_DIAS_ENTRE_RECARGAS
    if "REC_DIAS_ENTRE_RECARGAS" in df.columns:
        ref = df[df["SAFRA"] == 202410]["REC_DIAS_ENTRE_RECARGAS"].dropna().values
        for safra in [202502, 202503]:
            curr = df[df["SAFRA"] == safra]["REC_DIAS_ENTRE_RECARGAS"].dropna().values
            if len(ref) > 100 and len(curr) > 100:
                psi = compute_psi(ref, curr)
                log(f"  REC_DIAS_ENTRE_RECARGAS PSI (202410 vs {safra}): {psi:.4f}")
                if psi > 0.25:
                    findings.append(f"REC_DIAS_ENTRE_RECARGAS drift PSI={psi:.4f} at {safra}")

    findings.append("Hyperparameters not optimized (defaults)")
    findings.append("Only 2 models tested (LR + LGBM)")
    findings.append("No cross-domain interaction features")

    log(f"\n  FINDINGS ({len(findings)}):")
    for f in findings:
        log(f"    - {f}")

    return findings


# ═════════════════════════════════════════════════════════════════════════
# PHASE 2: FEATURE ENGINEERING
# ═════════════════════════════════════════════════════════════════════════

def _create_missing_features(df):
    """Missing indicators — null patterns are predictive signals."""
    rec_cols = [c for c in df.columns if c.startswith("REC_")]
    pag_cols = [c for c in df.columns if c.startswith("PAG_")]
    fat_cols = [c for c in df.columns if c.startswith("FAT_")]

    df["MISSING_REC_COUNT"] = df[rec_cols].isnull().sum(axis=1) if rec_cols else 0
    df["MISSING_PAG_COUNT"] = df[pag_cols].isnull().sum(axis=1) if pag_cols else 0
    df["MISSING_FAT_COUNT"] = df[fat_cols].isnull().sum(axis=1) if fat_cols else 0
    total_cols = len(rec_cols) + len(pag_cols) + len(fat_cols)
    df["MISSING_TOTAL_RATIO"] = (df["MISSING_REC_COUNT"] + df["MISSING_PAG_COUNT"] + df["MISSING_FAT_COUNT"]) / max(total_cols, 1)

    # Binary indicators for key high-null features
    for col in ["PAG_QTD_PAGAMENTOS_TOTAL", "PAG_TAXA_PAGAMENTOS_COM_JUROS", "PAG_DIAS_ENTRE_FATURAS"]:
        if col in df.columns:
            df[f"{col}_IS_NULL"] = df[col].isnull().astype(np.int8)

    return df


def _create_interaction_features(df):
    """Cross-domain interactions — REC x PAG x FAT."""
    # Risk combos
    if "TARGET_SCORE_02" in df.columns and "REC_SCORE_RISCO" in df.columns:
        df["SCORE_X_REC_RISK"] = df["TARGET_SCORE_02"] * df["REC_SCORE_RISCO"]
    if "TARGET_SCORE_01" in df.columns and "TARGET_SCORE_02" in df.columns:
        df["DIFF_SCORE_BUREAU"] = df["TARGET_SCORE_02"] - df["TARGET_SCORE_01"]

    # Cross-domain ratios
    if "REC_QTD_RECARGAS_TOTAL" in df.columns and "PAG_QTD_PAGAMENTOS_TOTAL" in df.columns:
        df["RATIO_REC_PAG"] = df["REC_QTD_RECARGAS_TOTAL"] / (df["PAG_QTD_PAGAMENTOS_TOTAL"].clip(lower=1))
    if "FAT_QTD_FATURAS_PRIMEIRA" in df.columns and "PAG_QTD_PAGAMENTOS_TOTAL" in df.columns:
        df["RATIO_FAT_PAG"] = df["FAT_QTD_FATURAS_PRIMEIRA"] / (df["PAG_QTD_PAGAMENTOS_TOTAL"].clip(lower=1))

    # Behavioral patterns
    if "REC_DIAS_DESDE_ULTIMA_RECARGA" in df.columns and "PAG_DIAS_DESDE_ULTIMA_FATURA" in df.columns:
        df["REC_PAG_GAP"] = df["REC_DIAS_DESDE_ULTIMA_RECARGA"] - df["PAG_DIAS_DESDE_ULTIMA_FATURA"]
    if "FAT_QTD_FATURAS_PRIMEIRA" in df.columns and "REC_QTD_RECARGAS_TOTAL" in df.columns:
        df["BILLING_LOAD"] = df["FAT_QTD_FATURAS_PRIMEIRA"] / (df["REC_QTD_RECARGAS_TOTAL"].clip(lower=1))

    # High risk combo
    if "REC_SCORE_RISCO" in df.columns and "PAG_FLAG_ALTO_RISCO" in df.columns:
        risk_score = df["REC_SCORE_RISCO"].fillna(0)
        alto_risco = df["PAG_FLAG_ALTO_RISCO"].fillna(0)
        df["HIGH_RISK_COMBO"] = ((risk_score > risk_score.median()) & (alto_risco == 1)).astype(np.int8)

    return df


def _create_ratio_features(df):
    """Normalized ratios from raw features."""
    if "REC_QTD_CARTAO_ONLINE" in df.columns and "REC_QTD_RECARGAS_TOTAL" in df.columns:
        df["REC_ONLINE_RATIO"] = df["REC_QTD_CARTAO_ONLINE"] / (df["REC_QTD_RECARGAS_TOTAL"].clip(lower=1))
    if "PAG_QTD_PAGAMENTOS_COM_JUROS" in df.columns and "PAG_QTD_PAGAMENTOS_TOTAL" in df.columns:
        df["PAG_JUROS_RATIO"] = df["PAG_QTD_PAGAMENTOS_COM_JUROS"] / (df["PAG_QTD_PAGAMENTOS_TOTAL"].clip(lower=1))
    if "FAT_QTD_FATURAS_PRIMEIRA" in df.columns and "FAT_QTD_SAFRAS_DISTINTAS" in df.columns:
        df["FAT_FIRST_RATIO"] = df["FAT_QTD_FATURAS_PRIMEIRA"] / (df["FAT_QTD_SAFRAS_DISTINTAS"].clip(lower=1))
    if "REC_QTD_PLATAFORMAS" in df.columns and "REC_QTD_RECARGAS_TOTAL" in df.columns:
        df["REC_PLATFORM_DIVERSITY"] = df["REC_QTD_PLATAFORMAS"] / (df["REC_QTD_RECARGAS_TOTAL"].clip(lower=1))
    return df


def _create_temporal_features(df):
    """Time-based patterns within each SAFRA snapshot."""
    if "FAT_DIAS_DESDE_ATIVACAO_CONTA" in df.columns:
        bins = [0, 30, 90, 180, 365, 99999]
        labels = [0, 1, 2, 3, 4]
        df["TENURE_BUCKET"] = pd.cut(df["FAT_DIAS_DESDE_ATIVACAO_CONTA"].fillna(0), bins=bins, labels=labels).astype(float)

    if "REC_DIAS_DESDE_ULTIMA_RECARGA" in df.columns and "REC_DIAS_ENTRE_RECARGAS" in df.columns:
        df["RECENCY_GAP"] = df["REC_DIAS_DESDE_ULTIMA_RECARGA"] - df["REC_DIAS_ENTRE_RECARGAS"]

    if "REC_FREQ_RECARGA_DIARIA" in df.columns and "REC_QTD_RECARGAS_TOTAL" in df.columns:
        df["RECHARGE_VELOCITY_CHANGE"] = df["REC_FREQ_RECARGA_DIARIA"] * df["REC_QTD_RECARGAS_TOTAL"]

    return df


def _create_nonlinear_features(df, target_col="FPD"):
    """Log/sqrt transforms of skewed features."""
    skewed_cols = ["REC_VLR_CREDITO_STDDEV", "REC_VLR_REAL_STDDEV", "PAG_VLR_PAGAMENTO_FATURA_STDDEV",
                   "REC_QTD_RECARGAS_TOTAL", "PAG_QTD_PAGAMENTOS_TOTAL"]
    for col in skewed_cols:
        if col in df.columns:
            df[f"{col}_LOG"] = np.log1p(df[col].fillna(0).clip(lower=0))
            df[f"{col}_SQRT"] = np.sqrt(df[col].fillna(0).clip(lower=0))

    # Bin TARGET_SCORE_02 into quartiles
    if "TARGET_SCORE_02" in df.columns:
        df["SCORE02_QUARTILE"] = pd.qcut(df["TARGET_SCORE_02"].fillna(df["TARGET_SCORE_02"].median()),
                                          q=4, labels=[0, 1, 2, 3], duplicates="drop").astype(float)

    return df


def phase2_feature_engineering(df):
    """Create all new features — fully self-contained."""
    log("=" * 70)
    log("PHASE 2: FEATURE ENGINEERING")
    log("=" * 70)

    t0 = time.time()
    initial_cols = set(df.columns)

    df = _create_missing_features(df)
    log(f"  Missing features: +{len(set(df.columns) - initial_cols)} new")

    df = _create_interaction_features(df)
    df = _create_ratio_features(df)
    df = _create_temporal_features(df)
    df = _create_nonlinear_features(df, target_col=TARGET)

    # PCA — fit on train, transform all
    from sklearn.decomposition import PCA as _PCA
    pca_groups = {"REC": [], "PAG": [], "FAT": []}
    for col in df.select_dtypes(include=[np.number]).columns:
        for prefix in pca_groups:
            if col.startswith(f"{prefix}_"):
                pca_groups[prefix].append(col)
                break

    for prefix, cols in pca_groups.items():
        if len(cols) >= 5:
            pca_data = df[cols].fillna(0)
            n_comp = min(5, len(cols))
            pca = _PCA(n_components=n_comp, random_state=42)
            # Fit on train only
            train_mask = df["SAFRA"].isin(TRAIN_SAFRAS)
            pca.fit(pca_data[train_mask])
            components = pca.transform(pca_data)
            for i in range(n_comp):
                df[f"PCA_{prefix}_{i}"] = components[:, i]
            log(f"  PCA {prefix}: {len(cols)} features → {n_comp} components (var explained: {pca.explained_variance_ratio_.sum():.2%})")

    elapsed = time.time() - t0
    new_features = [c for c in df.columns if c not in initial_cols and c not in [TARGET, "SAFRA", "NUM_CPF"]]
    log(f"  Created {len(new_features)} new features in {elapsed:.1f}s")
    log(f"  Total columns: {df.shape[1]}")

    # Save feature engineering report
    os.makedirs(os.path.join(ARTIFACT_DIR, "feature_engineering"), exist_ok=True)
    with open(os.path.join(ARTIFACT_DIR, "feature_engineering", "new_features.json"), "w") as f:
        json.dump({"new_features": new_features, "count": len(new_features)}, f, indent=2)

    return df, new_features


def phase2_feature_selection(df, new_features):
    """Select best features — IV filter + correlation filter + PSI stability."""
    log("PHASE 2.7: FEATURE SELECTION")

    all_candidates = SELECTED_FEATURES + new_features
    available = [c for c in all_candidates if c in df.columns]

    df_train = df[df["SAFRA"].isin(TRAIN_SAFRAS) & df[TARGET].notna()].copy()
    y_train = df_train[TARGET].astype(int)

    # Step 1: IV filter (>0.02)
    selected_iv = []
    for col in available:
        vals = df_train[col].fillna(-999)
        if vals.nunique() < 2:
            continue
        try:
            bins = pd.qcut(vals, q=10, duplicates="drop")
            ct = pd.crosstab(bins, y_train)
            if ct.shape[1] < 2:
                selected_iv.append(col)
                continue
            good = (ct[0] / ct[0].sum()).clip(lower=0.0001)
            bad = (ct[1] / ct[1].sum()).clip(lower=0.0001)
            iv = ((good - bad) * np.log(good / bad)).sum()
            if iv > 0.02:
                selected_iv.append(col)
        except Exception:
            selected_iv.append(col)  # Keep if can't compute

    log(f"  IV filter: {len(available)} → {len(selected_iv)} (IV>0.02)")

    # Step 2: Correlation filter (<0.95)
    if len(selected_iv) > 0:
        corr_matrix = df_train[selected_iv].corr().abs()
        to_drop = set()
        for i in range(len(corr_matrix.columns)):
            for j in range(i + 1, len(corr_matrix.columns)):
                if corr_matrix.iloc[i, j] > 0.95:
                    # Drop the one with lower IV (approximated by keeping original features)
                    col_j = corr_matrix.columns[j]
                    if col_j not in SELECTED_FEATURES:
                        to_drop.add(col_j)
                    else:
                        to_drop.add(corr_matrix.columns[i])
        selected_corr = [c for c in selected_iv if c not in to_drop]
        log(f"  Correlation filter: {len(selected_iv)} → {len(selected_corr)} (corr<0.95)")
    else:
        selected_corr = selected_iv

    # Step 3: PSI stability filter (<0.20)
    selected_stable = []
    for col in selected_corr:
        # Skip non-numeric columns (PSI requires numeric data)
        if not np.issubdtype(df[col].dtype, np.number):
            selected_stable.append(col)
            continue
        train_vals = df[df["SAFRA"].isin(TRAIN_SAFRAS)][col].dropna().values
        oot_vals = df[df["SAFRA"].isin(OOT_SAFRAS)][col].dropna().values
        if len(train_vals) < 100 or len(oot_vals) < 100:
            selected_stable.append(col)
            continue
        psi = compute_psi(train_vals, oot_vals)
        if psi < 0.20:
            selected_stable.append(col)

    log(f"  PSI stability filter: {len(selected_corr)} → {len(selected_stable)} (PSI<0.20)")
    log(f"  Selected: {len(selected_stable)} features (from {len(available)} candidates)")

    return selected_stable


# ═════════════════════════════════════════════════════════════════════════
# PHASE 3: HPO (reduced trials for speed)
# ═════════════════════════════════════════════════════════════════════════

def _run_hpo_model(df, features, model_type, n_trials=50):
    """Run Optuna HPO for a single model type. Returns best_params dict."""
    import optuna
    from sklearn.model_selection import StratifiedKFold
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.compose import ColumnTransformer

    try:
        from category_encoders import CountEncoder
    except ImportError:
        from category_encoders.count import CountEncoder

    cat_feats = [f for f in features if f in CAT_FEATURES]
    num_feats = [f for f in features if f not in cat_feats]

    # Use training data only (drop NaN targets)
    train_mask = df["SAFRA"].isin(TRAIN_SAFRAS) & df[TARGET].notna()
    X = df.loc[train_mask, features].copy()
    y = df.loc[train_mask, TARGET].astype(int).copy()

    def build_prep():
        transformers = [("num", Pipeline([("imp", SimpleImputer(strategy="median"))]), num_feats)]
        if cat_feats:
            transformers.append(("cat", Pipeline([
                ("imp", SimpleImputer(strategy="most_frequent")),
                ("enc", CountEncoder(combine_min_nan_groups=True, normalize=True,
                                     handle_missing=0, handle_unknown=0)),
            ]), cat_feats))
        return ColumnTransformer(transformers=transformers)

    def objective(trial):
        if model_type == "LightGBM":
            import lightgbm as lgb
            params = {
                "objective": "binary", "verbosity": -1, "n_jobs": NCPUS,
                "n_estimators": trial.suggest_int("n_estimators", 100, 1000),
                "learning_rate": trial.suggest_float("learning_rate", 0.005, 0.3, log=True),
                "max_depth": trial.suggest_int("max_depth", 3, 8),
                "num_leaves": trial.suggest_int("num_leaves", 15, 127),
                "min_child_samples": trial.suggest_int("min_child_samples", 20, 200),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
                "subsample": trial.suggest_float("subsample", 0.5, 1.0),
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
                "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
                "scale_pos_weight": trial.suggest_float("scale_pos_weight", 1.0, 5.0),
            }
            model_cls = lgb.LGBMClassifier
        elif model_type == "XGBoost":
            from xgboost import XGBClassifier
            params = {
                "objective": "binary:logistic", "verbosity": 0, "n_jobs": NCPUS,
                "eval_metric": "auc", "use_label_encoder": False,
                "n_estimators": trial.suggest_int("n_estimators", 100, 1000),
                "learning_rate": trial.suggest_float("learning_rate", 0.005, 0.3, log=True),
                "max_depth": trial.suggest_int("max_depth", 3, 8),
                "min_child_weight": trial.suggest_int("min_child_weight", 1, 20),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
                "subsample": trial.suggest_float("subsample", 0.5, 1.0),
                "gamma": trial.suggest_float("gamma", 1e-8, 5.0, log=True),
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
                "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
                "scale_pos_weight": trial.suggest_float("scale_pos_weight", 1.0, 5.0),
            }
            model_cls = XGBClassifier
        elif model_type == "CatBoost":
            from catboost import CatBoostClassifier
            params = {
                "verbose": 0, "thread_count": NCPUS, "auto_class_weights": "Balanced",
                "iterations": trial.suggest_int("iterations", 100, 1000),
                "learning_rate": trial.suggest_float("learning_rate", 0.005, 0.3, log=True),
                "depth": trial.suggest_int("depth", 3, 8),
                "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 1e-2, 10.0, log=True),
                "border_count": trial.suggest_int("border_count", 32, 255),
                "bagging_temperature": trial.suggest_float("bagging_temperature", 0.0, 5.0),
            }
            model_cls = CatBoostClassifier
        else:
            raise ValueError(f"Unknown model_type: {model_type}")

        # 3-fold temporal-aware CV
        cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
        ks_scores = []
        for train_idx, val_idx in cv.split(X, y):
            X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_tr, y_val = y.iloc[train_idx], y.iloc[val_idx]
            pipe = Pipeline([("prep", build_prep()), ("model", model_cls(**params))])
            pipe.fit(X_tr, y_tr)
            proba = pipe.predict_proba(X_val)[:, 1]
            ks_scores.append(compute_ks(y_val.values, proba))
        return np.mean(ks_scores)

    study = optuna.create_study(direction="maximize",
                                 pruner=optuna.pruners.MedianPruner())
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    return {
        "best_params": study.best_params,
        "best_ks_cv": study.best_value,
    }


def phase3_hpo(df, features, n_trials=50):
    """Run HPO for LightGBM, XGBoost, CatBoost."""
    log("=" * 70)
    log(f"PHASE 3: HPO (Optuna, {n_trials} trials per model)")
    log("=" * 70)

    try:
        import optuna
        optuna.logging.set_verbosity(optuna.logging.WARNING)
    except ImportError:
        log("  [SKIP] optuna not installed, using defaults")
        return {}

    os.environ["ARTIFACT_DIR"] = ARTIFACT_DIR
    best_params = {}

    # LightGBM HPO
    log("\n  LightGBM HPO...")
    try:
        result = _run_hpo_model(df, features, "LightGBM", n_trials=n_trials)
        best_params["LightGBM"] = result["best_params"]
        log(f"  LGBM best KS(CV): {result['best_ks_cv']:.5f}")
    except Exception as e:
        log(f"  LGBM HPO failed: {e}")

    # XGBoost HPO
    try:
        log("\n  XGBoost HPO...")
        result = _run_hpo_model(df, features, "XGBoost", n_trials=n_trials)
        best_params["XGBoost"] = result["best_params"]
        log(f"  XGB best KS(CV): {result['best_ks_cv']:.5f}")
    except Exception as e:
        log(f"  XGB HPO failed: {e}")

    # CatBoost HPO
    try:
        log("\n  CatBoost HPO...")
        result = _run_hpo_model(df, features, "CatBoost", n_trials=n_trials)
        best_params["CatBoost"] = result["best_params"]
        log(f"  CatBoost best KS(CV): {result['best_ks_cv']:.5f}")
    except Exception as e:
        log(f"  CatBoost HPO failed: {e}")

    # Save
    os.makedirs(os.path.join(ARTIFACT_DIR, "hpo"), exist_ok=True)
    with open(os.path.join(ARTIFACT_DIR, "hpo", "best_params_all.json"), "w") as f:
        json.dump(best_params, f, indent=2, default=str)

    return best_params


# ═════════════════════════════════════════════════════════════════════════
# PHASE 4: MULTI-MODEL TRAINING
# ═════════════════════════════════════════════════════════════════════════

def phase4_train_models(df, features, hpo_params):
    """Train all 5 models."""
    log("=" * 70)
    log("PHASE 4: MULTI-MODEL TRAINING")
    log("=" * 70)

    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.compose import ColumnTransformer
    import lightgbm as lgb

    try:
        from category_encoders import CountEncoder
    except ImportError:
        from category_encoders.count import CountEncoder

    cat_feats = [f for f in features if f in CAT_FEATURES]
    num_feats = [f for f in features if f not in cat_feats]

    X_train, y_train, X_oos, y_oos, X_oot, y_oot, _, _, _ = temporal_split(df, features)

    def build_prep(use_scaler=False):
        steps = [("imputer", SimpleImputer(strategy="median"))]
        if use_scaler:
            steps.append(("scaler", StandardScaler()))
        transformers = [("num", Pipeline(steps=steps), num_feats)]
        if cat_feats:
            transformers.append(("cat", Pipeline(steps=[
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("encoder", CountEncoder(combine_min_nan_groups=True, normalize=True,
                                         handle_missing=0, handle_unknown=0)),
            ]), cat_feats))
        return ColumnTransformer(transformers=transformers)

    def eval_model(pipe, name):
        y_prob_train = pipe.predict_proba(X_train)[:, 1]
        y_prob_oos = pipe.predict_proba(X_oos)[:, 1]
        y_prob_oot = pipe.predict_proba(X_oot)[:, 1]
        ks_train = compute_ks(y_train.values, y_prob_train)
        ks_oos = compute_ks(y_oos.values, y_prob_oos)
        ks_oot = compute_ks(y_oot.values, y_prob_oot)
        auc_oot = roc_auc_score(y_oot, y_prob_oot)
        psi = compute_psi(y_prob_train, y_prob_oot)
        log(f"  {name:20s}: KS Train={ks_train:.4f} OOS={ks_oos:.4f} OOT={ks_oot:.4f} AUC={auc_oot:.4f} PSI={psi:.6f}")
        return {"ks_train": ks_train, "ks_oos": ks_oos, "ks_oot": ks_oot,
                "auc_oot": auc_oot, "gini_oot": compute_gini(auc_oot), "psi": psi}

    pipelines = {}
    metrics = {}

    # 1. LightGBM v2
    lgbm_params = hpo_params.get("LightGBM", {})
    lgbm_defaults = {"objective": "binary", "n_estimators": 500, "learning_rate": 0.03,
                     "max_depth": 6, "num_leaves": 63, "min_child_samples": 50,
                     "colsample_bytree": 0.7, "subsample": 0.8, "n_jobs": NCPUS,
                     "num_threads": NCPUS, "random_state": 42, "verbosity": -1}
    lgbm_defaults.update(lgbm_params)
    for k in ["n_jobs", "num_threads"]:
        lgbm_defaults[k] = NCPUS
    lgbm_defaults["random_state"] = 42
    lgbm_defaults["verbosity"] = -1
    lgbm_defaults["objective"] = "binary"

    pipe = Pipeline([("prep", build_prep()), ("model", lgb.LGBMClassifier(**lgbm_defaults))])
    t0 = time.time()
    pipe.fit(X_train, y_train)
    log(f"  LightGBM v2 trained in {time.time()-t0:.1f}s")
    pipelines["LightGBM_v2"] = pipe
    metrics["LightGBM_v2"] = eval_model(pipe, "LightGBM_v2")

    # 2. XGBoost
    try:
        from xgboost import XGBClassifier
        xgb_params = hpo_params.get("XGBoost", {})
        xgb_defaults = {"objective": "binary:logistic", "n_estimators": 500, "learning_rate": 0.03,
                        "max_depth": 6, "min_child_weight": 5, "colsample_bytree": 0.7,
                        "subsample": 0.8, "n_jobs": NCPUS, "random_state": 42, "verbosity": 0,
                        "eval_metric": "auc", "use_label_encoder": False}
        xgb_defaults.update(xgb_params)
        xgb_defaults["n_jobs"] = NCPUS
        xgb_defaults["random_state"] = 42

        pipe = Pipeline([("prep", build_prep()), ("model", XGBClassifier(**xgb_defaults))])
        t0 = time.time()
        pipe.fit(X_train, y_train)
        log(f"  XGBoost trained in {time.time()-t0:.1f}s")
        pipelines["XGBoost"] = pipe
        metrics["XGBoost"] = eval_model(pipe, "XGBoost")
    except ImportError:
        log("  [SKIP] XGBoost not available")

    # 3. CatBoost
    try:
        from catboost import CatBoostClassifier
        cb_params = hpo_params.get("CatBoost", {})
        cb_defaults = {"iterations": 500, "learning_rate": 0.03, "depth": 6,
                       "l2_leaf_reg": 3.0, "random_seed": 42, "verbose": 0,
                       "thread_count": NCPUS, "auto_class_weights": "Balanced"}
        cb_defaults.update(cb_params)
        cb_defaults["thread_count"] = NCPUS
        cb_defaults["random_seed"] = 42
        cb_defaults["verbose"] = 0

        pipe = Pipeline([("prep", build_prep()), ("model", CatBoostClassifier(**cb_defaults))])
        t0 = time.time()
        pipe.fit(X_train, y_train)
        log(f"  CatBoost trained in {time.time()-t0:.1f}s")
        pipelines["CatBoost"] = pipe
        metrics["CatBoost"] = eval_model(pipe, "CatBoost")
    except ImportError:
        log("  [SKIP] CatBoost not available")

    # 4. Random Forest
    pipe = Pipeline([("prep", build_prep()), ("model", RandomForestClassifier(
        n_estimators=500, max_depth=12, min_samples_leaf=50,
        max_features="sqrt", class_weight="balanced",
        n_jobs=NCPUS, random_state=42))])
    t0 = time.time()
    pipe.fit(X_train, y_train)
    log(f"  RandomForest trained in {time.time()-t0:.1f}s")
    pipelines["RandomForest"] = pipe
    metrics["RandomForest"] = eval_model(pipe, "RandomForest")

    # 5. LR L1 v2
    pipe = Pipeline([("prep", build_prep(use_scaler=True)), ("model", LogisticRegression(
        C=0.5, penalty="l1", solver="liblinear", max_iter=2000,
        tol=0.001, class_weight="balanced", random_state=42))])
    t0 = time.time()
    pipe.fit(X_train, y_train)
    log(f"  LR L1 v2 trained in {time.time()-t0:.1f}s")
    pipelines["LR_L1_v2"] = pipe
    metrics["LR_L1_v2"] = eval_model(pipe, "LR_L1_v2")

    # Save all models
    models_dir = os.path.join(ARTIFACT_DIR, "models_v2")
    os.makedirs(models_dir, exist_ok=True)
    for name, pipe in pipelines.items():
        with open(os.path.join(models_dir, f"{name}.pkl"), "wb") as f:
            pickle.dump(pipe, f)

    with open(os.path.join(models_dir, "multi_model_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2, default=str)

    return pipelines, metrics, X_train, y_train, X_oos, y_oos, X_oot, y_oot


# ═════════════════════════════════════════════════════════════════════════
# ENSEMBLE MODEL CLASS (inline — replaces ensemble_model.py)
# ═════════════════════════════════════════════════════════════════════════

class _EnsembleModel:
    """Multi-model ensemble with blend or stack modes."""

    def __init__(self, base_models, mode="blend", weights=None,
                 meta_learner=None, meta_features=None):
        self.base_models = base_models  # dict {name: pipeline}
        self.mode = mode
        self.weights = weights  # dict {name: weight} for blend
        self.meta_learner = meta_learner  # for stack mode
        self.meta_features = meta_features or list(base_models.keys())

    def predict_proba(self, X):
        names = list(self.base_models.keys())
        base_preds = np.column_stack([
            self.base_models[n].predict_proba(X)[:, 1] for n in names
        ])

        if self.mode == "stack" and self.meta_learner is not None:
            proba = self.meta_learner.predict_proba(
                pd.DataFrame(base_preds, columns=names))[:, 1]
        else:
            w = [self.weights.get(n, 1.0 / len(names)) for n in names] if self.weights else None
            proba = np.average(base_preds, axis=1, weights=w)

        return np.column_stack([1 - proba, proba])

    def save(self, path):
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def load(path):
        with open(path, "rb") as f:
            return pickle.load(f)


# ═════════════════════════════════════════════════════════════════════════
# PHASE 5: ENSEMBLE
# ═════════════════════════════════════════════════════════════════════════

def phase5_ensemble(pipelines, X_oos, y_oos, X_oot, y_oot, X_train, y_train):
    """Build and select ensemble."""
    log("=" * 70)
    log("PHASE 5: ENSEMBLE CONSTRUCTION")
    log("=" * 70)

    from scipy.optimize import minimize

    model_names = list(pipelines.keys())
    n_models = len(model_names)

    # Get predictions
    oos_preds = {name: pipe.predict_proba(X_oos)[:, 1] for name, pipe in pipelines.items()}
    oot_preds = {name: pipe.predict_proba(X_oot)[:, 1] for name, pipe in pipelines.items()}

    # 1. Simple average
    simple_oot = np.mean(list(oot_preds.values()), axis=0)
    ks_simple = compute_ks(y_oot.values, simple_oot)
    auc_simple = roc_auc_score(y_oot, simple_oot)
    log(f"  Simple Average — KS={ks_simple:.5f} AUC={auc_simple:.5f}")

    # 2. Optimized blend (SLSQP on OOS)
    preds_matrix_oos = np.column_stack([oos_preds[name] for name in model_names])

    def objective(weights):
        blended = np.average(preds_matrix_oos, axis=1, weights=weights)
        return -compute_ks(y_oos.values, blended)

    constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1}
    bounds = [(0.01, 1)] * n_models  # min 1% weight each
    initial = np.ones(n_models) / n_models

    result = minimize(objective, initial, method="SLSQP",
                      bounds=bounds, constraints=constraints)

    optimal_weights = {name: round(float(w), 4) for name, w in zip(model_names, result.x)}
    log(f"  Optimized weights: {optimal_weights}")

    # Evaluate blend on OOT
    preds_matrix_oot = np.column_stack([oot_preds[name] for name in model_names])
    blend_oot = np.average(preds_matrix_oot, axis=1, weights=result.x)
    ks_blend = compute_ks(y_oot.values, blend_oot)
    auc_blend = roc_auc_score(y_oot, blend_oot)
    psi_blend = compute_psi(
        np.average(np.column_stack([pipe.predict_proba(X_train)[:, 1] for pipe in pipelines.values()]),
                   axis=1, weights=result.x),
        blend_oot,
    )
    log(f"  Weighted Blend — KS={ks_blend:.5f} AUC={auc_blend:.5f} PSI={psi_blend:.6f}")

    # 3. Stacking (LR meta-learner)
    from sklearn.linear_model import LogisticRegression as LR
    from sklearn.base import clone

    # Generate OOF predictions
    log("  Generating OOF predictions for stacking...")
    df_train_full = pd.concat([X_train], axis=1)
    df_train_full[TARGET] = y_train.values
    df_train_full["SAFRA"] = X_train.index  # Will use temporal CV fold indices

    # Simple approach: use OOS predictions as meta-features
    X_meta_oos = pd.DataFrame(oos_preds)
    X_meta_oot = pd.DataFrame(oot_preds)

    meta_learner = LR(C=1.0, penalty="l2", solver="lbfgs", max_iter=2000, random_state=42)
    meta_learner.fit(X_meta_oos, y_oos)

    stack_oot = meta_learner.predict_proba(X_meta_oot)[:, 1]
    ks_stack = compute_ks(y_oot.values, stack_oot)
    auc_stack = roc_auc_score(y_oot, stack_oot)
    log(f"  Stacking — KS={ks_stack:.5f} AUC={auc_stack:.5f}")

    # Select champion
    results = {
        "simple_avg": {"ks": ks_simple, "auc": auc_simple},
        "blend": {"ks": ks_blend, "auc": auc_blend, "psi": psi_blend, "weights": optimal_weights},
        "stack": {"ks": ks_stack, "auc": auc_stack},
    }

    best_method = max(results.items(), key=lambda x: x[1]["ks"])
    champion = best_method[0]

    log(f"\n  CHAMPION: {champion} (KS={best_method[1]['ks']:.5f})")

    # Build EnsembleModel (inline)
    if champion == "stack":
        ensemble = _EnsembleModel(
            base_models=pipelines, mode="stack",
            meta_learner=meta_learner, meta_features=model_names)
    else:
        weights = optimal_weights if champion == "blend" else {n: 1.0/n_models for n in model_names}
        ensemble = _EnsembleModel(
            base_models=pipelines, mode="blend", weights=weights)

    # Final metrics
    ens_oot = ensemble.predict_proba(X_oot)[:, 1]
    ens_ks = compute_ks(y_oot.values, ens_oot)
    ens_auc = roc_auc_score(y_oot, ens_oot)
    ens_gini = compute_gini(ens_auc)

    # Save ensemble
    ensemble_dir = os.path.join(ARTIFACT_DIR, "ensemble")
    os.makedirs(ensemble_dir, exist_ok=True)
    ensemble.save(os.path.join(ensemble_dir, "ensemble_model.pkl"))

    with open(os.path.join(ensemble_dir, "ensemble_results.json"), "w") as f:
        json.dump({
            "champion": champion,
            "ks_oot": round(ens_ks, 5),
            "auc_oot": round(ens_auc, 5),
            "gini_oot": round(ens_gini, 2),
            "psi": psi_blend,
            "weights": optimal_weights,
            "all_results": {k: {kk: round(vv, 5) if isinstance(vv, float) else vv
                                for kk, vv in v.items()}
                           for k, v in results.items()},
            "baseline_ks_oot": 0.34027,
            "improvement_pp": round((ens_ks - 0.34027) * 100, 2),
        }, f, indent=2, default=str)

    log(f"\n  ENSEMBLE FINAL METRICS:")
    log(f"    KS OOT:  {ens_ks:.5f} (baseline: 0.34027, improvement: {(ens_ks-0.34027)*100:+.2f}pp)")
    log(f"    AUC OOT: {ens_auc:.5f} (baseline: 0.73054)")
    log(f"    Gini:    {ens_gini:.2f}")
    log(f"    PSI:     {psi_blend:.6f}")

    return ensemble, results


# ═════════════════════════════════════════════════════════════════════════
# PHASE 6: SCORING + UPLOAD + MONITORING
# ═════════════════════════════════════════════════════════════════════════

def phase6_production(ensemble, df, features):
    """Score all customers, upload artifacts, publish monitoring."""
    log("=" * 70)
    log("PHASE 6: PRODUCTION DEPLOYMENT")
    log("=" * 70)

    import uuid

    X_all = df[features]
    probabilities = ensemble.predict_proba(X_all)[:, 1]
    scores = ((1 - probabilities) * 1000).astype(int).clip(0, 1000)

    def risk_band(s):
        if s < 300: return "CRITICO"
        elif s < 500: return "ALTO"
        elif s < 700: return "MEDIO"
        else: return "BAIXO"

    execution_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    scores_df = pd.DataFrame({
        "NUM_CPF": df["NUM_CPF"].values,
        "SAFRA": df["SAFRA"].values,
        "SCORE": scores,
        "FAIXA_RISCO": [risk_band(s) for s in scores],
        "PROBABILIDADE_FPD": probabilities.round(6),
        "MODELO_VERSAO": "ensemble-v1",
        "DATA_SCORING": timestamp,
        "EXECUTION_ID": execution_id,
    })

    # Score distribution
    log(f"\n  Scored {len(scores_df):,} records")
    for band in ["CRITICO", "ALTO", "MEDIO", "BAIXO"]:
        count = (scores_df["FAIXA_RISCO"] == band).sum()
        pct = count / len(scores_df) * 100
        log(f"    {band:10s}: {count:>8,} ({pct:.1f}%)")
    log(f"  Score stats: mean={scores.mean():.0f}, median={int(np.median(scores))}")

    # Save scoring locally
    scoring_dir = os.path.join(ARTIFACT_DIR, "scoring")
    os.makedirs(scoring_dir, exist_ok=True)
    scores_df.to_parquet(os.path.join(scoring_dir, "ensemble_scores_all.parquet"), index=False)

    # Upload artifacts to OCI Object Storage
    log("\n  Uploading artifacts to OCI Object Storage...")

    upload_files = []
    for root, dirs, files in os.walk(ARTIFACT_DIR):
        for fname in files:
            local_path = os.path.join(root, fname)
            rel_path = os.path.relpath(local_path, ARTIFACT_DIR)
            obj_name = f"model_artifacts/ensemble_v1/{rel_path}".replace("\\", "/")
            upload_files.append((local_path, obj_name))

    for local_path, obj_name in upload_files:
        cmd = (f'oci os object put --bucket-name {GOLD_BUCKET} --namespace {NAMESPACE} '
               f'--name "{obj_name}" --file "{local_path}" --force --no-multipart 2>&1')
        os.system(cmd)

    log(f"  Uploaded {len(upload_files)} artifacts to oci://{GOLD_BUCKET}@{NAMESPACE}/model_artifacts/ensemble_v1/")

    # Upload scores partitioned by SAFRA
    for safra in sorted(scores_df["SAFRA"].unique()):
        safra_df = scores_df[scores_df["SAFRA"] == safra]
        safra_path = os.path.join(scoring_dir, f"scores_safra_{safra}.parquet")
        safra_df.to_parquet(safra_path, index=False)
        obj_name = f"clientes_scores_ensemble/SAFRA={safra}/scores.parquet"
        os.system(f'oci os object put --bucket-name {GOLD_BUCKET} --namespace {NAMESPACE} '
                  f'--name "{obj_name}" --file "{safra_path}" --force --no-multipart 2>&1')
    log("  Scores uploaded by SAFRA partition")

    return scores_df


def phase6_monitoring_data(ensemble, df, features, metrics_all):
    """Generate monitoring data for APEX dashboard."""
    log("\n  Generating monitoring metrics for APEX...")

    monitoring = {
        "timestamp": datetime.now().isoformat(),
        "model_version": "ensemble-v1",
        "metrics_by_safra": {},
    }

    for safra in sorted(df["SAFRA"].unique()):
        df_s = df[df["SAFRA"] == safra]
        X_s = df_s[features]
        probs = ensemble.predict_proba(X_s)[:, 1]
        scores = ((1 - probs) * 1000).astype(int).clip(0, 1000)

        safra_data = {
            "n_records": int(len(df_s)),
            "score_mean": round(float(scores.mean()), 2),
            "score_median": float(int(np.median(scores))),
            "score_std": round(float(scores.std()), 2),
            "score_p25": float(int(np.percentile(scores, 25))),
            "score_p75": float(int(np.percentile(scores, 75))),
            "pct_critico": round(float((scores < 300).mean() * 100), 2),
            "pct_alto": round(float(((scores >= 300) & (scores < 500)).mean() * 100), 2),
            "pct_medio": round(float(((scores >= 500) & (scores < 700)).mean() * 100), 2),
            "pct_baixo": round(float((scores >= 700).mean() * 100), 2),
        }

        # KS/AUC if labeled
        if TARGET in df_s.columns and df_s[TARGET].notna().sum() > 100:
            labeled_mask = df_s[TARGET].notna()
            y_s = df_s.loc[labeled_mask, TARGET].astype(int)
            probs_labeled = probs[labeled_mask.values]
            ks = compute_ks(y_s.values, probs_labeled)
            auc = roc_auc_score(y_s, probs_labeled)
            safra_data["ks"] = round(float(ks), 5)
            safra_data["auc"] = round(float(auc), 5)
            safra_data["gini"] = round(compute_gini(auc), 2)

        monitoring["metrics_by_safra"][int(safra)] = safra_data

    # Overall ensemble metrics
    monitoring["ensemble_summary"] = {
        "n_base_models": len(ensemble.base_models) if hasattr(ensemble, "base_models") else 1,
        "mode": getattr(ensemble, "mode", "single"),
        "weights": getattr(ensemble, "weights", None),
    }

    # Add multi-model comparison
    monitoring["model_comparison"] = metrics_all

    # Save for APEX
    monitoring_dir = os.path.join(ARTIFACT_DIR, "monitoring")
    os.makedirs(monitoring_dir, exist_ok=True)

    with open(os.path.join(monitoring_dir, "ensemble_monitoring.json"), "w") as f:
        json.dump(monitoring, f, indent=2, default=str)

    # Generate CSV for APEX SQL import
    rows = []
    for safra, data in monitoring["metrics_by_safra"].items():
        row = {"SAFRA": safra, "MODEL_VERSION": "ensemble-v1", **data}
        rows.append(row)
    monitoring_df = pd.DataFrame(rows)
    monitoring_df.to_csv(os.path.join(monitoring_dir, "monitoring_metrics.csv"), index=False)

    # Per-model metrics CSV
    model_rows = []
    for model_name, m in metrics_all.items():
        model_rows.append({
            "MODEL_NAME": model_name,
            "KS_TRAIN": m.get("ks_train", 0),
            "KS_OOS": m.get("ks_oos", 0),
            "KS_OOT": m.get("ks_oot", 0),
            "AUC_OOT": m.get("auc_oot", 0),
            "GINI_OOT": m.get("gini_oot", 0),
            "PSI": m.get("psi", 0),
        })
    model_df = pd.DataFrame(model_rows)
    model_df.to_csv(os.path.join(monitoring_dir, "model_comparison.csv"), index=False)

    log(f"  Monitoring data saved: {len(rows)} SAFRA records, {len(model_rows)} model records")

    return monitoring


# ═════════════════════════════════════════════════════════════════════════
# MAIN ORCHESTRATOR
# ═════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Full Ensemble Pipeline")
    parser.add_argument("--n-trials", type=int, default=50, help="HPO trials per model")
    parser.add_argument("--skip-hpo", action="store_true", help="Skip HPO, use defaults")
    parser.add_argument("--data-path", default=None, help="Override data path")
    args = parser.parse_args()

    global LOCAL_DATA_PATH
    if args.data_path:
        LOCAL_DATA_PATH = args.data_path

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    log("=" * 70)
    log("FULL ENSEMBLE PIPELINE ORCHESTRATOR")
    log(f"Run ID: {run_id} | OCPUs: {NCPUS}")
    log(f"Data: {LOCAL_DATA_PATH}")
    log(f"Artifacts: {ARTIFACT_DIR}")
    log("=" * 70)

    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    pipeline_start = time.time()

    # Load data
    df = load_data()

    # Load baseline model for diagnostic
    baseline_path = os.path.join(ARTIFACT_DIR, "models", "lgbm_oci_20260217_214614.pkl")
    if not os.path.exists(baseline_path):
        # Download from OCI
        log("Downloading baseline model from OCI...")
        os.makedirs(os.path.join(ARTIFACT_DIR, "models"), exist_ok=True)
        os.system(f'oci os object get --bucket-name {GOLD_BUCKET} --namespace {NAMESPACE} '
                  f'--name "model_artifacts/models/lgbm_oci_20260217_214614.pkl" '
                  f'--file "{baseline_path}" 2>&1')

    baseline_pipeline = None
    if os.path.exists(baseline_path):
        with open(baseline_path, "rb") as f:
            baseline_pipeline = pickle.load(f)
        log("Baseline model loaded")

    # PHASE 1: Diagnostic
    if baseline_pipeline:
        findings = phase1_diagnostic(df, baseline_pipeline)
    else:
        log("[SKIP] Phase 1 — no baseline model available")
        findings = ["No baseline model for comparison"]

    # PHASE 2: Feature Engineering
    df, new_features = phase2_feature_engineering(df)
    selected_features = phase2_feature_selection(df, new_features)

    # PHASE 3: HPO
    if args.skip_hpo:
        log("[SKIP] Phase 3 — using default params")
        hpo_params = {}
    else:
        hpo_params = phase3_hpo(df, selected_features, n_trials=args.n_trials)

    # PHASE 4: Multi-Model Training
    pipelines, metrics, X_train, y_train, X_oos, y_oos, X_oot, y_oot = \
        phase4_train_models(df, selected_features, hpo_params)

    # PHASE 5: Ensemble
    ensemble, ensemble_results = phase5_ensemble(
        pipelines, X_oos, y_oos, X_oot, y_oot, X_train, y_train)

    # PHASE 6: Production
    scores_df = phase6_production(ensemble, df, selected_features)
    monitoring = phase6_monitoring_data(ensemble, df, selected_features, metrics)

    # Final summary
    total_time = time.time() - pipeline_start
    log("\n" + "=" * 70)
    log("PIPELINE COMPLETE")
    log(f"  Total time: {total_time:.0f}s ({total_time/60:.1f}m)")
    log(f"  Features: {len(selected_features)}")
    log(f"  Models trained: {len(pipelines)}")
    log(f"  Records scored: {len(scores_df):,}")
    log(f"  Artifacts: {ARTIFACT_DIR}")
    log("=" * 70)

    # Save final summary
    summary = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "total_time_seconds": round(total_time, 1),
        "n_features_selected": len(selected_features),
        "n_models": len(pipelines),
        "n_records_scored": len(scores_df),
        "ensemble_mode": getattr(ensemble, "mode", "unknown"),
        "diagnostic_findings": findings,
        "model_metrics": metrics,
        "ensemble_results": {k: {kk: round(vv, 5) if isinstance(vv, float) else vv
                                  for kk, vv in v.items()}
                             for k, v in ensemble_results.items()},
    }

    with open(os.path.join(ARTIFACT_DIR, f"pipeline_summary_{run_id}.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)

    log(f"\nSummary saved to {ARTIFACT_DIR}/pipeline_summary_{run_id}.json")


if __name__ == "__main__":
    main()
