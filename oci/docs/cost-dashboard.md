# Cost Dashboard — OCI Data Platform

**Period**: 2026-02-01 to 2026-03-07
**Trial Credit**: US$ 500.00 (creditos Oracle hackathon)
**Budget Alert (Terraform)**: R$ 500.00/month (alerta configurado)
**Total Spent (acumulado)**: R$ 171.71 (custos reportados em BRL pelo OCI)
**Current Month Spend (mar)**: R$ 28.85
**Forecast Monthly**: R$ 127.72

> **Nota sobre moeda**: O OCI reporta custos em **BRL** para a regiao sa-saopaulo-1.
> O credito do trial OCI e de **US$ 500** (programa hackathon Oracle).
> O budget de R$ 500/month no Terraform e um **alerta de monitoramento** configurado
> pela equipe, nao o limite real do trial. A taxa de conversao interna do OCI
> determina quanto dos US$ 500 de credito foi consumido.

---

## Cost Breakdown by Service (dados reais — OCI Usage API)

### Fevereiro 2026

| Service | Cost (R$) | % of Total | Notes |
|---------|-----------|------------|-------|
| Database (ADW) | 92.35 | 65.5% | ADW 2 ECPU + 1 TB storage. Principal custo — mesmo STOPPED gera custo de storage |
| Data Flow | 42.29 | 30.0% | 23 runs (7 succeeded, 12 failed, 4 canceled). 2,495 OCPU-hours |
| Object Storage | 6.40 | 4.5% | 6 buckets, ~461 objetos, ~209 GB-hours |
| Logging | 0.00 | 0.0% | Dentro do free tier |
| Telemetry | 0.00 | 0.0% | Dentro do free tier |
| VCN/Networking | 0.00 | 0.0% | Standard networking (free) |
| Data Science | 0.00 | 0.0% | Apenas projeto (sem notebook ativo) |
| **Total Fev** | **141.04** | **100%** | |

### Marco 2026 (parcial, ate 07/03)

| Service | Cost (R$) | Notes |
|---------|-----------|-------|
| Database (ADW) | 29.57 | ADW storage charges (STOPPED, sem compute) |
| Object Storage | 1.10 | Storage charges only |
| Logging/Telemetry | 0.00 | Free tier |
| **Total Mar (parcial)** | **30.67** | |

### Total Acumulado

| Periodo | Custo (R$) |
|---------|-----------|
| Fevereiro 2026 | 141.04 |
| Marco 2026 (parcial) | 30.67 |
| **Total** | **171.71** |
| **% do Budget** | **34.3%** |

---

## Monthly Projection by Scenario

### Scenario 1: Idle (ADW stopped, no pipeline runs)
ADW stopped, no Data Flow runs, storage only.

| Service | Monthly Est. |
|---------|-------------|
| ADW (STOPPED — storage only, 1 TB) | R$ 29.00 |
| Object Storage (6 buckets) | R$ 2.00 |
| Logging/Telemetry | R$ 0.00 |
| **Total** | **R$ 31.00** |

### Scenario 2: Development (weekly pipeline runs)
ADW started part-time, occasional Data Flow runs.

| Service | Monthly Est. |
|---------|-------------|
| ADW (started 8h/day, 5 days/week) | R$ 60.00 |
| Data Flow (3-5 runs/week) | R$ 15.00 |
| Object Storage | R$ 3.00 |
| **Total** | **R$ 78.00** |

### Scenario 3: Full Production (daily scoring, ADW 24/7)
Daily batch scoring, ADW always available, model endpoint.

| Service | Monthly Est. |
|---------|-------------|
| ADW (24/7, 2 ECPU) | R$ 92.00 |
| Data Flow (daily runs) | R$ 42.00 |
| Object Storage (growth) | R$ 8.00 |
| Data Science (notebook + deployment) | R$ 120.00 |
| Monitoring & Logging | R$ 5.00 |
| **Total** | **R$ 267.00** |

---

## Budget Alerts Configuration

Managed by Terraform `module.cost`:

| Alert | Threshold | Action |
|-------|-----------|--------|
| Budget Warning | 50% (R$ 250) | Email notification |
| Budget Critical | 80% (R$ 400) | Email + review required |
| Budget Exceeded | 100% (R$ 500) | Email + emergency stop |

Alert recipient: wandersonlima20@gmail.com

---

## Cost Optimization Measures

1. **ADW Start/Stop**: ADW kept STOPPED when not in active use. Compute savings: ~R$ 63/month (storage R$ 29/month remains)
2. **Data Flow On-Demand**: No idle compute costs. Pay only during pipeline runs
3. **ADW is NOT Free Tier**: `is-free-tier=false`. ADW storage (1 TB) gera custo mesmo quando STOPPED (~R$ 29/mes)
4. **Object Storage Tiering**: Standard tier sufficient for current volumes
5. **Notebook Session Control**: Deactivated when not in use
6. **ORDS Dashboard**: O dashboard de monitoramento (ORDS/APEX) roda dentro do ADW — custo zero adicional (incluso no compute/storage do ADW)

---

## Cost Monitoring Commands

```bash
# Quick cost report
bash oci/infrastructure/ops/cost-report.sh

# Detailed budget status
oci budgets budget list \
  --compartment-id $TENANCY_OCID \
  --query 'data[*].{Name:"display-name",Budget:amount,Spent:"actual-spend",Forecast:"forecasted-spend"}' \
  --output table

# Object Storage usage
for bucket in landing bronze silver gold logs scripts; do
  echo "pod-academy-${bucket}:"
  oci os object list --bucket-name pod-academy-${bucket} \
    --query 'data | length(@)' --raw-output
done
```

---

## Historical Spend (OCI Usage API — dados reais)

| Period | Spend (R$) | Activities |
|--------|-----------|------------|
| 2026-02 (Feb) | 141.04 | Full pipeline build: 23 Data Flow runs, ADW provisioning, model training |
| 2026-03 (parcial) | 30.67 | ADW storage (STOPPED) + Object Storage |
| **Acumulado** | **171.71** | **34.3% do budget de R$ 500** |

### Analise dos Custos

O principal driver de custo e o **ADW (Autonomous Data Warehouse)**:
- ADW cobra **storage** mesmo quando STOPPED (R$ ~29/mes por 1 TB)
- ADW cobra **compute (ECPU-hours)** quando AVAILABLE
- Em fevereiro, ADW ficou ativo por tempo suficiente para gerar R$ 92.35

O segundo maior custo e o **Data Flow**:
- 23 runs executados, 2,495 OCPU-hours consumidas
- Custo proporcional ao tempo de execucao (R$ 42.29)
- Runs com falha tambem consomem recursos

**Recomendacao**: Para minimizar custos pos-hackathon, fazer `terraform destroy` para eliminar o ADW e manter apenas Object Storage com os artifacts.

---

*Dashboard updated: 2026-03-07*
*Source: OCI Usage API (`oci usage-api usage-summary request-summarized-usages`)*
*Budget API: `oci budgets budget budget list`*
