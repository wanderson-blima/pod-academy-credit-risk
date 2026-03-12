# Guia de Arquitetura OCI - Plataforma de Risco de Credito

## Visao Geral

A plataforma de risco de credito foi implantada na Oracle Cloud Infrastructure (OCI) na regiao **sa-saopaulo-1**, utilizando instancias **E3.Flex** como base computacional. A arquitetura segue o padrao Medallion (Bronze/Silver/Gold) com orquestracao via Apache Airflow em Docker.

**Run ID de Referencia**: `20260311_015100`
**Plataforma de Treinamento**: VM.Standard.E3.Flex (4 OCPUs / 64 GB)

---

## Componentes da Arquitetura

### 1. Object Storage (4 Buckets)

| Bucket | Camada | Descricao |
|--------|--------|-----------|
| `landing` | Ingestao | Arquivos brutos (CSV, Parquet, Excel) |
| `bronze` | Bronze | Dados raw em formato Delta Lake, 19 tabelas, 163M linhas |
| `silver` | Silver | Dados limpos e deduplicados, 275K duplicatas removidas |
| `gold` | Gold | Feature store consolidada, 3.9M x 402 colunas |

**Namespace**: `grlxi07jz1mo`

### 2. Orchestrator (E3.Flex + Docker Airflow)

- **IP Publico**: 146.235.27.18:8080
- **Shape**: VM.Standard.E3.Flex
- **Runtime**: Apache Airflow em Docker (docker-compose)
- **DAGs**: `credit_risk_data_pipeline` (3 tasks) + `credit_risk_ml_pipeline` (12 tasks)
- **Funcao**: Orquestracao end-to-end do pipeline de dados e ML

### 3. Notebook (E3.Flex - Data Science)

- **IP Privado**: 10.0.1.10
- **Shape**: VM.Standard.E3.Flex
- **Status**: Pode estar INACTIVE (parar para economia de custos)
- **Funcao**: Desenvolvimento, treinamento de modelos, notebooks Jupyter
- **Scripts**: 6 scripts Python de producao

### 4. Autonomous Data Warehouse (ADW)

- **Tier**: Always Free
- **APEX URL**: `https://G95D3985BD0D2FD-PODACADEMY2.adb.sa-saopaulo-1.oraclecloudapps.com/ords/apex`
- **Funcao**: Armazenamento de metricas, dashboard de monitoramento

### 5. APEX Dashboard

- **Integrado ao ADW**: Dashboard de monitoramento de modelos
- **Metricas**: KS, AUC, Gini, PSI, distribuicao de scores
- **Faixas de Risco**: CRITICO (<300), ALTO (300-499), MEDIO (500-699), BAIXO (>=700)

### 6. Data Catalog

- **Tier**: Always Free, ACTIVE
- **Funcao**: Governanca de dados, catalogacao de assets do Object Storage

---

## Diagrama de Infraestrutura

```mermaid
graph TB
    subgraph VCN["VCN - Credit Risk Network (10.0.0.0/16)"]
        subgraph PUB["Subnet Publica (10.0.0.0/24)"]
            ORCH["Orchestrator<br/>E3.Flex 4 OCPUs / 64 GB<br/>146.235.27.18:8080<br/>Docker Airflow"]
        end

        subgraph PRIV["Subnet Privada (10.0.1.0/24)"]
            NB["Notebook<br/>E3.Flex<br/>10.0.1.10<br/>Data Science"]
        end

        ORCH -->|SSH / API| NB
    end

    subgraph OCI_SERVICES["Servicos OCI"]
        OS["Object Storage<br/>4 Buckets<br/>landing / bronze / silver / gold"]
        ADW["ADW Always Free<br/>+ APEX Dashboard"]
        DC["Data Catalog<br/>Always Free"]
    end

    ORCH -->|Leitura/Escrita| OS
    NB -->|Leitura/Escrita| OS
    ORCH -->|Metricas + Scores| ADW
    DC -->|Cataloga| OS

    USER["Usuario"] -->|SSH ~/.ssh/oci_pipeline| ORCH
    USER -->|HTTPS| ADW
```

---

## Diagrama do Pipeline Completo (Airflow Orchestration)

```mermaid
graph LR
    subgraph SOURCES["Fontes de Dados"]
        CSV["CSV / Excel<br/>(Claro)"]
        PARQUET["Parquet<br/>(Feature Store)"]
    end

    subgraph DAG1["DAG: credit_risk_data_pipeline"]
        direction TB
        B["Bronze<br/>19 tabelas<br/>163M rows"]
        S["Silver<br/>Dedup + Tipagem<br/>-275K dupes"]
        G["Gold<br/>Feature Engineering<br/>3.9M x 402 cols"]
        B --> S --> G
    end

    subgraph DAG2["DAG: credit_risk_ml_pipeline"]
        direction TB
        FS["Feature Selection<br/>5-stage funnel<br/>357 → 110 features"]
        TR["Training<br/>5 modelos HPO<br/>LR, LGBM, XGB, CB, RF"]
        EN["Ensemble<br/>Top-3 Average<br/>LGBM + XGB + CB"]
        SC["Batch Scoring<br/>3.9M clientes<br/>Score 0-1000"]
        MO["Monitoring<br/>PSI + Drift<br/>+ Backtesting"]
        FS --> TR --> EN --> SC --> MO
    end

    subgraph CONSUME["Consumption Layer"]
        APEX["APEX Dashboard<br/>KS/AUC/Gini/PSI<br/>4 abas interativas"]
        CATALOG["Data Catalog<br/>Governanca<br/>+ Linhagem"]
        PKL["6 Pipelines PKL<br/>Self-contained<br/>Scoring"]
    end

    CSV --> B
    PARQUET --> B
    G --> FS
    MO --> APEX
    SC --> PKL
    G --> CATALOG

    style B fill:#CD7F32,color:#fff,stroke:#D99A5B
    style S fill:#A8A9AD,color:#000,stroke:#C0C0C0
    style G fill:#FFD700,color:#000,stroke:#FFE44D

    subgraph AIRFLOW["Apache Airflow (Orchestrator)"]
        direction LR
        AF["Airflow Scheduler<br/>146.235.27.18:8080"]
    end

    AF -.->|"Orquestra"| DAG1
    AF -.->|"Orquestra"| DAG2
```

---

## Diagrama do ML Pipeline (Detalhado)

```mermaid
graph TB
    subgraph PREFLIGHT["Preflight Checks"]
        V1["verify_instance<br/>4 OCPUs / 64 GB?"]
        V2["install_ml_packages<br/>pip install"]
        V3["check_resources<br/>CPU, RAM, disco"]
        V4["check_gold_data<br/>600 parquets?"]
        V1 --> V2 --> V3 --> V4
    end

    subgraph FEATURE["Feature Selection"]
        F1["IV Filter<br/>357 → 185<br/>(IV > 0.02)"]
        F2["L1 Selection<br/>185 → 162"]
        F3["Correlation<br/>162 → 114<br/>(|r| < 0.90)"]
        F4["PSI Stability<br/>114 → 110<br/>(PSI < 0.25)"]
        F5["Anti-leakage<br/>110 → 110"]
        F1 --> F2 --> F3 --> F4 --> F5
    end

    subgraph TRAINING["Model Training (HPO)"]
        M1["LR L1 v2<br/>KS=0.3314"]
        M2["LightGBM v2<br/>KS=0.3494"]
        M3["XGBoost<br/>KS=0.3494"]
        M4["CatBoost<br/>KS=0.3482"]
        M5["Random Forest<br/>KS=0.3370"]
    end

    subgraph ENSEMBLE["Ensemble Selection"]
        E1["Simple Average<br/>(All 5)"]
        E2["Blend SLSQP<br/>(All 5)"]
        E3["Stacking LR<br/>(All 5)"]
        CHAMP["Champion<br/>Top-3 Average<br/>LGBM+XGB+CB<br/>KS=0.3501<br/>AUC=0.7368"]
        E1 --> CHAMP
        E2 --> CHAMP
        E3 --> CHAMP
    end

    subgraph SCORING["Batch Scoring"]
        SC1["3,900,378 clientes"]
        SC2["Score 0-1000"]
        SC3["4 Faixas de Risco"]
        SC1 --> SC2 --> SC3
    end

    subgraph MONITORING["Model Monitoring"]
        MO1["Score PSI<br/>(por SAFRA)"]
        MO2["Feature Drift<br/>(top 20 features)"]
        MO3["Backtesting<br/>(KS/AUC por SAFRA)"]
        MO4["Agreement Rate<br/>(entre 5 modelos)"]
    end

    PREFLIGHT --> FEATURE
    FEATURE --> TRAINING
    TRAINING --> ENSEMBLE
    ENSEMBLE --> SCORING
    SCORING --> MONITORING

    MONITORING --> REPORT["monitoring_report.json<br/>+ 6 PKLs self-contained"]
    MONITORING --> DASH["APEX Dashboard<br/>ADW + ORDS + Chart.js"]

    subgraph QG["Quality Gate QG-05"]
        Q1["KS OOT > 0.20 ✅"]
        Q2["AUC OOT > 0.65 ✅"]
        Q3["Gini OOT > 30% ✅"]
        Q4["PSI < 0.25 ✅"]
    end

    TRAINING --> QG
```

---

## Diagrama de Custos e Recursos

```mermaid
graph LR
    subgraph FREE["Always Free (R$ 0)"]
        ADW_F["ADW<br/>2 ECPUs"]
        DC_F["Data Catalog"]
        OS_F["Object Storage<br/>(10 GB/bucket)"]
    end

    subgraph COMPUTE["Compute (pago por hora)"]
        ORCH_IDLE["Orchestrator Idle<br/>2 OCPUs / 16 GB<br/>~R$ 0.40/h"]
        ORCH_ML["Orchestrator ML<br/>4 OCPUs / 64 GB<br/>~R$ 0.80/h"]
        NB_C["Notebook<br/>10 OCPUs / 160 GB<br/>~R$ 2.00/h"]
    end

    subgraph ONDEMAND["Sob Demanda"]
        DF["Data Flow<br/>~R$ 50/run"]
    end

    ORCH_IDLE -->|"resize-up<br/>(antes do ML)"| ORCH_ML
    ORCH_ML -->|"resize-down<br/>(apos ML)"| ORCH_IDLE
```

---

## Rede (VCN)

### Configuracao

| Recurso | CIDR / Detalhe |
|---------|----------------|
| VCN | 10.0.0.0/16 |
| Subnet Publica | 10.0.0.0/24 (Orchestrator) |
| Subnet Privada | 10.0.1.0/24 (Notebook) |
| Internet Gateway | Trafego publico para Orchestrator |
| NAT Gateway | Saida para Notebook (subnet privada) |
| Service Gateway | Acesso a servicos OCI internos |

### Security Lists

- **Publica**: Ingress TCP 22 (SSH), TCP 8080 (Airflow UI), Egress all
- **Privada**: Ingress TCP 22 (SSH do Orchestrator), Egress via NAT Gateway

---

## Terraform

### Modulos (9 modulos)

```
infrastructure/terraform/
├── main.tf
├── variables.tf
├── outputs.tf
├── provider.tf
├── terraform.tfstate          # Estado local
├── terraform.tfvars.dev       # Variaveis DEV
├── terraform.tfvars.prd       # Variaveis PRD
├── terraform.tfvars.example
└── modules/
    ├── cost/                  # Orcamento e alertas
    ├── data-catalog/          # Data Catalog
    ├── database/              # ADW
    ├── dataflow/              # Data Flow (Spark)
    ├── datascience/           # Notebook Session
    ├── monitoring/            # Alarmes e notificacoes
    ├── network/               # VCN, subnets, gateways
    ├── orchestrator/          # VM + Docker Airflow
    └── storage/               # Object Storage buckets
```

### Comandos Basicos

```bash
# Inicializar (ja executado)
cd infrastructure/terraform
terraform init

# Planejar alteracoes
terraform plan -var-file=terraform.tfvars.dev

# Aplicar
terraform apply -var-file=terraform.tfvars.dev

# Verificar estado
terraform state list
```

### Estado

- **Backend**: Local (`terraform.tfstate`)
- **Status**: Inicializado e aplicado com sucesso

---

## Pre-requisitos

### 1. OCI CLI

```bash
# Instalacao
bash -c "$(curl -L https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh)"

# Configuracao
oci setup config
```

### 2. Chave SSH

```bash
# Par de chaves utilizado
~/.ssh/oci_pipeline       # Chave privada
~/.ssh/oci_pipeline.pub   # Chave publica
```

### 3. Acesso ao Compartment

```
Compartment OCID: ocid1.compartment.oc1..aaaaaaaa7uh2lfpsc6qf73g7zalgbr262a2v6veb4lreykqn57gtjvoojeuq
Tenancy OCID:     ocid1.tenancy.oc1..aaaaaaaahse5thvzinsvm7bkyrd3zravzao2i6kpfl4bfxkplbu7ppla5x5a
Region:           sa-saopaulo-1
```

### 4. Terraform >= 1.0

```bash
terraform version
```

---

## Limitacoes do Trial

### ARM A1 (Ampere)

- **Status**: OUT_OF_HOST_CAPACITY em sa-saopaulo-1
- **Impacto**: Nao foi possivel provisionar instancias ARM A1 (Always Free)
- **Solucao adotada**: Todas as instancias utilizam shapes E3.Flex

### E3.Flex

- **Limite Trial**: Maximo 4 OCPUs por instancia (request de 8/128 bloqueado por LimitExceeded)
- **Configuracao usada**: E3.Flex com 4 OCPUs / 64 GB RAM para treinamento ML

### Data Science

- **Limite separado**: 24 OCPUs para servico Data Science
- **Permite**: Instancias maiores para treinamento de modelos

### Availability Domain

- **Unico AD disponivel**: TjOZ:SA-SAOPAULO-1-AD-1
- **Impacto**: Sem redundancia multi-AD

### Credito Trial

- **Valor**: $500 USD
- **Servicos Always Free**: ADW, Data Catalog, Object Storage (10 GB por bucket)

---

## Identificadores Chave

| Recurso | Identificador |
|---------|---------------|
| Namespace | `grlxi07jz1mo` |
| Region | `sa-saopaulo-1` |
| Compartment | `ocid1.compartment.oc1..aaaaaaaa7uh2lfpsc6qf73g7zalgbr262a2v6veb4lreykqn57gtjvoojeuq` |
| Tenancy | `ocid1.tenancy.oc1..aaaaaaaahse5thvzinsvm7bkyrd3zravzao2i6kpfl4bfxkplbu7ppla5x5a` |
| AD | `TjOZ:SA-SAOPAULO-1-AD-1` |
| ADW APEX | `G95D3985BD0D2FD-PODACADEMY2` |
