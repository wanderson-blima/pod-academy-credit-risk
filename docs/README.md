# Documentacao — Credit Risk FPD Pipeline

Indice completo da documentacao tecnica do projeto.

---

## Arquitetura

| Documento | Descricao |
|-----------|-----------|
| [Data Architecture](architecture/data-architecture.md) | Pipeline Medallion com 5 diagramas Mermaid (ingestao, ER, features, treinamento, deploy) |
| [Guia de Execucao Fabric](architecture/guia-execucao-fabric.md) | Configuracao de Lakehouses, parametros e troubleshooting no Microsoft Fabric |
| [Schemas (DDLs)](architecture/schemas/) | DDLs completos das 3 camadas (Bronze, Silver, Gold) |

## Feature Engineering

| Documento | Features | Descricao |
|-----------|----------|-----------|
| [Visao Geral](feature-engineering/README.md) | 402 | Indice dos books e logica de consolidacao |
| [Book Recarga](feature-engineering/book-recarga-cmv.md) | 90 | Variaveis REC_* — comportamento de recarga |
| [Book Pagamento](feature-engineering/book-pagamento.md) | 94 | Variaveis PAG_* — comportamento de pagamento |
| [Book Faturamento](feature-engineering/book-faturamento.md) | 114 | Variaveis FAT_* — dados de faturamento |

## Modelagem

| Documento | Descricao |
|-----------|-----------|
| [Preprocessamento](modeling/preprocessing.md) | Pipeline de limpeza: missing values, cardinality, encoding, split |
| [Selecao de Features](modeling/feature-selection.md) | Estrategia de selecao em 4 etapas (IV, L1, correlacao, LGBM) |
| [Modelo Baseline](modeling/model-baseline.md) | Configuracao: LR L1 + LightGBM, 398→59 features, temporal split |
| [Resultados do Modelo](modeling/model-results.md) | Metricas consolidadas, decil analysis, SHAP, comparacao LR vs LGBM |
| [Analise de Swap](modeling/swap-analysis.md) | Estabilidade de ranking entre SAFRAs, capture rate por threshold |
| [Monitoramento e Drift](modeling/monitoring.md) | Framework PSI, thresholds, resultado SAFRA 202503, alertas |

## Analytics

| Documento | Descricao |
|-----------|-----------|
| [Estudo Publico-Alvo](analytics/estudo-publico-alvo.md) | EDA completa: demografico, comportamental, segmentacao de risco |

## Decisoes Tecnicas

| Documento | Descricao |
|-----------|-----------|
| [Technical Decisions](technical-decisions.md) | 11 ADRs — Medallion, Delta Lake, leakage, split temporal, metricas, scoring |

## Visualizacoes

Todos os graficos de performance do modelo estao em [`images/`](images/):

| Imagem | Descricao |
|--------|-----------|
| [panel1_performance.png](images/panel1_performance.png) | 8 graficos de performance (KS, ROC, PR, Score Distribution) |
| [panel2_stability.png](images/panel2_stability.png) | 8 graficos de estabilidade (Decile, Lift, PSI, Swap, Calibration) |
| [panel3_business.png](images/panel3_business.png) | 8 graficos de negocio (Comparison, Coefficients, Risk Bands) |
| [shap_beeswarm.png](images/shap_beeswarm.png) | SHAP Beeswarm — Top 40 features por importancia |
| [shap_pareto.png](images/shap_pareto.png) | SHAP Pareto — Importancia cumulativa |
| [ks_incremental.png](images/ks_incremental.png) | KS Incremental — Contribuicao por fonte de dados |
