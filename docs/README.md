# Documentacao — Credit Risk FPD Pipeline

Indice da documentacao tecnica do projeto, organizada por arquitetura.

---

## Fabric (Microsoft Fabric)

Documentacao completa do pipeline Fabric em [`../fabric/docs/`](../fabric/docs/):

| Documento | Descricao |
|-----------|-----------|
| [Data Architecture](../fabric/docs/architecture/data-architecture.md) | Pipeline Medallion com diagramas Mermaid |
| [Guia de Execucao Fabric](../fabric/docs/architecture/guia-execucao-fabric.md) | Configuracao de Lakehouses e troubleshooting |
| [Schemas DDL](../fabric/schemas/ddl/) | DDLs completos (Bronze, Silver, Gold) |
| [Book Recarga (90 vars)](../fabric/docs/feature-engineering/book-recarga-cmv.md) | Variaveis REC_* |
| [Book Pagamento (94 vars)](../fabric/docs/feature-engineering/book-pagamento.md) | Variaveis PAG_* |
| [Book Faturamento (114 vars)](../fabric/docs/feature-engineering/book-faturamento.md) | Variaveis FAT_* |
| [Preprocessamento](../fabric/docs/modeling/preprocessing.md) | Pipeline de limpeza e transformacao |
| [Selecao de Features](../fabric/docs/modeling/feature-selection.md) | Estrategia de selecao em 4 etapas |
| [Resultados do Modelo](../fabric/docs/modeling/model-results.md) | Metricas, SHAP, comparacao LR vs LGBM |
| [Monitoramento e Drift](../fabric/docs/modeling/monitoring.md) | Framework PSI e alertas |
| [Decisoes Tecnicas](../fabric/docs/technical-decisions.md) | 11 ADRs arquiteturais |

## OCI (Oracle Cloud Infrastructure)

Documentacao do pipeline OCI em [`../oci/docs/`](../oci/docs/):

| Documento | Descricao |
|-----------|-----------|
| [PRD — OCI Pipeline Parity](../oci/docs/prd-oci-pipeline-parity.md) | Requisitos de paridade Fabric → OCI |
| [OCI Pipeline Execution Report](../oci/docs/oci-pipeline-execution-report.md) | Relatorio de execucao do pipeline |
| [OCI E2E Validation Report](../oci/docs/oci-e2e-validation-report.md) | Validacao end-to-end |
| [Quality Dashboard](../oci/docs/QUALITY-DASHBOARD.md) | Dashboard de qualidade |
| [OCI Knowledge Base](../oci/docs/oci-knowledge-base.md) | Base de conhecimento OCI |

## Compartilhado

| Documento | Descricao |
|-----------|-----------|
| [Apresentacao](presentation/) | Slides e roteiro da apresentacao do hackathon |
| [Report](report.html) | Relatorio HTML consolidado |
