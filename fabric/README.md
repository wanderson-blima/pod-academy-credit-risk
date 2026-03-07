# Microsoft Fabric — Pipeline de Credit Risk FPD

Pipeline de engenharia de dados e machine learning construido na plataforma **Microsoft Fabric** para predicao de **First Payment Default (FPD)** em clientes de telecomunicacoes.

## Arquitetura Medallion

```
CSV/Excel/Parquet → BRONZE (staging) → SILVER (rawdata + books) → GOLD (feature_store) → Modelo → Scoring
```

| Camada | Lakehouse | Schemas | Tabelas |
|--------|-----------|---------|---------|
| Bronze | `b8822164...` | config, staging, log | 21 |
| Silver | `5f8a4808...` | rawdata, book | 24 |
| Gold | `6a7135c7...` | feature_store | 1 (consolidado) |

## Feature Store

**Tabela**: `Gold.feature_store.clientes_consolidado`

- **Granularidade**: `NUM_CPF` + `SAFRA` (YYYYMM)
- **Registros**: ~3.9 milhoes
- **Features**: 402 colunas (90 REC_ + 94 PAG_ + 114 FAT_ + 103 base + 1 audit)
- **SAFRAs**: 202410 a 202503

## Estrutura

```
fabric/
├── src/
│   ├── ingestion/            # Stage 1: CSV → Bronze
│   ├── metadata/             # Stage 2: Tipagem + Dedup → Silver
│   ├── feature-engineering/  # Stage 4: Feature Books → Gold
│   └── modeling/             # Stage 5: Treinamento + Scoring + Monitoramento
├── notebooks/                # EDAs e analise exploratoria
├── config/                   # pipeline_config.py
├── utils/                    # data_quality.py
├── schemas/
│   ├── enriched-metadata/    # 15 JSONs de metadados enriquecidos
│   └── ddl/                  # DDLs Bronze/Silver/Gold
├── artifacts/                # Modelos (.pkl), metricas, SHAP, plots
└── docs/                     # Arquitetura, feature docs, modeling docs
```

## Ordem de Execucao

```bash
# 1. Ingestao (→ Bronze)
src/ingestion/ingestao-arquivos.py

# 2. Tipagem + Deduplicacao (→ Silver)
src/metadata/ajustes-tipagem-deduplicacao.py

# 3. Dimensoes
src/ingestion/criacao-dimensoes.py

# 4. Feature Engineering (→ Gold)
src/feature-engineering/book_recarga_cmv.py
src/feature-engineering/book_pagamento.py
src/feature-engineering/book_faturamento.py
src/feature-engineering/book_consolidado.py

# 5. Modelagem
src/modeling/modelo_baseline.ipynb
src/modeling/scoring-batch.ipynb
src/modeling/validacao-deploy.ipynb

# 6. Monitoramento (mensal)
src/modeling/monitoramento-drift.ipynb
```

## Tecnologias

| Componente | Tecnologia |
|------------|------------|
| Plataforma | Microsoft Fabric |
| Storage | Delta Lake (OneLake) |
| Processamento | PySpark 3.x |
| ML | scikit-learn 1.3.2, LightGBM |
| Tracking | MLflow 2.12.2 |

## Resultados

| Modelo | KS (OOT) | AUC (OOT) | Gini (OOT) |
|--------|-----------|-----------|-------------|
| **LightGBM** | **33.97%** | **0.7303** | **46.06 pp** |
| Logistic Regression L1 | 32.77% | 0.7207 | 44.15 pp |

> Supera o benchmark do Score Bureau em 0.87 pp de KS, com PSI < 0.002.

Para documentacao detalhada, veja [`docs/`](docs/).
