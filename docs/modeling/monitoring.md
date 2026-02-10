# Monitoramento e Drift — Framework de Acompanhamento

## Objetivo

O framework de monitoramento detecta degradacao do modelo ao longo do tempo, comparando distribuicoes de scores e features entre o periodo de treino (baseline) e novas SAFRAs. Alertas sao gerados automaticamente quando thresholds sao ultrapassados.

---

## Configuracao

| Parametro | Valor |
|-----------|-------|
| **Modelo** | credit-risk-fpd-lgbm_baseline_v6 |
| **Baseline** | SAFRAs 202410, 202411, 202412 (treino) |
| **Frequencia** | Mensal (a cada nova SAFRA) |
| **Top Features Monitoradas** | 20 (por importancia LGBM) |

### Thresholds

| Metrica | Verde | Amarelo | Vermelho |
|---------|-------|---------|----------|
| PSI Score | < 0.10 | 0.10 - 0.25 | > 0.25 |
| PSI Feature | < 0.10 | 0.10 - 0.20 | > 0.20 |
| KS Drift | < 5.0 pp | — | > 5.0 pp |
| AUC Drift | < 0.03 | — | > 0.03 |
| Gini Drift | < 5.0 pp | — | > 5.0 pp |

---

## Resultado: SAFRA 202503

### Status Geral: AMARELO (Atencao)

**Recomendacao**: Monitorar proxima SAFRA antes de agir.

### Score PSI

| Metrica | Valor | Status |
|---------|-------|--------|
| PSI Score Global | 0.0028 | VERDE |

> Distribuicao de scores extremamente estavel entre baseline e SAFRA 202503.

### Performance Drift

| Metrica | Baseline | SAFRA 202503 | Drift | Status |
|---------|----------|-------------|-------|--------|
| KS | 35.11 pp | 33.23 pp | -1.88 pp | VERDE |
| AUC | 0.7325 | 0.7206 | -0.0119 | VERDE |
| Gini | 46.50 pp | 44.12 pp | -2.38 pp | VERDE |

> Performance dentro dos thresholds em todas as metricas. Queda de ~2 pp e esperada em OOT.

### Feature Drift (Top 20 Features)

| Feature | PSI | Status |
|---------|-----|--------|
| **REC_DIAS_ENTRE_RECARGAS** | **1.3505** | **VERMELHO** |
| REC_QTD_PLAT_AUTOC | 0.0668 | VERDE |
| REC_VLR_REAL_STDDEV | 0.0518 | VERDE |
| REC_TAXA_STATUS_A | 0.0204 | VERDE |
| FAT_DIAS_MEDIO_CRIACAO_VENCIMENTO | 0.0098 | VERDE |
| PAG_VLR_PAGAMENTO_FATURA_STDDEV | 0.0085 | VERDE |
| TARGET_SCORE_01 | 0.0062 | VERDE |
| TARGET_SCORE_02 | 0.0033 | VERDE |
| REC_SCORE_RISCO | 0.0021 | VERDE |
| var_34 | 0.0018 | VERDE |
| REC_TAXA_CARTAO_ONLINE | 0.0010 | VERDE |
| *(demais 9 features)* | *< 0.07* | *VERDE* |

### Resumo

| Status | Quantidade |
|--------|-----------|
| VERDE | 19 features |
| AMARELO | 0 features |
| VERMELHO | 1 feature |

---

## Alerta: REC_DIAS_ENTRE_RECARGAS

**Severidade**: Critica (PSI = 1.3505 — muito acima do threshold de 0.20)

**O que significa**: A distribuicao de dias entre recargas mudou significativamente entre o periodo de treino (Q4 2024) e a SAFRA 202503 (marco 2025).

**Possiveis causas**:
1. Mudanca no mix de planos Pre-pago oferecidos pela Claro
2. Promocoes de recarga que alteraram o comportamento dos clientes
3. Sazonalidade (Q4 vs Q1 — festas vs periodo regular)
4. Mudanca na politica de credito de recarga

**Impacto no modelo**: Apesar do drift critico nesta feature, a **performance geral do modelo nao foi afetada** (KS drift de apenas -1.88 pp). Isso indica que o modelo e robusto o suficiente para absorver mudancas em features individuais.

**Acao recomendada**:
1. Monitorar a feature na SAFRA 202504
2. Se o drift persistir, considerar excluir ou recalcular a feature
3. Investigar mudancas de negocio que possam explicar a alteracao

---

## Volumes de Dados

| Periodo | Registros |
|---------|-----------|
| Baseline (202410-202412) | 1,358,578 |
| SAFRA 202503 | 444,306 |

---

## Pipeline de Monitoramento

O notebook [`src/modeling/monitoramento-drift.ipynb`](../../src/modeling/monitoramento-drift.ipynb) executa mensalmente:

1. **Carga do modelo** — MLflow Registry (Production stage)
2. **Carga dos dados** — Feature Store (baseline + nova SAFRA)
3. **Score PSI** — Compara distribuicao de scores em 10 bins
4. **Feature PSI** — Calcula PSI para Top 20 features
5. **Performance** — Calcula KS/AUC/Gini na nova SAFRA
6. **Drift comparison** — Compara com baseline e aplica thresholds
7. **Relatorio** — Gera JSON + CSV com resultados
8. **Alertas** — Status geral (VERDE/AMARELO/VERMELHO)

### Artefatos Gerados

| Artefato | Path | Conteudo |
|----------|------|----------|
| Relatorio completo | [`artifacts/monitoring/monitoring_safra_202503.json`](../../artifacts/monitoring-safra-202503/monitoring_safra_202503.json) | JSON com todas as metricas |
| Feature drift | [`artifacts/monitoring/feature_drift_safra_202503.csv`](../../artifacts/monitoring-safra-202503/feature_drift_safra_202503.csv) | CSV com PSI por feature |

---

*Fonte: [`artifacts/monitoring/`](../../artifacts/monitoring-safra-202503/) e [`src/modeling/monitoramento-drift.ipynb`](../../src/modeling/monitoramento-drift.ipynb)*
