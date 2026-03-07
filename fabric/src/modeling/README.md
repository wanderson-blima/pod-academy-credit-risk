# Stage 5 — Modelagem, Scoring e Monitoramento

Pipeline completo de machine learning para predicao de FPD (First Payment Default), desde treinamento ate monitoramento em producao.

## Notebooks

| Notebook | Descricao | Entregavel |
|----------|-----------|------------|
| [`modelo_baseline.ipynb`](modelo_baseline.ipynb) | Treinamento dual (LR L1 + LGBM) com feature selection | C |
| [`analise-swap.ipynb`](analise-swap.ipynb) | Swap analysis + visualizacoes de performance | D, F |
| [`scoring-batch.ipynb`](scoring-batch.ipynb) | Scoring batch em novas SAFRAs (score 0-1000) | E |
| [`validacao-deploy.ipynb`](validacao-deploy.ipynb) | Gate de validacao pre-deploy | — |
| [`monitoramento-drift.ipynb`](monitoramento-drift.ipynb) | Monitoramento PSI + performance drift | — |

## Pipeline de Treinamento (10 Etapas)

O `modelo_baseline.ipynb` executa um pipeline completo de 10 etapas:

1. **Data Loading** — Carga otimizada do Feature Store (Arrow + selfDestruct, 25% sample)
2. **Data Cleaning** — Tratamento de NULLs, CEP→UF, data nascimento→idade
3. **Temporal Split** — Treino (Q4/2024), OOS (Jan/2025), OOT (Feb-Mar/2025)
4. **Dual Training** — LR L1 + LGBM com GridSearch
5. **Feature Selection** — 4 etapas: IV → L1 → Correlacao → LGBM Top 70
6. **Cross-Validation** — 13-fold temporal
7. **KS Incremental** — Contribuicao por fonte de dados
8. **Model Selection** — Melhor modelo por KS OOT
9. **Swap Analysis** — Estabilidade de ranking entre SAFRAs
10. **PSI + Decile** — Validacao de estabilidade e calibracao

### Resultado

- **59 features** selecionadas de 398
- **LightGBM**: KS 33.97%, AUC 0.7303 (OOT)
- **LR L1**: KS 32.77%, AUC 0.7207 (OOT)
- 26+ visualizacoes geradas (3 paineis de 8 graficos + SHAP + KS incremental)

## Scoring Batch

O `scoring-batch.ipynb` aplica o modelo treinado em novas SAFRAs:

1. Carrega modelo do MLflow Registry
2. Prepara features (mesmas do treinamento)
3. Gera probabilidades (`predict_proba`)
4. Converte para score 0-1000
5. Classifica em faixas de risco (Critico/Alto/Medio/Baixo)
6. Salva em `Gold.feature_store.clientes_scores`

## Monitoramento

O `monitoramento-drift.ipynb` executa mensalmente:

1. Calcula PSI do score (distribuicao)
2. Calcula PSI das Top 20 features
3. Compara performance (KS/AUC/Gini) com baseline
4. Gera alertas (VERDE/AMARELO/VERMELHO)

## Artefatos Gerados

Todos os artefatos sao salvos em [`artifacts/`](../../artifacts/):

```
artifacts/
├── models/
│   ├── lgbm_baseline/    → .pkl + MLmodel + requirements
│   └── lr_baseline/      → .pkl + MLmodel + requirements
├── feature_selection/    → SHAP ranking + selected features
├── monitoring/           → JSON + CSV de drift
├── scoring/              → Distribuicao de scores
└── analysis/             → CSVs + PNGs de analise
```

## Decisoes Tecnicas

- **Split temporal** (nao cross-validation) — simula cenario real de producao
- **Metricas rank-based** (KS, AUC, Gini) — padrao da industria de credito
- **Scoring 0-1000** — escala interpretavel com faixas de risco
- **Monkey-patch sklearn** — compatibilidade com versao do Fabric
- **MLflow tracking** — reprodutibilidade e versionamento de experimentos

---

*Resultados detalhados: [docs/modeling/model-results.md](../../docs/modeling/model-results.md)*
*Decisoes tecnicas: [docs/technical-decisions.md](../../docs/technical-decisions.md)*
