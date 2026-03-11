# OCI Credit Risk Platform — Projeto Final

**Hackathon PoD Academy (Claro + Oracle)**
Credit Risk Modeling — First Payment Default (FPD) Prediction

## Sumario

Plataforma completa de modelagem de risco de credito em OCI, com pipeline Medallion (Bronze/Silver/Gold), treinamento de 5 modelos com hiperparametros otimizados (HPO), ensemble champion, batch scoring, analise de confusion matrix e monitoramento pos-deploy.

---

## Impacto Financeiro

| Indicador | Valor |
|-----------|-------|
| **Economia anual estimada** | **R$ 22,9M** (cutoff 700) |
| Reducao de FPD | 21,3% → 6,9% (-68%) |
| Base scorada | 3.900.378 clientes |
| Ensemble champion | Top-3 Average (KS=0.3501, AUC=0.7368, Gini=47.35%) |
| Precision (cutoff 700) | 93,13% |
| Specificity (cutoff 700) | 88,99% |
| ROI vs custo OCI | > 11.000x (infra ~R$ 168/mes) |

> O modelo reduz a inadimplencia em 68%, evitando ~503 mil defaults em 6 SAFRAs. Detalhes completos na [Analise de Valor Financeiro](docs/model/business-value-analysis.md).

---

## Arquitetura

```
 CSV/Excel/Parquet (Claro)
        |
  [OCI Object Storage]
        |
  Bronze (staging/) ──> Silver (rawdata/) ──> Gold (feature_store/)
  19 tabelas Delta       19 tabelas limpas     3 books + consolidado
  163M rows              275K dupes removed     3.9M rows x 402 cols
        |
  [OCI E3.Flex VM (4 OCPUs / 64 GB) + Airflow]
        |
  Feature Selection (5-stage funnel)
  357 → 185 (IV) → 162 (L1) → 114 (Corr) → 110 (PSI) → 110 (anti-leakage)
        |
  Model Training (5 modelos HPO-otimizados)
  LR L1 v2 | LightGBM v2 | XGBoost | CatBoost | Random Forest
        |
  Ensemble (3 estrategias: Average, Blend SLSQP, Stacking LR)
  Champion selecionado por max KS OOT
        |
  Batch Scoring (3,900,378 clientes, 0-1000 scale)
  CRITICO | ALTO | MEDIO | BAIXO
        |
  Confusion Matrix Analysis (multi-threshold + por faixa)
  Precision 93.1% | Specificity 89.0% | Gain/Lift charts
        |
  Monitoring (PSI, feature drift, backtesting, agreement)
        |
  [ADW + APEX Dashboard] + [OCI Data Catalog]
```

---

## Avaliacao do Modelo

### Confusion Matrix (Cutoff 700)

|  | Predicted Positive (Bom) | Predicted Negative (Mau) |
|--|--------------------------|--------------------------|
| **Actual Positive (Bom)** | TP = 856.141 | FN = 1.266.850 |
| **Actual Negative (Mau)** | FP = 63.133 | TN = 510.497 |

| Metrica | Valor | Interpretacao |
|---------|-------|---------------|
| **Precision** | 93,13% | De cada 100 aprovados, 93 pagam |
| **Recall** | 40,33% | Captura 40% dos bons pagadores |
| **Specificity** | 88,99% | Rejeita 89% dos inadimplentes |
| **F1-Score** | 56,28% | Balanco precision/recall |
| **Accuracy** | 50,67% | — |

### Faixas de Risco

| Faixa | Score | Clientes | % Base | FPD Rate |
|-------|-------|----------|--------|----------|
| CRITICO | 0–299 | 206.535 | 7,7% | 59,2% |
| ALTO | 300–499 | 652.566 | 24,3% | 34,8% |
| MEDIO | 500–699 | 918.246 | 34,2% | 17,5% |
| BAIXO | 700–1000 | 919.274 | 34,1% | 6,9% |

### Gain & Lift

| Decil | % Inadimplentes Capturados | Lift |
|-------|---------------------------|------|
| Top 10% | 26,4% | 2,64x |
| Top 20% | 44,1% | 2,21x |
| Top 30% | 58,7% | 1,96x |

> Detalhes completos: [Confusion Matrix Analysis](docs/model/confusion-matrix-analysis.md) | [Swap Analysis](docs/model/swap-analysis.md)

---

## Estrutura do Projeto

```
oci-oracle-cloud/
├── README.md                          # Este arquivo
├── EXECUTION-GUIDE.md                 # Passo-a-passo oficial de execucao
├── scripts/                           # 10 scripts Python de producao
│   ├── train_credit_risk.py           # Treinamento 5 modelos (HPO aplicado)
│   ├── feature_selection.py           # Funnel 5 estagios (357 → 110)
│   ├── ensemble.py                    # 3 estrategias de ensemble
│   ├── batch_scoring.py               # Scoring batch champion (3.9M clientes)
│   ├── monitoring.py                  # PSI, drift, backtesting
│   ├── data_quality.py                # Validacao Bronze/Silver/Gold
│   ├── ensemble_comparison.py         # Top 3 vs All 5 — gera ensemble_comparison.json
│   ├── swap_analysis.py               # Swap-in/swap-out por cutoff de score
│   ├── confusion_matrix_analysis.py   # Confusion matrix multi-threshold + faixas
│   └── sync_oci_costs.py              # Sincronizacao de custos OCI → ADW
├── artifacts/                         # Artefatos do Run 20260311_015100
│   ├── README.md                      # Manifesto de artefatos
│   ├── hpo/best_params_all.json       # Hiperparametros otimizados
│   ├── models/                        # 6 modelos (.pkl): 5 individuais + champion ensemble
│   ├── metrics/                       # 9 arquivos (training, ensemble, CM, feature importance)
│   ├── plots/                         # 16 visualizacoes PNG
│   ├── scoring/scoring_summary.json   # Resultado do batch scoring
│   └── monitoring/monitoring_report.json
├── research/                          # Pesquisa e experimentacao (6 fases)
│   ├── README.md                      # Guia completo das 6 fases
│   ├── 01_diagnostic/                 # Analise exploratoria, correlacoes, estabilidade
│   ├── 02_feature_engineering/        # Interacoes, ratios, PCA, nao-lineares
│   ├── 03_hpo/                        # HPO com Optuna (LGBM, XGBoost, CatBoost)
│   ├── 04_models/                     # Multi-modelo, analise de diversidade
│   ├── 05_ensemble/                   # Blend, stack, selecao de ensemble
│   ├── 06_production/                 # Avaliacao final, scorecard, MODEL_CARD
│   ├── artifacts/                     # Artefatos intermediarios de pesquisa
│   └── run_full_pipeline.py           # Pipeline completo de pesquisa
├── infrastructure/
│   ├── dags/                          # 3 Airflow DAGs
│   │   ├── credit_risk_data_pipeline.py  # DAG Dados: Bronze → Silver → Gold
│   │   ├── credit_risk_ml_pipeline.py    # DAG ML: FS → Train → Ensemble → Score → Monitor
│   │   └── credit_risk_pipeline.py       # [DEPRECATED] DAG unificado (referencia)
│   ├── terraform/                     # IaC (8 modulos Terraform)
│   ├── orchestrator/                  # Docker Compose Airflow + scripts
│   ├── adw/                           # SQL setup para ADW
│   ├── apex/                          # Dashboard APEX
│   └── ops/                           # Scripts operacionais (start/stop/validate)
├── notebooks/                         # 12 Jupyter notebooks (pipeline completo)
├── deliverable/                       # Pacote de entrega autonomo
│   ├── scoring.py                     # Script de scoring universal
│   ├── build_pipeline.py              # Gerador de pipeline PKLs (--build-all)
│   ├── validate.py                    # Validacao 27 checks
│   ├── Credit_Risk_Scoring_Deliverable.ipynb  # Notebook interativo
│   ├── models/                        # 6 pipelines self-contained (champion + 5 individuais)
│   ├── data/clientes_consolidado.parquet  # Dados Gold (3.9M rows)
│   └── config/selected_features.json
├── logs/                              # Logs das execucoes Airflow
└── docs/                              # Documentacao completa
    ├── architecture/                  # Guia de arquitetura + diagramas (PNG, PDF)
    ├── data/                          # Dicionario de dados + schema overview
    ├── model/                         # Ensemble, swap, CM analysis, monitoring, post-impl
    ├── operations/                    # Custos, CLI reference, runbook operacional
    └── pipeline/                      # Feature engineering, validacao, execucao
```

---

## Documentacao

| Documento | Descricao |
|-----------|-----------|
| [EXECUTION-GUIDE.md](EXECUTION-GUIDE.md) | Passo-a-passo oficial de execucao (8 steps) |
| [Analise de Valor Financeiro](docs/model/business-value-analysis.md) | Impacto em R$ — economia, ROI, trade-offs |
| [Confusion Matrix Analysis](docs/model/confusion-matrix-analysis.md) | Precision, recall, specificity, gain/lift por cutoff |
| [Selecao do Ensemble](docs/model/ensemble-selection.md) | Top-3 vs All-5, criterios de selecao |
| [Revisao Pos-Implementacao](docs/model/post-implementation-review.md) | Resultados, limitacoes, recomendacoes |
| [Monitoring Dashboard](docs/model/model-monitoring-dashboard.md) | APEX dashboard, PSI, alertas, retraining |
| [Swap Analysis](docs/model/swap-analysis.md) | Analise swap-in/swap-out por cutoff |
| [Overfitting Gap Analysis](docs/model/overfitting-gap-analysis.md) | GAP treino vs OOT, diagnostico |
| [Guia de Arquitetura](docs/architecture/) | Diagramas, decisoes tecnicas |
| [Dicionario de Dados](docs/data/) | Schema overview, feature catalog |
| [Runbook Operacional](docs/operations/) | Custos, CLI reference, ops |
| [Feature Engineering](docs/pipeline/) | Pipeline de features, validacao |
| [Pesquisa (6 fases)](research/README.md) | Diagnostic → HPO → Ensemble → Production |
| [Artefatos](artifacts/README.md) | Manifesto de modelos, metricas, plots |

---

## Resultados do Treinamento

### Hiperparametros Otimizados (HPO)

| Modelo | Param Principal | Valor |
|--------|----------------|-------|
| LightGBM v2 | n_estimators / lr / depth / leaves | 800 / 0.0388 / 8 / 99 |
| XGBoost | n_estimators / lr / depth / min_child | 793 / 0.0312 / 8 / 12 |
| CatBoost | iterations / lr / depth | 685 / 0.0682 / 6 |
| LR L1 v2 | C=0.5, penalty=l1, balanced | Standard (sem HPO) |
| Random Forest | n_estimators=500, depth=12 | Standard (sem HPO) |

### Metricas de Performance (Run 20260311_015100 — Airflow, 110 features, 3.9M rows)

| Modelo | KS Train | AUC Train | KS OOT | AUC OOT | Gini OOT | PSI | Tempo |
|--------|----------|-----------|--------|---------|----------|-----|-------|
| LR L1 v2 | 0.35143 | 0.73692 | 0.3314 | 0.7231 | 44.62 | 0.001361 | 448s |
| LightGBM v2 | 0.39723 | 0.76769 | 0.34943 | 0.73645 | 47.29 | 0.000933 | 137s |
| XGBoost | 0.40859 | 0.77501 | 0.34938 | 0.73619 | 47.24 | 0.000817 | 144s |
| CatBoost | 0.37423 | 0.75325 | 0.34821 | 0.73539 | 47.08 | 0.000563 | 154s |
| RF | 0.37153 | 0.75121 | 0.337 | 0.72778 | 45.56 | 0.001209 | 668s |
| **Ens Avg Top 3** | — | — | **0.35005** | **0.73677** | **47.35** | **0.000754** | — |

**Ensemble Champion**: Average (Top 3: LightGBM + XGBoost + CatBoost)
**Batch Scoring**: 3,900,378 registros scored (mean=538, min=23, max=982, scale 0-1000)
**Pipeline Total**: ~58 min via Airflow (E3.Flex 4 OCPUs / 64 GB)

### Quality Gate QG-05

| Criterio | Threshold | Status |
|----------|-----------|--------|
| KS OOT | > 0.20 | PASS |
| AUC OOT | > 0.65 | PASS |
| Gini OOT | > 30% | PASS |
| PSI | < 0.25 | PASS |

---

## Infraestrutura OCI

| Recurso | Status | Detalhes |
|---------|--------|----------|
| Object Storage | ACTIVE | 4 buckets (landing, bronze, silver, gold) |
| Orchestrator (Airflow) | RUNNING | 146.235.27.18:8080, Docker Compose |
| Data Science Notebook | CHECK | 10.0.1.10 (pode estar INACTIVE) |
| ADW | ACTIVE | Always Free, APEX dashboard |
| Data Catalog | ACTIVE | Always Free |
| Terraform | INITIALIZED | 8 modulos, state local |

## Chaves e Credenciais

| Item | Valor |
|------|-------|
| Namespace | grlxi07jz1mo |
| Region | sa-saopaulo-1 |
| Compartment | ocid1.compartment.oc1..aaaaaaaa7uh2lfpsc6qf73g7zalgbr262a2v6veb4lreykqn57gtjvoojeuq |
| SSH Key | ~/.ssh/oci_pipeline.pub |
| ADW ADMIN | (ver credenciais seguras — nao versionadas) |
| ADW ML User | (ver credenciais seguras — nao versionadas) |
