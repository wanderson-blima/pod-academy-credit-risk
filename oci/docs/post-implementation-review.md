# Post-Implementation Review — OCI Data Platform

**Date**: 2026-03-07
**Project**: Fabric-to-OCI Migration for Credit Risk FPD Pipeline
**Duration**: ~3 weeks (Feb 2026)

---

## Objective

Migrate the complete credit risk pipeline (data engineering + ML) from Microsoft Fabric to Oracle Cloud Infrastructure, achieving data and model parity while demonstrating cloud-native IaC practices.

**Result**: Migration COMPLETE. 100% data parity, 100% model parity (10/10 metrics), within US$ 500 trial credit.

---

## What Worked Well

### 1. Infrastructure as Code (Terraform)
- 7 modular Terraform configurations (network, storage, database, dataflow, datascience, cost, monitoring)
- 43 resources provisioned reproducibly
- Full tear-down and re-creation possible in ~20 minutes
- Modular design allowed independent testing of each layer

### 2. Medallion Architecture Portability
- Same Bronze/Silver/Gold pattern translated cleanly from Fabric to OCI
- Delta Lake format in Fabric mapped to Parquet + Object Storage in OCI
- Feature engineering logic required minimal changes between platforms

### 3. Model Parity Achievement
- 10/10 parity metrics PASS (within tolerance: KS +-2pp, AUC +-0.005)
- PSI stability: 0.0007 (LR), 0.0012 (LGBM) — near-zero drift
- Identical feature set (59 features) and preprocessing pipeline
- sklearn compatibility patch (force_all_finite) solved cross-version issues

### 4. Cost Efficiency
- R$ 171.71 total spend dentro do credito trial de US$ 500
- Data Flow on-demand pricing (R$ 42.29) — pay only during runs
- ADW is the largest cost driver (R$ 121.92) — storage charges persist even when STOPPED

### 5. Security by Default
- No public access on any bucket
- Least-privilege IAM policies (3 scoped policies)
- Dynamic groups for resource principals
- KMS vault with customer-managed encryption key

---

## What Didn't Work

### 1. OCI Trial Resource Limits
- **Impact**: Could not provision Data Science notebook (LimitExceeded)
- **Workaround**: Local training on OCI-connected machine with same data
- **Lesson**: Trial accounts have undocumented OCPU caps per service. Plan for this in POCs.

### 2. Gold Pipeline Performance
- **Impact**: Gold feature engineering took 287 min (vs estimated 60 min)
- **Root Cause**: Trial cluster limited to 6 OCPUs (vs 24 planned)
- **Lesson**: Memory-intensive joins need proportional compute. Budget for cluster sizing.

### 3. Data Flow Failure Rate
- **Impact**: 6/15 Data Flow runs failed (40% failure rate)
- **Root Causes**: OOM on large joins, incorrect bucket paths, Spark config tuning
- **Lesson**: Start with smallest datasets, tune Spark configs (spark.sql.shuffle.partitions), then scale.

---

## Architecture Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Object Storage over ADW for staging | Lower cost, better for large Parquet files | Good — ADW used only for query layer |
| Local training over DS Notebook | Trial limit on notebook | Acceptable — identical results |
| LightGBM over XGBoost | Faster on 3.9M records, better KS | Good — +1.2pp KS over LR |
| PSI for monitoring | Standard in credit risk | Good — proven stability (PSI < 0.002) |
| Terraform over manual provisioning | Reproducibility, team collaboration | Excellent — 43 resources managed cleanly |

---

## Metrics Summary

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Data Parity (columns) | 402 | 402 | PASS |
| Data Parity (rows) | 3,900,378 | 3,900,378 | PASS |
| Model Parity (KS diff) | < 2pp | 0.05pp (LGBM) | PASS |
| Model Parity (AUC diff) | < 0.005 | 0.0002 (LGBM) | PASS |
| PSI | < 0.25 | 0.0012 (LGBM) | PASS |
| Budget Utilization | < US$ 500 trial | R$ 171.71 acumulado (BRL) | PASS |
| Quality Gates | All PASS | 124/144 PASS (20 N/A) | PASS |

---

## Future Improvements

1. **Automated Pipeline Orchestration**: Use OCI Scheduler or Functions to trigger daily Data Flow runs
2. **Model Catalog Integration**: When paid account available, register models for versioning and lifecycle management
3. **REST Scoring Endpoint**: Deploy Model Deployment for real-time scoring (required for production)
4. **Feature Store on ADW**: Materialize Gold features in ADW for sub-second query access
5. **CI/CD for IaC**: GitHub Actions + Terraform Cloud for automated infrastructure changes
6. **Multi-region DR**: Replicate Object Storage buckets to secondary region

---

*Review completed: 2026-03-07*
