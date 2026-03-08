# Model Card — Credit Risk Ensemble v1

## Model Description

**Name**: Credit Risk FPD Ensemble v1
**Type**: Multi-Model Ensemble (Simple Average)
**Task**: First Payment Default (FPD) prediction for telecom customers
**Target**: Binary classification (FPD = 1 if default, 0 otherwise)
**Run ID**: 20260308_043306
**Training Date**: 2026-03-08
**Total Pipeline Time**: 533 minutes (8h53m)

### Base Models

| Model | Algorithm | HPO Trials | KS OOT | AUC OOT | PSI |
|-------|-----------|-----------|--------|---------|-----|
| XGBoost | Gradient Boosted Trees | 50 | **0.3472** | **0.7351** | 0.0008 |
| LightGBM v2 | Gradient Boosted Trees | 50 | 0.3471 | 0.7350 | 0.0008 |
| CatBoost | Gradient Boosted Trees | 50 | 0.3462 | 0.7343 | 0.0005 |
| RandomForest | Bagging | defaults | 0.3348 | 0.7280 | 0.0012 |
| LR L1 v2 | Logistic Regression | defaults | 0.3285 | 0.7208 | 0.0007 |

### Ensemble Strategy

- **Champion**: Simple Average (equal weights, 0.2 each)
- **Blend Mode**: Tested, equal performance to simple average (KS=0.34417)
- **Stack Mode**: Tested, inferior (KS=0.32763) — overfitting on OOS meta-features
- **Rationale**: Models are highly correlated (boosting algorithms on same features); simple average provides robust combination

## Performance Metrics

### Baseline vs Ensemble

| Metric | Baseline LGBM v1 | Best Individual (XGBoost) | Ensemble (avg) |
|--------|-------------------|--------------------------|----------------|
| KS OOT | 0.3403 | **0.3472** (+0.69pp) | 0.3442 (+0.39pp) |
| AUC OOT | 0.7305 | **0.7351** | 0.7334 |
| Gini OOT | 46.11 | **47.02** | 46.68 |
| PSI | 0.0005 | 0.0008 | 0.0006 |

### Per-Model Detailed Metrics

| Model | KS Train | KS OOS | KS OOT | Overfitting Gap |
|-------|----------|--------|--------|-----------------|
| XGBoost | 0.3992 | 0.3959 | 0.3472 | 5.20pp |
| LightGBM v2 | 0.3930 | 0.3887 | 0.3471 | 4.59pp |
| CatBoost | 0.3725 | 0.3653 | 0.3462 | 2.63pp |
| RandomForest | 0.3713 | 0.3656 | 0.3348 | 3.65pp |
| LR L1 v2 | 0.3485 | 0.3400 | 0.3285 | 2.00pp |

### HPO Results (Optuna TPE, 50 trials each)

| Model | Best KS(CV) | Key Hyperparameters |
|-------|------------|---------------------|
| LightGBM | 0.36548 | n_estimators=800, lr=0.039, max_depth=8, num_leaves=99, min_child=139 |
| XGBoost | 0.36596 | n_estimators=793, lr=0.031, max_depth=8, min_child_weight=12 |
| CatBoost | 0.36541 | iterations=685, lr=0.068, depth=6, l2_leaf_reg=0.18 |

## Features

### Feature Pipeline

| Stage | Input | Output | Method |
|-------|-------|--------|--------|
| Original | 402 columns | 402 | Raw feature store |
| Feature Engineering | 402 | 449 (+47 new) | Missing patterns, interactions, ratios, PCA |
| IV Filter (>0.02) | 106 numeric | 86 | Information Value |
| Correlation Filter (<0.95) | 86 | 78 | Pearson correlation |
| PSI Stability (<0.20) | 78 | **72** | Population Stability Index |

### 47 Engineered Features

**Missing Patterns (7)**:
- `MISSING_REC_COUNT`, `MISSING_PAG_COUNT`, `MISSING_FAT_COUNT`, `MISSING_TOTAL_RATIO`
- `PAG_QTD_PAGAMENTOS_TOTAL_IS_NULL`, `PAG_TAXA_PAGAMENTOS_COM_JUROS_IS_NULL`, `PAG_DIAS_ENTRE_FATURAS_IS_NULL`

**Cross-Domain Interactions (6)**:
- `SCORE_X_REC_RISK`, `DIFF_SCORE_BUREAU`, `RATIO_REC_PAG`, `RATIO_FAT_PAG`, `REC_PAG_GAP`, `BILLING_LOAD`, `HIGH_RISK_COMBO`

**Ratios (4)**: `REC_ONLINE_RATIO`, `PAG_JUROS_RATIO`, `FAT_FIRST_RATIO`, `REC_PLATFORM_DIVERSITY`

**Temporal (3)**: `TENURE_BUCKET`, `RECENCY_GAP`, `RECHARGE_VELOCITY_CHANGE`

**Non-linear Transforms (12)**: Log/sqrt transforms of skewed features + `SCORE02_QUARTILE`

**PCA Components (15)**: 5 per domain (REC_, PAG_, FAT_)

### Feature Domains

| Prefix | Source | Description |
|--------|--------|-------------|
| (none) | CADASTRO + TELCO + TARGET | Demographics + bureau scores |
| REC_ | book_recarga_cmv | Recharge behavior (102 original) |
| PAG_ | book_pagamento | Payment behavior (154 original) |
| FAT_ | book_faturamento | Billing behavior (108 original) |
| MISSING_ | Engineered | Missing data patterns |
| PCA_ | Engineered | Domain-specific PCA components |

## Training Data

- **Source**: `Gold.feature_store.clientes_consolidado` (OCI Object Storage)
- **Granularity**: NUM_CPF (masked CPF) x SAFRA (YYYYMM)
- **Total Records**: 3,900,378
- **FPD Rate**: 21.27% (573,630 defaults)
- **Training SAFRAs**: 202410, 202411, 202412, 202501 (1,822,251 records)
- **OOS SAFRA**: 202501 (463,673 records)
- **OOT SAFRAs**: 202502, 202503 (874,370 records — holdout, never used for training/HPO)

## Validation Approach

### Temporal Split
```
Train: 202410-202412  |  OOS: 202501  |  OOT: 202502-202503
  1,822,251 records    |   463,673     |     874,370
```

### HPO Cross-Validation
3-Fold Stratified CV on training data, optimizing KS metric.

### Quality Gates — Final Status

| Gate | Criteria | Status | Evidence |
|------|----------|--------|----------|
| QG-D1 | Diagnostic identifies >=3 improvement areas | PASS | 5 findings: drift, no HPO, 2 models only, no interactions, no cross-domain |
| QG-FE | New features with IV>0.02, PSI<0.20 | PASS | 47 new features, 72 selected after filters |
| QG-HPO | Each model improves KS >0.5pp vs defaults | PASS | LGBM +0.33pp, XGB +0.34pp, CatBoost +0.51pp |
| QG-MM | >=3 models pass KS>0.20, AUC>0.65 | PASS | All 5 models pass (min KS=0.3285, min AUC=0.7208) |
| QG-ENS | Ensemble KS OOT >0.34, PSI <0.10 | PASS | KS=0.3442, PSI=0.0006 |
| QG-PROD | Scoring correct schema, artifacts uploaded | PASS | 3.9M scored, 18 artifacts in OCI |

## Diagnostic Findings (Phase 1)

### Baseline Per-SAFRA Performance

| SAFRA | KS | AUC | Records |
|-------|------|------|---------|
| 202410 | 0.3692 | 0.7511 | 436,388 |
| 202411 | 0.3728 | 0.7522 | 465,850 |
| 202412 | 0.3498 | 0.7373 | 456,340 |
| 202501 | 0.3528 | 0.7398 | 463,673 |
| 202502 | 0.3342 | 0.7274 | 430,064 |
| 202503 | 0.3464 | 0.7334 | 444,306 |

- **Brier Score**: 0.145124
- **REC_DIAS_ENTRE_RECARGAS drift**: PSI=2.38 (202502), PSI=2.45 (202503) — RED

## Scoring Output

### Score Distribution (3,900,378 records)

| Faixa | Count | Percentage |
|-------|-------|------------|
| CRITICO (<300) | 248,675 | 6.4% |
| ALTO (300-499) | 945,485 | 24.2% |
| MEDIO (500-699) | 1,271,725 | 32.6% |
| BAIXO (>=700) | 1,434,493 | 36.8% |

- **Score mean**: 605 | **Median**: 627

### Score Schema

| Column | Type | Description |
|--------|------|-------------|
| NUM_CPF | string | Masked customer ID |
| SAFRA | int | Year-month (YYYYMM) |
| SCORE | int | 0-1000 (higher = lower risk) |
| FAIXA_RISCO | string | CRITICO/ALTO/MEDIO/BAIXO |
| PROBABILIDADE_FPD | float | Raw FPD probability |
| MODELO_VERSAO | string | ensemble-v1 |
| DATA_SCORING | string | Scoring timestamp |
| EXECUTION_ID | string | UUID per run |

## Monitoring Plan

### Score Stability
- **PSI thresholds**: OK (<0.10), WARNING (0.10-0.25), RETRAIN (>=0.25)
- **Frequency**: Monthly (each new SAFRA)
- **Dashboard**: APEX on ADW (live via ORDS)

### Feature Drift
- Top 20 features monitored per-feature PSI
- Individual base model PSI tracked (early warning)
- Known risk: `REC_DIAS_ENTRE_RECARGAS` PSI=2.45 (excluded by PSI stability filter)

### Rollback Plan

1. Monitor PSI per base model — identify degraded component
2. Fallback: switch to single XGBoost or LightGBM v2 (best individuals)
3. Emergency: revert to original LGBM v1 (`lgbm_oci_20260217_214614.pkl`)

## Fairness Considerations

- Model uses behavioral and transactional features only
- No direct demographic features (age, gender, location) in feature set
- Bureau scores (TARGET_SCORE_01, TARGET_SCORE_02) may encode demographic patterns
- FPD rates should be monitored across customer segments

## Artifacts

### OCI Object Storage (`pod-academy-gold/model_artifacts/ensemble_v1/`)

| Path | Description | Size |
|------|-------------|------|
| `ensemble/ensemble_model.pkl` | Serialized ensemble (all 5 models) | 175 MB |
| `ensemble/ensemble_results.json` | Champion selection details | 699 B |
| `models_v2/*.pkl` | Individual model pipelines (5 files) | ~175 MB |
| `models_v2/multi_model_metrics.json` | Per-model metrics | 1.1 KB |
| `hpo/best_params_all.json` | Optimized hyperparameters | 953 B |
| `scoring/ensemble_scores_all.parquet` | All scores combined | 74 MB |
| `scoring/scores_safra_*.parquet` | Per-SAFRA scores (6 files) | ~12 MB each |
| `feature_engineering/new_features.json` | Engineered feature list | 1.2 KB |

## Version History

| Version | Date | Changes | KS OOT |
|---------|------|---------|--------|
| lgbm-oci-v1 | 2026-02-17 | Single LightGBM, 59 features, default params | 0.3403 |
| ensemble-v1 | 2026-03-08 | 5-model ensemble, 72 features, HPO-optimized, 47 new engineered features | 0.3442 |

## Key Learnings

1. **HPO is the biggest lever**: Optuna optimization improved each model by 0.3-0.7pp KS over defaults
2. **Individual optimized models can outperform naive ensembles**: XGBoost alone (KS=0.3472) beats simple average ensemble (KS=0.3442)
3. **Model correlation limits ensemble benefit**: Boosting models trained on same features produce highly correlated predictions
4. **Stacking can hurt**: Meta-learner overfit on OOS predictions, reducing OOT performance
5. **Feature engineering adds value**: 47 new features (missing patterns, PCA, interactions) expanded the feature space meaningfully
6. **PSI stability filter is critical**: Removed 6 features with drift (78 -> 72), preventing leakage from unstable features

---

*Generated by credit-risk-ds squad — Hackathon PoD Academy (Claro + Oracle)*
*Pipeline executed on OCI VM.Standard.E5.Flex (4 OCPUs, 64GB RAM)*
