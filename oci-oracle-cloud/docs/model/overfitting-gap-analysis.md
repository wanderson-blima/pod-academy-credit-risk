# Analise de GAP (Overfitting) — KS Treino vs OOT

**Run ID**: `20260311_015100`
**Data**: 2026-03-10
**Plataforma**: VM.Standard.E3.Flex (4 OCPUs / 64 GB) — OCI
**Fonte dos dados**: `artifacts/metrics/training_results_20260311_015100.json`, `artifacts/metrics/ensemble_results.json`

---

## 1. Objetivo

Avaliar a **generalizacao** dos modelos de risco de credito comparando o desempenho entre o periodo de **treino** (SAFRAs 202410-202501) e o periodo **Out-of-Time (OOT)** (SAFRAs 202502-202503). O GAP entre treino e OOT e o principal indicador de overfitting.

### Definicoes

| Termo | Descricao |
|-------|-----------|
| **KS Train** | Kolmogorov-Smirnov calculado sobre os dados de treino (SAFRAs 202410-202501) |
| **KS OOS** | KS calculado na ultima safra do treino (202501), usada como Out-of-Sample |
| **KS OOT** | KS calculado no periodo fora do tempo (SAFRAs 202502-202503) — simulacao de producao |
| **GAP absoluto** | KS Train - KS OOT (em pontos decimais) |
| **GAP relativo (%)** | ((KS Train - KS OOT) / KS Train) x 100 |

### Criterios de Classificacao de GAP

| GAP Relativo (%) | Classificacao | Acao Recomendada |
|-------------------|---------------|------------------|
| < 10% | **Estavel** | Modelo generaliza bem — aprovado para producao |
| 10% a 15% | **Aceitavel** | Monitoramento proximo; avaliar regularizacao adicional |
| 15% a 25% | **Atencao** | Risco de degradacao em producao; investigar features instaaveis |
| > 25% | **Overfit** | Modelo nao recomendado para producao; retreinar com regularizacao |

---

## 2. GAP dos Modelos Individuais

### 2.1 Tabela Completa — Treino vs OOS vs OOT

| Modelo | KS Train | KS OOS (202501) | KS OOT | GAP Train→OOT (abs) | GAP Train→OOT (%) | Classificacao |
|--------|----------|-----------------|--------|----------------------|--------------------|---------------|
| **LR L1 v2** | 0.35143 | 0.34270 | 0.33140 | 0.02003 | **5.7%** | Estavel |
| **CatBoost** | 0.37423 | 0.36696 | 0.34821 | 0.02602 | **7.0%** | Estavel |
| **Random Forest** | 0.37153 | 0.36625 | 0.33700 | 0.03453 | **9.3%** | Estavel |
| **LightGBM v2** | 0.39723 | 0.39252 | 0.34943 | 0.04780 | **12.0%** | Aceitavel |
| **XGBoost** | 0.40859 | 0.40787 | 0.34938 | 0.05921 | **14.5%** | Aceitavel |

### 2.2 Ranking por Estabilidade (menor GAP primeiro)

| Rank | Modelo | GAP (%) | KS OOT | PSI | Veredicto |
|------|--------|---------|--------|-----|-----------|
| 1 | LR L1 v2 | 5.7% | 0.33140 | 0.001361 | Mais estavel — menor overfitting |
| 2 | CatBoost | 7.0% | 0.34821 | 0.000563 | Melhor equilibrio estabilidade x performance |
| 3 | Random Forest | 9.3% | 0.33700 | 0.001209 | Estavel, porem KS OOT mais baixo |
| 4 | LightGBM v2 | 12.0% | 0.34943 | 0.000933 | Melhor KS OOT, mas GAP no limiar de atencao |
| 5 | XGBoost | 14.5% | 0.34938 | 0.000817 | Maior GAP individual — HPO agressivo |

### 2.3 Observacoes sobre Modelos Individuais

**LR L1 v2 (GAP 5.7%)**: Regressao logistica com regularizacao L1 — por natureza, modelos lineares tem menor capacidade de memorizar padroes complexos do treino, resultando no menor GAP. Porem, o KS OOT (0.331) e o mais baixo entre todos.

**CatBoost (GAP 7.0%)**: Destaque como melhor trade-off entre performance e estabilidade. KS OOT alto (0.348) com GAP controlado. O CatBoost possui regularizacao intrinseca (ordered boosting) que contribui para generalizacao.

**LightGBM v2 e XGBoost (GAP 12-14.5%)**: Os hiperparametros otimizados via HPO (Optuna) favoreceram performance no treino ao custo de maior overfitting. Ainda assim, KS OOT permanece forte (0.349). A diferenca entre OOS e OOT sugere sensibilidade temporal — features podem ter distribuicao diferente nas safras mais recentes.

---

## 3. GAP dos Ensembles

### 3.1 Tabela Comparativa

| Estrategia | KS Train | KS OOS | KS OOT | GAP Train→OOT (abs) | GAP Train→OOT (%) | Classificacao |
|-----------|----------|--------|--------|----------------------|--------------------|---------------|
| **Top-3 Average** | 0.39441 | — | 0.35005 | 0.04436 | **11.2%** | Aceitavel |
| **Blend (SLSQP)** | 0.38485 | 0.37890 | 0.34772 | 0.03713 | **9.6%** | Estavel |
| **Stacking (LR)** | 0.45761 | 0.46187 | 0.31295 | 0.14466 | **31.6%** | Overfit |

### 3.2 Analise Detalhada do Stacking

O Stacking e o caso classico de overfitting em ensembles:

| Indicador | Valor | Problema |
|-----------|-------|----------|
| KS Train | 0.45761 | Muito superior aos modelos base (~0.37-0.41) |
| KS OOS | 0.46187 | OOS > Train sugere data leakage no fold |
| KS OOT | 0.31295 | Queda de 31.6% — pior que qualquer modelo individual |
| Meta-learner XGBoost coef | 24.4153 | Peso extremo — meta-learner dependente de 1 modelo |
| Meta-learner CatBoost coef | -20.8849 | Peso negativo extremo — instabilidade |

**Causa raiz**: O meta-learner (Logistic Regression) treinou sobre as probabilidades dos 5 modelos usando o mesmo periodo de treino. Sem proper out-of-fold prediction, o meta-learner memorizou a correlacao entre modelos especifica do periodo de treino.

**Conclusao**: Stacking **rejeitado** para producao. Para implementacao futura, seria necessario usar out-of-fold predictions (K-Fold stacking) para gerar as features do meta-learner.

---

## 4. Visao Consolidada — Todos os Modelos Ordenados por GAP

| Rank | Modelo/Ensemble | KS Train | KS OOT | GAP (abs) | GAP (%) | PSI | Status |
|------|----------------|----------|--------|-----------|---------|-----|--------|
| 1 | LR L1 v2 | 0.35143 | 0.33140 | 0.02003 | 5.7% | 0.001361 | Estavel |
| 2 | CatBoost | 0.37423 | 0.34821 | 0.02602 | 7.0% | 0.000563 | Estavel |
| 3 | Random Forest | 0.37153 | 0.33700 | 0.03453 | 9.3% | 0.001209 | Estavel |
| 4 | **Ens. Top-3 Average (Champion)** | 0.39441 | 0.35005 | 0.04436 | 11.2% | 0.000754 | Aceitavel |
| 5 | **Ens. Blend** | 0.38485 | 0.34772 | 0.03713 | 9.6% | 0.000398 | Estavel |
| 6 | LightGBM v2 | 0.39723 | 0.34943 | 0.04780 | 12.0% | 0.000933 | Aceitavel |
| 7 | XGBoost | 0.40859 | 0.34938 | 0.05921 | 14.5% | 0.000817 | Aceitavel |
| 8 | **Ens. Stacking** | 0.45761 | 0.31295 | 0.14466 | 31.6% | 0.001489 | Overfit |

---

## 5. GAP de AUC e Gini (Complementar)

### 5.1 AUC — Treino vs OOT

| Modelo | AUC Train | AUC OOT | GAP AUC (abs) | GAP AUC (%) |
|--------|-----------|---------|---------------|-------------|
| LR L1 v2 | 0.73692 | 0.72310 | 0.01382 | 1.9% |
| CatBoost | 0.75325 | 0.73539 | 0.01786 | 2.4% |
| Random Forest | 0.75121 | 0.72778 | 0.02343 | 3.1% |
| LightGBM v2 | 0.76769 | 0.73645 | 0.03124 | 4.1% |
| XGBoost | 0.77501 | 0.73619 | 0.03882 | 5.0% |
| Ens. Top-3 Average | 0.76611 | 0.73677 | 0.02934 | 3.8% |
| Ens. Blend | 0.76036 | 0.73502 | 0.02534 | 3.3% |
| Ens. Stacking | 0.80616 | 0.70698 | 0.09918 | 12.3% |

### 5.2 Gini — Treino vs OOT

| Modelo | Gini Train | Gini OOT | GAP Gini (abs) | GAP Gini (%) |
|--------|-----------|----------|----------------|--------------|
| LR L1 v2 | 47.38 | 44.62 | 2.76 | 5.8% |
| CatBoost | 50.65 | 47.08 | 3.57 | 7.0% |
| Random Forest | 50.24 | 45.56 | 4.68 | 9.3% |
| LightGBM v2 | 53.54 | 47.29 | 6.25 | 11.7% |
| XGBoost | 55.00 | 47.24 | 7.76 | 14.1% |
| Ens. Top-3 Average | 53.22* | 47.35 | 5.87 | 11.0% |
| Ens. Blend | 52.07* | 47.00 | 5.07 | 9.7% |
| Ens. Stacking | 61.23* | 41.40 | 19.83 | 32.4% |

*Gini Train estimado como (AUC Train - 0.5) x 200, consistente com a relacao Gini = 2 x AUC - 1.

---

## 6. Diagnostico de Estabilidade Temporal

### 6.1 Degradacao Train → OOS → OOT

A degradacao progressiva (Train → OOS → OOT) indica o quanto o modelo perde performance conforme se afasta do periodo de treino:

| Modelo | Train→OOS | OOS→OOT | Train→OOT | Padrao |
|--------|-----------|---------|-----------|--------|
| LR L1 v2 | -0.009 | -0.011 | -0.020 | Degradacao gradual e uniforme |
| CatBoost | -0.007 | -0.019 | -0.026 | Degradacao ligeiramente acelerada no OOT |
| Random Forest | -0.005 | -0.029 | -0.035 | Degradacao concentrada no OOT |
| LightGBM v2 | -0.005 | -0.043 | -0.048 | Degradacao forte no OOT |
| XGBoost | -0.001 | -0.058 | -0.059 | Estavel no OOS, queda abrupta no OOT |
| Ens. Top-3 Average | — | — | -0.044 | Suavizado pelo ensemble (Top-3: LGBM+XGB+CB) |
| Ens. Stacking | +0.004 | -0.149 | -0.145 | Anomalia: OOS > Train (leakage) |

### 6.2 Interpretacao

- **XGBoost e LightGBM** mostram um padrao onde o OOS (SAFRA 202501) ainda esta muito proximo do treino, mas o OOT (SAFRAs 202502-202503) sofre queda expressiva. Isso sugere que features com drift temporal (ex: sazonalidade) impactam mais estes modelos.

- **LR L1 v2** tem a degradacao mais uniforme — perda de ~1 ponto percentual por "salto" temporal. Previsivel e monitoravel.

- **Ensemble Average** suaviza as degradacoes individuais, resultando em queda moderada e estavel.

- **Stacking** apresenta anomalia grave: KS OOS (0.462) > KS Train (0.458), indicando que o meta-learner aprendeu padroes do fold de validacao durante o treino.

---

## 7. Correlacao GAP vs PSI

O PSI (Population Stability Index) mede a estabilidade da distribuicao de scores, enquanto o GAP mede a queda de performance discriminativa. A correlacao entre ambos confirma a consistencia da analise:

| Modelo | GAP KS (%) | PSI | Observacao |
|--------|-----------|-----|------------|
| LR L1 v2 | 5.7% | 0.001361 | GAP baixo, PSI baixo |
| CatBoost | 7.0% | 0.000563 | GAP baixo, PSI mais baixo de todos |
| Random Forest | 9.3% | 0.001209 | Consistente |
| Ens. Top-3 Average | 11.2% | 0.000754 | Ensemble estabiliza PSI |
| LightGBM v2 | 12.0% | 0.000933 | GAP moderado, PSI controlado |
| XGBoost | 14.5% | 0.000817 | Maior GAP, mas PSI ainda baixo |
| Ens. Stacking | 31.6% | 0.001489 | Overfit confirmado por ambas as metricas |

**Nota**: Todos os PSIs estao muito abaixo do limiar de 0.25 (QG-05), indicando que a distribuicao dos scores e estavel mesmo quando ha degradacao de KS. Isso ocorre porque o shift e de calibracao (rankeamento relativo muda) e nao de distribuicao (formato da curva se mantem).

---

## 8. Conclusoes e Recomendacoes

### 8.1 Conclusoes

1. **Nenhum modelo individual ou ensemble apresenta overfit critico**, exceto o Stacking (rejeitado).
2. O **Ensemble Top-3 Average (Champion)** com GAP de 11.2% esta dentro da faixa aceitavel (< 15%), composto por LightGBM + XGBoost + CatBoost.
3. **CatBoost** e o modelo individual com melhor relacao estabilidade-performance (GAP 7.0%, KS OOT 0.348).
4. **LightGBM e XGBoost** possuem GAPs de 12-14.5% — aceitaveis, mas requerem monitoramento proximo para detectar degradacao futura.
5. O ensemble **suaviza** os GAPs individuais: enquanto XGBoost tem GAP de 14.5%, o Top-3 Average ensemble fica em 11.2%.

### 8.2 Recomendacoes

| # | Recomendacao | Prioridade |
|---|-------------|------------|
| 1 | Monitorar o GAP mensalmente a cada novo periodo de scoring | Alta |
| 2 | Configurar alerta se GAP do ensemble ultrapassar 20% | Alta |
| 3 | Considerar CatBoost como modelo standalone em cenarios de simplificacao | Media |
| 4 | Investigar features com drift temporal que causam a queda OOS→OOT do XGBoost | Media |
| 5 | Implementar out-of-fold stacking se quiser revisitar essa estrategia | Baixa |
| 6 | Avaliar retreino trimestral para manter GAP abaixo de 10% | Media |

---

## 9. Visualizacao

O plot de overfitting esta disponivel em `artifacts/plots/03_overfitting_analysis.png`, gerado pelo script `scripts/generate_ensemble_plots.py`.

---

## 10. Arquivos Fonte

| Arquivo | Descricao |
|---------|-----------|
| `artifacts/metrics/training_results_20260311_015100.json` | Metricas completas de treino (KS, AUC, Gini para train/OOS/OOT) |
| `artifacts/metrics/ensemble_results.json` | Metricas dos 3 ensembles (Average, Blend, Stacking) |
| `artifacts/plots/03_overfitting_analysis.png` | Grafico visual de GAP por modelo |
| `docs/model/ensemble-selection.md` | Selecao do ensemble champion |
| `docs/model/post-implementation-review.md` | Revisao pos-implementacao completa |
