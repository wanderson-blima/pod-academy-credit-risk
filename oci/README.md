# Oracle Cloud Infrastructure — Pipeline de Credit Risk FPD

Evolucao cloud-native do pipeline de Credit Risk FPD, portado do Microsoft Fabric para **Oracle Cloud Infrastructure (OCI)**. Inclui pipeline Medallion completo, ensemble multi-modelo com HPO, dashboard APEX e infraestrutura 100% Terraform.

## Arquitetura OCI

```
Object Storage (Bronze) → Data Flow/Spark (Silver) → ADW (Gold) → Compute VM (Ensemble) → Scoring + APEX Dashboard
```

| Camada | Servico OCI | Funcao |
|--------|-------------|--------|
| Bronze | Object Storage | Ingestao de dados brutos (CSV/Parquet) |
| Silver | Data Flow (Spark) | Transformacao e limpeza |
| Gold | Autonomous Data Warehouse | Feature store consolidada |
| Model | Compute VM (E5.Flex) | Treinamento ensemble multi-modelo com HPO |
| Deploy | Object Storage + APEX | Scoring batch + dashboard de monitoramento |

## Resultados — Ensemble v1

Pipeline executado em **2026-03-08** em VM OCI (4 OCPUs, 64GB RAM) por 8h53m.

### Performance dos Modelos

| Modelo | KS OOT | AUC OOT | Gini OOT | PSI |
|--------|--------|---------|----------|-----|
| XGBoost (HPO) | **0.3472** | **0.7351** | 47.02 | 0.0008 |
| LightGBM v2 (HPO) | 0.3471 | 0.7350 | 47.00 | 0.0008 |
| CatBoost (HPO) | 0.3462 | 0.7343 | 46.87 | 0.0005 |
| **Ensemble (avg)** | **0.3442** | **0.7334** | **46.68** | **0.0006** |
| RandomForest | 0.3348 | 0.7280 | 45.60 | 0.0012 |
| LR L1 v2 | 0.3285 | 0.7208 | 44.16 | 0.0007 |
| *Baseline LGBM v1* | *0.3403* | *0.7305* | *46.11* | *0.0005* |

> Melhor modelo individual (XGBoost) supera baseline em **+0.69pp KS**. Ensemble melhora **+0.39pp KS** com PSI excelente (0.0006).

### HPO (Optuna, 50 trials por modelo)

| Modelo | Best KS(CV) | Tempo |
|--------|------------|-------|
| XGBoost | 0.36596 | ~2h23m |
| LightGBM | 0.36548 | ~2h31m |
| CatBoost | 0.36541 | ~3h20m |

### Scoring

- **3,900,378 registros** scored com ensemble
- Score medio: 605 | Mediana: 627
- Distribuicao: 6.4% CRITICO, 24.2% ALTO, 32.6% MEDIO, 36.8% BAIXO

## Estrutura

```
oci/
├── infrastructure/
│   ├── terraform/              # IaC completa (7 modulos, 43 recursos)
│   │   └── modules/ (network, storage, database, dataflow, datascience, monitoring, cost)
│   ├── apex/                   # Dashboard APEX (SQL + HTML + Chart.js)
│   │   ├── 01_create_schema.sql ... 04_create_apex_app.sql
│   │   ├── dashboard.html      # Dashboard dark-theme responsivo
│   │   └── upload_dashboard.py
│   ├── ops/                    # Scripts operacionais
│   ├── cloud_init_ensemble.sh  # Cloud-init para VM de treinamento
│   └── run_on_vm.sh            # Script de execucao na VM
│
├── pipeline/                   # Pipeline ETL (Bronze → Silver → Gold)
│   ├── ingest_bronze.py
│   ├── transform_silver.py
│   ├── engineer_gold.py
│   ├── validate_parity.py
│   └── cleanup_delta_orphans.py
│
├── model/                      # Treinamento e deploy de modelos
│   ├── train_credit_risk.py    # Treinamento baseline (LR + LGBM)
│   ├── evaluate_model.py       # Suite de avaliacao (decile tables, swap, PSI)
│   ├── batch_scoring.py        # Scoring batch (ensemble-first com fallback LGBM)
│   ├── deploy_endpoint.py      # Endpoint REST
│   ├── register_model_catalog.py  # Registro no OCI Model Catalog
│   ├── monitor_model.py        # Monitoramento de drift (ensemble + base models)
│   ├── oci_metrics.py          # Custom metrics no OCI Monitoring
│   └── seed_dashboard.py       # Seed de dados para APEX
│
├── artifacts/                  # Artefatos locais
│   ├── models/                 # Modelos baseline (.pkl)
│   ├── metrics/                # Metricas de treinamento (.json, .csv)
│   ├── hpo/                    # Hiperparametros otimizados
│   ├── ensemble/               # Resultados do ensemble
│   └── pipeline_summary_*.json # Resumo da execucao
│
├── deliverable/                # Entregavel do hackathon
│   ├── scoring_validacao.py    # Script de validacao
│   ├── dados_exemplo.csv       # Dados de exemplo
│   └── modelo-agnostico/       # Container Docker-ready
│
└── docs/                       # Documentacao OCI (14 arquivos)
    ├── oci-architecture-guide.md
    ├── oci-e2e-validation-report.md
    ├── oci-pipeline-execution-report.md
    ├── operations-runbook.md
    ├── cost-dashboard.md
    └── ...
```

## Pipeline de Execucao

### Pipeline Original (Baseline)

| # | Etapa | Script | Descricao |
|---|-------|--------|-----------|
| 0 | Infra | `infrastructure/terraform/` | `terraform apply` — 7 modulos, 43 recursos |
| 1 | Bronze | `pipeline/ingest_bronze.py` | Ingestao → Object Storage |
| 2 | Silver | `pipeline/transform_silver.py` | Transformacao via Data Flow |
| 3 | Gold | `pipeline/engineer_gold.py` | Feature engineering → ADW |
| 4 | Modelo | `model/train_credit_risk.py` | Treinamento LR + LGBM (baseline) |
| 5 | Deploy | `model/deploy_endpoint.py` | Endpoint REST |

### Pipeline Ensemble (Evolucao)

| # | Etapa | Script/Local | Descricao |
|---|-------|--------------|-----------|
| 1 | Setup | `infrastructure/cloud_init_ensemble.sh` | Python 3.9 + deps na VM |
| 2 | Data | `infrastructure/run_on_vm.sh` | Download feature store (1.3GB) |
| 3-6 | Pipeline | `5-treinamento-modelos/run_full_pipeline.py` | 6 fases automatizadas |

### Fases do Pipeline Ensemble

| Fase | Duracao | Descricao |
|------|---------|-----------|
| 1. Diagnostic | 25s | KS/AUC por SAFRA, Brier score, drift detection |
| 2. Feature Engineering | 5min | 47 novas features + PCA + selecao (IV/corr/PSI) |
| 3. HPO | ~8h | 50 trials Optuna por modelo (LGBM, XGB, CatBoost) |
| 4. Multi-Model | 15min | 5 modelos treinados com params otimizados |
| 5. Ensemble | 4min | Simple avg vs blend vs stacking |
| 6. Production | 5min | Scoring 3.9M + upload 18 artefatos para OCI |

## Artefatos no OCI Object Storage

Bucket: `pod-academy-gold` | Namespace: `grlxi07jz1mo`

| Prefixo | Artefatos | Tamanho Total |
|---------|-----------|---------------|
| `model_artifacts/ensemble_v1/ensemble/` | Modelo ensemble + resultados | 175 MB |
| `model_artifacts/ensemble_v1/models_v2/` | 5 modelos individuais + metricas | ~175 MB |
| `model_artifacts/ensemble_v1/hpo/` | Hiperparametros otimizados | 1 KB |
| `model_artifacts/ensemble_v1/scoring/` | Scores (total + por SAFRA) | ~148 MB |
| `clientes_scores_ensemble/SAFRA=*/` | Scores particionados (Hive) | ~72 MB |
| `pipeline_scripts/` | 6 scripts Python | ~122 KB |

## Infraestrutura como Codigo

A infraestrutura e 100% provisionada via **Terraform** com 7 modulos:

| Modulo | Recursos |
|--------|----------|
| `network` | VCN, subnets (publica, privada, bastion), security lists, gateways |
| `storage` | Object Storage buckets (bronze, silver, gold, scripts, logs) |
| `database` | Autonomous Data Warehouse (ADW) |
| `dataflow` | Data Flow applications (bronze, silver, gold) + pool |
| `datascience` | Data Science project + notebook session |
| `monitoring` | Custom metrics namespace |
| `cost` | Budget alerts + cost tracking |

### Quick Start

```bash
cd infrastructure/terraform/
cp terraform.tfvars.example terraform.tfvars
# Editar com credenciais OCI

terraform init
terraform plan
terraform apply
```

## Dashboard APEX

Dashboard de monitoramento disponivel em:
- **URL**: `https://G95D3985BD0D2FD-PODACADEMY.adb.sa-saopaulo-1.oraclecloudapps.com/ords/mlmonitor/dashboard/`
- **Tecnologia**: HTML + Chart.js + ORDS SQL (dark theme)
- **Paginas**: Overview (KPIs), Model Comparison, Score Distribution

## Custos

- **Trial Credit**: US$ 500
- **Acumulado**: ~R$ 171 (dentro do trial)
- **Compute Ensemble**: VM.Standard.E5.Flex (4 OCPUs, 64GB RAM) — ~9h de uso
- **Detalhes**: [`docs/cost-dashboard.md`](docs/cost-dashboard.md)

## Documentacao

| Documento | Descricao |
|-----------|-----------|
| [Architecture Guide](docs/oci-architecture-guide.md) | Guia completo da arquitetura OCI |
| [E2E Validation Report](docs/oci-e2e-validation-report.md) | Relatorio de validacao ponta-a-ponta |
| [Pipeline Execution](docs/oci-pipeline-execution-report.md) | Relatorio de execucao do pipeline |
| [Operations Runbook](docs/operations-runbook.md) | Procedimentos operacionais |
| [Cost Dashboard](docs/cost-dashboard.md) | Monitoramento de custos |
| [Quality Dashboard](docs/QUALITY-DASHBOARD-v2.md) | Dashboard de qualidade do modelo |

---

*Pipeline OCI — Hackathon PoD Academy (Claro + Oracle)*
