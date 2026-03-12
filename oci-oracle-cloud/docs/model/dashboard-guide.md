# Guia do Dashboard de Monitoramento ML — Credit Risk FPD

**Projeto**: Hackathon PoD Academy (Claro + Oracle)
**Plataforma**: Oracle Cloud Infrastructure — ADW Always Free + ORDS REST
**Versao**: 3.0 | **Run**: 20260311_015100
**Data**: 2026-03-11

---

## Acesso

**URL**: https://G95D3985BD0D2FD-PODACADEMY2.adb.sa-saopaulo-1.oraclecloudapps.com/ords/mlmonitor/dashboard/

Acesso publico, sem autenticacao. Dados carregados em tempo real do ADW via ORDS REST.

---

## Indice

1. [Visao Geral](#1-visao-geral)
2. [Arquitetura Tecnica](#2-arquitetura-tecnica)
3. [Pagina 1 — Executive Overview](#3-pagina-1--executive-overview)
4. [Pagina 2 — Model Performance](#4-pagina-2--model-performance)
5. [Pagina 3 — Overfitting & GAP Analysis](#5-pagina-3--overfitting--gap-analysis)
6. [Pagina 4 — Operations & Costs](#6-pagina-4--operations--costs)
7. [Guia de Acoes por Analise](#7-guia-de-acoes-por-analise)
8. [Procedimentos de Atualizacao](#8-procedimentos-de-atualizacao)
9. [Troubleshooting](#9-troubleshooting)
10. [Referencia Tecnica](#10-referencia-tecnica)

---

## 1. Visao Geral

O dashboard monitora em tempo real o modelo de credit risk (First Payment Default — FPD) para clientes de telecomunicacoes. Ele serve como central de comando para 4 areas criticas:

| Area | Pagina | Decisao que Habilita |
|------|--------|---------------------|
| Saude do Modelo | Executive Overview | O modelo esta performando dentro dos limites? Precisa de atencao? |
| Performance Detalhada | Model Performance | Quais modelos e features estao degradando? Em quais safras? |
| Risco de Overfitting | GAP Analysis | O modelo generaliza bem? Qual o risco de falhar em dados novos? |
| Custo & Operacao | Operations & Costs | O pipeline esta saudavel? Os custos estao dentro do orcamento? |

### Modelos Monitorados

| Modelo | Tipo | Status | KS OOT | AUC OOT |
|--------|------|--------|--------|---------|
| **Ensemble Average** | Top-3 Average (LGBM+XGB+CB) | **CHAMPION** | 0.35005 | 0.73677 |
| LightGBM v2 | Individual (HPO) | ACTIVE | 0.34943 | 0.73645 |
| XGBoost | Individual (HPO) | ACTIVE | 0.34938 | 0.73619 |
| CatBoost | Individual (HPO) | ACTIVE | 0.34821 | 0.73539 |
| Random Forest | Individual | ACTIVE | 0.33700 | 0.72778 |
| LR L1 v2 | Individual (baseline) | ACTIVE | 0.33140 | 0.72310 |

### Quality Gate (QG-05)

| Metrica | Threshold | Champion Atual | Status |
|---------|-----------|---------------|--------|
| KS | > 0.20 | 0.35005 | PASSED |
| AUC | > 0.65 | 0.73677 | PASSED |
| Gini | > 30% | 47.35% | PASSED |
| PSI | < 0.25 | 0.000754 | PASSED |

---

## 2. Arquitetura Tecnica

### Stack

```
Browser (HTML5 + Chart.js 4.4)
    |
    | fetch() via ORDS REST (8 endpoints)
    v
Oracle ADW Always Free (MLMONITOR schema)
    |
    | 8 tabelas com dados reais do pipeline
    v
Pipeline ML (Airflow DAG no Orchestrator)
    |
    | Scripts Python: train, ensemble, score, monitor
    v
Gold Layer (Object Storage — 600 parquets, 3.9M registros)
```

### Fluxo de Dados

```
1. Pipeline executa (Airflow DAG)
2. Scripts geram metricas (JSONs em artifacts/)
3. Seed script (03_seed_data.sql) ou sync_oci_costs.py popula ADW
4. Dashboard carrega dados via fetch() nos 8 endpoints ORDS
5. JavaScript normaliza nomes e renderiza charts/tables
6. Usuario analisa e toma decisoes
```

### Endpoints ORDS

| Endpoint | Tabela ADW | Rows | Conteudo |
|----------|-----------|------|----------|
| `/model_performance/` | MODEL_PERFORMANCE | 25+ | KS, AUC, Gini por modelo x safra x dataset |
| `/score_stability/` | SCORE_STABILITY | 6 | PSI do score por safra |
| `/score_distribution/` | SCORE_DISTRIBUTION | 6 | Distribuicao por faixa de risco |
| `/feature_drift/` | FEATURE_DRIFT | 40 | PSI por feature, 2 safras OOT |
| `/model_status/` | MODEL_STATUS | 6 | Status (CHAMPION/ACTIVE) |
| `/pipeline_runs/` | PIPELINE_RUNS | 6 | Historico de execucoes |
| `/cost_tracking/` | COST_TRACKING | 7 | Custos OCI por servico |
| `/model_gap_analysis/` | MODEL_GAP_ANALYSIS | 6 | Train vs OOT gap por modelo |

### Normalizacao de Nomes

O ADW armazena nomes tecnicos; o dashboard normaliza para exibicao:

| ADW (BD) | Dashboard (Display) |
|----------|-------------------|
| `Ensemble_Average` | Ensemble v1 |
| `LightGBM_v2` | LightGBM |
| `LR_L1_v2` | LR L1 |
| `XGBoost` | XGBoost |
| `CatBoost` | CatBoost |
| `RF` | Random Forest |

---

## 3. Pagina 1 — Executive Overview

### Proposito
Visao de alto nivel da saude do modelo champion. Responde: **"O modelo esta funcionando corretamente?"**

### KPIs (6 cards)

| KPI | O Que Mostra | Valor Atual | Como Interpretar |
|-----|-------------|-------------|-----------------|
| **Model Status** | Status do champion | CHAMPION | Verde = operando. Amarelo = atencao. Vermelho = critico. |
| **KS Statistic (OOT)** | Poder discriminante out-of-time | 35.0% | > 20% = OK. < 20% = modelo nao separa bons de maus. |
| **AUC-ROC** | Area sob a curva ROC | 0.7368 | > 0.65 = OK. < 0.65 = classificacao insuficiente. |
| **Gini** | Coeficiente de concentracao | 47.35% | > 30% = OK. = 2*AUC - 1. Mede ordenacao de risco. |
| **Score PSI** | Estabilidade do score | 0.0040 | < 0.10 = estavel. 0.10-0.25 = atencao. > 0.25 = retreinar. |
| **Volume Scored** | Total de registros scorados | 3.9M | Confirma que o pipeline processou o volume esperado. |

### Charts

#### KS por SAFRA (Line Chart)
- **O que mostra**: Evolucao do KS dos 3 modelos principais (Ensemble, LightGBM, LR L1) ao longo das 6 safras.
- **Eixo X**: SAFRA (202410 a 202503). As 4 primeiras sao TRAIN, as 2 ultimas OOT.
- **Eixo Y**: KS em percentual.
- **Como ler**: Queda consistente de KS nas safras OOT indica degradacao temporal. KS estavel indica modelo robusto.
- **Acao se KS cair**: Ver secao [7.1](#71-degradacao-de-ks).

#### PSI Trend (Line Chart)
- **O que mostra**: Estabilidade do score ao longo do tempo.
- **Eixo Y**: PSI (0 = identico ao treino, > 0.25 = distribuicao mudou significativamente).
- **Como ler**: Linha plana proxima de 0 = score estavel. Pico indica mudanca na populacao.
- **Acao se PSI subir**: Ver secao [7.2](#72-instabilidade-de-score-psi).

#### Risk Band Distribution (Stacked Bar)
- **O que mostra**: Proporcao de clientes em cada faixa de risco por safra.
- **Faixas**: Critico (0-299, vermelho), Alto (300-499, laranja), Medio (500-699, amarelo), Baixo (700-1000, verde).
- **Como ler**: Distribuicao estavel entre safras = populacao consistente. Aumento da faixa critica = piora no perfil.
- **Acao se faixa critica crescer**: Ver secao [7.3](#73-mudanca-no-perfil-de-risco).

#### Score Distribution (Grouped Bar)
- **O que mostra**: P25, Media e P75 dos scores por safra.
- **Como ler**: Barras estáveis = distribuicao consistente. Queda da media = populacao piorando.

---

## 4. Pagina 2 — Model Performance

### Proposito
Analise detalhada de performance e drift de features. Responde: **"Quais modelos e features estao degradando? Onde atuar?"**

### KPIs (4 cards)

| KPI | O Que Mostra | Valor Atual | Como Interpretar |
|-----|-------------|-------------|-----------------|
| **Features Selected** | Total de features no modelo | 110 | Funil de 5 estagios: 357 candidatas → 110 selecionadas. |
| **Features Monitored** | Features com drift monitorado | 20 | Top 20 features por PSI. |
| **Temporal Split** | Abrangencia temporal | 6 SAFRAs | 202410-202501 (TRAIN) + 202502-202503 (OOT). |
| **Drift Status** | Status geral de drift | WARNING | 13 features YELLOW (PSI 0.10-0.25), 0 RED. |

### Charts

#### AUC-ROC Evolution (Line Chart)
- **O que mostra**: AUC dos 3 modelos principais ao longo das safras.
- **Como ler**: AUC deve ser >= 0.65. Queda entre TRAIN e OOT indica overfitting.
- **Acao**: Gap > 5% entre TRAIN e OOT → investigar na pagina GAP Analysis.

#### Gini Coefficient Trend (Line Chart)
- **O que mostra**: Gini (= 2*AUC - 1) como percentual.
- **Como ler**: Gini >= 30% = OK. Mesma logica do AUC porem em escala mais intuitiva.

#### Comparison Table
- **O que mostra**: Tabela completa com KS, AUC e Gini por modelo por safra.
- **Colunas**: SAFRA | Dataset | ENS KS | ENS AUC | ENS Gini | LGBM KS | LGBM AUC | LGBM Gini | LR KS | LR AUC | LR Gini
- **Como ler**: Ensemble (navy) deve liderar. Se individual superar ensemble → reavaliar composicao.
- **Acao se individual superar ensemble**: Ver secao [7.4](#74-ensemble-sub-otimo).

### Feature Drift Table

| Coluna | Descricao |
|--------|----------|
| **Feature** | Nome da feature monitorada (ex: `FAT_QTD_FATURAS`) |
| **PSI (202502)** | PSI da safra anterior |
| **PSI (202503)** | PSI da safra mais recente |
| **Trend** | Seta com percentual de variacao. `▲ +8%` vermelho = piorando. `▼ -5%` verde = melhorando. |
| **Status** | Badge de cor: GREEN (PSI < 0.10), YELLOW (0.10-0.25), RED (> 0.25). |

**Como ler a tabela de drift**:
1. Ordenada por PSI decrescente (feature com mais drift no topo).
2. **13 features YELLOW**: PSI entre 0.10 e 0.25. Distribuicao mudou moderadamente.
3. **7 features GREEN**: PSI < 0.10. Estaveis.
4. **0 features RED**: Nenhuma ultrapassou o threshold critico (0.25).
5. **Trend**: Compara safra 202502 vs 202503. Seta vermelha para cima = drift piorando.

**Acao se feature ficar RED**: Ver secao [7.5](#75-feature-drift-critico).

---

## 5. Pagina 3 — Overfitting & GAP Analysis

### Proposito
Avaliar risco de overfitting e generalizacao do modelo. Responde: **"O modelo vai funcionar em dados novos ou so decorou os dados de treino?"**

### KPIs (4 cards)

| KPI | O Que Mostra | Valor Atual | Como Interpretar |
|-----|-------------|-------------|-----------------|
| **Champion GAP** | Gap KS do champion (train vs OOT) | 11.2% | < 10% = estavel. 10-15% = aceitavel. > 15% = atencao. |
| **Best Stability** | Modelo com menor gap | LR L1 v2 (5.7%) | Modelo mais conservador, menor risco de overfitting. |
| **Worst GAP** | Modelo com maior gap | XGBoost (14.5%) | Modelo com mais risco de degradacao temporal. |
| **Avg GAP (All)** | Media de gap entre todos | ~10% | Referencia geral da qualidade do ensemble. |

### Charts

#### KS GAP — Absolute (Horizontal Bar)
- **O que mostra**: Diferenca absoluta em pontos percentuais entre KS TRAIN e KS OOT.
- **Cores**: Verde (< 10%), Laranja (10-15%), Vermelho (> 15%).
- **Como ler**: Barras menores = melhor generalizacao. XGBoost tem a maior barra.

#### GAP Relativo % (Horizontal Bar)
- **O que mostra**: Mesmo gap porem como percentual do KS TRAIN.
- **Como ler**: Modelo com 14% de gap perdeu 14% do seu poder preditivo ao sair do treino.

#### Degradacao Train → OOS → OOT (Grouped Bar)
- **O que mostra**: Progressao do KS por etapa de validacao.
- **3 barras por modelo**: KS Train (azul escuro), KS OOS (azul claro), KS OOT (verde).
- **Como ler**: Queda suave = saudavel. Queda abrupta entre OOS e OOT = overfitting temporal.

### GAP Table (Tabela Completa)

| Coluna | Descricao |
|--------|----------|
| # | Posicao no ranking (menor gap = melhor) |
| Model | Nome do modelo. Champion destacado com badge verde. |
| Type | `individual` ou `ensemble` |
| KS Train | KS no dataset de treino |
| KS OOT | KS no dataset out-of-time |
| GAP (abs) | Diferenca absoluta em pontos percentuais |
| GAP (%) | Diferenca relativa ao KS Train |
| AUC GAP (%) | Mesma logica para AUC |
| PSI | Estabilidade do score do modelo |
| Status | Classificacao: Stable (< 10%), Acceptable (10-15%), Attention (15-25%), Overfit (> 25%) |

**Classificacao de risco por GAP**:

| GAP (%) | Classificacao | Acao |
|---------|--------------|------|
| < 10% | **Stable** | Nenhuma acao necessaria. |
| 10-15% | **Acceptable** | Monitorar. Comum em modelos complexos. |
| 15-25% | **Attention** | Investigar features com alto IV. Considerar regularizacao. |
| > 25% | **Overfit** | Retreinar com mais regularizacao ou reduzir features. |

---

## 6. Pagina 4 — Operations & Costs

### Proposito
Monitorar saude do pipeline e custos OCI. Responde: **"O pipeline esta rodando? Quanto estamos gastando?"**

### KPIs (4 cards)

| KPI | O Que Mostra | Valor Atual | Como Interpretar |
|-----|-------------|-------------|-----------------|
| **OCI Resources** | Total de recursos provisionados | 7 | Incluindo Always Free (custo zero). |
| **Monthly Cost** | Custo mensal total em BRL | R$ 168 | Se diz "Live from OCI Usage API" = dados em tempo real. |
| **Pipeline Stages** | Taxa de sucesso das etapas | 6/6 SUCCESS | Qualquer FAILED requer investigacao imediata. |
| **Last Run** | Identificador da ultima execucao | Run 20260311 | Data do ultimo pipeline completo. |

### Charts

#### Cost Donut
- **O que mostra**: Distribuicao de custos por servico OCI no periodo mais recente.
- **Servicos gratuitos**: Exibidos em cinza com label "(Free)".
- **Como ler**: Compute (E3.Flex) domina o custo. ADW, Data Catalog, VCN sao Always Free.

#### Cost Trend (Stacked Bar)
- **O que mostra**: Evolucao mensal dos custos por servico.
- **Como ler**: Crescimento indica novo recurso ou maior utilizacao.

### Pipeline Table

| Coluna | Descricao |
|--------|----------|
| Stage | Nome da etapa (Data Quality, Feature Selection, Training, etc.) |
| Status | Badge: SUCCESS (verde), RUNNING (azul), FAILED (vermelho). |
| Started | Data/hora de inicio (formato pt-BR). |
| Duration | Tempo de execucao em segundos. |
| Records | Volume processado (formatado com separador de milhar). |
| Notes | Observacoes (ex: "5 models trained", "13 YELLOW features"). |

### Custos por Cenario

| Cenario | Mensal (BRL) | Descricao |
|---------|-------------|-----------|
| Tudo parado | ~R$ 33 | Apenas Object Storage |
| 1 execucao/mes (8h) | ~R$ 120 | Orchestrator 8h + ADW |
| Dev semanal (8h/sem) | ~R$ 245 | + Notebook ativo |
| Producao 24/7 | ~R$ 900 | Tudo ligado |

---

## 7. Guia de Acoes por Analise

### 7.1 Degradacao de KS

**Sinal**: KS caiu abaixo de 30% nas safras OOT.

**Diagnostico**:
1. Verificar na Comparison Table se a queda e do ensemble ou de um modelo individual.
2. Checar na GAP Analysis se o gap aumentou (overfitting progressivo).
3. Verificar na Feature Drift Table se features-chave ficaram RED.

**Acoes**:
| Prioridade | Acao | Impacto |
|------------|------|---------|
| 1 | Verificar qualidade dos dados da safra afetada (Data Quality stage) | Pode ser problema de dados, nao de modelo |
| 2 | Avaliar se cutoff de aprovacao precisa ser ajustado (ver swap analysis) | Impacto direto na taxa de inadimplencia |
| 3 | Retreinar modelos com dados mais recentes no treino | Recupera poder preditivo |
| 4 | Reavaliar composicao do ensemble se um modelo individual degradou mais | Pode melhorar KS em 1-3 pp |

### 7.2 Instabilidade de Score (PSI)

**Sinal**: PSI > 0.10 (YELLOW) ou > 0.25 (RED) no PSI Trend chart.

**Diagnostico**:
1. PSI YELLOW (0.10-0.25): Distribuicao do score mudou moderadamente. Comum entre safras diferentes.
2. PSI RED (> 0.25): Mudanca significativa. Populacao de entrada pode ter mudado.

**Acoes**:
| Prioridade | Acao | Impacto |
|------------|------|---------|
| 1 | Investigar se houve mudanca de politica comercial ou campanha | Causa raiz mais comum de shift de populacao |
| 2 | Comparar distribuicao de features-chave entre safras (Feature Drift Table) | Identifica O QUE mudou |
| 3 | Se PSI > 0.25 por 2+ safras consecutivas: retreinar modelo | Modelo nao reflete mais a populacao atual |

### 7.3 Mudanca no Perfil de Risco

**Sinal**: Faixa "Critico" (0-299) crescendo no Risk Band Distribution chart.

**Diagnostico**:
1. Mais clientes estao recebendo scores baixos = perfil de risco da populacao piorou.
2. OU o modelo esta classificando mais gente como risco alto (drift de features).

**Acoes**:
| Prioridade | Acao | Impacto |
|------------|------|---------|
| 1 | Verificar se a inadimplencia real (FPD rate) tambem subiu | Confirma se e mudanca real ou artefato |
| 2 | Avaliar ajuste de cutoff: se FPD subiu, cutoff mais restritivo reduz perdas | Trade-off: menos aprovacoes, menos inadimplencia |
| 3 | Se perfil mudou permanentemente: retreinar com dados recentes | Recalibra o scoring para a nova populacao |

### 7.4 Ensemble Sub-otimo

**Sinal**: Um modelo individual (ex: LightGBM) superando o Ensemble na Comparison Table.

**Diagnostico**:
1. Verificar se e em todas as safras OOT ou apenas uma.
2. Se o ensemble perde em KS mas ganha em estabilidade (menor PSI), ainda e valido como champion.
3. Se o individual ganha consistentemente em KS E PSI: ensemble precisa ser recomposto.

**Acoes**:
| Prioridade | Acao | Impacto |
|------------|------|---------|
| 1 | Revalidar pesos do ensemble (pode ter mudado a contribuicao relativa) | Melhoria sem retreinar |
| 2 | Testar nova composicao (ex: Top-2 em vez de Top-3) | Simplifica e pode melhorar |
| 3 | Considerar promover o modelo individual a champion | Ultima opcao — perde diversificacao |

### 7.5 Feature Drift Critico

**Sinal**: Feature com PSI > 0.25 (RED) na Feature Drift Table. Ou trend `▲` crescente.

**Diagnostico**:
1. Verificar se e feature de negocio (mudanca real) ou tecnica (erro de dados).
2. Feature de faturamento (`FAT_*`) mudando: pode indicar mudanca de produto/pricing.
3. Feature de pagamento (`PAG_*`) mudando: pode indicar mudanca de comportamento de pagamento.
4. Feature de recarga (`REC_*`) mudando: pode indicar mudanca de oferta/campanha.

**Acoes**:
| Prioridade | Acao | Impacto |
|------------|------|---------|
| 1 | Validar se a feature ainda tem IV > 0.02 (poder preditivo) | Feature pode ter virado ruido |
| 2 | Se IV caiu: remover feature e retreinar | Remove fonte de instabilidade |
| 3 | Se IV se mantem mas distribuicao mudou: retreinar com dados recentes | Modelo se adapta a nova distribuicao |
| 4 | Se drift e temporario (ex: Black Friday): aguardar proxima safra | Nem toda mudanca requer acao |

### 7.6 Pipeline com Falha

**Sinal**: Stage com status FAILED na Pipeline Table.

**Acoes**:
| Prioridade | Acao | Impacto |
|------------|------|---------|
| 1 | Verificar logs do Airflow (146.235.27.18:8080) | Identifica erro especifico |
| 2 | Se falha em Data Quality: dados de entrada corrompidos | Corrigir na fonte |
| 3 | Se falha em Training: OOM ou timeout | Aumentar recursos ou reduzir batch |
| 4 | Re-executar DAG apos correcao | Pipeline idempotente — safe to retry |

### 7.7 Custos Acima do Esperado

**Sinal**: Monthly Cost subindo no Cost Trend chart.

**Acoes**:
| Prioridade | Acao | Impacto |
|------------|------|---------|
| 1 | Verificar se algum recurso ficou ligado 24/7 desnecessariamente | Compute E3.Flex custa ~R$ 7/dia |
| 2 | Parar Notebook e Orchestrator quando nao em uso | Economia de ~80% |
| 3 | Usar ADW auto-stop (Always Free para automaticamente em 7 dias de inatividade) | Custo zero |

---

## 8. Procedimentos de Atualizacao

### 8.1 Atualizar Dados Apos Nova Execucao do Pipeline

```bash
# 1. Executar pipeline (gera novos JSONs em artifacts/)
ssh opc@146.235.27.18
cd /home/opc/dags && airflow dags trigger credit_risk_ml_pipeline

# 2. Coletar artefatos
scp -r opc@146.235.27.18:/home/opc/artifacts/$(date +%Y%m%d)/ ./artifacts/

# 3. Regenerar seed SQL (usar gen_seed.py ou editar 03_seed_data.sql manualmente)
python /tmp/gen_seed.py

# 4. Executar seed no ADW via ORDS
curl -X POST \
  "https://G95D3985BD0D2FD-PODACADEMY2.adb.sa-saopaulo-1.oraclecloudapps.com/ords/mlmonitor/_/sql" \
  -u "MLMONITOR:CreditRisk2026#ML" \
  -H "Content-Type: application/sql" \
  -d @03_seed_data.sql

# 5. Dashboard atualiza automaticamente ao recarregar
```

### 8.2 Atualizar Custos em Tempo Real

```bash
# No orchestrator (instance_principal auth):
python3 /home/opc/scripts/sync_oci_costs.py

# Localmente (com fallback):
python3 scripts/sync_oci_costs.py --fallback
```

O script `sync_oci_costs.py` consulta a OCI Usage API e popula a tabela `COST_TRACKING` via ORDS. Esta incluido como task `sync_oci_costs` no DAG do Airflow.

### 8.3 Adicionar Nova SAFRA

Para cada nova safra (ex: 202504), inserir dados em 4 tabelas:

```sql
-- 1. MODEL_PERFORMANCE (1 row por modelo x dataset_type)
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('Ensemble_Average', '202504', 'OOT', 0.3450, 0.7340, 46.80, 650000, 0.2180, SYSTIMESTAMP);

-- 2. SCORE_STABILITY (1 row por safra)
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n, measured_at)
VALUES ('Ensemble_Average', '202504', 0.0045, 'GREEN', 538.06, 535.2, 2632587, 650000, SYSTIMESTAMP);

-- 3. SCORE_DISTRIBUTION (1 row por safra)
INSERT INTO score_distribution (model_name, safra, score_mean, score_median, score_p25, score_p75, score_std, pct_critico, pct_alto, pct_medio, pct_baixo, total_scored, scored_at)
VALUES ('Ensemble_Average', '202504', 535.2, 543, 348, 728, 212.5, 17.5, 26.0, 28.5, 28.0, 650000, SYSTIMESTAMP);

-- 4. FEATURE_DRIFT (1 row por feature monitorada)
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202504', 'FAT_QTD_FATURAS', 0.175, 'YELLOW', 3.61, 3.52, 4.04, 4.12, SYSTIMESTAMP);
-- ... (repetir para as 20 features monitoradas)

COMMIT;
```

### 8.4 Atualizar o HTML do Dashboard

```bash
# 1. Editar oci-oracle-cloud/infrastructure/apex/dashboard.html

# 2. Upload para ADW:
cd oci-oracle-cloud/infrastructure/apex/
python upload_dashboard.py
# Output esperado: "Stored HTML length: XXXXX bytes" + "ORDS handler updated successfully!"

# 3. Verificar: abrir URL do dashboard no browser
```

### 8.5 Promover Novo Champion

```sql
-- 1. Rebaixar champion atual
UPDATE model_status SET status = 'ACTIVE', status_code = 1
WHERE model_name = 'Ensemble_Average';

-- 2. Promover novo champion
UPDATE model_status SET status = 'CHAMPION', status_code = 2
WHERE model_name = 'LightGBM_v2';

COMMIT;
```

O dashboard detecta automaticamente o model com `status = 'CHAMPION'` para exibir nos KPIs.

---

## 9. Troubleshooting

### Dashboard mostra "Connecting..." ou "Connection Error"

**Causa**: ADW pode estar parado (auto-stop apos 7 dias de inatividade no Always Free).

**Solucao**:
```bash
# Verificar status
oci db autonomous-database get \
  --autonomous-database-id ocid1.autonomousdatabase.oc1.sa-saopaulo-1.antxeljr6dlb45iaangy5wpt4wec6ymecn7gpfzxzkag4xnyevcwn2elxlrq \
  --query 'data."lifecycle-state"' --raw-output

# Se STOPPED, iniciar:
oci db autonomous-database start \
  --autonomous-database-id ocid1.autonomousdatabase.oc1.sa-saopaulo-1.antxeljr6dlb45iaangy5wpt4wec6ymecn7gpfzxzkag4xnyevcwn2elxlrq

# Aguardar ~2 minutos para AVAILABLE
```

### Charts vazios mas KPIs funcionam

**Causa**: Modelo de referencia nos charts (ex: "Ensemble v1") nao encontrado nos dados.

**Solucao**: Verificar se `normalizeModelNames()` esta mapeando corretamente. O ADW deve ter `Ensemble_Average`, nao `Ensemble v1`.

### Feature Drift Table sem coluna Trend

**Causa**: Drift data em apenas 1 safra (precisa de 2 para calcular tendencia).

**Solucao**: Inserir drift para a safra anterior (ver secao 8.3).

### Upload do dashboard falha com "errorCode"

**Causa**: HTML com caracteres especiais que quebram o PL/SQL de decodificacao base64.

**Solucao**: Verificar se `upload_dashboard.py` esta usando base64 chunking (limite de 3000 chars por chunk).

---

## 10. Referencia Tecnica

### Schemas das Tabelas ADW

#### MODEL_PERFORMANCE
```sql
model_name       VARCHAR2(100)   -- Nome tecnico do modelo
safra            VARCHAR2(6)     -- YYYYMM
dataset_type     VARCHAR2(10)    -- TRAIN ou OOT
ks_statistic     NUMBER          -- 0.0 a 1.0
auc_roc          NUMBER          -- 0.0 a 1.0
gini             NUMBER          -- 0.0 a 100.0
n_records        NUMBER          -- Registros avaliados
fpd_rate         NUMBER          -- Taxa FPD na safra
evaluated_at     TIMESTAMP       -- Data da avaliacao
```

#### SCORE_STABILITY
```sql
model_name       VARCHAR2(100)
safra            VARCHAR2(6)
score_psi        NUMBER          -- PSI do score (train vs safra)
psi_status       VARCHAR2(20)    -- GREEN / YELLOW / RED
train_mean       NUMBER          -- Media do score no treino
scoring_mean     NUMBER          -- Media do score na safra
train_n          NUMBER          -- N registros no treino
scoring_n        NUMBER          -- N registros na safra
measured_at      TIMESTAMP
```

#### SCORE_DISTRIBUTION
```sql
model_name       VARCHAR2(100)
safra            VARCHAR2(6)
score_mean       NUMBER          -- Media
score_median     NUMBER          -- Mediana
score_p25        NUMBER          -- Percentil 25
score_p75        NUMBER          -- Percentil 75
score_std        NUMBER          -- Desvio padrao
pct_critico      NUMBER          -- % na faixa 0-299
pct_alto         NUMBER          -- % na faixa 300-499
pct_medio        NUMBER          -- % na faixa 500-699
pct_baixo        NUMBER          -- % na faixa 700-1000
total_scored     NUMBER          -- Total scorado
scored_at        TIMESTAMP
```

#### FEATURE_DRIFT
```sql
model_name       VARCHAR2(100)
safra            VARCHAR2(6)
feature_name     VARCHAR2(100)   -- Nome da feature
feature_psi      NUMBER          -- PSI da feature
drift_status     VARCHAR2(20)    -- GREEN / YELLOW / RED
train_mean       NUMBER          -- Media no treino
oot_mean         NUMBER          -- Media no OOT
train_std        NUMBER          -- Std no treino
oot_std          NUMBER          -- Std no OOT
measured_at      TIMESTAMP
```

#### MODEL_STATUS
```sql
model_name       VARCHAR2(100)
model_version    VARCHAR2(50)
status           VARCHAR2(20)    -- CHAMPION / ACTIVE / DEPRECATED
status_code      NUMBER          -- 1=ACTIVE, 2=CHAMPION
quality_gate     VARCHAR2(20)    -- PASSED / FAILED
last_trained     TIMESTAMP
last_scored      TIMESTAMP
last_monitored   TIMESTAMP
notes            VARCHAR2(500)
updated_at       TIMESTAMP
```

#### PIPELINE_RUNS
```sql
stage            VARCHAR2(100)   -- Nome da etapa
status           VARCHAR2(20)    -- SUCCESS / FAILED / RUNNING
started_at       TIMESTAMP
finished_at      TIMESTAMP
duration_sec     NUMBER
records_in       NUMBER
records_out      NUMBER
notes            VARCHAR2(500)
```

#### COST_TRACKING
```sql
period           VARCHAR2(7)     -- YYYY-MM
service_name     VARCHAR2(200)
cost_brl         NUMBER          -- Custo em BRL
pct_of_total     NUMBER          -- % do total
notes            VARCHAR2(500)
```

#### MODEL_GAP_ANALYSIS
```sql
model_name       VARCHAR2(100)
ks_train         NUMBER
ks_oot           NUMBER
ks_gap           NUMBER          -- ks_train - ks_oot
ks_gap_pct       NUMBER          -- gap / train * 100
auc_train        NUMBER
auc_oot          NUMBER
auc_gap          NUMBER
auc_gap_pct      NUMBER
gini_train       NUMBER
gini_oot         NUMBER
gini_gap         NUMBER
gini_gap_pct     NUMBER
overfit_risk     VARCHAR2(20)    -- LOW / MODERATE / HIGH
psi              NUMBER          -- PSI do modelo
```

### Arquivos do Dashboard

| Arquivo | Funcao |
|---------|--------|
| `infrastructure/apex/dashboard.html` | HTML + CSS + JS do dashboard (Chart.js 4.4) |
| `infrastructure/apex/upload_dashboard.py` | Upload para ADW via base64 chunked ORDS |
| `infrastructure/apex/01_create_schema.sql` | Cria user MLMONITOR + workspace APEX |
| `infrastructure/apex/02_create_tables.sql` | DDL das 8 tabelas + ORDS auto-REST |
| `infrastructure/apex/03_seed_data.sql` | Dados reais do Run 20260311_015100 |
| `scripts/sync_oci_costs.py` | Sincroniza custos OCI via Usage API |

### Thresholds de Monitoramento

| Metrica | GREEN | YELLOW | RED | Acao RED |
|---------|-------|--------|-----|----------|
| KS (OOT) | > 0.30 | 0.20-0.30 | < 0.20 | Retreinar |
| AUC (OOT) | > 0.70 | 0.65-0.70 | < 0.65 | Retreinar |
| Gini (OOT) | > 40% | 30-40% | < 30% | Retreinar |
| Score PSI | < 0.10 | 0.10-0.25 | > 0.25 | Retreinar |
| Feature PSI | < 0.10 | 0.10-0.25 | > 0.25 | Remover feature |
| GAP KS (%) | < 10% | 10-15% | > 15% | Regularizar |
| Pipeline | SUCCESS | - | FAILED | Investigar logs |
| Custo mensal | < R$ 200 | R$ 200-500 | > R$ 500 | Otimizar recursos |

---

*Dashboard Guide v3.0 — Run 20260311_015100 — Hackathon PoD Academy (Claro + Oracle)*
