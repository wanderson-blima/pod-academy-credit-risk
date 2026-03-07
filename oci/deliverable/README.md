# Entregavel C — Modelo Baseline de Behavior (Credit Risk FPD)

**Squad 2** | Hackathon PoD Academy | Claro + Oracle

---

## Conteudo do Pacote

```
entregavel/
├── README.md                          # Este arquivo
├── requirements.txt                   # Dependencias Python (testado com Python 3.11)
├── scoring_validacao.py               # Script standalone de escoragem + metricas
├── dados_exemplo.csv                  # Dados sinteticos de exemplo (500 registros)
├── modelos/
│   ├── lgbm_baseline_v6.pkl           # Modelo LightGBM (pipeline sklearn completa)
│   └── lr_l1_v6.pkl                   # Modelo Logistic Regression L1 (pipeline sklearn completa)
└── metadata/
    ├── lgbm_baseline_v6_metadata.json # Metadata + metricas + lista de features
    └── lr_l1_v6_metadata.json         # Metadata + metricas + lista de features
```

---

## O que cada arquivo .pkl contem

Cada `.pkl` e um **sklearn Pipeline completo** serializado com `joblib` + `cloudpickle`.
O pipeline contem **toda a preparacao de dados + modelo treinado** em um unico objeto:

```
Pipeline(steps=[
    ('prep', ColumnTransformer([
        ('num', Pipeline([
            ('imputer', SimpleImputer(strategy='median')),  # Trata missing numericos
            # ('scaler', StandardScaler()),                 # Apenas no modelo LR
        ]), [57 features numericas]),
        ('cat', Pipeline([
            ('imputer', SimpleImputer(strategy='most_frequent')),  # Trata missing categoricos
            ('encoder', CountEncoder()),                            # Encoding categorico
        ]), ['var_34', 'var_67']),
    ])),
    ('model', LGBMClassifier(...))  # ou LogisticRegression(...) para lr_l1_v6.pkl
])
```

**Nao e necessario** aplicar nenhum preprocessamento manualmente.
O pipeline recebe os dados brutos (59 colunas) e retorna probabilidades diretamente.

---

## Guia Rapido (5 minutos)

### 1. Criar ambiente virtual e instalar dependencias

```bash
# Criar venv isolada (recomendado para evitar conflitos de versao)
python -m venv .venv

# Ativar venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
# source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

Nota: O modelo requer `scikit-learn>=1.2.2,<1.4.0` e `category-encoders`.
A venv garante que as versoes corretas sejam usadas sem afetar seu ambiente.

### 2. Teste rapido com dados de exemplo (30 segundos)

```bash
# Testar com os dados sinteticos incluidos (valida que o ambiente funciona):
python scoring_validacao.py --dados dados_exemplo.csv --modelo modelos/lgbm_baseline_v6.pkl --target FPD --output teste_scores.csv
```

Nota: Os dados de exemplo sao sinteticos (aleatorios), entao as metricas serao baixas.
O objetivo e validar que o pipeline carrega e executa corretamente.

### 3. Escorar sua base real

```bash
# Apenas gerar scores (sem metricas):
python scoring_validacao.py --dados sua_base.csv --modelo modelos/lgbm_baseline_v6.pkl

# Gerar scores + calcular KS/Gini/AUC (requer coluna FPD na base):
python scoring_validacao.py --dados sua_base.csv --modelo modelos/lgbm_baseline_v6.pkl --target FPD

# Salvar scores em CSV:
python scoring_validacao.py --dados sua_base.csv --modelo modelos/lgbm_baseline_v6.pkl --target FPD --output scores_output.csv
```

### 4. Escorar via Python (import)

```python
import joblib
import pandas as pd
from scoring_validacao import carregar_modelo, preparar_features, escorar, calcular_metricas

# 1. Carregar modelo
modelo = carregar_modelo("modelos/lgbm_baseline_v6.pkl")

# 2. Carregar dados (CSV, Parquet ou Excel)
df = pd.read_csv("sua_base.csv")   # ou pd.read_parquet("sua_base.parquet")

# 3. Selecionar as 59 features
X = preparar_features(df)

# 4. Escorar
resultado = escorar(modelo, X)
# resultado contem: SCORE_PROB (0-1), SCORE (0-1000), FAIXA_RISCO (1-5)

# 5. Calcular metricas (se houver coluna FPD na base)
metricas = calcular_metricas(df["FPD"].values, resultado["SCORE_PROB"].values)
# metricas = {"ks": 33.97, "auc": 0.7303, "gini": 46.06}
```

### 5. Escorar diretamente com joblib (sem o script)

```python
import joblib
import pandas as pd

# Carregar
modelo = joblib.load("modelos/lgbm_baseline_v6.pkl")

# Preparar dados (59 colunas na ordem correta)
df = pd.read_csv("sua_base.csv")
X = df[FEATURES]  # ver lista abaixo

# Escorar
probabilidades = modelo.predict_proba(X)[:, 1]   # P(FPD=1)
scores = ((1 - probabilidades) * 1000).round(0)   # 0-1000 (maior = menor risco)
```

---

## Lista das 59 Features Obrigatorias

A base de dados deve conter **exatamente estas 59 colunas** (na ordem indicada):

| # | Feature | Tipo | Origem |
|---|---------|------|--------|
| 1 | TARGET_SCORE_02 | Numerica | Score bureau |
| 2 | TARGET_SCORE_01 | Numerica | Score bureau |
| 3 | REC_SCORE_RISCO | Numerica | Recarga |
| 4 | REC_TAXA_STATUS_A | Numerica | Recarga |
| 5 | REC_QTD_LINHAS | Numerica | Recarga |
| 6 | REC_DIAS_ENTRE_RECARGAS | Numerica | Recarga |
| 7 | REC_QTD_INST_DIST_REG | Numerica | Recarga |
| 8 | REC_DIAS_DESDE_ULTIMA_RECARGA | Numerica | Recarga |
| 9 | REC_TAXA_CARTAO_ONLINE | Numerica | Recarga |
| 10 | REC_QTD_STATUS_ZB2 | Numerica | Recarga |
| 11 | REC_QTD_CARTAO_ONLINE | Numerica | Recarga |
| 12 | REC_COEF_VARIACAO_REAL | Numerica | Recarga |
| 13 | var_26 | Numerica | Cadastro |
| 14 | FAT_DIAS_MEDIO_CRIACAO_VENCIMENTO | Numerica | Faturamento |
| 15 | REC_VLR_CREDITO_STDDEV | Numerica | Recarga |
| 16 | REC_TAXA_PLAT_PREPG | Numerica | Recarga |
| 17 | REC_VLR_REAL_STDDEV | Numerica | Recarga |
| 18 | REC_QTD_CARTAO_CHIPPRE | Numerica | Recarga |
| 19 | REC_QTD_PLANOS | Numerica | Recarga |
| 20 | REC_QTD_PLAT_AUTOC | Numerica | Recarga |
| 21 | PAG_QTD_PAGAMENTOS_TOTAL | Numerica | Pagamento |
| 22 | FAT_QTD_FATURAS_PRIMEIRA | Numerica | Faturamento |
| 23 | var_73 | Numerica | Cadastro |
| 24 | REC_QTD_STATUS_ZB1 | Numerica | Recarga |
| 25 | FAT_TAXA_PRIMEIRA_FAT | Numerica | Faturamento |
| 26 | FAT_DIAS_ATRASO_MIN | Numerica | Faturamento |
| 27 | PAG_TAXA_PAGAMENTOS_COM_JUROS | Numerica | Pagamento |
| 28 | FAT_DIAS_MAX_CRIACAO_VENCIMENTO | Numerica | Faturamento |
| 29 | REC_COEF_VARIACAO_CREDITO | Numerica | Recarga |
| 30 | PAG_DIAS_ENTRE_FATURAS | Numerica | Pagamento |
| 31 | FAT_DIAS_DESDE_ATIVACAO_CONTA | Numerica | Faturamento |
| 32 | var_85 | Numerica | Cadastro |
| 33 | REC_FREQ_RECARGA_DIARIA | Numerica | Recarga |
| 34 | FAT_DIAS_DESDE_ULTIMA_FAT | Numerica | Faturamento |
| 35 | FAT_DIAS_DESDE_PRIMEIRA_FAT | Numerica | Faturamento |
| 36 | PAG_QTD_FATURAS_DISTINTAS | Numerica | Pagamento |
| 37 | var_82 | Numerica | Cadastro |
| 38 | PAG_DIAS_DESDE_ULTIMA_FATURA | Numerica | Pagamento |
| 39 | REC_TAXA_PLAT_CONTROLE | Numerica | Recarga |
| 40 | var_90 | Numerica | Cadastro |
| 41 | PAG_TAXA_FORMA_PA | Numerica | Pagamento |
| 42 | PAG_QTD_PAGAMENTOS_COM_JUROS | Numerica | Pagamento |
| 43 | PAG_QTD_AREAS | Numerica | Pagamento |
| 44 | FAT_DIAS_ATRASO_MEDIO | Numerica | Faturamento |
| 45 | REC_QTD_RECARGAS_TOTAL | Numerica | Recarga |
| 46 | var_28 | Numerica | Cadastro |
| 47 | var_44 | Numerica | Cadastro |
| 48 | PAG_VLR_PAGAMENTO_FATURA_STDDEV | Numerica | Pagamento |
| 49 | REC_QTD_TIPOS_RECARGA | Numerica | Recarga |
| 50 | var_34 | **Categorica** | Cadastro |
| 51 | FAT_QTD_FAT_PREPG | Numerica | Faturamento |
| 52 | PAG_FLAG_ALTO_RISCO | Numerica | Pagamento |
| 53 | var_67 | **Categorica** | Cadastro |
| 54 | REC_QTD_PLATAFORMAS | Numerica | Recarga |
| 55 | PAG_QTD_STATUS_R | Numerica | Pagamento |
| 56 | PAG_COEF_VARIACAO_PAGAMENTO | Numerica | Pagamento |
| 57 | FAT_QTD_FATURAS_ACA | Numerica | Faturamento |
| 58 | REC_QTD_INSTITUICOES | Numerica | Recarga |
| 59 | FAT_QTD_SAFRAS_DISTINTAS | Numerica | Faturamento |

**Origem dos prefixos:**
- `REC_*` — Book de recargas (`Silver.book.ass_recarga_cmv`)
- `PAG_*` — Book de pagamentos (`Silver.book.pagamento`)
- `FAT_*` — Book de faturamento (`Silver.book.faturamento`)
- `TARGET_SCORE_*` — Score bureau movel (`Silver.rawdata.score_bureau_movel_full`)
- `var_*` — Dados cadastrais/telco (`Silver.rawdata.dados_cadastrais` / `telco`)

---

## Metricas de Referencia (Treinamento Original)

### LightGBM Baseline v6 (modelo principal)

| Metrica | OOS (202501) | OOT (202502-202503) |
|---------|-------------|---------------------|
| **KS** | 35.89 | 33.97 |
| **Gini** | 48.75 | 46.06 |
| **AUC** | 0.7437 | 0.7303 |

### Logistic Regression L1 v6 (modelo alternativo)

| Metrica | OOS (202501) | OOT (202502-202503) |
|---------|-------------|---------------------|
| **KS** | 34.79 | 32.77 |
| **Gini** | 46.94 | 44.15 |
| **AUC** | 0.7347 | 0.7207 |

### Split Temporal

| Dataset | SAFRAs | Uso |
|---------|--------|-----|
| Treino | 202410, 202411, 202412, 202501 | Treinamento do modelo |
| OOS (Out-of-Sample) | 202501 | Validacao cruzada temporal |
| OOT (Out-of-Time) | 202502, 202503 | Validacao de estabilidade |

---

## Interpretacao do Score

| SCORE | SCORE_PROB | FAIXA_RISCO | Interpretacao |
|-------|-----------|-------------|---------------|
| 900-1000 | 0.00-0.10 | 5 | Baixissimo risco |
| 800-899 | 0.10-0.20 | 4 | Baixo risco |
| 600-799 | 0.20-0.40 | 3 | Risco moderado |
| 400-599 | 0.40-0.60 | 2 | Risco elevado |
| 0-399 | 0.60-1.00 | 1 | Alto risco de default |

- **SCORE_PROB**: Probabilidade de FPD (First Payment Default). Quanto maior, mais risco.
- **SCORE**: Score de credito 0-1000. Quanto maior, MENOS risco (padrao mercado).
- **FAIXA_RISCO**: Quintil de risco (1=pior, 5=melhor).

---

## Informacoes Tecnicas

| Item | Detalhe |
|------|---------|
| Framework | scikit-learn 1.2.2 |
| Serializacao | joblib + cloudpickle |
| Python | 3.8+ (testado em 3.11.8) |
| Features | 59 (57 numericas + 2 categoricas) |
| Selecao | SHAP values (de 398 candidatas) |
| Target | FPD (First Payment Default — 0/1) |
| Granularidade | NUM_CPF + SAFRA (YYYYMM) |
| Leakage check | FAT_VLR_FPD removido; SCORE_RISCO verificado como seguro |
| Registros treino | ~2.6M (4 SAFRAs, apenas FLAG_INSTALACAO=1) |

---

## Troubleshooting

### Erro: `ModuleNotFoundError: No module named 'category_encoders'`
```bash
pip install category-encoders==2.6.3
```

### Erro: `TypeError: check_array() got unexpected keyword argument 'force_all_finite'`
O script `scoring_validacao.py` ja aplica o patch automaticamente.
Se estiver usando `joblib.load()` diretamente, adicione antes do `predict_proba()`:
```python
import lightgbm.sklearn as _lgbm_sklearn
_orig = _lgbm_sklearn._LGBMCheckArray
def _patch(*a, **kw):
    kw.pop('force_all_finite', None)
    kw.pop('ensure_all_finite', None)
    return _orig(*a, **kw)
_lgbm_sklearn._LGBMCheckArray = _patch
```

### Erro: `AttributeError: 'SimpleImputer' object has no attribute '_fill_dtype'`
O script `scoring_validacao.py` ja aplica o patch automaticamente.
Se estiver usando `joblib.load()` diretamente, veja a funcao `_patch_fill_dtype` no script.

### Erro: Features ausentes na base
Verifique que a base possui todas as 59 colunas listadas acima.
Os nomes devem ser identicos (case-sensitive).

---

## Contato

**Squad 2** — Hackathon PoD Academy 2025
