# Credit Risk Scoring — Deliverable Package

Pacote completo de entrega do pipeline de risco de credito, com **6 pipelines self-contained** (champion ensemble + 5 modelos individuais), artefatos de treinamento e dados para validacao.

## Requisitos

```bash
pip install -r requirements.txt
```

**Python**: 3.8+
**Nota**: Os modelos foram treinados com scikit-learn 1.3.2. Use exatamente essa versao para compatibilidade com os PKLs.

## Estrutura

Este pacote e **100% self-contained** — basta a pasta `deliverable/` para rodar o notebook e scoring.

```
deliverable/
├── scoring.py                          # Script CLI de scoring
├── build_pipeline.py                   # Gera todos os pipeline PKLs
├── validate.py                         # Smoke test / validacao (38 checks)
├── requirements.txt                    # Dependencias Python
├── README.md                           # Este arquivo
├── Credit_Risk_Scoring_Deliverable.ipynb  # Notebook completo com plots
├── models/                             # 6 pipelines self-contained
│   ├── champion_pipeline.pkl           #   Ensemble Top-3 Average (RECOMENDADO) — 16.9 MB
│   ├── pipeline_lgbm_v2.pkl            #   LightGBM v2 (HPO) — 7.4 MB
│   ├── pipeline_xgboost.pkl            #   XGBoost (HPO) — 8.7 MB
│   ├── pipeline_catboost.pkl           #   CatBoost (HPO) — 0.8 MB
│   ├── pipeline_rf.pkl.gz              #   Random Forest (comprimido) — 56 MB
│   └── pipeline_lr_l1_v2.pkl           #   LR L1 v2 — 16 KB
├── config/
│   └── selected_features.json          # 110 features selecionadas
├── data/
│   └── clientes_consolidado.parquet    # 3.9M registros (110 features + ID + FPD)
└── artifacts/                          # Metricas, plots e artefatos do pipeline
    ├── metrics/                        #   Metricas de todos os modelos
    │   ├── training_results_20260311_015100.json
    │   ├── ensemble_results.json
    │   ├── champion_metadata.json
    │   ├── confusion_matrix_results.json
    │   └── feature_importance_*.csv    #   5 CSVs (1 por modelo)
    ├── scoring/
    │   └── scoring_summary.json        #   Resumo batch scoring 3.9M
    ├── monitoring/
    │   └── monitoring_report.json      #   PSI, drift, backtesting
    ├── swap_analysis/
    │   └── swap_summary.json           #   Analise de swap por cutoff
    ├── plots/                          #   16 visualizacoes PNG
    ├── funnel_summary.json             #   Funil de feature selection
    ├── selected_features.json          #   110 features (copia)
    └── data_quality_report.json        #   Validacao de qualidade
```

Cada PKL e um `ScoringPipeline` auto-contido — basta `pipeline.score(df)` para obter scores. Nenhum arquivo externo necessario.

## Pipelines Self-contained

Todos os 6 PKLs no `models/` sao `ScoringPipeline` — encapsulam **tudo** necessario para scoring:

1. **110 features** selecionadas (lista embutida)
2. **Medianas do treino** (SAFRAs 202410-202501) para imputacao de NaN
3. **Modelo** (ensemble ou individual)
4. **Conversao de score** (0-1000) e classificacao de risco
5. **Metadata** com metricas do modelo

| Pipeline | Modelo | KS OOT | AUC OOT | Tamanho |
|----------|--------|--------|---------|---------|
| **champion_pipeline.pkl** | **Ensemble Top-3 Average** | **0.35005** | **0.73677** | **16.9 MB** |
| pipeline_lgbm_v2.pkl | LightGBM v2 (HPO) | 0.34943 | 0.73645 | 7.4 MB |
| pipeline_xgboost.pkl | XGBoost (HPO) | 0.34938 | 0.73619 | 8.7 MB |
| pipeline_catboost.pkl | CatBoost (HPO) | 0.34821 | 0.73539 | 0.8 MB |
| pipeline_rf.pkl.gz | Random Forest | 0.33700 | 0.72778 | 56 MB |
| pipeline_lr_l1_v2.pkl | LR L1 v2 | 0.33140 | 0.72310 | 16 KB |

### Uso em Python

```python
from build_pipeline import ScoringPipeline

# Qualquer pipeline funciona da mesma forma:
pipeline = ScoringPipeline.load("models/champion_pipeline.pkl")

# Info do pipeline
pipeline.info()

# Scoring completo (recebe DataFrame bruto, retorna scores)
result = pipeline.score(df_clientes)
# result: NUM_CPF | SAFRA | SCORE | FAIXA_RISCO | PROBABILIDADE_FPD | MODELO_VERSAO

# Apenas probabilidades
probas = pipeline.predict_proba(df_clientes)

# Apenas preprocessing (sem scoring)
X_preprocessed = pipeline.preprocess(df_clientes)

# Exemplo com modelo individual:
lgbm = ScoringPipeline.load("models/pipeline_lgbm_v2.pkl")
result_lgbm = lgbm.score(df_clientes)
```

### Tratamento interno do pipeline

| Etapa | O que faz | Fonte |
|-------|-----------|-------|
| 1. Feature selection | Seleciona 110 features do treinamento | `pipeline.features` |
| 2. Inf removal | Substitui `inf`/`-inf` por `NaN` | Inline |
| 3. NaN imputation | Preenche NaN com mediana do **treino** | `pipeline.train_medians` |
| 4. Predict | Ensemble (3 modelos, media simples) ou modelo individual | `pipeline.model` |
| 5. Score | `int((1 - prob) * 1000)` clipped 0-1000 | Inline |
| 6. Risk band | CRITICO < 300 < ALTO < 500 < MEDIO < 700 < BAIXO | Inline |

### Rebuild dos pipelines

```bash
# Reconstruir apenas o champion (Top 3):
python build_pipeline.py --data-path data/clientes_consolidado.parquet

# Reconstruir todos os 6 pipelines (champion + 5 individuais):
python build_pipeline.py --build-all --data-path data/clientes_consolidado.parquet

# Champion com All 5 em vez de Top 3:
python build_pipeline.py --data-path data/clientes_consolidado.parquet --models 5
```

## Scoring via CLI

```bash
python scoring.py --data-path /caminho/para/dados.parquet
```

### Parametros

| Parametro | Obrigatorio | Default | Descricao |
|-----------|-------------|---------|-----------|
| `--data-path` | Sim | — | Caminho para parquet (arquivo ou diretorio) |
| `--artifacts-path` | Nao | `artifacts` | Diretorio com `models/` e `config/` |
| `--output-path` | Nao | `output` | Diretorio para salvar resultados |

## Outputs

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| `NUM_CPF` | string | CPF mascarado do cliente |
| `SAFRA` | int | Safra (YYYYMM) |
| `SCORE` | int | Score de credito (0-1000, maior = menor risco) |
| `FAIXA_RISCO` | string | CRITICO / ALTO / MEDIO / BAIXO |
| `PROBABILIDADE_FPD` | float | Probabilidade de First Payment Default |
| `MODELO_VERSAO` | string | Versao do modelo usado |

### Faixas de Risco

| Faixa | Score | Interpretacao |
|-------|-------|---------------|
| BAIXO | 700-1000 | Baixo risco de inadimplencia |
| MEDIO | 500-699 | Risco moderado |
| ALTO | 300-499 | Alto risco |
| CRITICO | 0-299 | Risco critico |

## Validacao

```bash
python validate.py
```

Executa 38 checks: carregamento de PKL, atributos do pipeline, features, preprocessing, predict_proba, scoring completo, score conversion, risk bands, e metadata do ensemble.

## Notebook

```bash
jupyter notebook Credit_Risk_Scoring_Deliverable.ipynb
```

O notebook resolve automaticamente a pasta `artifacts/` local (dentro de `deliverable/`). Nao depende de pastas externas.

13 secoes com plots interativos cobrindo o pipeline completo:
1. Setup e carregamento de artefatos
2. **Resultados dos 5 modelos + 2 ensembles** (KS, AUC, Gini, PSI)
3. Feature selection funnel (357 -> 110)
4. Feature importance (LightGBM vs XGBoost)
5. Distribuicao de risco e scoring (batch 3.9M)
6. Monitoring (PSI por SAFRA, feature drift, backtesting)
7. **Ensemble analysis — Top 3 vs All 5** (comparacao detalhada)
8. Model agreement (concordancia entre 5 modelos base)
9. Quality Gate QG-05
10. Plots PNG do pipeline
11. **Scoring Live OOT** — escora SAFRAs 202502-202503 (dados nao vistos) com pipeline auto-contido
12. Resumo executivo

## Modelos Testados

### 5 Modelos Individuais

| Modelo | KS OOT | AUC OOT | Gini OOT | PSI | PKL |
|--------|--------|---------|----------|-----|-----|
| LightGBM v2 (HPO) | 0.3494 | 0.7365 | 47.29% | 0.0009 | 7.4 MB |
| XGBoost (HPO) | 0.3494 | 0.7362 | 47.24% | 0.0008 | 8.7 MB |
| CatBoost (HPO) | 0.3482 | 0.7354 | 47.08% | 0.0006 | 0.8 MB |
| Random Forest | 0.3370 | 0.7278 | 45.56% | 0.0012 | 131.6 MB |
| LR L1 v2 | 0.3314 | 0.7231 | 44.62% | 0.0014 | 0.01 MB |

### 3 Estrategias de Ensemble (All 5)

| Estrategia | KS OOT | AUC OOT | Gini OOT | PSI |
|------------|--------|---------|----------|-----|
| Simple Average | 0.3477 | 0.7350 | 47.00% | 0.0004 |
| Blend (SLSQP) | 0.3477 | 0.7350 | 47.00% | 0.0004 |
| Stacking (LR) | 0.3130 | 0.7070 | 41.40% | 0.0015 |

### Selecao do Champion

| Ensemble | KS OOT | AUC OOT | Gini OOT | Gap KS | PKL |
|----------|--------|---------|----------|--------|-----|
| **Top 3 (Champion)** | **0.35005** | **0.73677** | **47.35%** | +0.045 | **16.9 MB** |
| All 5 | 0.34772 | 0.73502 | 47.00% | +0.037 | 148.5 MB |

**Treino**: SAFRAs 202410-202501 | **OOT**: SAFRAs 202502-202503

Top 3 (LightGBM + XGBoost + CatBoost) selecionado: melhor KS/AUC OOT, 89% menor PKL. LR L1 e Random Forest removidos por pior performance individual — RF sozinho responsavel por 93% do tamanho do PKL. Ver `docs/model/ensemble-selection.md`.
