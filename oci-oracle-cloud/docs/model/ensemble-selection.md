# Selecao do Ensemble Champion

**Run ID**: `20260311_015100`
**Plataforma**: VM.Standard.E3.Flex (4 OCPUs / 64 GB)
**Features selecionadas**: 110

---

## 1. Estrategias Testadas

Tres estrategias de ensemble foram avaliadas para combinar os 5 modelos individuais (LR L1 v2, LightGBM v2, XGBoost, CatBoost, Random Forest):

| # | Estrategia | Descricao |
|---|-----------|-----------|
| 1 | **Simple Average** | Media simples das probabilidades dos 5 modelos |
| 2 | **Blend (SLSQP)** | Pesos otimizados via minimizacao SLSQP (scipy) |
| 3 | **Stacking** | Meta-learner Logistic Regression sobre as probabilidades dos 5 modelos |

---

## 2. Resultados Comparativos

### Ensemble All-5 (5 modelos)

| Estrategia | KS OOT | AUC OOT | Gini OOT | PSI |
|-----------|--------|---------|----------|-----|
| **Simple Average** | 0.34772 | 0.73502 | 47.00 | 0.000398 |
| **Blend (SLSQP)** | 0.34772 | 0.73502 | 47.00 | 0.000398 |
| **Stacking (LR)** | 0.31295 | 0.70698 | 41.40 | 0.001489 |

### Modelos Individuais (referencia)

| Modelo | KS OOT | AUC OOT | Gini OOT | PSI |
|--------|--------|---------|----------|-----|
| LR L1 v2 | 0.33140 | 0.72310 | 44.62 | 0.001361 |
| LightGBM v2 | 0.34943 | 0.73645 | 47.29 | 0.000933 |
| XGBoost | 0.34938 | 0.73619 | 47.24 | 0.000817 |
| CatBoost | 0.34821 | 0.73539 | 47.08 | 0.000563 |
| Random Forest | 0.33700 | 0.72778 | 45.56 | 0.001209 |

---

## 3. Analise das Estrategias

### 3.1 Simple Average vs Blend

O otimizador Blend (SLSQP) convergiu para pesos iguais (1/5 = 0.20 por modelo), resultando em metricas identicas ao Simple Average. Isso indica que o espaco de solucao e plano — nenhuma combinacao de pesos produz resultado significativamente superior a media simples para este conjunto de modelos.

### 3.2 Stacking — Overfitting Detectado

O Stacking com meta-learner LR apresentou overfitting severo:

- **KS Train**: 0.45761
- **KS OOT**: 0.31295
- **Delta**: -0.14466 (queda de 31.6%)

A queda expressiva entre treino e OOT indica que o meta-learner memorizou padroes especificos do periodo de treino que nao se generalizam. **Estrategia rejeitada.**

> Para a analise completa de GAP (treino vs OOT) de todos os modelos e ensembles, incluindo AUC, Gini e diagnostico de estabilidade temporal, consulte [overfitting-gap-analysis.md](overfitting-gap-analysis.md).

### 3.3 Selecao do Champion

**Champion: Simple Average (Top-3: LightGBM + XGBoost + CatBoost)** — selecionado pelos seguintes criterios:

1. **Maior KS OOT** (0.35005) entre todas as configuracoes de ensemble
2. **Estabilidade**: PSI 0.000754 — excelente estabilidade temporal
3. **Simplicidade**: media simples, sem pesos otimizados nem meta-learner
4. **Reproducibilidade**: resultado deterministico, sem risco de overfitting
5. **PKL compacto**: 3 modelos vs 5 — 89% menor tamanho de artefato

---

## 4. Top 3 vs All 5

Alem do ensemble com todos os 5 modelos, foi avaliada a combinacao **Top 3** (LightGBM + XGBoost + CatBoost), que exclui os modelos mais fracos (LR L1 v2 e Random Forest).

| Configuracao | Modelos | Descricao |
|-------------|---------|-----------|
| **All 5** | LR, LGBM, XGB, CB, RF | Todos os 5 modelos |
| **Top 3** | LGBM, XGB, CB | 3 melhores por KS OOT |

### Racional da Decisao

O **Top 3** foi preferido para entrega final pelos seguintes motivos:

1. **PKL menor**: 3 modelos serializados vs 5 — reduz tamanho do artefato e tempo de carga
2. **OOT ligeiramente superior**: ao excluir LR e RF (modelos mais fracos), o ensemble top-3 tende a manter ou melhorar as metricas OOT
3. **Estabilidade**: os 3 modelos selecionados possuem os menores PSIs individuais (0.000563 a 0.000933)
4. **Simplicidade operacional**: menos modelos para manter, retreinar e monitorar

### Metricas Comparativas

| Configuracao | KS OOT | AUC OOT | Gini OOT | PSI | PKL Size |
|-------------|--------|---------|----------|-----|----------|
| **Top 3 (Champion)** | **0.35005** | **0.73677** | **47.35%** | 0.000754 | **16.9 MB** |
| All 5 | 0.34772 | 0.73502 | 47.00% | 0.000398 | 148.5 MB |

O Top 3 supera o All 5 em todas as metricas de performance OOT (+0.00233 KS, +0.00175 AUC, +0.35 Gini). O PSI ligeiramente maior (0.000754 vs 0.000398) permanece excelente (GREEN).

A comparacao detalhada e gerada pelo script `ensemble_comparison.py` e salva em `artifacts/metrics/ensemble_comparison.json`.

---

## 5. Quality Gate QG-05

Todos os limiares foram atendidos pelo ensemble champion:

| Metrica | Limiar | Resultado (Top-3) | Status |
|---------|--------|-------------------|--------|
| KS OOT | > 0.20 | 0.35005 | PASSED |
| AUC OOT | > 0.65 | 0.73677 | PASSED |
| Gini OOT | > 30% | 47.35% | PASSED |
| PSI | < 0.25 | 0.000754 | PASSED |

---

## 6. Arquivos Fonte

| Arquivo | Descricao |
|---------|-----------|
| `artifacts/metrics/ensemble_results.json` | Metricas do ensemble All-5 (3 estrategias) |
| `artifacts/metrics/ensemble_comparison.json` | Comparacao Top 3 vs All 5 |
| `scripts/ensemble.py` | Script de treinamento do ensemble |
