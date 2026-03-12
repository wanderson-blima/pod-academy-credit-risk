# Analise de Swap-In / Swap-Out

**Run ID**: `20260311_015100`
**Ensemble Champion**: Top-3 Average (LightGBM v2 + XGBoost + CatBoost)
**Registros scorados**: 3.900.378 | **Score medio**: 538.06 | **Mediana**: 546

---

## 1. O que e Analise de Swap

No contexto de risco de credito para telecomunicacoes, a analise de swap avalia o impacto operacional de diferentes pontos de corte (cutoffs) na aprovacao de clientes:

- **Swap-Out**: clientes **maus** (FPD=1) que estao sendo **aprovados** pelo modelo. Representam risco financeiro direto — sao inadimplentes que passam pelo filtro.
- **Swap-In**: clientes **bons** (FPD=0) que estao sendo **rejeitados** pelo modelo. Representam perda de receita — sao adimplentes que o modelo esta barrando desnecessariamente.

O objetivo e encontrar o ponto de corte que **minimiza o swap-out** (risco) sem **maximizar o swap-in** (perda de bons clientes).

---

## 2. Populacoes

| Populacao | Registros | Descricao | FPD |
|-----------|-----------|-----------|-----|
| **Rotulada** | 2.696.621 | Clientes com FPD observado (FPD rate = 21.27%) | 0 ou 1 |
| **Nao rotulada** | 1.203.757 | Clientes sem FPD observado | NULL |

A analise de swap primaria e feita sobre a **populacao rotulada**. A populacao nao rotulada e analisada por projecao de distribuicao de scores.

**PSI entre populacoes**: 0.6435 — distribuicoes significativamente divergentes. A populacao nao rotulada tem score medio inferior (449.7 vs 603.9), indicando perfil de risco distinto.

### Distribuicao por SAFRA

| SAFRA | Total | Rotulados | Nao Rotulados | FPD Rate |
|-------|-------|-----------|---------------|----------|
| 202410 | 653.586 | 436.388 | 217.198 | 20.44% |
| 202411 | 665.737 | 465.850 | 199.887 | 21.65% |
| 202412 | 646.037 | 456.340 | 189.697 | 21.55% |
| 202501 | 667.227 | 463.673 | 203.554 | 21.32% |
| 202502 | 619.961 | 430.064 | 189.897 | 21.10% |
| 202503 | 647.830 | 444.306 | 203.524 | 21.54% |

---

## 3. Metodologia

### 3.1 Scoring das Populacoes

Ambas as populacoes (rotulada e nao rotulada) sao scoradas com o ensemble champion (Top-3 Average). O score varia de 0 (alto risco) a 1000 (baixo risco).

### 3.2 Comparacao de Distribuicoes

- **Histograma overlay**: distribuicao de scores da populacao rotulada vs nao rotulada
- **PSI entre populacoes**: 0.6435 (divergentes — projecao com ressalvas)
- Score medio rotulados: **603.9** | Score medio nao rotulados: **449.7**
- Se PSI < 0.10: populacoes similares — projecao confiavel
- Se PSI > 0.25: populacoes divergentes — projecao com ressalvas

### 3.3 Tabela de Cutoff (Resultados Reais)

| Cutoff | Aprovados | % Aprov. | FPD Aprovados | Swap-Out (% aprov) | Rejeitados | FPD Rejeitados | Swap-In (% rej) |
|--------|-----------|----------|---------------|---------------------|------------|----------------|-----------------|
| **300** | 2.514.949 | 93.26% | 18.43% | 463.589 (18.4%) | 181.672 | 60.57% | 71.631 (39.4%) |
| **400** | 2.250.450 | 83.45% | 15.60% | 351.095 (15.6%) | 446.171 | 49.88% | 223.636 (50.1%) |
| **500** | 1.877.480 | 69.62% | 12.47% | 234.202 (12.5%) | 819.141 | 41.44% | 479.713 (58.6%) |
| **600** | 1.450.020 | 53.77% | 9.69% | 140.506 (9.7%) | 1.246.601 | 34.74% | 813.477 (65.3%) |
| **700** | 977.829 | 36.26% | 7.15% | 69.915 (7.2%) | 1.718.792 | 29.31% | 1.215.077 (70.7%) |

### 3.4 Cutoffs Avaliados

| Cutoff | Interpretacao |
|--------|---------------|
| **300** | Aprovacao agressiva — 93% aprovados, FPD 18.4%, swap-out 463K |
| **400** | Aprovacao moderada — 83% aprovados, FPD 15.6%, swap-out 351K |
| **500** | Ponto medio — 70% aprovados, FPD 12.5%, swap-out 234K |
| **600** | Aprovacao conservadora — 54% aprovados, FPD 9.7%, swap-out 140K |
| **700** | Aprovacao restritiva — 36% aprovados, FPD 7.2%, swap-out 70K |

---

## 4. Como Interpretar

### 4.1 Trade-off Fundamental

```
Cutoff BAIXO (ex: 300)          Cutoff ALTO (ex: 700)
  + Mais aprovacoes (93%)         + Menos inadimplencia (7.2%)
  + Maior receita potencial       + Menor perda financeira
  - Mais inadimplentes (18.4%)    - Menos clientes (36%)
  - Maior swap-out (463K)         - Maior swap-in (1.2M)
```

### 4.2 Metricas-Chave por Cutoff

- **Taxa de aprovacao**: % de clientes com score >= cutoff
- **Taxa FPD entre aprovados**: % de inadimplentes entre os aprovados (quanto menor, melhor)
- **Swap-out count**: numero absoluto de maus clientes aprovados
- **Swap-in count**: numero absoluto de bons clientes rejeitados

### 4.3 Regra Geral

O cutoff ideal depende da **tolerancia a risco** da operacao:
- Operacao com margem alta (pre-pago) → cutoff mais baixo (aceitar mais risco)
- Operacao com margem baixa (pos-pago) → cutoff mais alto (reduzir risco)

---

## 5. Populacao Nao Rotulada

Para clientes sem FPD observado (1.203.757 registros):

1. **Score medio**: 449.7 (vs 603.9 da populacao rotulada)
2. **PSI**: 0.6435 — distribuicoes divergentes
3. **Interpretacao**: a populacao nao rotulada concentra-se em faixas de score mais baixas, indicando perfil de risco mais elevado que a populacao rotulada
4. **Implicacao**: projecoes de FPD baseadas na relacao score-vs-FPD da populacao rotulada tendem a subestimar o risco real da populacao nao rotulada

---

## 6. Cenarios Operacionais — Decisao de Negocio

A escolha do cutoff e uma **decisao estrategica** que depende do apetite de risco, margem unitaria e metas comerciais. A tabela abaixo apresenta tres cenarios com o impacto financeiro completo (economia bruta vs receita perdida):

| Cenario | Cutoff | Aprovados | FPD Aprov. | Swap-Out | Economia Bruta | Receita Perdida | **Economia Liquida** |
|---------|--------|-----------|------------|----------|----------------|-----------------|----------------------|
| **Agressivo** | 300 | 93.3% | 18.43% | 463K | R$ 4,92M | R$ 3,22M | **+R$ 1,70M** |
| **Moderado** | 400 | 83.5% | 15.60% | 351K | R$ 9,99M | R$ 10,04M | **~Breakeven** |
| **Conservador** | 700 | 36.3% | 7.15% | 70K | R$ 22,61M | R$ 54,56M | **-R$ 31,95M** |

### Analise por cenario

1. **Cutoff 300 (Agressivo)**: Unico cenario com economia liquida positiva. Maximiza volume (93%) com reducao moderada de FPD (18,4% vs 21,3%). Ideal para pre-pago ou operacoes com baixo CAC
2. **Cutoff 400 (Moderado)**: Ponto de breakeven — economia bruta e receita perdida se equilibram. Aprova 83% com FPD de 15,6%. Indicado como ponto de partida para testes
3. **Cutoff 700 (Conservador)**: Maximiza protecao contra inadimplencia (FPD 7,15%, reducao de 66%). Porem, rejeita 64% da base, gerando perda de receita de R$ 54,6M que excede as perdas evitadas (R$ 22,6M). Indicado apenas para pos-pago de alto ARPU onde a perda por inadimplente e significativamente maior que o LGD proxy usado (R$ 44,89)

> **Nota**: A receita perdida assume que bons clientes rejeitados (swap-in) gerariam receita integral. Na pratica, parte desses clientes pode ser reconquistada com ofertas alternativas (pre-pago, limites condicionais), mitigando a perda. A decisao final e da operadora.

### Fatores para a decisao

1. Margem unitaria por produto (pre-pago vs pos-pago)
2. Custo de aquisicao de cliente (CAC)
3. Perda real por inadimplencia (LGD — o proxy usado e R$ 44,89)
4. Metas comerciais de volume
5. Capacidade de re-oferta a clientes rejeitados

---

## 7. Arquivos Fonte

| Arquivo | Descricao |
|---------|-----------|
| `artifacts/swap_analysis/swap_summary.json` | Tabela de cutoffs com metricas por ponto de corte |
| `scripts/swap_analysis.py` | Script de geracao da analise de swap |

### Visualizacoes

| Plot | Descricao |
|------|-----------|
| `swap_distributions.png` | Histograma overlay: rotulados vs nao rotulados |
| `swap_cutoff_analysis.png` | Curvas de aprovacao, FPD rate e swap por cutoff |
| `swap_by_safra.png` | Distribuicao de scores por SAFRA |
| `swap_impact_table.png` | Tabela visual de impacto por cutoff |
