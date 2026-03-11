# APEX Monitoring Dashboard — Setup Guide

Dashboard de monitoramento de modelos de Credit Risk no Oracle APEX, servido via ORDS sobre ADW Always Free.

## Arquitetura

```
ADW (Always Free)
├── Schema: MLMONITOR
│   ├── 8 tabelas (model_performance, score_stability, ...)
│   ├── 4 views (v_model_comparison, v_drift_summary, ...)
│   └── ORDS handler (dashboard/)
└── APEX Workspace
    └── App: Credit Risk ML Dashboard (Chart.js)
```

**URL do Dashboard**: `https://G95D3985BD0D2FD-PODACADEMY.adb.sa-saopaulo-1.oraclecloudapps.com/ords/mlmonitor/dashboard/`

## Pre-requisitos

1. **ADW** provisionado e ACTIVE (Always Free tier)
2. Acesso ao **SQL Workshop** via APEX ou **SQL Developer Web**
3. Credenciais ADMIN do ADW (ou user MLMONITOR criado)

### Credenciais

| User | Senha | Uso |
|------|-------|-----|
| ADMIN | (gerada pelo Terraform) | Administracao do ADW |
| MLMONITOR | `CreditRisk2026#ML` | Schema do dashboard |

## Scripts SQL (executar em ordem)

| # | Script | O que faz | Idempotente? |
|---|--------|-----------|--------------|
| 01 | `01_create_schema.sql` | Cria user MLMONITOR, grants, ORDS enable | Sim (BEGIN/EXCEPTION) |
| 02 | `02_create_tables.sql` | 8 tabelas + 4 views | Nao (CREATE TABLE) |
| 03 | `03_seed_data.sql` | ~170 INSERTs com dados do Run 20260311_015100 | Nao (INSERT) |
| 04 | `04_create_apex_app.sql` | Instrucoes para criar app APEX + dashboard HTML | Manual |

### Execucao

```sql
-- 1. Conectar como ADMIN no SQL Workshop
-- APEX > SQL Workshop > SQL Commands

-- 2. Executar na ordem:
@01_create_schema.sql
@02_create_tables.sql
@03_seed_data.sql

-- 3. Para o dashboard HTML, usar o script upload_dashboard.py
--    (ou copiar o conteudo de dashboard.html manualmente via 04_create_apex_app.sql)
```

### Via ORDS REST API (alternativa)

```bash
# Usar o endpoint ORDS para executar SQL remotamente
curl -u "MLMONITOR:CreditRisk2026#ML" \
  -X POST "https://G95D3985BD0D2FD-PODACADEMY.adb.sa-saopaulo-1.oraclecloudapps.com/ords/mlmonitor/_/sql" \
  -H "Content-Type: application/sql" \
  --data-binary @02_create_tables.sql
```

## Schema — Tabelas

### model_performance
Metricas KS, AUC, Gini por modelo e SAFRA.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| model_name | VARCHAR2(50) | Nome do modelo (e.g., LightGBM_v2, Ensemble_Average) |
| safra | VARCHAR2(6) | Periodo YYYYMM |
| dataset_type | VARCHAR2(10) | TRAIN, OOS (Out-of-Sample), OOT (Out-of-Time) |
| ks_statistic | NUMBER(10,5) | Kolmogorov-Smirnov statistic |
| auc_roc | NUMBER(10,5) | Area Under ROC Curve |
| gini | NUMBER(10,2) | Gini coefficient (%) |
| PK | (model_name, safra, dataset_type) | UNIQUE constraint |

### score_stability
PSI (Population Stability Index) por modelo e SAFRA.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| model_name | VARCHAR2(50) | Nome do modelo |
| safra | VARCHAR2(6) | Periodo YYYYMM |
| score_psi | NUMBER(10,6) | PSI value (< 0.1 = OK, 0.1-0.25 = WARNING, > 0.25 = RETRAIN) |
| psi_status | VARCHAR2(20) | OK / WARNING / RETRAIN |
| PK | (model_name, safra) | UNIQUE constraint |

### score_distribution
Estatisticas de distribuicao de scores por modelo e SAFRA.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| model_name | VARCHAR2(50) | Nome do modelo |
| safra | VARCHAR2(6) | Periodo YYYYMM |
| pct_critico / pct_alto / pct_medio / pct_baixo | NUMBER(5,2) | % em cada faixa de risco |
| PK | (model_name, safra) | UNIQUE constraint |

### feature_drift
PSI por feature individual, detecta drift de distribuicao.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| model_name | VARCHAR2(50) | Nome do modelo |
| feature_name | VARCHAR2(100) | Nome da feature |
| feature_psi | NUMBER(10,6) | PSI da feature |
| drift_status | VARCHAR2(20) | GREEN / YELLOW / RED |
| PK | (model_name, safra, feature_name) | UNIQUE constraint |

### model_status
Status geral de cada modelo (retrain necessario?).

### model_gap_analysis
Analise de overfitting: gap entre metricas TRAIN vs OOT.

### pipeline_runs
Historico de execucao do pipeline (Bronze, Silver, Gold, Training, etc.).

### cost_tracking
Custos mensais por servico OCI.

## Views

| View | Descricao |
|------|-----------|
| `v_model_comparison` | Ensemble_Average vs CatBoost side-by-side |
| `v_drift_summary` | Resumo de drift por modelo (total features, OK/WARNING/RED) |
| `v_risk_evolution` | Evolucao das faixas de risco por modelo e SAFRA |
| `v_cost_trend` | Tendencia de custos mensais por servico |

## Dashboard HTML (Chart.js)

O dashboard e servido via ORDS handler em `/mlmonitor/dashboard/`. O HTML e armazenado na tabela `dashboard_content`.

### Deploy do Dashboard

```bash
# Via script Python (recomendado)
python upload_dashboard.py

# Ou manualmente: copiar conteudo de dashboard.html para a tabela dashboard_content
# (ver instrucoes em 04_create_apex_app.sql)
```

### Abas do Dashboard

| Aba | Charts | Dados |
|-----|--------|-------|
| **Executive Overview** | KPI cards, KS/AUC trend, PSI stability, Risk bands | Ensemble_Average + 5 modelos |
| **Model Deep Dive** | Model comparison table, Feature importance, Gap analysis | 4 modelos principais |
| **CatBoost Focus** | CatBoost metrics, Score distribution, Feature drift | CatBoost isolado |
| **Operations** | Pipeline history, Cost tracking | pipeline_runs, cost_tracking |

## Atualizando Dados

Os dados em `03_seed_data.sql` sao do Run 20260311_015100. Para atualizar apos um novo run:

1. Gerar novo `monitoring_report.json` via `scripts/monitoring.py`
2. Converter metricas para INSERT statements
3. Executar TRUNCATE + INSERT nas tabelas relevantes:

```sql
-- Limpar dados antigos
TRUNCATE TABLE model_performance;
TRUNCATE TABLE score_stability;
-- ... etc

-- Inserir novos dados
@03_seed_data.sql
```

## Troubleshooting

| Erro | Causa | Solucao |
|------|-------|---------|
| `ORA-01920: user name conflicts` | MLMONITOR ja existe | Ignorar (01_create_schema.sql trata isso) |
| `ORA-00955: name already used` | Tabela ja existe | DROP TABLE primeiro ou usar 02 com IF NOT EXISTS |
| `ORA-00001: unique constraint violated` | Dados duplicados no seed | TRUNCATE tabela antes de re-inserir |
| Dashboard em branco | dashboard_content vazio | Re-executar upload_dashboard.py |
| ORDS 404 | Handler nao registrado | Verificar ORDS enable no 01_create_schema.sql |
