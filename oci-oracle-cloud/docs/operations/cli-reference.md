# Referencia Rapida OCI CLI - Operacoes Comuns

## Configuracao

```bash
# Variaveis de ambiente (ajustar conforme necessario)
export COMPARTMENT_ID="ocid1.compartment.oc1..aaaaaaaa7uh2lfpsc6qf73g7zalgbr262a2v6veb4lreykqn57gtjvoojeuq"
export NAMESPACE="grlxi07jz1mo"
export REGION="sa-saopaulo-1"
export ADW_ID="ocid1.autonomousdatabase.oc1.sa-saopaulo-1.antxeljr6dlb45iaangy5wpt4wec6ymecn7gpfzxzkag4xnyevcwn2elxlrq"
```

**Nota**: No Orchestrator VM, utilizar `--auth instance_principal` ao inves de `--auth api_key` (nao ha `~/.oci/config` configurado na VM).

---

## 1. Gerenciamento de Instancias

### Listar instancias do compartment

```bash
oci compute instance list \
  --compartment-id $COMPARTMENT_ID \
  --query 'data[].{nome:"display-name", estado:"lifecycle-state", id:id}' \
  --output table
```

### Iniciar instancia

```bash
oci compute instance action \
  --instance-id <INSTANCE_OCID> \
  --action START
```

### Parar instancia (soft stop)

```bash
oci compute instance action \
  --instance-id <INSTANCE_OCID> \
  --action SOFTSTOP
```

### Verificar estado de uma instancia

```bash
oci compute instance get \
  --instance-id <INSTANCE_OCID> \
  --query 'data.{"estado":"lifecycle-state","nome":"display-name"}' \
  --output table
```

---

## 2. Conectar via SSH

### Orchestrator (IP publico)

```bash
ssh -i ~/.ssh/oci_pipeline opc@146.235.27.18
```

### Notebook (via Orchestrator como jump host)

```bash
ssh -i ~/.ssh/oci_pipeline -J opc@146.235.27.18 opc@10.0.1.10
```

### Copiar arquivos para o Orchestrator

```bash
scp -i ~/.ssh/oci_pipeline arquivo.py opc@146.235.27.18:/home/opc/
```

### Copiar arquivos para o Notebook (via jump host)

```bash
scp -i ~/.ssh/oci_pipeline -o ProxyJump=opc@146.235.27.18 arquivo.py opc@10.0.1.10:/home/opc/
```

---

## 3. Object Storage

### Listar buckets

```bash
oci os bucket list \
  --compartment-id $COMPARTMENT_ID \
  --namespace-name $NAMESPACE \
  --query 'data[].name' \
  --output table
```

### Listar objetos em um bucket

```bash
oci os object list \
  --bucket-name gold \
  --namespace-name $NAMESPACE \
  --query 'data[].name' \
  --output table
```

### Download de arquivo

```bash
oci os object get \
  --bucket-name gold \
  --namespace-name $NAMESPACE \
  --name "caminho/do/arquivo.parquet" \
  --file ./arquivo_local.parquet
```

### Download de pasta (bulk)

```bash
oci os object bulk-download \
  --bucket-name gold \
  --namespace-name $NAMESPACE \
  --prefix "clientes_consolidado/" \
  --download-dir ./dados_gold/
```

### Upload de arquivo

```bash
oci os object put \
  --bucket-name landing \
  --namespace-name $NAMESPACE \
  --name "dados/novo_arquivo.csv" \
  --file ./novo_arquivo.csv
```

### Upload de pasta (bulk)

```bash
oci os object bulk-upload \
  --bucket-name landing \
  --namespace-name $NAMESPACE \
  --src-dir ./dados_locais/ \
  --prefix "upload_20260310/"
```

### Verificar tamanho de um bucket

```bash
oci os object list \
  --bucket-name gold \
  --namespace-name $NAMESPACE \
  --query 'data[].size' \
  --all \
  --output json | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'{sum(d)/1e9:.2f} GB')"
```

---

## 4. Airflow (API REST)

### Verificar se o Airflow esta rodando

```bash
curl -s http://146.235.27.18:8080/health | python3 -m json.tool
```

### Listar DAGs

```bash
curl -s -u admin:admin \
  http://146.235.27.18:8080/api/v1/dags \
  | python3 -c "import json,sys; dags=json.load(sys.stdin)['dags']; [print(f\"{d['dag_id']}: {d['is_paused']}\") for d in dags]"
```

### Trigger de uma DAG

```bash
curl -X POST \
  -u admin:admin \
  -H "Content-Type: application/json" \
  -d '{"conf": {}}' \
  http://146.235.27.18:8080/api/v1/dags/credit_risk_pipeline/dagRuns
```

### Verificar status da ultima execucao

```bash
curl -s -u admin:admin \
  "http://146.235.27.18:8080/api/v1/dags/credit_risk_pipeline/dagRuns?order_by=-start_date&limit=1" \
  | python3 -m json.tool
```

### Verificar status de tasks de uma execucao

```bash
curl -s -u admin:admin \
  "http://146.235.27.18:8080/api/v1/dags/credit_risk_pipeline/dagRuns/<DAG_RUN_ID>/taskInstances" \
  | python3 -c "
import json, sys
tasks = json.load(sys.stdin)['task_instances']
for t in tasks:
    print(f\"{t['task_id']:30s} {t['state']}\")"
```

### Pausar/Despausar uma DAG

```bash
# Pausar
curl -X PATCH -u admin:admin \
  -H "Content-Type: application/json" \
  -d '{"is_paused": true}' \
  http://146.235.27.18:8080/api/v1/dags/credit_risk_pipeline

# Despausar
curl -X PATCH -u admin:admin \
  -H "Content-Type: application/json" \
  -d '{"is_paused": false}' \
  http://146.235.27.18:8080/api/v1/dags/credit_risk_pipeline
```

---

## 5. ADW (Autonomous Database)

### Verificar status do ADW

```bash
oci db autonomous-database get \
  --autonomous-database-id $ADW_ID \
  --query 'data.{"estado":"lifecycle-state","nome":"display-name","ocpus":"cpu-core-count"}' \
  --output table
```

### Parar ADW

```bash
oci db autonomous-database stop \
  --autonomous-database-id $ADW_ID
```

### Iniciar ADW

```bash
oci db autonomous-database start \
  --autonomous-database-id $ADW_ID
```

### Acessar APEX (navegador)

```
https://G95D3985BD0D2FD-PODACADEMY.adb.sa-saopaulo-1.oraclecloudapps.com/ords/apex
```

**Credenciais**:
- ADMIN: `CreditRisk2026#ADW`
- MLMONITOR: `CreditRisk2026#ML`

---

## 6. Data Science (Notebook Session)

### Listar notebook sessions

```bash
oci data-science notebook-session list \
  --compartment-id $COMPARTMENT_ID \
  --query 'data[].{"nome":"display-name","estado":"lifecycle-state","id":id}' \
  --output table
```

### Ativar notebook session

```bash
oci data-science notebook-session activate \
  --notebook-session-id <NOTEBOOK_SESSION_OCID>
```

### Desativar notebook session

```bash
oci data-science notebook-session deactivate \
  --notebook-session-id <NOTEBOOK_SESSION_OCID>
```

---

## 7. Data Catalog

### Verificar status

```bash
oci data-catalog catalog get \
  --catalog-id ocid1.datacatalog.oc1.sa-saopaulo-1.amaaaaaa7ratcziaojodsijuxmfgdhsxnnes3ekivu2x4wpf3a5f63vsoxgq \
  --query 'data.{"estado":"lifecycle-state","nome":"display-name"}' \
  --output table
```

---

## 8. Monitoramento e Custos

### Verificar uso de creditos

```bash
oci account subscription list \
  --compartment-id $COMPARTMENT_ID \
  --query 'data[].{"moeda":"currency","usado":"total-consumed","disponivel":"total-value"}' \
  --output table
```

### Listar alertas de custo

```bash
oci budgets budget list \
  --compartment-id $COMPARTMENT_ID \
  --query 'data[].{"nome":"display-name","valor":"amount","gasto":"actual-spend"}' \
  --output table
```

---

## 9. Terraform

### Comandos basicos (executar de `oci/infrastructure/terraform/`)

```bash
# Inicializar
terraform init

# Planejar (ambiente dev)
terraform plan -var-file=terraform.tfvars.dev

# Aplicar (ambiente dev)
terraform apply -var-file=terraform.tfvars.dev

# Verificar estado
terraform state list

# Ver detalhes de um recurso
terraform state show <RESOURCE_ADDRESS>

# Destruir (CUIDADO)
terraform destroy -var-file=terraform.tfvars.dev
```

---

## 10. Operacoes do Pipeline Completo

### Fluxo tipico de execucao

```bash
# 1. Verificar infraestrutura
oci compute instance list --compartment-id $COMPARTMENT_ID --output table

# 2. Iniciar Orchestrator (se parado)
oci compute instance action --instance-id <ORCH_OCID> --action START

# 3. Aguardar Airflow subir (~2 min)
until curl -s http://146.235.27.18:8080/health | grep -q healthy; do sleep 10; done

# 4. Trigger do pipeline
curl -X POST -u admin:admin \
  -H "Content-Type: application/json" \
  -d '{"conf": {}}' \
  http://146.235.27.18:8080/api/v1/dags/credit_risk_pipeline/dagRuns

# 5. Monitorar execucao
watch -n 30 'curl -s -u admin:admin \
  "http://146.235.27.18:8080/api/v1/dags/credit_risk_pipeline/dagRuns?order_by=-start_date&limit=1" \
  | python3 -m json.tool'

# 6. Apos conclusao, parar para economizar
oci compute instance action --instance-id <ORCH_OCID> --action SOFTSTOP
```

### Tempos esperados do pipeline

| Etapa | Tempo |
|-------|-------|
| Bronze (19 tabelas, 163M linhas) | ~22 min |
| Silver (deduplicacao) | ~25.5 min |
| Gold (feature engineering) | ~4h58 |
| Treinamento (5 modelos + ensemble) | ~2-3h |
| Scoring (3.9M registros) | ~30 min |
| **Total end-to-end** | **~8-9h** |
