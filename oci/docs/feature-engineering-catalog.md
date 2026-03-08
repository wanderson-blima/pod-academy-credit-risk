# Feature Engineering Catalog — Ensemble v1

Documentacao completa das 47 features criadas durante a Fase 2 do pipeline de Credit Risk FPD.
Todas passaram pelos filtros de selecao: IV > 0.02, Correlacao < 0.95, PSI < 0.20.

**Pipeline**: 402 originais → +47 engineered (449) → 86 (IV) → 78 (correlacao) → **72 finais**

---

## 1. Missing Patterns (7 features)

Features que capturam padroes de dados faltantes — indicadores de falta de relacionamento com o servico.

| Feature | Tipo | Descricao | Justificativa |
|---------|------|-----------|---------------|
| `MISSING_REC_COUNT` | int | Contagem de colunas `REC_*` nulas por cliente | Clientes sem recargas tendem a ter mais campos nulos — indica menor engajamento |
| `MISSING_PAG_COUNT` | int | Contagem de colunas `PAG_*` nulas | Ausencia de dados de pagamento pode indicar inadimplencia |
| `MISSING_FAT_COUNT` | int | Contagem de colunas `FAT_*` nulas | Falta de faturas pode indicar conta recente ou inativa |
| `MISSING_TOTAL_RATIO` | float | Proporcao total de campos numericos nulos | Visao holistica de completude dos dados — clientes com muitos nulls sao perfis de risco |
| `PAG_QTD_PAGAMENTOS_TOTAL_IS_NULL` | binary | 1 se `PAG_QTD_PAGAMENTOS_TOTAL` e null | Flag direta: sem historico de pagamentos |
| `PAG_TAXA_PAGAMENTOS_COM_JUROS_IS_NULL` | binary | 1 se `PAG_TAXA_PAGAMENTOS_COM_JUROS` e null | Ausencia de dado de juros indica falta de fatura ou pagamento |
| `PAG_DIAS_ENTRE_FATURAS_IS_NULL` | binary | 1 se `PAG_DIAS_ENTRE_FATURAS` e null | Sem intervalo entre faturas sugere conta nova |

**Metodo**: `df[cols].isnull().sum(axis=1)` e `df[col].isnull().astype(int)`

---

## 2. Cross-Domain Interactions (7 features)

Combinacoes entre dominios (REC_, PAG_, FAT_, SCORE) que capturam relacoes nao-lineares.

| Feature | Tipo | Formula | Justificativa |
|---------|------|---------|---------------|
| `SCORE_X_REC_RISK` | float | `TARGET_SCORE_02 * REC_SCORE_RISCO` | Interacao entre score bureau e risco de recarga — amplifica sinal quando ambos indicam risco |
| `DIFF_SCORE_BUREAU` | float | `TARGET_SCORE_01 - TARGET_SCORE_02` | Divergencia entre dois scores bureau — discrepancia pode indicar fraude ou dados inconsistentes |
| `RATIO_REC_PAG` | float | `REC_QTD_RECARGAS_TOTAL / PAG_QTD_PAGAMENTOS_TOTAL` | Proporcao recargas vs pagamentos — valor alto indica muitas recargas mas poucos pagamentos |
| `RATIO_FAT_PAG` | float | `FAT_QTD_FATURAS_TOTAL / PAG_QTD_PAGAMENTOS_TOTAL` | Proporcao faturas vs pagamentos — ratio > 1 indica faturas em aberto |
| `REC_PAG_GAP` | float | `REC_QTD_RECARGAS - PAG_QTD_PAGAMENTOS` | Diferenca absoluta recargas-pagamentos — gap positivo = mais recargas que pagamentos |
| `BILLING_LOAD` | float | `FAT_VLR_TOTAL_FATURAS / PAG_QTD_PAGAMENTOS` | Carga media por pagamento — valor alto indica pagamentos insuficientes para cobrir faturas |
| `HIGH_RISK_COMBO` | binary | `(SCORE_02 < 500) & (JUROS > 0.3)` | Flag de risco combinado: score baixo E alta taxa de juros juntos |

**Metodo**: Operacoes aritmeticas entre colunas de dominios diferentes. Divisoes usam `fillna(1).replace(0, 1)` para evitar divisao por zero.

---

## 3. Ratios Normalizados (4 features)

Proporcoes que normalizam comportamento em escala comparavel.

| Feature | Tipo | Formula | Justificativa |
|---------|------|---------|---------------|
| `REC_ONLINE_RATIO` | float | `REC_QTD_RECARGAS_ONLINE / REC_QTD_RECARGAS_TOTAL` | % de recargas feitas online — clientes digitais tem perfil diferente de risco |
| `PAG_JUROS_RATIO` | float | `PAG_TAXA_PAGAMENTOS_COM_JUROS` (direta) | Taxa de pagamentos com juros — indicador direto de atraso |
| `FAT_FIRST_RATIO` | float | `FAT_VLR_PRIMEIRA_FATURA / FAT_VLR_TOTAL_FATURAS` | Proporcao da 1a fatura sobre total — fatura inicial alta relativa ao total indica risco |
| `REC_PLATFORM_DIVERSITY` | float | `REC_QTD_CANAIS_DISTINTOS / REC_QTD_RECARGAS_TOTAL` | Diversidade de canais de recarga — mais canais pode indicar cliente mais ativo e engajado |

**Metodo**: Divisao simples com tratamento de zeros e nulls.

---

## 4. Temporal (3 features)

Padroes temporais dentro do snapshot do SAFRA.

| Feature | Tipo | Formula | Justificativa |
|---------|------|---------|---------------|
| `TENURE_BUCKET` | ordinal (0-4) | `pd.cut(TEMPO_CONTA_MESES, bins=[-1,3,6,12,24,999])` | Faixa de tempo de conta: 0-3m, 3-6m, 6-12m, 12-24m, 24m+ — contas novas tem maior risco |
| `RECENCY_GAP` | float | `REC_DIAS_DESDE_ULTIMA_RECARGA - PAG_DIAS_DESDE_ULTIMO_PAGAMENTO` | Diferenca de recencia entre recarga e pagamento — gap positivo = parou de pagar antes de recarregar |
| `RECHARGE_VELOCITY_CHANGE` | float | `REC_QTD_RECARGAS_TOTAL * REC_DIAS_ENTRE_RECARGAS` | Proxy de velocidade de recarga — combina frequencia e intervalo |

**Metodo**: `pd.cut` para binning, operacoes aritmeticas para gaps e velocidade.

---

## 5. Non-linear Transforms (12 features)

Transformacoes log/sqrt para features com distribuicao enviesada (skewed).

| Feature | Tipo | Origem | Justificativa |
|---------|------|--------|---------------|
| `REC_VLR_CREDITO_STDDEV_LOG` | float | `log1p(REC_VLR_CREDITO_STDDEV)` | Reduz impacto de outliers na variabilidade de creditos |
| `REC_VLR_CREDITO_STDDEV_SQRT` | float | `sqrt(REC_VLR_CREDITO_STDDEV)` | Transformacao mais suave que log |
| `REC_VLR_REAL_STDDEV_LOG` | float | `log1p(REC_VLR_REAL_STDDEV)` | Variabilidade de valores reais de recarga (log) |
| `REC_VLR_REAL_STDDEV_SQRT` | float | `sqrt(REC_VLR_REAL_STDDEV)` | Variabilidade de valores reais (sqrt) |
| `PAG_VLR_PAGAMENTO_FATURA_STDDEV_LOG` | float | `log1p(PAG_VLR_PAG_FATURA_STDDEV)` | Variabilidade de pagamentos (log) — alta variabilidade = risco |
| `PAG_VLR_PAGAMENTO_FATURA_STDDEV_SQRT` | float | `sqrt(PAG_VLR_PAG_FATURA_STDDEV)` | Variabilidade de pagamentos (sqrt) |
| `REC_QTD_RECARGAS_TOTAL_LOG` | float | `log1p(REC_QTD_RECARGAS_TOTAL)` | Quantidade de recargas (log) — distribuicao muito skewed |
| `REC_QTD_RECARGAS_TOTAL_SQRT` | float | `sqrt(REC_QTD_RECARGAS_TOTAL)` | Quantidade de recargas (sqrt) |
| `PAG_QTD_PAGAMENTOS_TOTAL_LOG` | float | `log1p(PAG_QTD_PAGAMENTOS_TOTAL)` | Quantidade de pagamentos (log) |
| `PAG_QTD_PAGAMENTOS_TOTAL_SQRT` | float | `sqrt(PAG_QTD_PAGAMENTOS_TOTAL)` | Quantidade de pagamentos (sqrt) |
| `SCORE02_QUARTILE` | ordinal (0-3) | `pd.qcut(TARGET_SCORE_02, q=4)` | Score bureau em quartis — discretiza para capturar efeitos nao-lineares |

**Nota**: Apenas 11 listadas — a contagem original de 12 inclui `SCORE02_QUARTILE` como non-linear.

**Metodo**: `np.log1p()` (log(1+x) para evitar log(0)), `np.sqrt()`, `pd.qcut()`. Valores negativos clipados para 0 antes da transformacao.

---

## 6. PCA Components (15 features)

Componentes principais por dominio para reduzir dimensionalidade e correlacao.

| Feature | Dominio | Componente | Justificativa |
|---------|---------|------------|---------------|
| `PCA_REC_0` a `PCA_REC_4` | Recarga (REC_) | 5 componentes | Comprime ~84 features de recarga em 5 dimensoes ortogonais |
| `PCA_PAG_0` a `PCA_PAG_4` | Pagamento (PAG_) | 5 componentes | Comprime ~86 features de pagamento em 5 dimensoes |
| `PCA_FAT_0` a `PCA_FAT_4` | Faturamento (FAT_) | 5 componentes | Comprime ~113 features de faturamento em 5 dimensoes |

**Metodo**:
1. `StandardScaler().fit(X_train)` — normaliza usando **apenas dados de treino**
2. `PCA(n_components=5).fit(X_train_scaled)` — extrai componentes do **treino**
3. `.transform(X_all)` — aplica a todos os dados (treino + OOS + OOT)

**Variancia Explicada**:
- REC_: ~58% da variancia em 5 componentes
- PAG_: ~59%
- FAT_: ~57%

**IMPORTANTE**: Os objetos `StandardScaler` e `PCA` fitted NAO foram persistidos como artefatos separados. Isso significa que ao recriar as features para inference, os componentes PCA serao diferentes. **Recomendacao para v2: salvar scalers e PCA como pickle junto com os modelos.**

---

## Pipeline de Selecao

```
402 colunas originais
    |
    +47 engineered features
    |
449 total
    |
    IV Filter (>0.02) → 86 features
    |
    Correlacao (<0.95) → 78 features
    |
    PSI Stability (<0.20) → 72 features finais
```

### Filtros Detalhados

| Filtro | Entrada | Saida | Removidas | Criterio |
|--------|---------|-------|-----------|----------|
| Information Value | 106 numericas | 86 | 20 | IV < 0.02 (sem poder preditivo) |
| Correlacao Pearson | 86 | 78 | 8 | Correlacao > 0.95 (redundantes) |
| PSI Temporal | 78 | 72 | 6 | PSI > 0.20 entre SAFRAs (instavel) |

### Feature Eliminada por Drift (Notavel)

- `REC_DIAS_ENTRE_RECARGAS`: PSI = **2.45** (SAFRA 202503) — drift severo, eliminada pelo filtro de estabilidade

---

## Dominio das 72 Features Finais

| Dominio | Prefixo | Features Originais | Engineered | Total Final |
|---------|---------|-------------------|------------|-------------|
| Cadastro + Bureau | (nenhum) | ~15 | 3 (DIFF_SCORE, SCORE_X_REC, SCORE02_Q) | ~12 |
| Recarga | `REC_` | ~20 | 9 (missing, ratio, PCA, log/sqrt) | ~18 |
| Pagamento | `PAG_` | ~15 | 11 (missing, ratio, PCA, log/sqrt) | ~16 |
| Faturamento | `FAT_` | ~10 | 7 (missing, ratio, PCA) | ~11 |
| Cross-domain | misto | 0 | 8 (interactions, combos) | ~8 |
| Temporal | misto | 0 | 3 (tenure, recency, velocity) | ~3 |
| Outros | misto | ~5 | 6 (missing counts) | ~4 |

---

## Artefatos no OCI

| Artefato | Bucket Path | Tamanho |
|----------|-------------|---------|
| Lista de features | `model_artifacts/ensemble_v1/ensemble/new_features.json` | 1.3 KB |
| Feature store engineered | `model_artifacts/ensemble_v2_top3/feature_store_engineered.parquet` | 1.3 GB |
| Hiperparametros | `model_artifacts/ensemble_v1/hpo/best_params_all.json` | 953 B |

---

*Feature Engineering Catalog — Hackathon PoD Academy (Claro + Oracle)*
*Pipeline executado em 2026-03-08 em OCI VM.Standard.E5.Flex*
