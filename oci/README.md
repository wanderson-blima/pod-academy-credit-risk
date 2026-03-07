# Oracle Cloud Infrastructure — Pipeline de Credit Risk FPD

Evolucao cloud-native do pipeline de Credit Risk FPD, portado do Microsoft Fabric para **Oracle Cloud Infrastructure (OCI)**. Mantém paridade funcional com o pipeline Fabric, utilizando servicos nativos OCI.

## Arquitetura OCI

```
Object Storage (Bronze) → Data Flow/Spark (Silver) → ADW (Gold) → Data Science (Model) → Scoring Endpoint
```

| Camada | Servico OCI | Funcao |
|--------|-------------|--------|
| Bronze | Object Storage | Ingestao de dados brutos (CSV/Parquet) |
| Silver | Data Flow (Spark) | Transformacao e limpeza |
| Gold | Autonomous Data Warehouse | Feature store consolidada |
| Model | Data Science | Treinamento e deploy |

## Estrutura

```
oci/
├── infrastructure/
│   ├── terraform/          # IaC completa (6 modulos)
│   │   ├── main.tf, provider.tf, variables.tf, outputs.tf
│   │   ├── terraform.tfvars.example
│   │   └── modules/ (network, storage, database, dataflow, datascience, cost)
│   └── ops/                # Scripts operacionais (start/stop infra)
├── pipeline/               # Pipeline ETL (Bronze → Silver → Gold)
│   ├── ingest_bronze.py
│   ├── transform_silver.py
│   ├── engineer_gold.py
│   ├── validate_parity.py
│   └── cleanup_delta_orphans.py
├── model/                  # Treinamento e deploy de modelos
│   ├── train_credit_risk.py
│   ├── evaluate_model.py
│   ├── batch_scoring.py
│   ├── deploy_endpoint.py
│   ├── run_local_training.py
│   └── phase5_model_training_oci.ipynb
├── artifacts/              # Modelos treinados e metricas
│   ├── models/ (.pkl)
│   └── metrics/ (.json, .csv)
├── deliverable/            # Entregavel do hackathon
│   ├── scoring_validacao.py
│   ├── dados_exemplo.csv
│   ├── modelos/, metadata/
│   └── modelo-agnostico/ (Docker-ready scoring)
└── docs/                   # Documentacao OCI
    ├── prd-oci-pipeline-parity.md
    ├── oci-pipeline-execution-report.md
    ├── oci-e2e-validation-report.md
    ├── QUALITY-DASHBOARD.md
    └── oci-knowledge-base.md
```

## Infraestrutura como Codigo

A infraestrutura e 100% provisionada via **Terraform** com 6 modulos:

| Modulo | Recursos |
|--------|----------|
| `network` | VCN, subnets (publica, privada, bastion), security lists, NAT/Internet gateways |
| `storage` | Object Storage buckets (bronze, silver, gold, scripts, logs) |
| `database` | Autonomous Data Warehouse (ADW) |
| `dataflow` | Data Flow applications (bronze, silver, gold) + pool |
| `datascience` | Data Science project + notebook session |
| `cost` | Budget alerts + cost tracking |

### Quick Start

```bash
cd infrastructure/terraform/
cp terraform.tfvars.example terraform.tfvars
# Editar terraform.tfvars com suas credenciais OCI

terraform init
terraform plan
terraform apply
```

## Resultados

Pipeline OCI alcanca **paridade funcional** com o pipeline Fabric:

- Mesmo pipeline Medallion (Bronze → Silver → Gold)
- Mesmas features e transformacoes
- Modelos treinados com metricas equivalentes
- Scoring endpoint containerizado (Docker-ready)

Para comparacao detalhada, veja [`docs/oci-e2e-validation-report.md`](docs/oci-e2e-validation-report.md).
