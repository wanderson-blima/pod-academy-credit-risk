# Documentacao Tecnica — Modelo de Risco de Credito (FPD)

> **Projeto**: Hackathon PoD Academy | **Parceria**: Claro + Oracle
> **Epic**: EPIC-HD-001 | **Story**: HD-3.4 | **Entregavel**: D

## 1. Visao Geral do Projeto

Pipeline completo de engenharia de dados e machine learning para **previsao de First Payment Default (FPD)** em clientes Claro que migram de planos Pre-pago para Controle.

### Numeros do Projeto

| Metrica | Valor |
|---------|-------|
| Registros | ~3.9 milhoes |
| Features | 468 |
| SAFRAs | 6 (202410 a 202503) |
| Books de variaveis | 3 (Recarga, Pagamento, Faturamento) |
| Modelos | 2 (Logistic Regression L1, LightGBM GBDT) |
| Plataforma | Microsoft Fabric (OneLake, PySpark, Delta Lake) |

### Arquitetura Medallion

```
Bronze (Raw)  →  Silver (Cleansed)  →  Gold (Features)
  staging         rawdata + book         feature_store
  config                                 clientes_consolidado
  log
```

## 2. Estrutura da Documentacao

```
0-docs/
├── README.md                              ← ESTE ARQUIVO
├── architecture/
│   └── data-architecture.md               ← Arquitetura completa (5 diagramas Mermaid)
├── books/
│   ├── README.md                          ← Indice dos books
│   ├── book-recarga-cmv.md                ← 102 variaveis (REC_)
│   ├── book-pagamento.md                  ← 154 variaveis (PAG_)
│   └── book-faturamento.md                ← ~108 variaveis (FAT_)
├── methodology/
│   ├── preprocessing.md                   ← Pipeline de pre-processamento
│   ├── feature-selection.md               ← Selecao de features (IV, L1, correlacao)
│   └── model-baseline.md                  ← Configuracao e resultados do modelo
├── analytics/
│   ├── estudo-publico-alvo.md             ← Analise do publico-alvo (Entregavel A)
│   └── fig_*.png                          ← Visualizacoes (geradas pelo notebook)
├── sessions/
│   └── 2026-02/                           ← Handoffs de sessao
│
docs/
├── prd/
│   └── brownfield-prd-credit-risk.md      ← PRD do projeto
├── stories/
│   ├── epic-hackathon-delivery.md         ← Epic principal
│   └── story-*.md                         ← Stories individuais
└── architecture/
    ├── system-architecture.md
    └── db-audit.md
```

## 3. Entregaveis do Hackathon

| ID | Entregavel | Artefato | Status |
|----|-----------|----------|--------|
| A | Estudo do Publico-Alvo | `3-edas/estudo_publico_alvo.ipynb` + `0-docs/analytics/estudo-publico-alvo.md` | ARTEFATO PRONTO |
| B | Documentacao de Variaveis | `0-docs/books/book-*.md` (3 docs) | ARTEFATO PRONTO |
| C | Modelo Baseline (.pkl + MLflow) | `5-treinamento-modelos/modelo_baseline_*.ipynb` + `export_model.py` | ARTEFATO PRONTO |
| D | Documentacao Tecnica | `0-docs/` (este diretorio completo) | ARTEFATO PRONTO |
| E | Arquitetura de Dados | `0-docs/architecture/data-architecture.md` | COMPLETO |
| F | Apresentacao Final | A compilar | PENDENTE |

## 4. Pipeline de Dados

### 4.1 Ingestao (Bronze)
- **Script**: `1-ingestao-dados/ingestao-arquivos.py`
- Carrega CSV/Excel/Parquet para Bronze staging
- Tracking via `_execution_id` e `_data_inclusao`

### 4.2 Metadados (Silver)
- **Script**: `2-metadados/ajustes-tipagem-deduplicacao.py`
- Type casting via `config.metadados_tabelas`
- Deduplicacao por PK + `_data_inclusao` DESC

### 4.3 Books (Silver → Gold)
- **Scripts**: `4-construcao-books/book_*.py`
- Feature engineering: 102 + 154 + 108 = 364 variaveis de books
- Consolidacao em 468 features totais

### 4.4 Modelo (Gold)
- **Notebook**: `5-treinamento-modelos/modelo_baseline_risco_telecom_sklearn.ipynb`
- Selecao de ~70 features via IV + L1 + correlacao + LGBM importance
- Modelos: LR (L1) e LightGBM com MLflow tracking

## 5. Validacao de Qualidade

- **Script**: `utils/data_quality.py` (891 linhas, 5 funcoes de validacao)
- Valida Bronze→Silver, books, feature store
- Detecta leakage, problemas de tipo, duplicatas

### Leakage Auditado

| Feature | Status | Acao |
|---------|--------|------|
| FAT_VLR_FPD | LEAKAGE | REMOVIDO (era MAX(FPD), copia do target) |
| REC_SCORE_RISCO | SEGURO | Usa indicadores operacionais |
| PAG_SCORE_RISCO | SEGURO | Usa indicadores de pagamento |
| FAT_SCORE_RISCO | SEGURO | Usa indicadores de faturamento |

## 6. Configuracao Centralizada

```python
# config/pipeline_config.py
SAFRAS = [202410, 202411, 202412, 202501, 202502, 202503]
BRONZE_BASE = "abfss://...@onelake.dfs.fabric.microsoft.com/..."
SILVER_BASE = "abfss://...@onelake.dfs.fabric.microsoft.com/..."
GOLD_BASE = "abfss://...@onelake.dfs.fabric.microsoft.com/..."
EXPERIMENT_NAME = "hackathon-pod-academy/credit-risk-fpd"
```

## 7. Como Executar

### Ordem de Execucao no Fabric

```
1. ingestao-arquivos.py           (CSV → Bronze)
2. ajustes-tipagem-deduplicacao.py (Bronze → Silver)
3. criacao-dimensoes.py           (Dimensoes Silver)
4. book_recarga_cmv.py            (Silver → Book)
5. book_pagamento.py              (Silver → Book)
6. book_faturamento.py            (Silver → Book)
7. book_consolidado.py            (Books → Gold)
8. modelo_baseline_*.ipynb        (Gold → Modelo)
9. export_model.py                (Modelo → .pkl + MLflow)
10. analise_swap_visualizacoes.ipynb (Modelo → Graficos)
```

### Pre-requisitos
- Microsoft Fabric workspace com 3 lakehouses (Bronze, Silver, Gold)
- PySpark 3.x com Delta Lake
- sklearn, lightgbm, mlflow, matplotlib, seaborn

---

## 8. Equipe

**Hackathon PoD Academy** — Parceria Claro + Oracle

---
*Documento gerado como parte da Story HD-3.4 — Entregavel D*
