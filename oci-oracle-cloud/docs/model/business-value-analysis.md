# Analise de Valor Financeiro — Modelo de Credit Risk FPD

**Run ID**: `20260311_015100`
**Ensemble Champion**: Top-3 Average (LightGBM + XGBoost + CatBoost)
**Base scorada**: 3.900.378 clientes | 6 SAFRAs (202410–202503)

---

## 1. Resumo Executivo

> O modelo de credit risk permite reduzir a taxa de FPD de 21,3% para 7,2%–18,4% dependendo do cutoff aplicado, evitando ate **R$ 22,6M em perdas brutas** (cutoff 700). Porem, a **economia liquida** depende do trade-off entre perdas evitadas e receita perdida por rejeicao de bons clientes. O cutoff ideal e uma **decisao de negocio** que depende da estrategia comercial da operadora.

| Cenario | Cutoff | Economia Bruta | Receita Perdida | **Economia Liquida** | FPD Aprov. |
|---------|--------|----------------|-----------------|----------------------|------------|
| **Agressivo** | 300 | R$ 4,92M | R$ 3,22M | **+R$ 1,70M** | 18,4% |
| **Equilibrado** | 400 | R$ 9,99M | R$ 10,04M | **-R$ 0,05M** | 15,6% |
| **Conservador** | 700 | R$ 22,61M | R$ 54,56M | **-R$ 31,95M** | 7,2% |

| Indicador | Valor |
|-----------|-------|
| Perdas brutas evitadas (cutoff 700) | R$ 22,6M |
| Receita perdida por rejeicao (cutoff 700) | R$ 54,6M |
| Economia liquida (cutoff 700) | **-R$ 31,95M** |
| Reducao de FPD | 21,3% → 7,2% (-66%) no cutoff 700 |
| Base scorada | 3,9M clientes |
| Modelo champion | Ensemble Top-3 (KS=0.3501, AUC=0.7368) |

> **Nota**: A economia bruta considera apenas as perdas evitadas (defaults barrados × LGD). A economia liquida desconta a receita perdida por rejeicao de bons clientes (swap-in × LGD proxy). O cutoff 300 e o unico com economia liquida positiva; cutoffs mais altos protegem mais contra inadimplencia mas rejeitam volume significativo de bons pagadores.

---

## 2. Contexto Financeiro — Dados Reais das EDAs

Os valores abaixo foram extraidos dos metadados enriquecidos do faturamento (dados reais da Claro):

| Variavel | Mediana (p50) | Media | Fonte |
|----------|---------------|-------|-------|
| VAL_FAT_LIQUIDO | R$ 44,89 | R$ 70,76 | metadados_enriquecidos_dados_faturamento.json |
| VAL_FAT_BRUTO | R$ 56,21 | R$ 99,42 | idem |
| VAL_FAT_ABERTO | R$ 44,89 | — | idem (proxy LGD) |
| VAL_FAT_ABERTO_LIQ | R$ 43,54 | — | idem |

---

## 3. Proxy de Perda (LGD)

Para estimar o impacto financeiro do modelo, utilizamos **VAL_FAT_ABERTO** (valor de fatura em aberto) como proxy da perda por default (Loss Given Default — LGD):

- **LGD proxy** = Mediana de VAL_FAT_ABERTO = **R$ 44,89**
- Representa o valor mediano que a operadora deixa de receber quando um cliente entra em default no primeiro pagamento (FPD)

> **Nota**: Este e um proxy conservador. A perda real pode incluir custos de cobranca, churn subsequente e custo de aquisicao do cliente (CAC).

---

## 4. Perda Baseline (Sem Modelo)

Sem nenhum modelo de credit risk aplicado, todos os clientes sao aprovados:

| Metrica | Valor | Fonte |
|---------|-------|-------|
| Total de clientes labelados | 2.696.621 | scoring_summary.json |
| Taxa FPD baseline | 21,27% | swap_summary.json |
| Total de defaults (6 SAFRAs) | 573.630 | scoring_summary.json (soma fpd_count) |
| Defaults por SAFRA (media) | 95.605 | idem |
| **Perda total baseline** | **R$ 25,75M** | 573.630 × R$ 44,89 |
| Perda anualizada (×2) | **R$ 51,50M** | Projecao para 12 SAFRAs |

---

## 5. Impacto por Cutoff de Score

A tabela abaixo mostra o impacto financeiro de cada cutoff de score, baseado nos dados reais do `swap_summary.json`:

| Cutoff | Aprovados | % Aprovados | FPD Aprovados | Defaults Evitados | Perda Residual | Economia Bruta |
|--------|-----------|-------------|---------------|-------------------|----------------|----------------|
| 300 | 2.514.949 | 93,3% | 18,4% | 110.041 | R$ 20,83M | **R$ 4,92M** |
| 400 | 2.250.450 | 83,5% | 15,6% | 222.399 | R$ 15,76M | **R$ 9,99M** |
| 500 | 1.877.480 | 69,6% | 12,5% | 339.428 | R$ 10,52M | **R$ 15,23M** |
| 600 | 1.450.020 | 53,8% | 9,7% | 433.173 | R$ 6,31M | **R$ 19,44M** |
| **700** | **977.829** | **36,3%** | **7,2%** | **503.715** | **R$ 3,14M** | **R$ 22,61M** |

> **Importante**: Os valores acima representam a **economia bruta** (perdas evitadas). Para a economia liquida, descontar a receita perdida por rejeicao de bons clientes — ver Secao 7.

### Calculo detalhado (cutoff 700)

```
Defaults aprovados  = 977.829 × 7,15% = 69.915
Perda residual      = 69.915 × R$ 44,89 = R$ 3,14M
Defaults evitados   = 573.630 - 69.915 = 503.715
Economia            = R$ 25,75M - R$ 3,14M = R$ 22,61M
```

---

## 6. Custo vs Retorno (ROI)

### Custo da Infraestrutura OCI

| Recurso | Tipo | Custo Estimado/mes |
|---------|------|--------------------|
| Orchestrator VM | E3.Flex 4 OCPUs / 64 GB | ~R$ 120 |
| Object Storage | 4 buckets (~10 GB) | ~R$ 5 |
| ADW | Always Free | R$ 0 |
| Data Catalog | Always Free | R$ 0 |
| Networking | VCN + Subnet | ~R$ 43 |
| **Total** | | **~R$ 168/mes** |

### ROI (sobre perdas brutas evitadas)

| Metrica | Valor |
|---------|-------|
| Custo anual OCI | ~R$ 2.016 |
| Perdas brutas evitadas (cutoff 700) | R$ 22,61M |
| **ROI bruto** | **> 11.000x** |
| Payback | < 1 dia |

> **Nota**: O ROI acima e calculado sobre as **perdas brutas evitadas** vs custo de infraestrutura. Nao inclui a receita perdida por rejeicao de bons clientes (ver Secao 7). O custo-beneficio real depende da estrategia de cutoff e de acoes de mitigacao para clientes rejeitados (re-ofertas, produtos alternativos).

---

## 7. Trade-off: Receita Perdida vs Reducao de Default

Ao rejeitar clientes com score baixo, a operadora tambem perde receita de bons clientes rejeitados (falsos positivos). Analise do trade-off:

| Cutoff | Rejeitados | Bons Rejeitados (swap-in) | Receita Perdida Estimada | Economia Liquida |
|--------|------------|---------------------------|--------------------------|------------------|
| 300 | 181.672 | 71.631 (39,4%) | R$ 3,22M | R$ 1,70M |
| 400 | 446.171 | 223.636 (50,1%) | R$ 10,04M | -R$ 0,05M |
| 500 | 819.141 | 479.713 (58,6%) | R$ 21,53M | -R$ 6,30M |
| 600 | 1.246.601 | 813.477 (65,3%) | R$ 36,52M | -R$ 17,08M |
| 700 | 1.718.792 | 1.215.077 (70,7%) | R$ 54,56M | -R$ 31,95M |

> **Nota importante**: A "Receita Perdida Estimada" assume que TODOS os bons rejeitados gerariam receita integral. Na pratica, muitos desses clientes podem ser reconquistados com ofertas diferenciadas ou limites de credito condicionais. O cutoff ideal depende da estrategia de negocio da operadora — o modelo fornece a **informacao** para essa decisao.

### Cenarios de Cutoff — Decisao de Negocio

A escolha do cutoff e uma **decisao estrategica** que depende do apetite de risco, margem unitaria e metas comerciais da operadora:

| Cenario | Cutoff | Economia Bruta | Receita Perdida | Economia Liquida | FPD Aprov. | Aprovados |
|---------|--------|----------------|-----------------|------------------|------------|-----------|
| **Agressivo** | 300 | R$ 4,92M | R$ 3,22M | **+R$ 1,70M** | 18,4% | 93,3% |
| **Moderado** | 400 | R$ 9,99M | R$ 10,04M | **~Breakeven** | 15,6% | 83,5% |
| **Conservador** | 700 | R$ 22,61M | R$ 54,56M | **-R$ 31,95M** | 7,2% | 36,3% |

1. **Cutoff 300 (Agressivo)**: Unico cenario com economia liquida positiva (+R$ 1,70M). Aprova 93% da base mas mantem FPD em 18,4% — reducao de 14% vs baseline
2. **Cutoff 400 (Moderado)**: Ponto de breakeven. Aprova 83% da base com FPD de 15,6% — reducao de 27% vs baseline
3. **Cutoff 700 (Conservador)**: Maximiza protecao contra inadimplencia (FPD 7,2%, -66%), porem a receita perdida por rejeicao de bons clientes (R$ 54,6M) excede significativamente as perdas evitadas (R$ 22,6M)

> **Recomendacao**: O modelo fornece a **informacao** para a decisao. Clientes rejeitados nao sao perdidos — podem receber ofertas alternativas (pre-pago, limites condicionais, re-avaliacao periodica). A mitigacao da receita perdida depende dessas acoes complementares

---

## 8. Analise de Sensibilidade ao LGD

A economia **bruta** varia conforme a premissa de perda (LGD). Sensibilidade para cutoff 700:

| Premissa LGD | Valor | Perda Baseline | Economia Bruta (cutoff 700) |
|--------------|-------|----------------|----------------------|
| Percentil 25 | R$ 19,90 | R$ 11,41M | R$ 10,02M |
| **Mediana (p50)** | **R$ 44,89** | **R$ 25,75M** | **R$ 22,61M** |
| Media | R$ 70,76 | R$ 40,60M | R$ 35,65M |
| Percentil 75 | R$ 85,00* | R$ 48,76M | R$ 42,82M |

*Percentil 75 estimado com base na distribuicao dos dados.

> Em todos os cenarios de LGD, as perdas brutas evitadas sao substanciais. Porem, a economia liquida (descontando receita perdida) depende do cutoff — ver Secao 7 para a analise completa de trade-off.

---

## 9. Fontes de Dados

Todos os valores financeiros sao rastreaveais a dados reais do projeto:

| Dado | Arquivo | Campo |
|------|---------|-------|
| Valores de faturamento | `fabric/schemas/enriched-metadata/metadados_enriquecidos_dados_faturamento.json` | p50 de VAL_FAT_ABERTO, VAL_FAT_BRUTO, VAL_FAT_LIQUIDO |
| Analise de cutoffs | `artifacts/swap_analysis/swap_summary.json` | cutoff_analysis[] |
| FPD counts por SAFRA | `artifacts/scoring/scoring_summary.json` | safra_metrics[].fpd_count |
| Metricas do ensemble | `artifacts/metrics/training_results_20260311_015100.json` | Resultados do champion |
| Taxa FPD baseline | `artifacts/swap_analysis/swap_summary.json` | labeled_fpd_rate |

---

*Documento gerado: 2026-03-11 | Projeto: Hackathon PoD Academy (Claro + Oracle) | Plataforma: OCI sa-saopaulo-1*
