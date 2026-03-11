# Scripts Operacionais — OCI Credit Risk Platform

Scripts bash e PowerShell para gerenciamento do ciclo de vida da infraestrutura OCI.

## Inventario de Scripts

### Lifecycle (Start/Stop)

| Script | Plataforma | Descricao |
|--------|------------|-----------|
| `start-infra.sh` | Linux/Mac | Inicia todos os recursos OCI stopaveis (ADW, Notebook, Orchestrator) |
| `stop-infra.sh` | Linux/Mac | Para todos os recursos OCI stopaveis para economia |
| `start-infra.ps1` | Windows | Equivalente PowerShell do start-infra.sh |
| `stop-infra.ps1` | Windows | Equivalente PowerShell do stop-infra.sh |
| `orchestrator-lifecycle.sh` | Linux/Mac | Start/stop/resize do orchestrator (Airflow VM) |
| `destroy-infra.sh` | Linux/Mac | Executa `terraform destroy` com confirmacao |

### Validacao

| Script | Descricao | Output |
|--------|-----------|--------|
| `health-check.sh` | Verifica status de TODOS os componentes OCI | Terminal (verde/vermelho) |
| `validate_buckets.sh` | Inventario de buckets e objetos | `evidence/story-2.1/bucket_inventory.json` |
| `validate_bronze.sh` | Valida integridade do layer Bronze | `evidence/story-2.2/bronze_tables.json` |
| `validate_notebook.sh` | Verifica Notebook Session ativo | `evidence/story-4.1/notebook_status.json` |
| `validate_model_catalog.sh` | Verifica registro no Model Catalog | `evidence/story-4.3/model_ocids.json` |
| `validate_scores.sh` | Valida output de batch scoring no Gold bucket | `evidence/story-4.4/score_distribution.json` |
| `validate_deployment.sh` | Testa endpoint REST de model deployment | `evidence/story-4.5/endpoint_url.json` |
| `validate_catalog.sh` | Verifica harvest do Data Catalog | `evidence/story-5.3/catalog_harvest.json` |

### Data & Pipeline

| Script | Descricao |
|--------|-----------|
| `upload_scripts.sh` | Upload dos scripts Python para Object Storage |
| `run_silver.sh` | Executa Data Flow run para camada Silver |
| `run_gold.sh` | Executa Data Flow run para camada Gold |
| `backup-data.sh` | Backup de dados criticos (artifacts, configs) |

### Setup & Custos

| Script | Plataforma | Descricao |
|--------|------------|-----------|
| `conda-setup.sh` | Linux | Setup do ambiente conda no Notebook/Orchestrator |
| `cost-report.sh` | Linux/Mac | Consulta custos OCI do mes atual |
| `cost-report.ps1` | Windows | Equivalente PowerShell |
| `cost-check.ps1` | Windows | Verificacao rapida de custos |
| `harvest-catalog.sh` | Linux/Mac | Cria assets e executa harvest no Data Catalog |

### Outros

| Arquivo | Descricao |
|---------|-----------|
| `check-adw.ps1` | Verifica status do ADW (PowerShell) |
| `terraform.tfvars.template` | Template alternativo de variaveis Terraform |

## Workflows Comuns

### 1. Iniciar ambiente para ML pipeline

```bash
# 1. Verificar saude geral
bash health-check.sh

# 2. Iniciar recursos (se parados)
bash start-infra.sh

# 3. Resize orchestrator para ML (4 OCPUs / 64 GB)
bash orchestrator-lifecycle.sh resize-up

# 4. Executar pipeline via Airflow
ssh -i ~/.ssh/oci_pipeline opc@146.235.27.18
docker exec airflow-webserver airflow dags trigger credit_risk_ml_pipeline
```

### 2. Parar ambiente apos ML (economia)

```bash
# 1. Resize down orchestrator (2 OCPUs / 16 GB)
bash orchestrator-lifecycle.sh resize-down

# 2. Parar recursos nao essenciais
bash stop-infra.sh

# 3. Verificar custos
bash cost-report.sh
```

### 3. Validacao completa (gerar evidencias)

```bash
# Executar todas as validacoes em sequencia
bash validate_buckets.sh       # Story 2.1
bash validate_bronze.sh        # Story 2.2
bash validate_notebook.sh      # Story 4.1
bash validate_model_catalog.sh # Story 4.3
bash validate_scores.sh        # Story 4.4
bash validate_deployment.sh    # Story 4.5
bash validate_catalog.sh       # Story 5.3
```

### 4. Destruir infraestrutura (cleanup final)

```bash
# 1. Backup de dados importantes
bash backup-data.sh

# 2. Destruir via Terraform
bash destroy-infra.sh
# (pede confirmacao interativa)
```

## Pre-requisitos

- **OCI CLI** configurado (`oci setup config`)
- **jq** instalado (para parsing de JSON)
- **SSH Key** em `~/.ssh/oci_pipeline` (para acesso ao orchestrator)
- **Variaveis de ambiente** (opcional):
  - `COMPARTMENT_OCID` — OCID do compartment
  - `NAMESPACE` — Object Storage namespace (`grlxi07jz1mo`)

## Estimativa de Custos Mensais

| Recurso | Spec | Custo/Hora | Custo/Mes (24x7) | Custo/Mes (8h/dia) |
|---------|------|------------|-------------------|---------------------|
| **Orchestrator** (idle) | E3.Flex 2 OCPUs / 16 GB | ~R$ 0.40 | ~R$ 290 | ~R$ 97 |
| **Orchestrator** (ML) | E3.Flex 4 OCPUs / 64 GB | ~R$ 0.80 | N/A | ~R$ 5/run |
| **Notebook** | E4.Flex 10 OCPUs / 160 GB | ~R$ 2.00 | ~R$ 1,440 | ~R$ 480 |
| **ADW** | Always Free (2 ECPUs) | Gratuito | Gratuito | Gratuito |
| **Data Catalog** | Always Free | Gratuito | Gratuito | Gratuito |
| **Object Storage** | ~2 GB (4 buckets) | ~R$ 0.01 | ~R$ 5 | ~R$ 5 |
| **Data Flow** | Sob demanda | ~R$ 50/run | N/A | N/A |

**Recomendacao**: Manter apenas ADW + Object Storage ligados continuamente. Ligar Orchestrator e Notebook apenas quando necessario. Parar com `stop-infra.sh` apos uso.

**Trial OCI (US$ 500)**: Com uso otimizado (start/stop), o trial dura ~3 meses.
