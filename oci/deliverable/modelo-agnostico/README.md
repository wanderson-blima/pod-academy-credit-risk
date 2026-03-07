# Modelo de Risco de Credito — Portatil (Qualquer Plataforma)

**Squad 2** | Hackathon PoD Academy | Claro + Oracle

---

## O que e este pacote

Modelos de risco de credito **100% portaveis** para predicao de First Payment Default (FPD)
em clientes de telecomunicacoes. Funciona em **qualquer plataforma** sem dependencia de cloud.

### Modelos incluidos

| Modelo | Arquivo | KS OOT | AUC OOT | Gini | PSI |
|--------|---------|--------|---------|------|-----|
| **LightGBM GBDT** | `lgbm_oci_20260217_214614.pkl` | 34.03 | 0.7305 | 46.11 | 0.0012 |
| LR L1 Scorecard | `lr_l1_oci_20260217_214614.pkl` | 32.86 | 0.7209 | 44.19 | 0.0007 |

Ambos os modelos foram validados com **paridade exata** entre Microsoft Fabric e OCI (10/10 metricas PASS).

---

## Estrutura do Pacote

```
modelo-agnostico/
├── README.md                                    # Este arquivo
├── requirements.txt                             # Dependencias (sklearn 1.2-1.6+)
├── Dockerfile                                   # Docker para teste em 1 comando
├── scoring.py                                   # Script universal de escoragem
├── dados_exemplo.csv                            # Dados sinteticos (500 registros)
├── modelos/
│   ├── lgbm_oci_20260217_214614.pkl            # LightGBM (pipeline completa)
│   └── lr_l1_oci_20260217_214614.pkl           # Logistic Regression L1 (pipeline completa)
└── metadata/
    ├── training_results_20260217_214614.json    # Metricas completas + paridade
    └── feature_importance_20260217_214614.csv   # Importancia das features (LGBM)
```

---

## Inicio Rapido (3 opcoes)

### Opcao 1: Python local (2 minutos)

```bash
# Criar ambiente virtual
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows

# Instalar dependencias
pip install -r requirements.txt

# Escorar dados de exemplo
python scoring.py --dados dados_exemplo.csv --modelo modelos/lgbm_oci_20260217_214614.pkl

# Escorar com metricas (se tiver coluna FPD)
python scoring.py --dados sua_base.csv --modelo modelos/lgbm_oci_20260217_214614.pkl --target FPD --output scores.csv
```

### Opcao 2: Docker (1 comando)

```bash
docker build -t credit-risk-scoring .
docker run credit-risk-scoring

# Ou com sua base:
docker run -v /caminho/para/dados:/data credit-risk-scoring \
  python scoring.py --dados /data/sua_base.csv --modelo modelos/lgbm_oci_20260217_214614.pkl --output /data/scores.csv
```

### Opcao 3: Import Python (para integracao)

```python
from scoring import carregar_modelo, preparar_features, escorar, calcular_metricas

# 1. Carregar modelo
modelo = carregar_modelo("modelos/lgbm_oci_20260217_214614.pkl")

# 2. Carregar dados
import pandas as pd
df = pd.read_csv("sua_base.csv")       # ou pd.read_parquet("base.parquet")

# 3. Selecionar features
X = preparar_features(df)

# 4. Escorar
resultado = escorar(modelo, X)
# resultado: DataFrame com SCORE_PROB (0-1), SCORE (0-1000), FAIXA_RISCO

# 5. Metricas (opcional, precisa coluna FPD)
metricas = calcular_metricas(df["FPD"].values, resultado["SCORE_PROB"].values)
# {"ks": 34.03, "gini": 46.11, "auc": 0.7305}
```

---

## As 59 Features Obrigatorias

A base deve conter **exatamente estas 59 colunas**:

| # | Feature | Tipo | Origem |
|---|---------|------|--------|
| 1 | TARGET_SCORE_02 | Num | Score bureau |
| 2 | TARGET_SCORE_01 | Num | Score bureau |
| 3 | REC_SCORE_RISCO | Num | Recarga |
| 4-20 | REC_* (16 features) | Num | Book de recargas |
| 21 | PAG_QTD_PAGAMENTOS_TOTAL | Num | Pagamento |
| 22-28 | FAT_* + PAG_* (7 features) | Num | Faturamento/Pagamento |
| 29-49 | Mix REC/PAG/FAT/var | Num | Varios |
| 50 | **var_34** | **Cat** | Cadastro |
| 51-52 | FAT/PAG | Num | Faturamento/Pagamento |
| 53 | **var_67** | **Cat** | Cadastro |
| 54-59 | Mix REC/PAG/FAT | Num | Varios |

Lista completa no arquivo `metadata/training_results_20260217_214614.json` (campo `feature_names`).

**Prefixos:**
- `REC_*` — Book de recargas (comportamento pre-pago)
- `PAG_*` — Book de pagamentos (historico financeiro)
- `FAT_*` — Book de faturamento (ciclo de vida conta)
- `TARGET_SCORE_*` — Score de bureau movel
- `var_*` — Dados cadastrais/telco

**Nota sobre var_34 e var_67:** Estes campos sao categoricos. Se sua base os tiver como
texto (strings), o script `scoring.py` aplica **count encoding automatico** (frequencia
normalizada). Se ja estiverem como numerico, sao usados diretamente.

---

## Interpretacao do Score

| SCORE | Probabilidade | Faixa | Interpretacao |
|-------|--------------|-------|---------------|
| 700-1000 | 0-30% | BAIXO | Baixo risco de default |
| 500-699 | 30-50% | MEDIO | Risco moderado |
| 300-499 | 50-70% | ALTO | Risco elevado |
| 0-299 | 70-100% | CRITICO | Alto risco de default |

- **SCORE_PROB**: P(FPD=1) — probabilidade de default. Maior = mais risco.
- **SCORE**: Score de credito 0-1000. Maior = MENOS risco (padrao mercado).
- **FAIXA_RISCO**: Classificacao qualitativa.

---

## Compatibilidade

| Componente | Versoes testadas |
|------------|-----------------|
| Python | 3.9, 3.10, 3.11 |
| scikit-learn | 1.2.2, 1.3.2, 1.4.x, 1.5.x, 1.6.1 |
| lightgbm | 4.0+, 4.3+, 4.5+ |
| pandas | 1.5+, 2.0+ |
| numpy | 1.23+, 1.26+ |
| OS | Windows, Linux, macOS |
| Cloud | OCI, AWS, GCP, Azure, Databricks |

O script `scoring.py` aplica patches automaticos para garantir compatibilidade
entre todas as versoes do scikit-learn.

---

## Pipeline original

Estes modelos foram treinados com dados de 3.9M clientes Claro processados
em um pipeline medallion (Bronze > Silver > Gold) executado tanto no
Microsoft Fabric quanto no OCI Data Flow, com paridade completa entre ambos.

| Aspecto | Valor |
|---------|-------|
| Registros de treino | ~2.7M (4 SAFRAs com FPD observado) |
| Features candidatas | 398 |
| Features selecionadas | 59 (IV + correlation + missing filter) |
| Target | FPD (First Payment Default, 0/1) |
| FPD rate | 21.3% |
| Split temporal | Train: 202410-202501, OOS: 202501, OOT: 202502-503 |
| Leakage check | FAT_VLR_FPD removido, SCORE_RISCO verificado |

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'category_encoders'`
```bash
pip install category-encoders>=2.6.0
```

### `TypeError: check_array() got unexpected keyword argument`
O script `scoring.py` ja aplica o patch automaticamente. Se estiver usando
`pickle.load()` diretamente, importe `scoring` antes para ativar o patch.

### Features ausentes na base
Verifique que a base possui todas as 59 colunas (case-sensitive).
Lista completa em `metadata/training_results_20260217_214614.json`.

---

**Squad 2** — Hackathon PoD Academy 2025 | Claro + Oracle
