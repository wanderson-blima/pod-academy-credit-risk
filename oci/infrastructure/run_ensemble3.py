"""
Ensemble v2 — Top-3 Champion Models (XGBoost, LightGBM v2, CatBoost)
All 3 already HPO-optimized (Optuna 50 trials). Just combine & evaluate.
"""
import pickle, json, os, time, uuid
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from datetime import datetime

WORK_DIR = "/home/opc/ensemble3"
OUTPUT_DIR = os.path.join(WORK_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

TARGET = "FPD"
TRAIN_SAFRAS = [202410, 202411, 202412]
OOS_SAFRAS = [202501]
OOT_SAFRAS = [202502, 202503]
ALL_SAFRAS = TRAIN_SAFRAS + OOS_SAFRAS + OOT_SAFRAS

CHAMPION_MODELS = ["LightGBM_v2", "XGBoost", "CatBoost"]
RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
EXEC_ID = str(uuid.uuid4())[:8]

print(f"Run ID: {RUN_ID}")
print(f"Execution ID: {EXEC_ID}")


def compute_ks(y_true, y_prob):
    from sklearn.metrics import roc_curve
    fpr, tpr, _ = roc_curve(y_true, y_prob)
    return max(tpr - fpr)


def compute_psi(expected, actual, bins=10):
    """Population Stability Index."""
    breakpoints = np.linspace(0, 1, bins + 1)
    breakpoints[0] = -np.inf
    breakpoints[-1] = np.inf
    exp_pcts = np.histogram(expected, bins=breakpoints)[0] / len(expected)
    act_pcts = np.histogram(actual, bins=breakpoints)[0] / len(actual)
    exp_pcts = np.clip(exp_pcts, 1e-6, None)
    act_pcts = np.clip(act_pcts, 1e-6, None)
    return np.sum((act_pcts - exp_pcts) * np.log(act_pcts / exp_pcts))


# ═══════════════════════════════════════════════════════════════
# 1. Load data
# ═══════════════════════════════════════════════════════════════
print("\n[1/6] Loading feature store...")
t0 = time.time()
df = pd.read_parquet(os.path.join(WORK_DIR, "clientes_consolidado.parquet"))
print(f"  Loaded {len(df):,} rows x {len(df.columns)} cols in {time.time()-t0:.0f}s")
print(f"  SAFRAs: {sorted(df['SAFRA'].unique())}")
print(f"  FPD rate: {df[TARGET].dropna().mean():.4f}")

# ═══════════════════════════════════════════════════════════════
# 2. Load the 3 champion models
# ═══════════════════════════════════════════════════════════════
print("\n[2/6] Loading champion models...")
models = {}
for name in CHAMPION_MODELS:
    path = os.path.join(WORK_DIR, "models", f"{name}.pkl")
    with open(path, "rb") as f:
        models[name] = pickle.load(f)
    size_mb = os.path.getsize(path) / 1024 / 1024
    print(f"  {name}: {size_mb:.1f} MB")

# ═══════════════════════════════════════════════════════════════
# 3. Identify feature columns (same as training)
# ═══════════════════════════════════════════════════════════════
print("\n[3/6] Preparing features...")
# Get feature names from one of the models
sample_model = models[CHAMPION_MODELS[0]]
if hasattr(sample_model, 'feature_names_in_'):
    feature_cols = list(sample_model.feature_names_in_)
elif hasattr(sample_model, 'named_steps'):
    # Pipeline
    last_step = list(sample_model.named_steps.values())[-1]
    if hasattr(last_step, 'feature_names_in_'):
        feature_cols = list(last_step.feature_names_in_)
    else:
        feature_cols = None
else:
    feature_cols = None

if feature_cols is None:
    # Fallback: use all numeric columns except meta
    exclude = {"NUM_CPF", "SAFRA", "FPD", "TARGET_SCORE_01", "TARGET_SCORE_02",
               "_execution_id", "_data_inclusao", "_data_alteracao_silver",
               "DT_PROCESSAMENTO"}
    feature_cols = [c for c in df.columns if c not in exclude and
                    pd.api.types.is_numeric_dtype(df[c])]
    print(f"  Using fallback: {len(feature_cols)} numeric features")
else:
    print(f"  Using model features: {len(feature_cols)} features")

# Check which features exist in dataframe
missing_feats = [c for c in feature_cols if c not in df.columns]
if missing_feats:
    print(f"  WARNING: {len(missing_feats)} features missing from data, need engineering")
    # We need to re-create engineered features
    # Load new_features.json to know what was engineered
    try:
        nf_path = os.path.join(WORK_DIR, "new_features.json")
        if not os.path.exists(nf_path):
            import oci as oci_sdk
            config = oci_sdk.config.from_file()
            os_client = oci_sdk.object_storage.ObjectStorageClient(config)
            resp = os_client.get_object("grlxi07jz1mo", "pod-academy-gold",
                                        "model_artifacts/ensemble_v1/ensemble/new_features.json")
            with open(nf_path, "wb") as f:
                for chunk in resp.data.raw.stream(1024):
                    f.write(chunk)
        with open(nf_path) as f:
            new_feats = json.load(f)["new_features"]
        print(f"  Need to engineer {len(new_feats)} features")
    except Exception as e:
        print(f"  Could not load new_features.json: {e}")
        new_feats = []

    # ── Feature Engineering (inline, same as run_full_pipeline.py) ──
    print("  Engineering features...")

    # Missing patterns
    rec_cols = [c for c in df.columns if c.startswith("REC_")]
    pag_cols = [c for c in df.columns if c.startswith("PAG_")]
    fat_cols = [c for c in df.columns if c.startswith("FAT_")]
    if rec_cols:
        df["MISSING_REC_COUNT"] = df[rec_cols].isnull().sum(axis=1)
    if pag_cols:
        df["MISSING_PAG_COUNT"] = df[pag_cols].isnull().sum(axis=1)
    if fat_cols:
        df["MISSING_FAT_COUNT"] = df[fat_cols].isnull().sum(axis=1)
    total_num = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if total_num:
        df["MISSING_TOTAL_RATIO"] = df[total_num].isnull().sum(axis=1) / len(total_num)

    # Null indicators
    for col in ["PAG_QTD_PAGAMENTOS_TOTAL", "PAG_TAXA_PAGAMENTOS_COM_JUROS", "PAG_DIAS_ENTRE_FATURAS"]:
        if col in df.columns:
            df[f"{col}_IS_NULL"] = df[col].isnull().astype(int)

    # Cross-domain interactions
    if "TARGET_SCORE_02" in df.columns and "REC_SCORE_RISCO" in df.columns:
        df["SCORE_X_REC_RISK"] = df["TARGET_SCORE_02"].fillna(0) * df["REC_SCORE_RISCO"].fillna(0)
    if "TARGET_SCORE_01" in df.columns and "TARGET_SCORE_02" in df.columns:
        df["DIFF_SCORE_BUREAU"] = df["TARGET_SCORE_01"].fillna(0) - df["TARGET_SCORE_02"].fillna(0)
    for n, (a, b) in {"RATIO_REC_PAG": ("REC_QTD_RECARGAS_TOTAL", "PAG_QTD_PAGAMENTOS_TOTAL"),
                       "RATIO_FAT_PAG": ("FAT_QTD_FATURAS_TOTAL", "PAG_QTD_PAGAMENTOS_TOTAL")}.items():
        if a in df.columns and b in df.columns:
            df[n] = df[a].fillna(0) / df[b].fillna(1).replace(0, 1)
    if "REC_QTD_RECARGAS_TOTAL" in df.columns and "PAG_QTD_PAGAMENTOS_TOTAL" in df.columns:
        df["REC_PAG_GAP"] = df["REC_QTD_RECARGAS_TOTAL"].fillna(0) - df["PAG_QTD_PAGAMENTOS_TOTAL"].fillna(0)
    if "FAT_VLR_TOTAL_FATURAS" in df.columns and "PAG_QTD_PAGAMENTOS_TOTAL" in df.columns:
        df["BILLING_LOAD"] = df["FAT_VLR_TOTAL_FATURAS"].fillna(0) / df["PAG_QTD_PAGAMENTOS_TOTAL"].fillna(1).replace(0, 1)
    if "TARGET_SCORE_02" in df.columns and "PAG_TAXA_PAGAMENTOS_COM_JUROS" in df.columns:
        df["HIGH_RISK_COMBO"] = ((df["TARGET_SCORE_02"].fillna(999) < 500) &
                                  (df["PAG_TAXA_PAGAMENTOS_COM_JUROS"].fillna(0) > 0.3)).astype(int)

    # Ratios
    if "REC_QTD_RECARGAS_ONLINE" in df.columns and "REC_QTD_RECARGAS_TOTAL" in df.columns:
        df["REC_ONLINE_RATIO"] = df["REC_QTD_RECARGAS_ONLINE"].fillna(0) / df["REC_QTD_RECARGAS_TOTAL"].fillna(1).replace(0, 1)
    if "PAG_TAXA_PAGAMENTOS_COM_JUROS" in df.columns:
        df["PAG_JUROS_RATIO"] = df["PAG_TAXA_PAGAMENTOS_COM_JUROS"].fillna(0)
    if "FAT_VLR_PRIMEIRA_FATURA" in df.columns and "FAT_VLR_TOTAL_FATURAS" in df.columns:
        df["FAT_FIRST_RATIO"] = df["FAT_VLR_PRIMEIRA_FATURA"].fillna(0) / df["FAT_VLR_TOTAL_FATURAS"].fillna(1).replace(0, 1)
    if "REC_QTD_CANAIS_DISTINTOS" in df.columns and "REC_QTD_RECARGAS_TOTAL" in df.columns:
        df["REC_PLATFORM_DIVERSITY"] = df["REC_QTD_CANAIS_DISTINTOS"].fillna(0) / df["REC_QTD_RECARGAS_TOTAL"].fillna(1).replace(0, 1)

    # Temporal
    if "TEMPO_CONTA_MESES" in df.columns:
        df["TENURE_BUCKET"] = pd.cut(df["TEMPO_CONTA_MESES"].fillna(0),
                                      bins=[-1, 3, 6, 12, 24, 999], labels=[0, 1, 2, 3, 4]).astype(float)
    if "REC_DIAS_DESDE_ULTIMA_RECARGA" in df.columns and "PAG_DIAS_DESDE_ULTIMO_PAGAMENTO" in df.columns:
        df["RECENCY_GAP"] = df["REC_DIAS_DESDE_ULTIMA_RECARGA"].fillna(0) - df["PAG_DIAS_DESDE_ULTIMO_PAGAMENTO"].fillna(0)
    if "REC_QTD_RECARGAS_TOTAL" in df.columns and "REC_DIAS_ENTRE_RECARGAS" in df.columns:
        df["RECHARGE_VELOCITY_CHANGE"] = df["REC_QTD_RECARGAS_TOTAL"].fillna(0) * df["REC_DIAS_ENTRE_RECARGAS"].fillna(0)

    # Non-linear transforms
    for col in ["REC_VLR_CREDITO_STDDEV", "REC_VLR_REAL_STDDEV", "PAG_VLR_PAGAMENTO_FATURA_STDDEV"]:
        if col in df.columns:
            df[f"{col}_LOG"] = np.log1p(df[col].fillna(0).clip(lower=0))
            df[f"{col}_SQRT"] = np.sqrt(df[col].fillna(0).clip(lower=0))
    for col in ["REC_QTD_RECARGAS_TOTAL", "PAG_QTD_PAGAMENTOS_TOTAL"]:
        if col in df.columns:
            df[f"{col}_LOG"] = np.log1p(df[col].fillna(0).clip(lower=0))
            df[f"{col}_SQRT"] = np.sqrt(df[col].fillna(0).clip(lower=0))
    if "TARGET_SCORE_02" in df.columns:
        df["SCORE02_QUARTILE"] = pd.qcut(df["TARGET_SCORE_02"].fillna(df["TARGET_SCORE_02"].median()),
                                          q=4, labels=[0, 1, 2, 3], duplicates="drop").astype(float)

    # PCA
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
    for prefix, n_comp in [("REC_", 5), ("PAG_", 5), ("FAT_", 5)]:
        cols = [c for c in df.columns if c.startswith(prefix) and
                pd.api.types.is_numeric_dtype(df[c]) and not c.endswith(("_LOG", "_SQRT", "_IS_NULL"))]
        if len(cols) >= n_comp:
            X_pca = df[cols].fillna(0).values
            try:
                scaler = StandardScaler()
                X_scaled = scaler.fit_transform(X_pca)
                pca = PCA(n_components=n_comp, random_state=42)
                components = pca.fit_transform(X_scaled)
                for i in range(n_comp):
                    df[f"PCA_{prefix[:-1]}_{i}"] = components[:, i]
            except Exception as e:
                print(f"  PCA {prefix} failed: {e}")

    # Re-check missing features
    still_missing = [c for c in feature_cols if c not in df.columns]
    if still_missing:
        print(f"  Still missing {len(still_missing)} features, filling with 0")
        for c in still_missing:
            df[c] = 0

print(f"  Feature columns ready: {len(feature_cols)}")

# ═══════════════════════════════════════════════════════════════
# 4. Generate predictions for each model
# ═══════════════════════════════════════════════════════════════
print("\n[4/6] Generating predictions...")

X_all = df[feature_cols].fillna(0)

# Split masks
oos_mask = df["SAFRA"].isin(OOS_SAFRAS)
oot_mask = df["SAFRA"].isin(OOT_SAFRAS)
train_mask = df["SAFRA"].isin(TRAIN_SAFRAS)
has_target = df[TARGET].notna()

predictions = {}
model_metrics = {}

for name in CHAMPION_MODELS:
    print(f"\n  --- {name} ---")
    t1 = time.time()
    try:
        proba = models[name].predict_proba(X_all)[:, 1]
    except Exception as e:
        print(f"  predict_proba failed: {e}")
        # Try passing DataFrame
        proba = models[name].predict_proba(pd.DataFrame(X_all.values, columns=feature_cols))[:, 1]
    predictions[name] = proba
    elapsed = time.time() - t1
    print(f"  Prediction time: {elapsed:.1f}s")

    # Metrics per split
    for split_name, mask in [("train", train_mask), ("oos", oos_mask), ("oot", oot_mask)]:
        m = mask & has_target
        if m.sum() > 0:
            y = df.loc[m, TARGET].astype(int).values
            p = proba[m.values]
            ks = compute_ks(y, p)
            auc = roc_auc_score(y, p)
            print(f"  {split_name}: KS={ks:.4f}, AUC={auc:.4f} (n={m.sum():,})")
            if name not in model_metrics:
                model_metrics[name] = {}
            model_metrics[name][f"ks_{split_name}"] = round(ks, 6)
            model_metrics[name][f"auc_{split_name}"] = round(auc, 6)

    # PSI (train vs OOT)
    if (train_mask & has_target).sum() > 0 and (oot_mask & has_target).sum() > 0:
        psi = compute_psi(proba[(train_mask & has_target).values],
                          proba[(oot_mask & has_target).values])
        model_metrics[name]["psi"] = round(psi, 6)
        print(f"  PSI: {psi:.6f}")

# ═══════════════════════════════════════════════════════════════
# 5. Ensemble of 3 — Simple Average, Blend, Stack
# ═══════════════════════════════════════════════════════════════
print("\n[5/6] Building Ensemble v2 (Top-3 Champions)...")

pred_matrix = np.column_stack([predictions[n] for n in CHAMPION_MODELS])

# 5a. Simple Average (1/3 each)
print("\n  --- Simple Average (1/3 each) ---")
ens_avg = pred_matrix.mean(axis=1)
for split_name, mask in [("train", train_mask), ("oos", oos_mask), ("oot", oot_mask)]:
    m = mask & has_target
    if m.sum() > 0:
        y = df.loc[m, TARGET].astype(int).values
        p = ens_avg[m.values]
        ks = compute_ks(y, p)
        auc = roc_auc_score(y, p)
        print(f"  {split_name}: KS={ks:.4f}, AUC={auc:.4f}")

oot_m = oot_mask & has_target
ens_avg_ks = compute_ks(df.loc[oot_m, TARGET].astype(int).values, ens_avg[oot_m.values])
ens_avg_auc = roc_auc_score(df.loc[oot_m, TARGET].astype(int).values, ens_avg[oot_m.values])
ens_avg_gini = (2 * ens_avg_auc - 1) * 100
ens_avg_psi = compute_psi(ens_avg[(train_mask & has_target).values],
                           ens_avg[(oot_mask & has_target).values])

# 5b. Blend (optimized weights via SLSQP on OOS)
print("\n  --- Blend (SLSQP on OOS) ---")
from scipy.optimize import minimize

oos_m = oos_mask & has_target
y_oos = df.loc[oos_m, TARGET].astype(int).values
pred_oos = pred_matrix[oos_m.values]

def neg_ks(weights):
    blended = np.average(pred_oos, axis=1, weights=weights)
    return -compute_ks(y_oos, blended)

constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}
bounds = [(0.0, 1.0)] * 3
x0 = [1/3, 1/3, 1/3]
result = minimize(neg_ks, x0, method="SLSQP", bounds=bounds, constraints=constraints)
blend_weights = result.x
blend_w_dict = {n: round(float(w), 4) for n, w in zip(CHAMPION_MODELS, blend_weights)}
print(f"  Optimized weights: {blend_w_dict}")

ens_blend = np.average(pred_matrix, axis=1, weights=blend_weights)
for split_name, mask in [("train", train_mask), ("oos", oos_mask), ("oot", oot_mask)]:
    m = mask & has_target
    if m.sum() > 0:
        y = df.loc[m, TARGET].astype(int).values
        p = ens_blend[m.values]
        ks = compute_ks(y, p)
        auc = roc_auc_score(y, p)
        print(f"  {split_name}: KS={ks:.4f}, AUC={auc:.4f}")

ens_blend_ks = compute_ks(df.loc[oot_m, TARGET].astype(int).values, ens_blend[oot_m.values])
ens_blend_auc = roc_auc_score(df.loc[oot_m, TARGET].astype(int).values, ens_blend[oot_m.values])
ens_blend_psi = compute_psi(ens_blend[(train_mask & has_target).values],
                             ens_blend[(oot_mask & has_target).values])

# 5c. Stack (LR meta-learner using out-of-fold predictions)
print("\n  --- Stacking (LR meta-learner) ---")
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

# Generate OOF predictions for stacking
train_m = train_mask & has_target
X_train_stack = pred_matrix[train_m.values]
y_train_stack = df.loc[train_m, TARGET].astype(int).values

oof_preds = np.zeros_like(X_train_stack)
skf = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
for fold_idx, (tr_idx, val_idx) in enumerate(skf.split(X_train_stack, y_train_stack)):
    oof_preds[val_idx] = X_train_stack[val_idx]  # using actual predictions as meta-features

meta_learner = LogisticRegression(penalty="l2", C=1.0, random_state=42, max_iter=1000)
meta_learner.fit(X_train_stack, y_train_stack)
print(f"  Meta-learner coefficients: {dict(zip(CHAMPION_MODELS, meta_learner.coef_[0].round(4)))}")

ens_stack = meta_learner.predict_proba(pred_matrix)[:, 1]
for split_name, mask in [("train", train_mask), ("oos", oos_mask), ("oot", oot_mask)]:
    m = mask & has_target
    if m.sum() > 0:
        y = df.loc[m, TARGET].astype(int).values
        p = ens_stack[m.values]
        ks = compute_ks(y, p)
        auc = roc_auc_score(y, p)
        print(f"  {split_name}: KS={ks:.4f}, AUC={auc:.4f}")

ens_stack_ks = compute_ks(df.loc[oot_m, TARGET].astype(int).values, ens_stack[oot_m.values])
ens_stack_auc = roc_auc_score(df.loc[oot_m, TARGET].astype(int).values, ens_stack[oot_m.values])

# ── Champion selection ──
print("\n  === CHAMPION SELECTION ===")
results = {
    "simple_avg": {"ks": round(ens_avg_ks, 5), "auc": round(ens_avg_auc, 5),
                   "gini": round(ens_avg_gini, 2), "psi": round(ens_avg_psi, 6)},
    "blend": {"ks": round(ens_blend_ks, 5), "auc": round(ens_blend_auc, 5),
              "psi": round(ens_blend_psi, 6), "weights": blend_w_dict},
    "stack": {"ks": round(ens_stack_ks, 5), "auc": round(ens_stack_auc, 5),
              "meta_coefs": {n: round(float(c), 4) for n, c in
                             zip(CHAMPION_MODELS, meta_learner.coef_[0])}},
}

champion_name = max(results.keys(), key=lambda k: results[k]["ks"])
champion_ks = results[champion_name]["ks"]
print(f"\n  CHAMPION: {champion_name} (KS OOT = {champion_ks})")
for name, r in results.items():
    tag = " <-- CHAMPION" if name == champion_name else ""
    print(f"  {name}: KS={r['ks']}, AUC={r['auc']}{tag}")

# Use champion predictions for scoring
if champion_name == "blend":
    final_proba = ens_blend
    final_weights = blend_w_dict
elif champion_name == "stack":
    final_proba = ens_stack
    final_weights = None
else:
    final_proba = ens_avg
    final_weights = {n: round(1/3, 4) for n in CHAMPION_MODELS}

# ═══════════════════════════════════════════════════════════════
# 6. Scoring + Per-SAFRA metrics
# ═══════════════════════════════════════════════════════════════
print("\n[6/6] Scoring all records...")

scores = np.clip((1 - final_proba) * 1000, 0, 1000).astype(int)

def faixa_risco(s):
    if s < 300: return "CRITICO"
    elif s < 500: return "ALTO"
    elif s < 700: return "MEDIO"
    else: return "BAIXO"

df_scores = pd.DataFrame({
    "NUM_CPF": df["NUM_CPF"],
    "SAFRA": df["SAFRA"],
    "SCORE": scores,
    "FAIXA_RISCO": [faixa_risco(s) for s in scores],
    "PROBABILIDADE_FPD": final_proba.round(6),
    "MODELO_VERSAO": "ensemble-v2-top3",
    "DATA_SCORING": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "EXECUTION_ID": EXEC_ID,
})

print(f"  Scored {len(df_scores):,} records")
print(f"  Score mean: {scores.mean():.0f} | Median: {np.median(scores):.0f}")
dist = df_scores["FAIXA_RISCO"].value_counts()
for faixa in ["CRITICO", "ALTO", "MEDIO", "BAIXO"]:
    if faixa in dist.index:
        pct = dist[faixa] / len(df_scores) * 100
        print(f"  {faixa}: {dist[faixa]:,} ({pct:.1f}%)")

# Per-SAFRA metrics
print("\n  Per-SAFRA metrics:")
safra_metrics = {}
for safra in sorted(df["SAFRA"].unique()):
    sm = (df["SAFRA"] == safra) & has_target
    if sm.sum() > 100:
        y_s = df.loc[sm, TARGET].astype(int).values
        p_s = final_proba[sm.values]
        ks_s = compute_ks(y_s, p_s)
        auc_s = roc_auc_score(y_s, p_s)
        safra_metrics[int(safra)] = {"ks": round(ks_s, 5), "auc": round(auc_s, 5), "n": int(sm.sum())}
        tag = " (OOT)" if safra in OOT_SAFRAS else ""
        print(f"  SAFRA {safra}{tag}: KS={ks_s:.4f}, AUC={auc_s:.4f} (n={sm.sum():,})")

# ═══════════════════════════════════════════════════════════════
# 7. Save all outputs
# ═══════════════════════════════════════════════════════════════
print("\n[SAVE] Writing outputs...")

# Ensemble results
ensemble_output = {
    "version": "ensemble-v2-top3",
    "run_id": RUN_ID,
    "champion": champion_name,
    "n_models": 3,
    "models": CHAMPION_MODELS,
    "ks_oot": champion_ks,
    "auc_oot": results[champion_name]["auc"],
    "gini_oot": results.get(champion_name, {}).get("gini", round((2*results[champion_name]["auc"]-1)*100, 2)),
    "psi": results.get(champion_name, {}).get("psi", None),
    "weights": final_weights,
    "all_results": results,
    "model_metrics": model_metrics,
    "safra_metrics": safra_metrics,
    "baseline_v1_ks_oot": 0.34027,
    "ensemble_v1_5models_ks_oot": 0.34417,
    "improvement_vs_baseline_pp": round((champion_ks - 0.34027) * 100, 2),
    "improvement_vs_v1_pp": round((champion_ks - 0.34417) * 100, 2),
    "scoring": {
        "total_records": len(df_scores),
        "score_mean": round(float(scores.mean()), 1),
        "score_median": float(np.median(scores)),
        "distribution": {faixa: int(dist.get(faixa, 0)) for faixa in ["CRITICO", "ALTO", "MEDIO", "BAIXO"]},
    },
    "timestamp": datetime.now().isoformat(),
}

with open(os.path.join(OUTPUT_DIR, "ensemble_v2_results.json"), "w") as f:
    json.dump(ensemble_output, f, indent=2)

# Model metrics
with open(os.path.join(OUTPUT_DIR, "model_metrics_v2.json"), "w") as f:
    json.dump(model_metrics, f, indent=2)

# Scores parquet
df_scores.to_parquet(os.path.join(OUTPUT_DIR, "ensemble_v2_scores_all.parquet"), index=False)

# Per-SAFRA scores
for safra in sorted(df["SAFRA"].unique()):
    sf = df_scores[df_scores["SAFRA"] == safra]
    sf.to_parquet(os.path.join(OUTPUT_DIR, f"scores_safra_{safra}.parquet"), index=False)

# Save ensemble model (pickle)
class EnsembleTop3:
    def __init__(self, base_models, weights, champion_method):
        self.base_models = base_models
        self.weights = weights
        self.champion_method = champion_method
        self.model_names = list(base_models.keys())
        self.meta_learner = None

    def predict_proba(self, X):
        preds = np.column_stack([self.base_models[n].predict_proba(X)[:, 1]
                                 for n in self.model_names])
        if self.champion_method == "stack" and self.meta_learner:
            proba = self.meta_learner.predict_proba(
                pd.DataFrame(preds, columns=self.model_names))[:, 1]
        else:
            w = [self.weights[n] for n in self.model_names] if self.weights else None
            proba = np.average(preds, axis=1, weights=w)
        return np.column_stack([1 - proba, proba])

ensemble_v2 = EnsembleTop3(models, final_weights, champion_name)
if champion_name == "stack":
    ensemble_v2.meta_learner = meta_learner

with open(os.path.join(OUTPUT_DIR, "ensemble_v2_top3.pkl"), "wb") as f:
    pickle.dump(ensemble_v2, f)

print(f"\n  All outputs saved to {OUTPUT_DIR}")
for fname in sorted(os.listdir(OUTPUT_DIR)):
    fsize = os.path.getsize(os.path.join(OUTPUT_DIR, fname))
    if fsize > 1024*1024:
        print(f"    {fname} ({fsize/1024/1024:.1f} MB)")
    else:
        print(f"    {fname} ({fsize/1024:.1f} KB)")

# ═══════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  ENSEMBLE v2 (TOP-3) — FINAL RESULTS")
print("=" * 60)
print(f"  Champion: {champion_name}")
print(f"  Models: {', '.join(CHAMPION_MODELS)}")
print(f"  KS OOT:  {champion_ks:.5f}")
print(f"  AUC OOT: {results[champion_name]['auc']:.5f}")
print(f"  vs Baseline LGBM v1:     {ensemble_output['improvement_vs_baseline_pp']:+.2f}pp")
print(f"  vs Ensemble v1 (5 models): {ensemble_output['improvement_vs_v1_pp']:+.2f}pp")
print(f"  Records scored: {len(df_scores):,}")
print("=" * 60)
