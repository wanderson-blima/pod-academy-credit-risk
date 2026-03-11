# Revisao Pos-Implementacao — Pipeline de Risco de Credito

**Run ID**: `20260311_015100`
**Data**: 2026-03-10
**Plataforma**: VM.Standard.E3.Flex (4 OCPUs / 64 GB) — OCI

---

## 1. Objetivo

Desenvolver um modelo preditivo de **First Payment Default (FPD)** para clientes de telecomunicacoes da Claro, utilizando dados comportamentais, transacionais e demograficos, com pipeline completo em OCI (Object Storage, Data Science, ADW, Airflow).

---

## 2. Dados

| Dimensao | Valor |
|----------|-------|
| **Registros** | 3.900.378 |
| **SAFRAs** | 6 (202410 a 202503) |
| **Features brutas** | 402 |
| **Features selecionadas** | 110 |
| **Granularidade** | NUM_CPF + SAFRA |
| **Target** | FPD (First Payment Default) |

### Origem das Features

| Prefixo | Fonte | Quantidade Original |
|---------|-------|---------------------|
| (nenhum) | Cadastro + Telco + Target | ~103 |
| `REC_` | book_recarga_cmv | 102 |
| `PAG_` | book_pagamento | 154 |
| `FAT_` | book_faturamento | 108 |

---

## 3. Configuracao de Treino

| Parametro | Valor |
|-----------|-------|
| **Treino** | SAFRAs 202410 a 202501 |
| **OOT (Out-of-Time)** | SAFRAs 202502 a 202503 |
| **Validacao cruzada** | Estratificada por SAFRA no treino |
| **Metricas primarias** | KS, AUC, Gini |
| **Estabilidade** | PSI (Population Stability Index) |

---

## 4. Feature Selection — Funil de 5 Estagios

| Estagio | Criterio | Features Entrada | Features Saida |
|---------|----------|------------------|----------------|
| 1. Information Value | IV > 0.02 | 357 | 185 |
| 2. L1 Regularization | Coeficiente != 0 | 185 | 162 |
| 3. Correlacao | \|r\| < 0.90 | 162 | 114 |
| 4. Estabilidade PSI | PSI < 0.25 | 114 | 110 |
| 5. Anti-leakage | Remocao de vazamento | 110 | 110 |

**Resultado final**: 357 features candidatas reduzidas a **110 features** de producao.

---

## 5. Resultados dos Modelos

### 5.1 Modelos Individuais

| Modelo | KS OOT | AUC OOT | Gini OOT | PSI | QG-05 |
|--------|--------|---------|----------|-----|-------|
| LR L1 v2 | 0.33140 | 0.72310 | 44.62 | 0.001361 | PASSED |
| LightGBM v2 | 0.34943 | 0.73645 | 47.29 | 0.000933 | PASSED |
| XGBoost | 0.34938 | 0.73619 | 47.24 | 0.000817 | PASSED |
| CatBoost | 0.34821 | 0.73539 | 47.08 | 0.000563 | PASSED |
| Random Forest | 0.33700 | 0.72778 | 45.56 | 0.001209 | PASSED |

### 5.2 Ensemble Champion (Top-3 Average — LightGBM + XGBoost + CatBoost)

| Metrica | Valor |
|---------|-------|
| KS OOT | 0.35005 |
| AUC OOT | 0.73677 |
| Gini OOT | 47.35 |
| PSI | 0.000754 |

### 5.3 Ensemble Stacking (Rejeitado)

| Metrica | Valor |
|---------|-------|
| KS OOT | 0.31295 |
| AUC OOT | 0.70698 |
| Gini OOT | 41.40 |
| PSI | 0.001489 |

Rejeitado por overfitting (KS Train muito superior ao KS OOT). Ver analise detalhada em [overfitting-gap-analysis.md](overfitting-gap-analysis.md).

### 5.4 Quality Gate QG-05

| Metrica | Limiar | Ensemble | Status |
|---------|--------|----------|--------|
| KS OOT | > 0.20 | 0.35005 | PASSED |
| AUC OOT | > 0.65 | 0.73677 | PASSED |
| Gini OOT | > 30% | 47.35% | PASSED |
| PSI | < 0.25 | 0.000754 | PASSED |

**Todos os 5 modelos individuais e o ensemble passaram no QG-05.**

---

## 6. Scoring em Batch

| Metrica | Valor |
|---------|-------|
| Registros scorados | 3.900.378 |
| Score medio | 538.81 |
| Escala | 0 a 1000 |

### Faixas de Risco

| Faixa | Score | Interpretacao |
|-------|-------|---------------|
| CRITICO | 0-299 | Alto risco de inadimplencia |
| ALTO | 300-499 | Risco elevado |
| MEDIO | 500-699 | Risco moderado |
| BAIXO | 700-1000 | Baixo risco |

---

## 7. Monitoramento

- **Status geral**: overall_status=WARNING
- **Features com drift YELLOW**: 13 (PSI 0.09-0.18)
- **Features com drift RED**: 0
- **Score PSI**: todos GREEN
- **Backtesting**: ensemble supera baseline
- **Agreement entre modelos**: consistente
- **Recomendacao**: Model is stable. No action required.

---

## 8. Limitacoes Conhecidas

1. **Duplicatas no Gold bucket**: Delta Lake gravou 2 versoes de cada arquivo parquet no Object Storage. Resolvido via deduplicacao no carregamento (drop_duplicates por NUM_CPF + SAFRA).

2. **Populacao FPD NULL**: clientes sem FPD observado (novos ou tempo insuficiente para observacao) nao podem ser validados diretamente — o modelo aplica score, mas sem label para conferencia.

3. **Limitacoes do trial OCI**:
   - ARM A1 (Ampere): indisponivel em sa-saopaulo-1 (OUT_OF_HOST_CAPACITY)
   - Maximo 4 OCPUs para compute geral (E3.Flex usado para treinamento)
   - Always Free tier para ADW e Data Catalog

4. **Restricao de memoria**: E3.Flex com 64 GB RAM requer processamento em batches para o dataset completo (402 colunas). Solucao: PyArrow com leitura seletiva de colunas e subsampling para L1.

---

## 9. Recomendacoes

1. **Retreino mensal**: retreinar modelos mensalmente com SAFRAs mais recentes para manter performance
2. **Expandir populacao rotulada**: aumentar cobertura de labels FPD para reduzir a populacao NULL
3. **Considerar CatBoost standalone**: possui o menor PSI (0.000563) entre os modelos individuais — candidato a modelo unico caso se deseje simplificar o pipeline
4. **Monitorar drift por SAFRA**: implementar alertas automaticos quando PSI de feature individual ultrapassar 0.10
5. **Otimizar infraestrutura**: migrar para instancia com mais memoria (ou usar OCI Data Flow / Spark) para eliminar a necessidade de batch processing
6. **Pipeline de dados**: corrigir a escrita Delta Lake no Gold bucket para evitar duplicatas na origem
