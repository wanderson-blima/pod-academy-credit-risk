# Metodologia do Modelo Baseline

> Story: HD-3.4 | Epic: EPIC-HD-001 | Entregavel: D

## 1. Objetivo

Construir um modelo baseline de classificacao binaria para prever **First Payment Default (FPD)** em clientes Claro que migram de planos Pre-pago para Controle.

## 2. Configuracao Experimental

### Dados
| Item | Valor |
|------|-------|
| Feature Store | Gold.feature_store.clientes_consolidado |
| Registros | ~3.9M (amostra 25% = ~975K) |
| Features iniciais | 468 |
| Features pos-selecao | ~70 |
| Target | FPD (0/1) |
| Granularidade | NUM_CPF + SAFRA |

### Split Temporal
| Conjunto | SAFRAs | Uso |
|----------|--------|-----|
| Treino | 202410, 202411, 202412, 202501 | Treinamento do modelo |
| OOS (Out-of-Sample) | 202502 | Validacao e tunning |
| OOT (Out-of-Time) | 202503 | Teste final (benchmark) |

### Benchmark
- **KS OOT >= 33.1%** (meta de performance)
- Referencia: score bureau movel existente

## 3. Modelos

### 3.1 Logistic Regression (L1)

```python
Pipeline([
    ("scaler", StandardScaler()),
    ("model", LogisticRegression(
        penalty="l1",
        solver="saga",
        C=1.0,
        max_iter=1000,
        random_state=42,
        class_weight="balanced"
    ))
])
```

**Justificativa**: Baseline interpretavel, feature selection embutida via L1, robusto para alta dimensionalidade.

### 3.2 LightGBM (GBDT)

```python
Pipeline([
    ("model", LGBMClassifier(
        objective="binary",
        boosting_type="gbdt",
        n_estimators=250,
        max_depth=7,
        learning_rate=0.05,
        num_leaves=31,
        random_state=42,
        class_weight="balanced",
        verbose=-1
    ))
])
```

**Hyperparameter Tuning**: GridSearchCV com:
- n_estimators: [100, 250, 500]
- max_depth: [5, 7, 10]
- Scoring: AUC
- CV: 3-fold

**Melhor resultado**: n_estimators=250, max_depth=7, AUC=0.736

## 4. Metricas de Avaliacao

| Metrica | Descricao | Uso |
|---------|-----------|-----|
| KS (Kolmogorov-Smirnov) | Maxima separacao entre distribuicoes | Metrica principal |
| AUC (Area Under ROC) | Capacidade discriminativa global | Metrica secundaria |
| Precisao | TP / (TP + FP) | Qualidade das previsoes positivas |
| Recall | TP / (TP + FN) | Cobertura dos defaults reais |
| F1-Score | Media harmonica Precisao/Recall | Equilibrio |

### Selecao do Melhor Modelo
- Criterio: **KS OOT** (maximizar)
- Desempate: AUC OOT
- Estabilidade: |KS_OOS - KS_OOT| < 5pp

## 5. Tracking (MLflow)

```python
mlflow.set_experiment("hackathon-pod-academy/credit-risk-fpd")
mlflow.autolog()
```

Artefatos logados:
- Parametros do modelo
- Metricas (KS, AUC, Precision, Recall, F1) por SAFRA
- Modelo serializado (.pkl)
- Feature importance
- Graficos de avaliacao

## 6. Resultados Esperados

| Modelo | KS OOS (202502) | KS OOT (202503) | AUC OOT |
|--------|-----------------|-----------------|---------|
| Logistic Regression (L1) | ~35% | >= 33.1% | ~0.73 |
| LightGBM (GBDT) | ~36% | >= 33.1% | ~0.74 |

> **Nota**: Resultados reais pendentes de execucao no Fabric com dados completos.

## 7. Checklist de Validacao

- [ ] KS OOT >= 33.1% (benchmark)
- [ ] |KS_OOS - KS_OOT| < 5pp (estabilidade)
- [ ] Sem leakage (FAT_VLR_FPD removido)
- [ ] SCORE_RISCO features validadas como seguras
- [ ] MLflow run registrado com artefatos completos
- [ ] .pkl exportado e verificado (joblib.load funciona)
- [ ] Metadata JSON gerado

---
*Hackathon PoD Academy (Claro + Oracle)*
