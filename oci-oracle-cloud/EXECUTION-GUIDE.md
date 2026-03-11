# Guia de Execucao Oficial — OCI Credit Risk Platform

**Versao**: 1.2 | **Data**: 2026-03-11
**Validado por**: Atlas (OCI Platform Chief)

---

## Limitacoes do Trial OCI

> **ATENCAO**: O ambiente OCI e um trial com limites de recursos:
> - **Max 4 OCPUs / 64 GB** para instancias E3.Flex (8/128 bloqueado por LimitExceeded)
> - **ARM A1**: OUT_OF_HOST_CAPACITY em sa-saopaulo-1 (indisponivel)
> - **64 GB pode causar OOM** ao carregar 402 colunas — scripts usam PyArrow com leitura seletiva de colunas
> - **Always Free ADW e Data Catalog** — sem custos adicionais
> - Recomendado parar instancias quando nao em uso (ver Passo 9)

---

## Pre-requisitos

1. **OCI CLI** configurado (`oci setup config` ou `~/.oci/config`)
2. **SSH Key** para acesso ao notebook e orchestrator (`~/.ssh/oci_pipeline`)
3. **Airflow** rodando no orchestrator (146.235.27.18:8080)
4. **Data Science Notebook** ativo (10.0.1.10)
5. **Gold data** no Object Storage: `oci://pod-academy-gold@grlxi07jz1mo/feature_store/clientes_consolidado/`

---

## Passo 1 — Verificar Infraestrutura

```bash
# Verificar Airflow
ssh -i ~/.ssh/oci_pipeline opc@146.235.27.18 "docker ps | grep airflow"

# Verificar Notebook Session (pode precisar ativar)
oci data-science notebook-session list \
  --compartment-id ocid1.compartment.oc1..aaaaaaaa7uh2lfpsc6qf73g7zalgbr262a2v6veb4lreykqn57gtjvoojeuq \
  --lifecycle-state ACTIVE \
  --query 'data[*].{name:"display-name",state:"lifecycle-state"}'

# Se notebook INACTIVE, ativar:
oci data-science notebook-session activate \
  --notebook-session-id <NOTEBOOK_SESSION_OCID>

# Verificar Gold data no bucket
oci os object list \
  --bucket-name pod-academy-gold \
  --namespace grlxi07jz1mo \
  --prefix "feature_store/clientes_consolidado/" \
  --limit 5
```

---

## Passo 2 — Upload dos Scripts para o Notebook

```bash
# Destino: /home/datascience/scripts/ no notebook
NOTEBOOK_IP="10.0.1.10"
SSH_KEY="~/.ssh/oci_pipeline"

# Criar diretorio remoto
ssh -i $SSH_KEY datascience@$NOTEBOOK_IP "mkdir -p /home/datascience/scripts"

# Upload dos scripts
for script in train_credit_risk.py feature_selection.py ensemble.py \
              batch_scoring.py monitoring.py data_quality.py \
              ds_job_runner.py ensemble_comparison.py swap_analysis.py; do
  scp -i $SSH_KEY scripts/$script datascience@$NOTEBOOK_IP:/home/datascience/scripts/
  echo "Uploaded: $script"
done

# Verificar
ssh -i $SSH_KEY datascience@$NOTEBOOK_IP "ls -la /home/datascience/scripts/"
```

**Scripts e suas funcoes:**

| # | Script | Funcao | Tempo estimado |
|---|--------|--------|----------------|
| 1 | `feature_selection.py` | Funnel 5 estagios (IV > L1 > Corr > PSI > Leakage), 357 → 110 features | ~30 min |
| 2 | `train_credit_risk.py` | Treina 5 modelos com HPO params otimizados | ~2-4h |
| 3 | `ensemble.py` | 3 ensembles (Average, Blend, Stacking), seleciona champion | ~15 min |
| 4 | `batch_scoring.py` | Scoring 3.9M clientes com champion ensemble | ~30 min |
| 5 | `monitoring.py` | PSI por SAFRA, feature drift, backtesting, agreement | ~20 min |
| 6 | `data_quality.py` | Validacao Bronze/Silver/Gold via OCI CLI | ~5 min |
| 7 | `ds_job_runner.py` | Runner para OCI Data Science Jobs | ~5 min |
| 8 | `ensemble_comparison.py` | Comparacao detalhada entre ensembles | ~10 min |
| 9 | `swap_analysis.py` | Analise de swap entre modelos (pos-monitoring) | ~10 min |

---

## Passo 3 — Upload dos DAGs para o Airflow

O pipeline usa 2 DAGs separados (alem do legado unificado):

| DAG | Arquivo | Funcao |
|-----|---------|--------|
| `credit_risk_data_pipeline` | `credit_risk_data_pipeline.py` | Bronze → Silver → Gold (dados) |
| `credit_risk_ml_pipeline` | `credit_risk_ml_pipeline.py` | Feature Selection → Training → Ensemble → Scoring → Monitoring |
| `credit_risk_pipeline` | `credit_risk_pipeline.py` | DAG legado unificado (13 tasks) — opcional |

```bash
ORCH_IP="146.235.27.18"

# Upload dos 2 DAGs principais
scp -i $SSH_KEY infrastructure/dags/credit_risk_data_pipeline.py \
  opc@$ORCH_IP:/home/opc/airflow/dags/
scp -i $SSH_KEY infrastructure/dags/credit_risk_ml_pipeline.py \
  opc@$ORCH_IP:/home/opc/airflow/dags/

# (Opcional) Upload do DAG legado unificado
scp -i $SSH_KEY infrastructure/dags/credit_risk_pipeline.py \
  opc@$ORCH_IP:/home/opc/airflow/dags/

# Verificar DAGs detectados pelo Airflow
ssh -i $SSH_KEY opc@$ORCH_IP \
  "docker exec airflow-webserver airflow dags list | grep credit_risk"

# Configurar variaveis Airflow (se ainda nao configuradas)
ssh -i $SSH_KEY opc@$ORCH_IP << 'COMMANDS'
docker exec airflow-webserver airflow variables set COMPARTMENT_OCID \
  "ocid1.compartment.oc1..aaaaaaaa7uh2lfpsc6qf73g7zalgbr262a2v6veb4lreykqn57gtjvoojeuq"
docker exec airflow-webserver airflow variables set NOTEBOOK_IP "10.0.1.10"
COMMANDS
```

---

## Passo 4 — Trigger do Pipeline via Airflow

### Opcao A: 2 DAGs separados (recomendado)

```bash
# 1. Trigger do pipeline de dados (Bronze → Silver → Gold)
ssh -i $SSH_KEY opc@$ORCH_IP \
  "docker exec airflow-webserver airflow dags trigger credit_risk_data_pipeline"

# 2. Apos conclusao do data pipeline, trigger do ML pipeline
ssh -i $SSH_KEY opc@$ORCH_IP \
  "docker exec airflow-webserver airflow dags trigger credit_risk_ml_pipeline"
```

### Opcao B: DAG legado unificado

```bash
# Trigger manual do DAG unificado (13 tasks)
ssh -i $SSH_KEY opc@$ORCH_IP \
  "docker exec airflow-webserver airflow dags trigger credit_risk_pipeline"
```

### Monitoramento

```bash
# Opcao 1: Web UI
# Abrir http://146.235.27.18:8080 no browser

# Opcao 2: CLI
ssh -i $SSH_KEY opc@$ORCH_IP \
  "docker exec airflow-webserver airflow dags list-runs -d credit_risk_ml_pipeline --limit 3"
```

### Fluxo de execucao:

```
Data Pipeline (credit_risk_data_pipeline):
  run_bronze → validate_bronze → run_silver → validate_silver → run_gold → validate_gold

ML Pipeline (credit_risk_ml_pipeline):
  run_feature_selection → run_training → run_ensemble → run_scoring → run_monitoring → collect_artifacts

(DAG legado unificado: ambos os fluxos acima + run_data_quality em paralelo)
```

### Timeouts por task:

| Task | Timeout |
|------|---------|
| run_bronze | 2h |
| run_silver | 3h |
| run_gold | 3h |
| run_feature_selection | 2h |
| run_training | 4h |
| run_ensemble | 1h |
| run_scoring | 2h |
| run_monitoring | 1h |
| collect_artifacts | 15min |
| run_data_quality | 30min |

---

## Passo 5 — Execucao Manual (alternativa ao Airflow)

Caso prefira executar manualmente no notebook:

```bash
# SSH no notebook
ssh -i $SSH_KEY datascience@$NOTEBOOK_IP

# Instalar dependencias (se necessario)
pip install lightgbm xgboost catboost category-encoders psutil pyarrow

# Configurar variaveis de ambiente
export DATA_PATH="/home/datascience/data/clientes_consolidado/"
export ARTIFACT_DIR="/home/datascience/artifacts"
export OCI_NAMESPACE="grlxi07jz1mo"
export NOTEBOOK_OCPUS=$(nproc)

# Executar pipeline sequencial
cd /home/datascience/scripts

# 1. Feature Selection
python feature_selection.py

# 2. Training (5 modelos com HPO)
python train_credit_risk.py

# 3. Ensemble
python ensemble.py

# 4. Batch Scoring
python batch_scoring.py

# 5. Monitoring
python monitoring.py

# 6. Data Quality (validacao)
python data_quality.py --namespace grlxi07jz1mo --artifact-dir $ARTIFACT_DIR

# 7. (Opcional) Swap Analysis — apos monitoring, analisa troca de modelos
python swap_analysis.py

# 8. (Opcional) Ensemble Comparison — comparacao detalhada entre ensembles
python ensemble_comparison.py
```

---

## Passo 6 — Coletar Artefatos

```bash
# Baixar artefatos do notebook para local
LOCAL_DIR="artifacts/run_$(date +%Y%m%d)"
mkdir -p $LOCAL_DIR

scp -i $SSH_KEY -r datascience@$NOTEBOOK_IP:/home/datascience/artifacts/models/ $LOCAL_DIR/
scp -i $SSH_KEY -r datascience@$NOTEBOOK_IP:/home/datascience/artifacts/metrics/ $LOCAL_DIR/
scp -i $SSH_KEY -r datascience@$NOTEBOOK_IP:/home/datascience/artifacts/plots/ $LOCAL_DIR/
scp -i $SSH_KEY -r datascience@$NOTEBOOK_IP:/home/datascience/artifacts/monitoring/ $LOCAL_DIR/
scp -i $SSH_KEY -r datascience@$NOTEBOOK_IP:/home/datascience/artifacts/scoring/ $LOCAL_DIR/

echo "Artifacts downloaded to $LOCAL_DIR"
ls -lR $LOCAL_DIR
```

---

## Passo 7 — Validacao de Quality Gate QG-05

Apos execucao, verificar nos artefatos:

```bash
# Verificar resultados do treinamento
cat $LOCAL_DIR/metrics/training_results_*.json | python -m json.tool | grep -A5 "quality_gate"

# Verificar ensemble champion
cat $LOCAL_DIR/metrics/ensemble_results.json | python -m json.tool | grep -A3 "champion"

# Verificar monitoring status
cat $LOCAL_DIR/monitoring/monitoring_report.json | python -m json.tool | grep "overall_status"
```

### Criterios QG-05:

| Metrica | Threshold | Acao se FAIL |
|---------|-----------|--------------|
| KS OOT > 0.20 | Minimo discriminacao | Revisar features, rebalancear |
| AUC OOT > 0.65 | Minimo performance | Ajustar HPO, adicionar features |
| Gini OOT > 30% | Minimo discriminacao | Revisar target, dados |
| PSI < 0.25 | Estabilidade | Checar drift temporal |

---

## Passo 8 — (Opcional) Swap Analysis e Ensemble Comparison

Apos o monitoring, executar analises adicionais para validar a escolha do champion:

```bash
# Swap Analysis: analisa impacto de trocar modelos individuais no ensemble
ssh -i $SSH_KEY datascience@$NOTEBOOK_IP \
  "cd /home/datascience/scripts && python swap_analysis.py"

# Ensemble Comparison: comparacao detalhada entre os 3 ensembles
ssh -i $SSH_KEY datascience@$NOTEBOOK_IP \
  "cd /home/datascience/scripts && python ensemble_comparison.py"
```

Os resultados sao salvos em `artifacts/plots/` (ensemble_comparison.png) e `artifacts/metrics/`.

---

## Passo 9 — Gestao de Custos

```bash
# Parar infraestrutura quando nao em uso
ssh -i $SSH_KEY opc@$ORCH_IP "sudo systemctl stop docker"

# Desativar notebook (preserva dados)
oci data-science notebook-session deactivate \
  --notebook-session-id <NOTEBOOK_SESSION_OCID>

# Para reativar:
oci data-science notebook-session activate \
  --notebook-session-id <NOTEBOOK_SESSION_OCID>
```

---

## Orchestrator Lifecycle (Resize)

O ML pipeline requer 4 OCPUs / 64 GB. O orchestrator normalmente roda com 2 OCPUs / 16 GB para economia de custos. Antes de executar o ML pipeline, fazer resize-up; apos conclusao, resize-down.

```bash
INSTANCE_OCID="<ORCHESTRATOR_INSTANCE_OCID>"

# Resize-up antes do ML pipeline (4 OCPUs / 64 GB)
oci compute instance update \
  --instance-id $INSTANCE_OCID \
  --shape-config '{"ocpus": 4, "memoryInGBs": 64}' \
  --force

# Aguardar ~2 min para resize completar
# Verificar:
oci compute instance get --instance-id $INSTANCE_OCID \
  --query 'data."shape-config"' --output table

# Resize-down apos ML pipeline (2 OCPUs / 16 GB)
oci compute instance update \
  --instance-id $INSTANCE_OCID \
  --shape-config '{"ocpus": 2, "memoryInGBs": 16}' \
  --force
```

O DAG `credit_risk_ml_pipeline` inclui a task `resize_down_reminder` como ultimo passo para lembrar de reduzir a instancia.

---

## Tempos de Execucao (Run 20260311_015100 — Airflow)

Pipeline ML completo executado via Airflow em ~58 min (E3.Flex 4 OCPUs / 64 GB):

| Task | Tempo |
|------|-------|
| verify_instance | 0s |
| install_ml_packages | 2s |
| check_resources | 0s |
| check_gold_data | 0s |
| run_data_quality | 0s |
| run_feature_selection | 13.1 min |
| run_training | 30.5 min |
| run_ensemble | 3.3 min |
| run_scoring | 2.3 min |
| run_monitoring | 8.9 min |
| collect_artifacts | 0s |
| resize_down_reminder | 0s |
| **Total** | **~58 min** |

Feature Selection: 357 -> 185 (IV>0.02) -> 162 (L1) -> 114 (|r|<0.90) -> 110 (PSI<0.25) -> 110 (anti-leakage)
Dados: 600 parquets (100 por SAFRA x 6 SAFRAs) = 1.3 GB, 3,900,378 rows

---

## Artefatos Existentes (Run 20260311_015100 — Airflow, HPO-Optimized)

| Tipo | Quantidade | Detalhes |
|------|-----------|---------|
| Modelos (.pkl) | 8 | 334 MB (5 individuais + 3 ensembles) |
| Metricas (.json) | 7 | training, ensemble, champion, evaluation |
| Plots (.png) | 27 | Performance, SHAP, scoring, ensemble, stability |
| HPO params | 1 | best_params_all.json (953 B) |
| Feature Selection | 110 features | Funnel 5 estagios (357 -> 110) |
| Batch Scoring | 3,900,378 | Registros scored (mean=538, scale 0-1000) |

---

## Troubleshooting

### Notebook INACTIVE
```bash
oci data-science notebook-session activate --notebook-session-id <OCID>
# Aguardar ~5 min para ACTIVE
```

### OOM durante treinamento
- Verificar se `psutil` esta instalado
- Reduzir features: `FEATURE_SELECTION_MODE=legacy` (usa 59 features fixas em vez de 110)
- Usar swap: `sudo fallocate -l 8G /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile`

### Airflow DAG nao aparece
```bash
ssh opc@146.235.27.18 "docker exec airflow-webserver airflow dags list"
# Se nao aparecer, verificar logs:
ssh opc@146.235.27.18 "docker exec airflow-scheduler tail -50 /opt/airflow/logs/scheduler/latest/dagbag_loading.log"
```

### CatBoost nao instalado
```bash
pip install catboost
# O script trata graciosamente: se CatBoost nao instalado, treina 4 modelos
```
