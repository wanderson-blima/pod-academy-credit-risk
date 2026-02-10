# Artefatos do Modelo

Artefatos gerados pelos notebooks de treinamento, scoring e monitoramento.

## Estrutura

```
artifacts/
├── models/                          # Modelos treinados
│   ├── lgbm_baseline/               #   LightGBM v6 (.pkl + MLflow format)
│   │   ├── lgbm_baseline_v6_*.pkl
│   │   ├── lgbm_baseline_v6_metadata_*.json
│   │   └── model/                   #   MLflow model directory
│   └── lr_baseline/                 #   Logistic Regression L1 v6
│       ├── lr_l1_v6_*.pkl
│       ├── lr_l1_v6_metadata_*.json
│       └── model/                   #   MLflow model directory
│
├── feature_selection/               # Features selecionadas
│   ├── selected_features_shap.pkl   #   Objeto serializado com features
│   └── shap_feature_ranking.csv     #   261 features ranked por SHAP
│
├── monitoring/                      # Relatorios de monitoramento
│   ├── monitoring_safra_202503.json #   Relatorio completo (SAFRA 202503)
│   └── feature_drift_safra_202503.csv  # PSI por feature
│
├── scoring/                         # Resultados de scoring batch
│   └── scoring_distribution.csv     #   Distribuicao por faixa de risco
│
└── analysis/                        # Analises e visualizacoes
    ├── plots/                       #   Graficos PNG
    │   ├── panel1_performance_8plots.png
    │   ├── panel2_stability_8plots.png
    │   ├── panel3_business_8plots.png
    │   ├── shap_beeswarm_top40.png
    │   ├── shap_pareto_cumulative.png
    │   └── ks_incremental_dual.png
    └── csv/                         #   CSVs de analise
        ├── model_comparison_results.csv
        ├── decile_analysis_oot.csv
        ├── swap_analysis_results.csv
        ├── psi_results.csv
        ├── lgbm_feature_importance_baseline.csv
        ├── lr_coefficients_odds_ratios.csv
        └── ks_incremental_results.csv
```

## Modelo Selecionado

**LightGBM baseline v6** — KS 33.97%, AUC 0.7303 (OOT)

- **Metadata**: `models/lgbm_baseline/lgbm_baseline_v6_metadata_*.json`
- **Pickle**: `models/lgbm_baseline/lgbm_baseline_v6_*.pkl`
- **MLflow**: `models/lgbm_baseline/model/`

## Formato MLflow

Cada modelo inclui diretorio `model/` compativel com MLflow:
- `MLmodel` — Configuracao do modelo
- `model.pkl` — Modelo serializado
- `conda.yaml` + `requirements.txt` — Dependencias
- `python_env.yaml` — Ambiente Python

---

*Documentacao dos resultados: [docs/modeling/model-results.md](../docs/modeling/model-results.md)*
