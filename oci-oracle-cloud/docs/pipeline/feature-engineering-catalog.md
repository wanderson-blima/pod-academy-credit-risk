# Catalogo de Engenharia de Features - Funil de Selecao

## Visao Geral do Funil

| Estagio | Metodo | Entrada | Saida | Removidas |
|---------|--------|---------|-------|-----------|
| 1. Filtro IV | IV > 0.02 | 357 | 185 | 172 |
| 2. Regressao L1 | Coeficientes nao-zero | 185 | 162 | 23 |
| 3. Filtro Correlacao | \|r\| < 0.90 | 162 | 114 | 48 |
| 4. Filtro PSI | PSI < 0.25 | 114 | 110 | 4 |
| 5. Anti-leakage | Padroes de vazamento | 110 | 110 | 0 |

**Resultado final**: 110 features selecionadas de 357 candidatas (retencao de 30.8%)

**Fonte**: `artifacts/funnel_summary.json`, `artifacts/selected_features.json`

---

## Estagio 1 - Filtro de Information Value (IV)

### Criterio

**IV > 0.02**: Remover features sem poder preditivo univariado.

### Descricao

O Information Value (IV) mede o poder preditivo univariado de cada feature em relacao a variavel alvo (FPD). Baseia-se na distribuicao de bons vs. maus em cada faixa (bin) da feature:

```
IV = SUM( (%Bons_i - %Maus_i) * ln(%Bons_i / %Maus_i) )
```

### Resultado

- **Entrada**: 357 features candidatas (402 colunas - chaves - auditoria)
- **Saida**: 185 features com IV > 0.02
- **Removidas**: 172 features (maioria com IV = 0.00, features constantes ou sem variancia)

### Interpretacao do IV

| Faixa IV | Poder Preditivo | Qtd Selecionadas |
|----------|-----------------|-------------------|
| 0.02 - 0.10 | Fraco | ~95 |
| 0.10 - 0.30 | Medio | ~70 |
| 0.30 - 0.50 | Forte | ~15 |
| > 0.50 | Muito forte | ~5 (TARGET_SCORE_02 = 0.6377) |

### Top 10 por IV

| Feature | IV |
|---------|-----|
| TARGET_SCORE_02 | 0.6377 |
| TARGET_SCORE_01 | 0.4271 |
| FAT_TAXA_PRIMEIRA_FAT | 0.3677 |
| FAT_DIAS_DESDE_ATIVACAO_CONTA | 0.3428 |
| FAT_DIAS_ATRASO_MAX | 0.3279 |
| FAT_VLR_PRIMEIRA_FAT | 0.2957 |
| FAT_QTD_FATURAS_PRIMEIRA | 0.2519 |
| FAT_QTD_FATURAS_NAO_ISENTAS | 0.2410 |
| FAT_AMPLITUDE_RELATIVA_FAT | 0.2010 |
| PAG_VLR_ALOCACAO_PYM | 0.1825 |

---

## Estagio 2 - Regressao L1 (Lasso)

### Criterio

**Coeficientes nao-zero**: Manter apenas features com coeficiente != 0 na Regressao Logistica L1.

### Descricao

A Regressao Logistica com penalidade L1 (Lasso) realiza selecao automatica de features ao forcar coeficientes irrelevantes a zero. O parametro de regularizacao `C` controla a intensidade da penalidade.

### Implementacao

- **Modelo**: LogisticRegression(penalty='l1', solver='saga')
- **Dados**: Amostra de treinamento (50K linhas por limitacao de memoria)
- **Features padronizadas**: StandardScaler antes do ajuste
- **Criterio**: Manter features com |coeficiente| > 0

### Resultado

- **Entrada**: 185 features (do Estagio 1)
- **Saida**: 162 features com coeficientes nao-zero
- **Removidas**: 23 features com coeficiente zerado pelo L1

### Justificativa

Features removidas pelo L1 sao redundantes ou possuem informacao ja capturada por outras features. A penalidade L1 prefere solucoes esparsas, selecionando o subconjunto mais informativo.

---

## Estagio 3 - Filtro de Correlacao

### Criterio

**|r| < 0.90**: Remover pares altamente correlacionados, mantendo a feature com maior IV.

### Descricao

Features altamente correlacionadas (|r| >= 0.90) carregam informacao redundante e podem causar instabilidade nos coeficientes do modelo. Para cada par correlacionado, a feature com menor IV e removida.

### Implementacao

1. Calcular matriz de correlacao de Pearson (162 x 162)
2. Identificar pares com |r| >= 0.90
3. Para cada par, manter a feature com maior IV
4. **Desempate por IV**: Para pares correlacionados, manter a feature com maior Information Value

### Resultado

- **Entrada**: 162 features (do Estagio 2)
- **Saida**: 114 features
- **Removidas**: 48 features por alta correlacao

### Observacoes

- A maioria das remocoes ocorreu dentro do mesmo grupo de prefixo (ex: FAT_VLR_FAT_BRUTO_TOTAL correlacionado com FAT_VLR_FAT_LIQUIDO_TOTAL)
- Features de valor total vs. valor medio frequentemente correlacionadas
- O desempate por referencia Fabric preservou features ja validadas no ambiente Microsoft

---

## Estagio 4 - Filtro de PSI (Population Stability Index)

### Criterio

**PSI < 0.25**: Remover features temporalmente instaveis entre treino e OOT.

### Descricao

O PSI mede a estabilidade da distribuicao de uma feature entre dois periodos:

```
PSI = SUM( (P_i - Q_i) * ln(P_i / Q_i) )
```

Onde P = distribuicao no treino (202410-202501) e Q = distribuicao no OOT (202502-202503).

### Resultado

- **Entrada**: 114 features (do Estagio 3)
- **Saida**: 110 features com PSI < 0.25
- **Removidas**: 4 features com PSI >= 0.25 (instabilidade temporal)

### Features Removidas (PSI >= 0.25)

Baseado nos dados de `psi_scores.csv`, as features com PSI RED (> 0.25) que foram removidas neste estagio incluem features temporais fortemente correlacionadas com o tempo de relacionamento do cliente (ex: dias desde primeira fatura, meses ativos).

### Distribuicao de PSI nas 110 Features Finais

| Faixa PSI | Alerta | Quantidade |
|-----------|--------|------------|
| 0.00 - 0.10 | GREEN | 99 |
| 0.10 - 0.25 | YELLOW | 11 |
| **Total** | | **110** |

---

## Estagio 5 - Anti-leakage

### Criterio

Remover features com vazamento de informacao (data leakage):
- Padroes: `VLR_FPD`, `TARGET_FPD`, `_LEAKAGE`
- Features com |corr| > 0.95 com a variavel alvo FPD

### Descricao

Features com leakage sao aquelas que contem informacao do futuro (variavel alvo) no momento da predicao. Incluem:
- Features calculadas usando o proprio FPD
- Features derivadas de eventos posteriores ao ponto de decisao
- Features com correlacao quase perfeita com o target

### Resultado

- **Entrada**: 110 features (do Estagio 4)
- **Saida**: 110 features
- **Removidas**: 0 (nenhuma feature com leakage detectada)

### Justificativa

Nenhuma feature passou pelos estagios anteriores com padroes de leakage. Os filtros de IV e correlacao ja haviam removido candidatas suspeitas.

---

## Distribuicao Final por Grupo

| Grupo | Candidatas (357) | Apos IV | Apos L1 | Apos Corr | Apos PSI | Final |
|-------|------------------|---------|---------|-----------|----------|-------|
| FAT_ | ~108 | ~65 | ~55 | ~40 | 36 | 36 |
| PAG_ | ~96 | ~50 | ~40 | ~28 | 25 | 25 |
| REC_ | ~92 | ~45 | ~40 | ~33 | 31 | 31 |
| var_ | ~93 | ~22 | ~20 | ~19 | 19 | 19 |
| TARGET_ | 2 | 2 | 2 | 2 | 2 | 2 |
| Outros | ~10 | ~1 | ~5 | ~0 | 0 | 0 |

---

## Metricas do Modelo com 110 Features

### Ensemble Champion (Top-3 Average: LGBM+XGB+CB)

| Metrica | Valor |
|---------|-------|
| KS OOT | 0.35005 |
| AUC OOT | 0.73677 |
| Gini OOT | 47.35% |
| PSI Modelo | 0.000754 |

### Quality Gate QG-05: APROVADO

| Criterio | Limiar | Resultado | Status |
|----------|--------|-----------|--------|
| KS | > 0.20 | 0.35005 | APROVADO |
| AUC | > 0.65 | 0.73677 | APROVADO |
| Gini | > 30% | 47.35% | APROVADO |
| PSI | < 0.25 | 0.000754 | APROVADO |

---

## Scoring em Producao

| Metrica | Valor |
|---------|-------|
| Registros scorados | 3.900.378 |
| Score medio | 538.81 |
| Score mediano | 542 |
| Run ID | 20260311_015100 |

### Faixas de Risco

| Faixa | Intervalo | Descricao |
|-------|-----------|-----------|
| CRITICO | < 300 | Alto risco de inadimplencia |
| ALTO | 300 - 499 | Risco elevado |
| MEDIO | 500 - 699 | Risco moderado |
| BAIXO | >= 700 | Baixo risco |
