# Guia de Execucao no Microsoft Fabric

**Data**: 2026-02-08
**Versao**: 1.0
**Projeto**: Hackathon PoD Academy — Credit Risk FPD (Claro + Oracle)

---

## 1. Visao Geral

Este guia documenta todas as configuracoes necessarias para executar o pipeline completo — da deduplicacao ao deploy — de forma 100% automatica no Microsoft Fabric.

### Pipeline Resumido

```
Deduplicacao (Silver) → Books (Silver) → Consolidacao (Gold) → Treino → Export → Scoring → Validacao → Monitoramento
```

---

## 2. Pre-Requisitos do Workspace

### 2.1 Lakehouses

O workspace precisa de 3 Lakehouses configurados:

| Camada | Lakehouse ID | Schemas |
|--------|-------------|---------|
| Bronze | `b8822164-7b67-4b17-9a01-3d0737dace7e` | staging, config, log |
| Silver | `5f8a4808-6f65-401b-a427-b0dd9d331b35` | rawdata, book |
| Gold | `6a7135c7-0d8d-4625-815d-c4c4a02e4ed4` | feature_store |

**Workspace ID**: `febb8631-d5c0-43d8-bf08-5e89c8f2d17e`

> Se os Lakehouses forem recriados, atualize os IDs em `config/pipeline_config.py`.

### 2.2 Dados Fonte

Antes de executar o pipeline, os dados brutos devem estar ingeridos no Bronze (`staging.*`). Isso e feito pelo script `1-ingestao-dados/ingestao-arquivos.py` (etapa anterior a este guia).

### 2.3 Dependencias Python

O Spark Runtime 3.x do Fabric ja inclui a maioria dos pacotes. Verifique:

| Pacote | Usado em | Incluido no Fabric |
|--------|---------|-------------------|
| `pyspark` | Todos | Sim |
| `pandas` / `numpy` | Todos | Sim |
| `scikit-learn` | Modelo, Export, Validacao | Sim |
| `mlflow` | Modelo, Export, Scoring, Validacao, Drift | Sim |
| `lightgbm` | Modelo | Sim |
| `scipy` | Validacao, Drift | Sim |
| `delta-spark` | Dedup, Consolidado | Sim |
| `category_encoders` | Modelo | **Pode precisar instalar** |

Se `category_encoders` nao estiver disponivel, adicione no inicio do notebook de treino:

```python
%pip install category_encoders
```

---

## 3. Estrutura de Arquivos no Lakehouse

Todos os scripts importam configuracao via:

```python
import sys
sys.path.insert(0, "/lakehouse/default/Files/projeto-final")
from config.pipeline_config import ...
```

Portanto, o **default Lakehouse** de cada notebook deve conter a pasta `Files/projeto-final/` com esta estrutura:

```
Files/
└── projeto-final/
    ├── config/
    │   └── pipeline_config.py          ← OBRIGATORIO (todos importam daqui)
    ├── utils/
    │   ├── __init__.py
    │   └── data_quality.py
    ├── 2-metadados/
    │   └── ajustes-tipagem-deduplicacao.py
    ├── 4-construcao-books/
    │   ├── book_recarga_cmv.py
    │   ├── book_pagamento.py
    │   ├── book_faturamento.py
    │   └── book_consolidado.py
    └── 5-treinamento-modelos/
        ├── export_model.py
        ├── validacao_deploy.py
        ├── monitoramento_drift.py
        └── artifacts/                  ← criada automaticamente pelo export_model.py
```

> **Dica**: Se cada notebook usa um Lakehouse default diferente, copie pelo menos `config/pipeline_config.py` para o `Files/projeto-final/config/` de cada Lakehouse.

---

## 4. Lakehouse Attachment por Notebook

Cada notebook no Fabric precisa ter os Lakehouses corretos anexados. O **default Lakehouse** determina onde fica o `/lakehouse/default/`.

| # | Script/Notebook | Default Lakehouse | Lakehouses Adicionais |
|---|----------------|-------------------|----------------------|
| 1 | `ajustes-tipagem-deduplicacao` | **Bronze** `b8822164` | Silver `5f8a4808` |
| 2 | `book_recarga_cmv` | **Silver** `5f8a4808` | — |
| 3 | `book_pagamento` | **Silver** `5f8a4808` | — |
| 4 | `book_faturamento` | **Silver** `5f8a4808` | — |
| 5 | `book_consolidado` | **Silver** `5f8a4808` | Gold `6a7135c7` |
| 6 | `modelo_baseline` | **Gold** `6a7135c7` | — |
| 7 | `scoring_batch` | **Gold** `6a7135c7` | — |
| 8 | `validacao_deploy` | **Gold** `6a7135c7` | — |
| 9 | `monitoramento_drift` | **Gold** `6a7135c7` | — |

### Como configurar no Fabric

1. Abra o notebook no Fabric
2. No painel lateral esquerdo, clique em **"Lakehouses"**
3. Clique em **"Add Lakehouse"** → selecione o Lakehouse correto
4. Defina o **default** clicando no icone de pin no Lakehouse desejado
5. Adicione Lakehouses adicionais conforme a tabela acima

---

## 5. Fluxo de Execucao

### 5.1 Diagrama de Dependencias

```
┌─────────────────────────────────────────────────────────┐
│  ETAPA 1: SILVER (Dedup + Tipagem)                      │
│  ajustes-tipagem-deduplicacao.py                        │
│  Le: Bronze.staging.* → Escreve: Silver.rawdata.*       │
└──────────────────────┬──────────────────────────────────┘
                       │
       ┌───────────────┼───────────────┐
       ▼               ▼               ▼
┌──────────┐   ┌──────────┐   ┌──────────┐
│ ETAPA 2a │   │ ETAPA 2b │   │ ETAPA 2c │  ← PODEM RODAR EM PARALELO
│ book_    │   │ book_    │   │ book_    │
│ recarga  │   │ pagamento│   │ fatura-  │
│ (90 var) │   │ (94 var) │   │ mento    │
│          │   │          │   │ (114 var)│
└────┬─────┘   └────┬─────┘   └────┬─────┘
     └───────────────┼───────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  ETAPA 3: GOLD (Consolidacao)                           │
│  book_consolidado.py                                    │
│  Le: Silver.rawdata + Silver.book → Gold.feature_store  │
│  Output: 402 colunas, ~3.9M registros                   │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│  ETAPA 4: TREINAMENTO + EXPORT                          │
│  modelo_baseline_risco_telecom_sklearn.ipynb            │
│  Le: Gold.feature_store → Treina LR + LGBM             │
│  + Celulas de export → MLflow Registry (Staging)        │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│  ETAPA 5: SCORING BATCH                                 │
│  scoring_batch.ipynb                                    │
│  Le: Gold.feature_store + MLflow Model                  │
│  Escreve: Gold.feature_store.clientes_scores            │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│  ETAPA 6: VALIDACAO DE DEPLOY                           │
│  validacao_deploy.py                                    │
│  Compara metricas scoring vs treino (KS/AUC/Gini)      │
│  Resultado: PASS ou FAIL                                │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│  ETAPA 7: MONITORAMENTO (mensal, apos deploy)           │
│  monitoramento_drift.py                                 │
│  PSI score + PSI features + drift de performance        │
│  Resultado: GREEN / YELLOW / RED                        │
└─────────────────────────────────────────────────────────┘
```

### 5.2 Tabela de Leitura/Escrita

| Etapa | Script | Le de | Escreve em |
|-------|--------|-------|-----------|
| 1 | `ajustes-tipagem-deduplicacao.py` | Bronze.staging.{dados_cadastrais, telco, score_bureau_movel_full} + Bronze.config.metadados_tabelas | Silver.rawdata.* + Bronze.log.log_info |
| 2a | `book_recarga_cmv.py` | Silver.rawdata.{ass_recarga_cmv_nova, canal_aquisicao_credito, plano_preco, tipo_recarga, tipo_insercao, forma_pagamento, instituicao} | Silver.book.ass_recarga_cmv |
| 2b | `book_pagamento.py` | Silver.rawdata.{pagamento, forma_pagamento, instituicao, tipo_faturamento} | Silver.book.pagamento |
| 2c | `book_faturamento.py` | Silver.rawdata.{dados_faturamento, plataforma, tipo_faturamento} | Silver.book.faturamento |
| 3 | `book_consolidado.py` | Silver.rawdata.{dados_cadastrais, telco, score_bureau_movel_full} + Silver.book.{ass_recarga_cmv, pagamento, faturamento} | Gold.feature_store.clientes_consolidado |
| 4 | `modelo_baseline + export_model` | Gold.feature_store.clientes_consolidado | MLflow Registry + artifacts/ (.pkl, .json) |
| 5 | `scoring_batch.ipynb` | Gold.feature_store.clientes_consolidado + MLflow Model | Gold.feature_store.clientes_scores |
| 6 | `validacao_deploy.py` | Gold.feature_store.clientes_consolidado + MLflow Model + MLflow Metrics | — (apenas validacao) |
| 7 | `monitoramento_drift.py` | Gold.feature_store.clientes_consolidado + MLflow Model | MLflow (drift metrics + artifacts) |

---

## 6. Parametros Configuraveis

### 6.1 Configuracao Centralizada (`config/pipeline_config.py`)

Todos os scripts importam deste arquivo. Parametros principais:

| Parametro | Valor Atual | Quando Mudar |
|-----------|-------------|-------------|
| `WORKSPACE_ID` | `febb8631-d5c0-43d8-bf08-5e89c8f2d17e` | Se mudar de workspace |
| `BRONZE_ID` | `b8822164-7b67-4b17-9a01-3d0737dace7e` | Se recriar o Lakehouse |
| `SILVER_ID` | `5f8a4808-6f65-401b-a427-b0dd9d331b35` | Se recriar o Lakehouse |
| `GOLD_ID` | `6a7135c7-0d8d-4625-815d-c4c4a02e4ed4` | Se recriar o Lakehouse |
| `SAFRAS` | `[202410, 202411, 202412, 202501, 202502, 202503]` | Se adicionar novas SAFRAs |
| `EXPERIMENT_NAME` | `"hackathon-pod-academy/credit-risk-fpd"` | Se mudar o experimento MLflow |
| `SILVER_TABLES` | `["score_bureau_movel_full", "dados_cadastrais", "telco"]` | Se adicionar tabelas Silver |

### 6.2 Parametros por Script (ajustar antes de cada execucao)

| Arquivo | Parametro | Valor Default | Descricao |
|---------|-----------|---------------|-----------|
| `scoring_batch.ipynb` | `SCORING_SAFRAS` | `[202502, 202503]` | SAFRAs para aplicar scoring |
| `scoring_batch.ipynb` | `MODEL_STAGE` | `"Production"` | Stage do modelo no MLflow |
| `scoring_batch.ipynb` | `MODEL_NAME` | `"credit-risk-fpd-lgbm_baseline"` | Nome do modelo registrado |
| `validacao_deploy.py` | `VALIDATION_SAFRA` | `202501` | SAFRA OOS com FPD conhecido |
| `validacao_deploy.py` | `MODEL_STAGE` | `"Staging"` | Validar antes de promover |
| `monitoramento_drift.py` | `MONITOR_SAFRA` | `202503` | SAFRA mais recente para monitorar |
| `monitoramento_drift.py` | `BASELINE_SAFRAS` | `[202410, 202411, 202412]` | SAFRAs de treino (referencia) |

---

## 7. Ponto Critico: Export dentro do Notebook de Treino

O `export_model.py` **nao roda sozinho** — ele e chamado de dentro do notebook de treinamento porque precisa das variaveis `pipeline_LGBM`, `X_test`, `y_test` que so existem na memoria do notebook.

### Celulas de Export (adicionar ao final do notebook de treino)

```python
# --- Celula: Export dos modelos ---
from export_model import export_model, promote_to_production

# Exportar LGBM (modelo principal)
result_lgbm = export_model(
    pipeline=pipeline_LGBM,
    model_name="lgbm_baseline",
    X_test=X_oot_agg,
    y_test=y_oot_agg,
    feature_names=list(X_train_final.columns),
)
print(f"LGBM exportado: {result_lgbm['registered_name']} (run={result_lgbm['mlflow_run_id']})")

# Exportar LR (benchmark)
result_lr = export_model(
    pipeline=pipeline_LR,
    model_name="logistic_regression_l1",
    X_test=X_oot_agg,
    y_test=y_oot_agg,
    feature_names=list(X_train_final.columns),
)
print(f"LR exportado: {result_lr['registered_name']} (run={result_lr['mlflow_run_id']})")
```

### Variaveis criadas pelo notebook de treino (consumidas pelo export):

| Variavel | Tipo | Descricao |
|----------|------|-----------|
| `pipeline_LR` | sklearn.Pipeline (fitted) | Logistic Regression L1 |
| `pipeline_LGBM` | sklearn.Pipeline (fitted) | LightGBM GBDT |
| `X_train_final` | pd.DataFrame | Features de treino (nomes das colunas) |
| `X_oot_agg` | pd.DataFrame | Features OOT para validacao |
| `y_oot_agg` | pd.Series | Target OOT |

---

## 8. Ciclo de Vida do Modelo no MLflow

```
  export_model.py          validacao_deploy.py       promote_to_production()
       │                          │                          │
       ▼                          ▼                          ▼
  ┌─────────┐             ┌──────────┐              ┌────────────┐
  │  None    │ ──auto──→  │ Staging  │ ──manual──→  │ Production │
  │ (registro)│            │(validacao)│              │  (deploy)  │
  └─────────┘             └──────────┘              └────────────┘
```

1. **export_model.py** registra o modelo e transiciona automaticamente para **Staging**
2. **validacao_deploy.py** valida o modelo em Staging (compara KS/AUC/Gini com treino)
3. Se PASS, promover manualmente para **Production**:

```python
from export_model import promote_to_production
promote_to_production("credit-risk-fpd-lgbm_baseline")
```

4. **scoring_batch.ipynb** usa o modelo em **Production** para scoring
5. **monitoramento_drift.py** monitora o modelo em **Production** mensalmente

---

## 9. Output do Scoring

### Tabela: `Gold.feature_store.clientes_scores`

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| `NUM_CPF` | string | CPF mascarado (chave) |
| `SAFRA` | int | Periodo YYYYMM (particao) |
| `SCORE_PROB` | double | Probabilidade de FPD (0-1) |
| `SCORE` | int | Score de credito (0-1000, invertido: maior = melhor) |
| `FAIXA_RISCO` | int | Faixa de risco (1-5, quintis) |
| `MODEL_NAME` | string | Nome do modelo usado |
| `MODEL_VERSION` | string | Versao do modelo |
| `DT_SCORING` | string | Timestamp do scoring |

---

## 10. Thresholds de Monitoramento

O `monitoramento_drift.py` usa estes thresholds para classificar o drift:

| Metrica | Verde | Amarelo | Vermelho |
|---------|-------|---------|----------|
| PSI Score | < 0.10 | 0.10 - 0.25 | > 0.25 |
| PSI Features | < 0.10 | 0.10 - 0.20 | > 0.20 |
| KS Drift | < 5.0 pp | — | > 5.0 pp |
| AUC Drift | < 0.03 | — | > 0.03 |

**Acoes recomendadas**:
- **Verde**: Nenhuma acao necessaria
- **Amarelo**: Investigar features com maior drift, preparar re-treino
- **Vermelho**: Re-treinar modelo imediatamente, pausar scoring se necessario

---

## 11. Checklist de Setup

### Primeiro Setup (unica vez)

- [ ] Workspace Fabric criado com os 3 Lakehouses (Bronze, Silver, Gold)
- [ ] Lakehouse IDs atualizados em `config/pipeline_config.py`
- [ ] Pasta `Files/projeto-final/` criada no default Lakehouse de cada notebook
- [ ] `config/pipeline_config.py` copiado para todos os Lakehouses usados como default
- [ ] MLflow habilitado no workspace (automatico no Fabric)
- [ ] Pacote `category_encoders` disponivel (ou `%pip install` no notebook de treino)
- [ ] Celulas de export adicionadas ao final do notebook de treino
- [ ] Dados fonte ingeridos no Bronze (`staging.*`)

### Antes de cada execucao

- [ ] Cada notebook com o **default Lakehouse** correto (ver Secao 4)
- [ ] Lakehouses adicionais anexados quando necessario
- [ ] `SCORING_SAFRAS` atualizado em `scoring_batch.ipynb`
- [ ] `MONITOR_SAFRA` atualizado em `monitoramento_drift.py`
- [ ] `SAFRAS` atualizado em `pipeline_config.py` se houver novas SAFRAs

### Apos execucao

- [ ] Verificar logs de cada etapa (sem erros)
- [ ] Conferir contagem de registros no Gold (`Gold.feature_store.clientes_consolidado`)
- [ ] Validar que modelo foi registrado no MLflow (`Staging`)
- [ ] Executar `validacao_deploy.py` — resultado deve ser **PASS**
- [ ] Promover modelo para Production
- [ ] Executar scoring batch
- [ ] Executar monitoramento — resultado deve ser **GREEN**

---

## 12. Troubleshooting

### Erro: `ModuleNotFoundError: No module named 'config'`

**Causa**: O default Lakehouse nao contem `Files/projeto-final/config/pipeline_config.py`.

**Solucao**: Copie a pasta `config/` para `Files/projeto-final/` no Lakehouse que esta como default.

### Erro: `Table or view not found`

**Causa**: Lakehouse nao anexado ao notebook, ou etapa anterior nao foi executada.

**Solucao**: Verifique se o Lakehouse correto esta anexado (ver Secao 4) e se a etapa anterior completou com sucesso.

### Erro: `Nenhuma versao encontrada no MLflow Registry`

**Causa**: O `export_model.py` nao foi executado, ou o modelo nao foi registrado.

**Solucao**: Execute as celulas de export no notebook de treino primeiro.

### Erro: `category_encoders not found`

**Causa**: Pacote nao disponivel no Spark runtime.

**Solucao**: Adicione `%pip install category_encoders` como primeira celula do notebook de treino.

### Import de notebook falha no Fabric

**Causa**: Notebooks `.ipynb` precisam de metadata especifica do Fabric.

**Solucao**: Garantir que o notebook tenha:
- Kernel: `synapse_pyspark` com `"language": "Python"`
- Metadata: `microsoft`, `nteract`, `kernel_info`, `spark_compute`
- Line endings: LF (Unix), nao CRLF (Windows)
- nbformat: 4.5

---

*Hackathon PoD Academy | Claro + Oracle | Microsoft Fabric*
