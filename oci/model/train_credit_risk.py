"""
Credit Risk Model Training — OCI Data Science
Phase 5: Model Migration (Fabric → OCI)

Trains dual models (LR L1 Scorecard + LightGBM GBDT) for FPD prediction.
Replicates exact Fabric pipeline with performance parity (±0.5%).

Architecture: VM.Standard.E4.Flex — 10 OCPUs, 160 GB RAM (trial limit)
Threading: OMP_NUM_THREADS=10, LightGBM num_threads=10

Usage:
    Run in OCI Data Science notebook session (10 OCPUs, 160 GB).
    Requires: scikit-learn==1.3.2, lightgbm, category-encoders==2.6.3, pyarrow
"""
import os
import json
import time
from datetime import datetime

# ── Threading config (BEFORE any numpy/sklearn import) ─────────────────────
NCPUS = int(os.environ.get("NOTEBOOK_OCPUS", "10"))
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

# Object Storage paths (update namespace before running)
NAMESPACE = os.environ.get("OCI_NAMESPACE", "SET_YOUR_NAMESPACE")
GOLD_BUCKET = os.environ.get("GOLD_BUCKET", "pod-academy-gold")
GOLD_PATH = f"oci://{GOLD_BUCKET}@{NAMESPACE}/clientes_consolidado/"

# Local path (if pre-copied to block volume for faster I/O)
LOCAL_DATA_PATH = "/home/datascience/data/clientes_consolidado/"

# Artifact output directory
ARTIFACT_DIR = "/home/datascience/artifacts"

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
# DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════

def load_data():
    """Load Gold feature store — local block volume preferred for speed."""
    import pyarrow.parquet as pq

    columns_to_load = SELECTED_FEATURES + [TARGET, "SAFRA", "NUM_CPF"]
    t0 = time.time()

    if os.path.exists(LOCAL_DATA_PATH):
        print(f"[DATA] Reading from local block volume: {LOCAL_DATA_PATH}")
        table = pq.read_table(LOCAL_DATA_PATH, columns=columns_to_load)
        df = table.to_pandas(self_destruct=True)
    else:
        print(f"[DATA] Reading from Object Storage: {GOLD_PATH}")
        df = pd.read_parquet(GOLD_PATH, columns=columns_to_load)

    elapsed = time.time() - t0
    print(f"[DATA] Loaded: {len(df):,} rows, {df.shape[1]} columns in {elapsed:.1f}s")
    print(f"[DATA] SAFRAs: {sorted(df['SAFRA'].unique())}")
    print(f"[DATA] FPD rate: {df[TARGET].mean():.4f} ({df[TARGET].sum():,} defaults)")

    # Validations
    assert len(SELECTED_FEATURES) == 59, f"Expected 59 features, got {len(SELECTED_FEATURES)}"
    # FPD may have NaN for OOT SAFRAs where outcome not yet observed
    non_null_fpd = df[TARGET].dropna()
    assert non_null_fpd.isin([0, 1, 0.0, 1.0]).all(), "FPD must be binary (0/1)"
    print(f"[DATA] FPD null: {df[TARGET].isna().sum():,} | non-null: {len(non_null_fpd):,}")

    return df

# ═══════════════════════════════════════════════════════════════════════════
# TEMPORAL SPLIT
# ═══════════════════════════════════════════════════════════════════════════

def temporal_split(df):
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

    X_train = df_train[SELECTED_FEATURES]
    y_train = df_train[TARGET].astype(int)
    X_oos = df_oos[SELECTED_FEATURES]
    y_oos = df_oos[TARGET].astype(int)
    X_oot = df_oot[SELECTED_FEATURES]
    y_oot = df_oot[TARGET].astype(int)

    return X_train, y_train, X_oos, y_oos, X_oot, y_oot

# ═══════════════════════════════════════════════════════════════════════════
# PREPROCESSING PIPELINES (exact Fabric v6 replication)
# ═══════════════════════════════════════════════════════════════════════════

def build_lr_pipeline():
    """LR L1 Scorecard pipeline — matches Fabric ColumnTransformer exactly."""
    preprocessor = ColumnTransformer(transformers=[
        ("num", Pipeline(steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]), NUM_FEATURES),
        ("cat", Pipeline(steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", CountEncoder(
                combine_min_nan_groups=True,
                normalize=True,
                handle_missing=0,
                handle_unknown=0,
            )),
        ]), CAT_FEATURES),
    ])

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

def build_lgbm_pipeline():
    """LightGBM GBDT pipeline — matches Fabric ColumnTransformer exactly."""
    preprocessor = ColumnTransformer(transformers=[
        ("num", Pipeline(steps=[
            ("imputer", SimpleImputer(strategy="median")),
        ]), NUM_FEATURES),
        ("cat", Pipeline(steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", CountEncoder(
                combine_min_nan_groups=True,
                normalize=True,
                handle_missing=0,
                handle_unknown=0,
            )),
        ]), CAT_FEATURES),
    ])

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
    """Full training pipeline: load → split → train → evaluate → compare."""
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 1. Load data
    print("=" * 70)
    print("PHASE 5 — MODEL TRAINING (OCI Data Science)")
    print(f"Run ID: {run_id} | OCPUs: {NCPUS}")
    print("=" * 70)

    df = load_data()

    # 2. Temporal split
    X_train, y_train, X_oos, y_oos, X_oot, y_oot = temporal_split(df)
    del df  # Free memory

    # 3. Train LR L1 Scorecard
    print("\n" + "-" * 70)
    print("MODEL 1: LR L1 Scorecard")
    print("-" * 70)
    t0 = time.time()

    lr_pipeline = build_lr_pipeline()
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

    lgbm_pipeline = build_lgbm_pipeline()
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
        "n_features": 59,
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
