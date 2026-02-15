# Apresentacao Hackathon PoD Academy — Modelo de Risco FPD
> Roteiro de apresentacao (10 min) | Claro + Oracle | Fev 2025

---

## SLIDE 1 — CAPA (15s)

**Titulo**: Modelo Preditivo de Inadimplencia (FPD)
**Subtitulo**: Migracao Pre-pago para Controle — Claro Telecom
**Rodape**: Hackathon PoD Academy | Claro + Oracle | Fevereiro 2025
**Visual**: Logo Claro + Oracle + icone de analytics

> Nota: Fundo branco, accent color azul Claro (#00A1E0) + laranja Oracle (#F80000)

---

## SLIDE 2 — SUMARIO EXECUTIVO (1 min)

**Titulo**: Resultados Alcancados

**Layout**: 4 cards grandes em destaque (KPI cards)

| KPI | Valor | Contexto |
|-----|-------|----------|
| KS do Modelo | **33.97%** | +0.87 pp acima do Score Bureau |
| Lift no Top Decil | **2.47x** | Decil 1 captura 52.7% de inadimplentes |
| Economia Mensal Estimada | **R$ 1.25M** | Estrategia de corte top 30% |
| Estabilidade (PSI) | **0.0011** | Modelo estavel entre safras |

**Frase de impacto** (centralizada abaixo):
> "Com 59 variaveis selecionadas de 398, o modelo identifica mais da metade dos inadimplentes nos primeiros 10% da base."

---

## SLIDE 3 — CONTEXTO DE NEGOCIO (1.5 min)

**Titulo**: Entendimento do Negocio

**Layout**: Lado esquerdo texto, lado direito icone/ilustracao de funil

**Problema**:
- Clientes migrando de **Pre-pago para Controle** representam alto risco de inadimplencia na primeira fatura (FPD)
- Sem modelo dedicado, a aprovacao e feita apenas com score de bureau externo

**Oportunidade**:
- ~450 mil clientes elegiveis por mes
- Fatura media: ~R$ 50
- Enriquecimento com dados internos (recargas, pagamentos, faturamento) melhora a predicao

**Objetivo**:
- Construir modelo de **First Payment Default (FPD)** combinando dados cadastrais, telco e comportamentais
- Gerar score de risco para subsidiar decisao de credito na migracao

**Nota do apresentador**: Explicar que FPD = cliente que nao paga a primeira fatura apos migrar para pos-pago. E o momento de maior risco.

---

## SLIDE 4 — ARQUITETURA DE DADOS (1.5 min)

**Titulo**: Arquitetura Medallion — Microsoft Fabric

**Layout**: Diagrama horizontal (pipeline flow)

```
[Fontes]          [Bronze]           [Silver]             [Gold]
 19 CSVs    -->   19 tabelas    -->  21 rawdata      -->  Feature Store
 Excel            staging            3 books              402 colunas
 Parquet          (raw)              (engenharia)         3.9M registros
                                     24 tabelas total     Score de Risco
```

**Detalhes abaixo do diagrama** (3 colunas):

| Bronze | Silver | Gold |
|--------|--------|------|
| Ingestao bruta | Tipagem + Dedup | Consolidacao |
| 19 tabelas staging | 21 tabelas rawdata | 402 colunas |
| Auditoria + Lineage | 3 Books de Features | 2 tabelas finais |
| Delta Lake | 90 + 94 + 114 features | Particionado por SAFRA |

**Volumes processados**:
- 99.9M transacoes de recarga
- 27.9M transacoes de pagamento
- 32.7M registros de faturamento

**Nota do apresentador**: Enfatizar que tudo roda no Microsoft Fabric com PySpark e Delta Lake. Pipeline reproduzivel e auditavel.

---

## SLIDE 5 — PERFIL DO PUBLICO-ALVO (1.5 min)

**Titulo**: Quem sao os Clientes de Migracao?

**Layout**: 3 graficos lado a lado

### Grafico 1 — Inadimplencia por Regiao (barra horizontal)
| Regiao | Taxa FPD | Volume |
|--------|----------|--------|
| Norte (N) | Maior taxa | Menor volume |
| Nordeste (NE) | Alta | Alto volume |
| Centro-Oeste (CO) | Media | Medio |
| Sudeste (SE) | Media-baixa | **Maior volume** |
| Sul (S) | Menor taxa | Medio |

**Insight**: Norte e Nordeste concentram as maiores taxas de inadimplencia, mas Sudeste tem o maior volume absoluto de defaults.

### Grafico 2 — Contratos por Regiao (treemap ou barra)
- **SP, RJ, MG** dominam em volume
- **BA, PE** representam o Nordeste
- Distribuicao segue a populacao, mas risco varia

### Grafico 3 — Faixa Etaria (histograma)
- Maior concentracao: **25-40 anos**
- Maior risco FPD: **18-25 anos** (jovens sem historico)
- Menor risco: **50+ anos** (mais estaveis)

**Nota do apresentador**: Esses dados vem do estudo de publico-alvo com 3.9M registros em 6 safras (Out/2024 a Mar/2025).

---

## SLIDE 6 — METRICAS DO MODELO (1.5 min)

**Titulo**: Performance do Modelo — LightGBM vs Logistic Regression

**Layout**: Tabela comparativa + grafico de barras

### Comparacao de Modelos (OOT — Dados Futuros)

| Metrica | LightGBM (Selecionado) | Logistic Regression L1 | Score Bureau |
|---------|----------------------|----------------------|--------------|
| **KS** | **33.97%** | 32.77% | ~33.1% |
| **AUC** | **0.7303** | 0.7207 | — |
| **Gini** | **46.06 pp** | 44.15 pp | — |
| **PSI** | **0.0011** | 0.0016 | — |

### Estabilidade Temporal (LightGBM)

| Safra | Tipo | KS | AUC |
|-------|------|-----|-----|
| 202410-412 | Treino | 37.65% | 0.7537 |
| 202501 | Validacao (OOS) | 35.89% | 0.7437 |
| 202502 | Teste (OOT1) | 34.97% | 0.7380 |
| 202503 | Teste (OOT2) | 33.23% | 0.7206 |

**Visual sugerido**: Usar imagem `artifacts/analysis/plots/panel1_performance_8plots.png`

**Frase de destaque**:
> "Degradacao controlada de apenas 4.4 pp no KS entre treino e teste — modelo robusto e estavel."

**Nota do apresentador**: KS acima de 30% e considerado bom para credito. O modelo supera o score bureau existente.

---

## SLIDE 7 — ANALISE DE SWAP (1 min)

**Titulo**: Analise de Swap-In / Swap-Out

**Layout**: Tabela + explicacao visual

### O que e Swap?
- **Swap-Out**: Clientes que o modelo NOVO reprovaria mas o bureau APROVARIA (evita defaults)
- **Swap-In**: Clientes que o modelo NOVO aprovaria mas o bureau REPROVARIA (ganha receita)
- **Net Swap positivo** = modelo novo e melhor

### Resultado por Faixa de Corte

| Estrategia | Aprovacao | Defaults Evitados | Captura |
|------------|-----------|-------------------|---------|
| Top 5% negado | 95% | 13.9% dos defaults | Alta precisao |
| **Top 10% negado** | **90%** | **24.7% dos defaults** | **Equilibrado** |
| Top 20% negado | 80% | 42.1% dos defaults | Agressivo |
| Top 30% negado | 70% | 55.8% dos defaults | Conservador |

**Visual sugerido**: Usar imagem `artifacts/analysis/plots/panel2_stability_8plots.png`

### Ranking Top Decil
- Taxa de default no Decil 1 (pior): **52.73%**
- Taxa de default no Decil 10 (melhor): **5.07%**
- **Separacao de 10x** entre melhor e pior decil

**Nota do apresentador**: O swap analysis mostra que o modelo mantem ranking estavel entre safras (overlap de 59% no top 5%).

---

## SLIDE 8 — IMPACTO NO NEGOCIO (1.5 min)

**Titulo**: Impacto Financeiro Estimado

**Layout**: 3 cenarios em cards + grafico de barras

### Cenarios de Implementacao

| Cenario | Corte | Aprovacao | Defaults/Mes Evitados | Economia Mensal |
|---------|-------|-----------|----------------------|-----------------|
| Conservador | Top 10% | 90% | ~11 mil | **~R$ 550K** |
| Moderado | Top 20% | 80% | ~19 mil | **~R$ 950K** |
| Agressivo | Top 30% | 70% | ~25 mil | **~R$ 1.25M** |

**Visual sugerido**: Usar imagem `artifacts/analysis/plots/panel3_business_8plots.png`

### Feature Selection — Eficiencia

```
398 features iniciais
  |-- IV Filter (> 0.02)
  |-- L1 Regularization
  |-- Correlation Filter (< 0.95)
  |-- LGBM Top 70
  = 59 features finais (reducao de 85%)
```

**Top 5 Features Mais Importantes** (SHAP):
1. TARGET_SCORE_02 (Score Bureau) — 29.2%
2. TARGET_SCORE_01 (Score Bureau 2) — 6.8%
3. REC_SCORE_RISCO (Score Interno Recarga) — 4.7%
4. REC_TAXA_STATUS_A (Taxa Status Ativo) — 2.5%
5. REC_QTD_LINHAS (Qtd Linhas Recarga) — 2.3%

**Frase de destaque**:
> "Dados internos de recarga, pagamento e faturamento adicionam +7 pp de KS sobre o bureau sozinho."

---

## SLIDE 9 — ENCERRAMENTO (30s)

**Titulo**: Proximos Passos e Conclusao

**Layout**: Checklist + frase final

### Entregues
- [x] Pipeline de dados completo (Bronze -> Silver -> Gold)
- [x] Feature Store com 402 colunas consolidadas
- [x] Modelo LightGBM com KS 33.97% e PSI 0.0011
- [x] Analise de swap e impacto financeiro
- [x] Monitoramento de drift implementado

### Proximos Passos
- [ ] Deploy em producao via Scoring Batch no Fabric
- [ ] Integracao com motor de decisao de credito
- [ ] Monitoramento continuo com alertas automaticos
- [ ] Retreino trimestral com novas safras

**Frase final** (centralizada, grande):
> "Um modelo robusto, estavel e interpretavel — pronto para reduzir a inadimplencia na migracao Pre-Controle."

---

## NOTAS DE DESIGN

### Paleta de Cores
- **Fundo**: Branco (#FFFFFF)
- **Texto principal**: Cinza escuro (#333333)
- **Accent primario**: Azul Claro (#00A1E0)
- **Accent secundario**: Laranja Oracle (#F80000)
- **Positivo**: Verde (#28A745)
- **Negativo**: Vermelho (#DC3545)
- **Neutro**: Cinza (#6C757D)

### Tipografia
- Titulos: **Montserrat Bold** ou **Google Sans** (32-40pt)
- Corpo: **Open Sans** ou **Roboto** (18-24pt)
- Numeros grandes: **Montserrat Black** (48-72pt)

### Visuais Disponiveis (ja gerados)
| Arquivo | Uso Sugerido |
|---------|-------------|
| `artifacts/analysis/plots/panel1_performance_8plots.png` | Slide 6 — Metricas |
| `artifacts/analysis/plots/panel2_stability_8plots.png` | Slide 7 — Swap |
| `artifacts/analysis/plots/panel3_business_8plots.png` | Slide 8 — Impacto |
| `artifacts/analysis/plots/shap_beeswarm_top40.png` | Slide 8 — Features |
| `artifacts/analysis/plots/shap_pareto_cumulative.png` | Slide 8 — Pareto |
| `docs/images/panel1_performance.png` | Alternativa Slide 6 |
| `docs/images/panel2_stability.png` | Alternativa Slide 7 |
| `docs/images/panel3_business.png` | Alternativa Slide 8 |
| `docs/images/shap_beeswarm.png` | Alternativa Slide 8 |

### Dicas de Apresentacao (10 min)
- Slide 1: 15s — Apenas se apresentar
- Slide 2: 1 min — Ir direto aos numeros, criar impacto
- Slide 3: 1.5 min — Contextualizar o problema
- Slide 4: 1.5 min — Mostrar pipeline, dar credibilidade tecnica
- Slide 5: 1.5 min — Mostrar que conhece o publico
- Slide 6: 1.5 min — Foco no KS e estabilidade
- Slide 7: 1 min — Explicar swap de forma simples
- Slide 8: 1.5 min — Focar no $ — e o que o negocio quer ouvir
- Slide 9: 30s — Fechar com confianca

---

*Hackathon PoD Academy — Claro + Oracle | Fevereiro 2025*
