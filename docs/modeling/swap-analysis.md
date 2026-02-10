# Analise de Swap — Estabilidade de Ranking

## Objetivo

A analise de swap avalia a **estabilidade do ranking** de clientes entre diferentes periodos de tempo (SAFRAs). Um modelo com boa estabilidade deve manter classificacoes consistentes — clientes de alto risco devem permanecer classificados como alto risco em diferentes SAFRAs.

---

## Metodologia

### Comparacao OOT1 vs OOT2

- **OOT1** (Out-of-Time 1): SAFRA 202502
- **OOT2** (Out-of-Time 2): SAFRA 202503
- **Modelo**: LightGBM baseline v6

Para cada threshold de corte (Top 5%, 10%, 20%, 30%), comparamos:
- Quantos clientes "top risco" em OOT1 continuam "top risco" em OOT2
- Quantos novos clientes entram na faixa (swap in)
- Qual a taxa de captura de defaults

---

## Resultados

| Threshold | N Top | Overlap | Swap In | Capture Rate | Default Rate |
|-----------|-------|---------|---------|-------------|-------------|
| **Top 5%** | 43,718 | 25,834 | 17,884 | 13.86% | 59.09% |
| **Top 10%** | 87,437 | 46,107 | 41,330 | 24.73% | 52.73% |
| **Top 20%** | 174,874 | 78,441 | 96,433 | 42.08% | 44.86% |
| **Top 30%** | 262,311 | 179,955 | 82,356 | 55.82% | 39.67% |

### Interpretacao

**Estabilidade de Ranking**:
- No threshold de 10%, **52.7%** dos clientes classificados como top risco em OOT1 continuam na mesma faixa em OOT2
- No threshold de 30%, **68.7%** dos clientes overlap (179,955 de 262,311) — boa estabilidade

**Eficacia da Captura**:
- Ao negar credito para os Top 10%, o modelo captura **24.7% de todos os defaults** com taxa de default de 52.73% na faixa
- Ao negar os Top 30%, captura **55.8% de todos os defaults**

**Trade-off Negocio**:
- Corte em 10%: Nega 10% da base, evita 24.7% dos defaults → taxa de aprovacao 90%, perda reduzida em 24.7%
- Corte em 30%: Nega 30% da base, evita 55.8% dos defaults → taxa de aprovacao 70%, perda reduzida em 55.8%

---

## Analise de Valor de Negocio

### Cenario: Aplicacao do Modelo na Migracao PRE → Controle

Assumindo uma base mensal de ~450K clientes elegíveis e ticket medio de primeira fatura de R$ 50:

| Cenario | Corte | Aprovados | Defaults Evitados | Economia Estimada |
|---------|-------|-----------|-------------------|-------------------|
| Conservador | Top 10% | 405K | ~11K defaults | ~R$ 550K/mes |
| Moderado | Top 20% | 360K | ~19K defaults | ~R$ 950K/mes |
| Agressivo | Top 30% | 315K | ~25K defaults | ~R$ 1.25M/mes |

> Valores ilustrativos para demonstrar o impacto potencial do modelo.

---

## Visualizacao

<p align="center">
  <img src="../images/panel2_stability.png" alt="Stability Panel" width="100%">
  <br><em>Painel de estabilidade incluindo analise de swap, decile analysis e PSI</em>
</p>

---

*Fonte: [`artifacts/analysis/csv/swap_analysis_results.csv`](../../artifacts/visualization-plot/analysis_v6/swap_analysis_results.csv)*
