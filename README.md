# Hackathon PoD Academy — Credit Risk FPD

Pipeline completo de engenharia de dados e machine learning para predicao de **First Payment Default (FPD)** em clientes de telecomunicacoes, desenvolvido em parceria com **Claro** e **Oracle** na plataforma **Microsoft Fabric**.

## Contexto de Negocio

Clientes migrando de planos Pre-pago para Controle (pos-pago) representam um risco de credito que precisa ser quantificado. Este projeto constroi um score de risco que prediz a probabilidade de inadimplencia no primeiro pagamento (FPD), permitindo decisoes de credito mais assertivas.

## Arquitetura

### Medallion Data Pipeline

```
CSV/Excel/Parquet                Delta Lake                    Delta Lake
      |                              |                              |
      v                              v                              v
 +---------+                  +-----------+                  +---------+
 | BRONZE  |  -- tipagem -->  |  SILVER   |  -- features --> |  GOLD   |
 | staging |  deduplicacao    |  rawdata  |  engineering     | feature |
 | config  |                  |  books    |                  |  store  |
 | log     |                  |           |                  |         |
 +---------+                  +-----------+                  +---------+
   7 tabelas                    23 tabelas                    1 tabela
                                                         468 features
                                                         3.9M records
```

### Lakehouses (Microsoft Fabric)

| Camada | Lakehouse ID | Schemas |
|--------|-------------|---------|
| Bronze | `b8822164-7b67-4b17-9a01-3d0737dace7e` | staging, config, log |
| Silver | `5f8a4808-6f65-401b-a427-b0dd9d331b35` | rawdata, book |
| Gold | `6a7135c7-0d8d-4625-815d-c4c4a02e4ed4` | feature_store |

## Pipeline de Execucao

| Etapa | Script | Descricao |
|-------|--------|-----------|
| 1. Ingestao | `1-ingestao-dados/ingestao-arquivos.py` | CSV/Excel/Parquet para Bronze (staging) |
| 2. Metadados | `2-metadados/ajustes-tipagem-deduplicacao.py` | Tipagem + deduplicacao para Silver (rawdata) |
| 3. Dimensoes | `1-ingestao-dados/criacao-dimensoes.py` | Tabelas dimensionais (calendario, CPF) |
| 4a. Book Recarga | `4-construcao-books/book_recarga_cmv.py` | 102 features (REC_*) |
| 4b. Book Pagamento | `4-construcao-books/book_pagamento.py` | 154 features (PAG_*) |
| 4c. Book Faturamento | `4-construcao-books/book_faturamento.py` | 108 features (FAT_*) |
| 4d. Consolidado | `4-construcao-books/book_consolidado.py` | 468 features consolidadas para Gold |
| 5. Modelo | `5-treinamento-modelos/modelo_baseline_*.ipynb` | Treinamento LR + LGBM |
| 6. Export | `5-treinamento-modelos/export_model.py` | .pkl + MLflow Registry |
| 7. Scoring | `5-treinamento-modelos/scoring_batch.ipynb` | Scoring batch sobre novas SAFRAs |
| 8. Validacao | `5-treinamento-modelos/validacao_deploy.py` | Validacao de deploy (KS/AUC/Gini) |
| 9. Monitoramento | `5-treinamento-modelos/monitoramento_drift.py` | PSI drift + performance tracking |

## Feature Store

**Tabela**: `Gold.feature_store.clientes_consolidado`

| Atributo | Valor |
|----------|-------|
| Granularidade | `NUM_CPF` + `SAFRA` (YYYYMM) |
| Registros | ~3.9 milhoes |
| Features | 468 |
| SAFRAs | 202410 a 202503 (6 periodos) |
| Particionamento | Por SAFRA |

### Composicao de Features

| Prefixo | Origem | Quantidade |
|---------|--------|-----------|
| (nenhum) | Cadastro + Telco + Target | ~103 |
| `REC_` | book_recarga_cmv | 102 |
| `PAG_` | book_pagamento | 154 |
| `FAT_` | book_faturamento | 108 |

### Join Pattern

```
dados_cadastrais (base)
  |-- LEFT JOIN telco               ON (NUM_CPF, SAFRA)
  |-- LEFT JOIN score_bureau_movel  ON (NUM_CPF, SAFRA)  -- targets
  |-- LEFT JOIN book_recarga_cmv    ON (NUM_CPF, SAFRA)  -- REC_*
  |-- LEFT JOIN book_pagamento      ON (NUM_CPF, SAFRA)  -- PAG_*
  |-- LEFT JOIN book_faturamento    ON (NUM_CPF, SAFRA)  -- FAT_*
```

## Modelos

### Target

**FPD** (First Payment Default) — binario {0, 1}. Indica se o cliente deixou de pagar a primeira fatura apos migrar para Controle.

### Algoritmos

| Modelo | Tipo | Configuracao |
|--------|------|-------------|
| Logistic Regression (L1) | Baseline interpretavel | penalty="l1", solver="saga", class_weight="balanced" |
| LightGBM (GBDT) | Ensemble tree-based | n_estimators=250, max_depth=7, learning_rate=0.05 |

### Split Temporal

| Conjunto | SAFRAs | Uso |
|----------|--------|-----|
| Treino | 202410, 202411, 202412 | Treinamento do modelo |
| OOS (Out-of-Sample) | 202501 | Validacao |
| OOT (Out-of-Time) | 202502, 202503 | Teste temporal |

### Selecao de Features

Pipeline de 4 etapas:
1. **IV Filter** — Information Value > 0.02
2. **L1 Coefficients** — Features com coeficientes nao-zero na Logistic Regression
3. **Correlacao** — Remocao de pares com correlacao > 0.95
4. **LGBM Importance** — Top 70 features por importancia do LightGBM

### Metricas de Referencia

| Metrica | Benchmark (Score Bureau) | LightGBM |
|---------|------------------------|----------|
| KS | 33.1% | 34.2% |

> Metricas definitivas pendentes de execucao no Fabric.

### Controles de Qualidade do Modelo

- **Leakage audit**: `FAT_VLR_FPD` identificado e removido (era copia direta do target)
- **SCORE_RISCO**: Validado como NAO-leakage (usa indicadores operacionais)
- **SAFRA excluida** dos features (previne leakage temporal)
- **Metricas rank-based** apenas (KS, AUC, Gini — sem P/R/F1 para dados desbalanceados)

## Monitoramento

Script `monitoramento_drift.py` executa mensalmente:

| Metrica | Threshold Verde | Threshold Amarelo | Threshold Vermelho |
|---------|----------------|-------------------|-------------------|
| PSI Score | < 0.10 | 0.10 - 0.25 | > 0.25 |
| PSI Features | < 0.10 | 0.10 - 0.20 | > 0.20 |
| KS Drift | < 5.0 pp | — | > 5.0 pp |
| AUC Drift | < 0.03 | — | > 0.03 |

## Estrutura do Projeto

```
projeto-final/
|-- 0-docs/                          # Documentacao tecnica
|   |-- projeto-banco-dados/         #   DDLs Bronze/Silver/Gold
|   |-- architecture/                #   Diagramas Mermaid
|   |-- books/                       #   Documentacao das variaveis
|   |-- methodology/                 #   Metodologia do modelo
|   +-- analytics/                   #   Estudo do publico-alvo
|
|-- 1-ingestao-dados/                # Stage 1: Ingestao
|   |-- ingestao-arquivos.py         #   CSV/Excel/Parquet -> Bronze
|   +-- criacao-dimensoes.py         #   Dimensoes (calendario, CPF)
|
|-- 2-metadados/                     # Stage 2: Tipagem + Deduplicacao
|   +-- ajustes-tipagem-deduplicacao.py
|
|-- 3-edas/                          # Stage 3: Analise Exploratoria
|   |-- estudo_publico_alvo.ipynb    #   EDA do publico-alvo
|   +-- 3.2-metadados-enriquecidos/  #   15 JSONs de metadata
|
|-- 4-construcao-books/              # Stage 4: Feature Engineering
|   |-- book_recarga_cmv.py          #   102 features (REC_*)
|   |-- book_pagamento.py            #   154 features (PAG_*)
|   |-- book_faturamento.py          #   108 features (FAT_*)
|   +-- book_consolidado.py          #   468 features -> Gold
|
|-- 5-treinamento-modelos/           # Stage 5: Modelagem + Deploy
|   |-- modelo_baseline_*.ipynb      #   Treinamento LR + LGBM
|   |-- export_model.py              #   .pkl + MLflow Registry
|   |-- scoring_batch.ipynb          #   Scoring batch
|   |-- validacao_deploy.py          #   Validacao de deploy
|   |-- monitoramento_drift.py       #   PSI drift detection
|   +-- analise_swap_visualizacoes.ipynb  # Swap analysis
|
|-- config/
|   +-- pipeline_config.py           # Configuracao centralizada
|
|-- utils/
|   |-- data_quality.py              # Validacao de qualidade de dados
|   +-- __init__.py
|
+-- docs/                            # Documentacao do projeto
    |-- README.md                    #   Indice de documentacao
    |-- architecture/                #   Arquitetura de dados
    |-- books/                       #   Docs das variaveis (3 books)
    |-- methodology/                 #   Metodologia do modelo
    |-- analytics/                   #   Estudos analiticos
    +-- sessions/                    #   Handoffs de sessao
```

## Entregaveis

| ID | Entregavel | Descricao | Status |
|----|-----------|-----------|--------|
| A | Estudo do Publico-Alvo | EDA com 8 visualizacoes + documento analitico | Pronto |
| B | Documentacao de Variaveis | 364 variaveis documentadas (3 books) | Pronto |
| C | Modelo Baseline | .pkl + MLflow + metricas OOS/OOT | Pronto |
| D | Documentacao Tecnica | Metodologia, preprocessing, feature selection | Pronto |
| E | Arquitetura de Dados | 5 diagramas Mermaid + DDLs completos | Pronto |
| F | Apresentacao Final | Compilacao de slides | Pendente |

## Como Executar

### Pre-requisitos

- Workspace Microsoft Fabric com 3 Lakehouses configurados
- Spark Runtime 3.x com PySpark
- MLflow habilitado no workspace
- Arquivos fonte (CSV/Excel/Parquet) carregados na pasta `Files/` do Bronze Lakehouse

### Ordem de Execucao

```bash
# 1. Ingestao (Bronze)
executar: 1-ingestao-dados/ingestao-arquivos.py

# 2. Tipagem + Deduplicacao (Silver)
executar: 2-metadados/ajustes-tipagem-deduplicacao.py

# 3. Dimensoes
executar: 1-ingestao-dados/criacao-dimensoes.py

# 4. Books (Silver -> Silver.book)
executar: 4-construcao-books/book_recarga_cmv.py
executar: 4-construcao-books/book_pagamento.py
executar: 4-construcao-books/book_faturamento.py

# 5. Consolidacao (Silver -> Gold)
executar: 4-construcao-books/book_consolidado.py

# 6. Modelagem
executar: 5-treinamento-modelos/modelo_baseline_risco_telecom_sklearn.ipynb

# 7. Export + Deploy
executar: 5-treinamento-modelos/export_model.py
executar: 5-treinamento-modelos/scoring_batch.ipynb
executar: 5-treinamento-modelos/validacao_deploy.py

# 8. Monitoramento (mensal)
executar: 5-treinamento-modelos/monitoramento_drift.py
```

> Todos os scripts importam configuracao de `config/pipeline_config.py`. Nenhum ID ou path de Lakehouse e hardcoded nos scripts.

## Configuracao Centralizada

Todas as constantes do pipeline estao em `config/pipeline_config.py`:

```python
from config.pipeline_config import (
    BRONZE_BASE, SILVER_BASE, GOLD_BASE,    # OneLake paths
    PATH_FEATURE_STORE,                      # Gold table path
    SAFRAS,                                  # [202410, ..., 202503]
    EXPERIMENT_NAME,                         # MLflow experiment
    TARGET_COLUMNS,                          # ["FPD", "TARGET_SCORE_01", "TARGET_SCORE_02"]
    LEAKAGE_BLACKLIST,                       # ["FAT_VLR_FPD"]
)
```

## Tecnologias

| Componente | Tecnologia |
|-----------|-----------|
| Plataforma | Microsoft Fabric |
| Storage | Delta Lake (OneLake) |
| Processamento | PySpark 3.x |
| ML Framework | scikit-learn, LightGBM |
| Experiment Tracking | MLflow |
| Linguagem | Python 3.x |
| Formato de Dados | Delta, Parquet, CSV, Excel |

## Volumes de Dados

| Fonte | Registros Brutos |
|-------|-----------------|
| Recarga | 99.9M transacoes |
| Pagamento | 27.9M transacoes |
| Faturamento | 32.7M registros |
| Feature Store (Gold) | 3.9M (NUM_CPF x SAFRA) |

---

**Hackathon PoD Academy** | Claro + Oracle | Microsoft Fabric
