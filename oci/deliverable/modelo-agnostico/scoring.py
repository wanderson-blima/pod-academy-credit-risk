"""
Scoring Universal — Credit Risk FPD (Hackathon PoD Academy / Squad 2)

Script 100% standalone para carregar o modelo .pkl, escorar uma base de dados
e calcular metricas de discriminacao (KS, Gini, AUC).

Funciona em QUALQUER ambiente:
  - Local (Windows/Linux/Mac)
  - Docker
  - OCI Data Science
  - AWS SageMaker
  - Google Colab
  - Azure ML
  - Databricks
  - Jupyter Notebook

Compativel com scikit-learn 1.2.x a 1.6.x (patch automatico incluso).

Uso:
    python scoring.py --dados base.csv --modelo modelos/lgbm_oci_20260217_214614.pkl
    python scoring.py --dados base.parquet --modelo modelos/lr_l1_oci_20260217_214614.pkl --target FPD --output scores.csv
"""

import argparse
import json
import os
import sys
import warnings
import pickle

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", message=".*Trying to unpickle estimator.*")

import numpy as np
import pandas as pd

# =============================================================================
# 1. PATCH DE COMPATIBILIDADE sklearn (1.2 a 1.6+)
# =============================================================================
# O parametro 'force_all_finite' foi renomeado para 'ensure_all_finite' no
# sklearn >= 1.4. Este patch garante que o modelo funcione em QUALQUER versao.

import sklearn.utils.validation as _val
_original_check = _val.check_array

def _patched_check(*a, **kw):
    force_val = kw.pop("force_all_finite", None)
    if force_val is not None and "ensure_all_finite" not in kw:
        kw["ensure_all_finite"] = force_val
    return _original_check(*a, **kw)

_val.check_array = _patched_check

# Patch LightGBM sklearn wrapper
try:
    import lightgbm.sklearn as _lgbm_sklearn
    if hasattr(_lgbm_sklearn, '_LGBMCheckArray'):
        _orig_lgbm = _lgbm_sklearn._LGBMCheckArray
        def _patched_lgbm(*args, **kwargs):
            force_val = kwargs.pop('force_all_finite', None)
            if force_val is not None and 'ensure_all_finite' not in kwargs:
                kwargs['ensure_all_finite'] = force_val
            return _orig_lgbm(*args, **kwargs)
        _lgbm_sklearn._LGBMCheckArray = _patched_lgbm
except Exception:
    pass

# Patch SimpleImputer._fill_dtype para sklearn >= 1.4
try:
    from sklearn.impute import SimpleImputer as _SI
    def _patch_fill_dtype(obj):
        if isinstance(obj, _SI) and not hasattr(obj, '_fill_dtype'):
            if hasattr(obj, 'statistics_'):
                obj._fill_dtype = obj.statistics_.dtype
        if hasattr(obj, 'steps'):
            for _, step in obj.steps:
                _patch_fill_dtype(step)
        if hasattr(obj, 'transformers_'):
            for _, transformer, _ in obj.transformers_:
                _patch_fill_dtype(transformer)
except Exception:
    _patch_fill_dtype = lambda obj: None


# =============================================================================
# 2. LISTA DE FEATURES (59 variaveis selecionadas)
# =============================================================================
FEATURE_NAMES = [
    "TARGET_SCORE_02", "TARGET_SCORE_01", "REC_SCORE_RISCO",
    "REC_TAXA_STATUS_A", "REC_QTD_LINHAS", "REC_DIAS_ENTRE_RECARGAS",
    "REC_QTD_INST_DIST_REG", "REC_DIAS_DESDE_ULTIMA_RECARGA",
    "REC_TAXA_CARTAO_ONLINE", "REC_QTD_STATUS_ZB2", "REC_QTD_CARTAO_ONLINE",
    "REC_COEF_VARIACAO_REAL", "var_26", "FAT_DIAS_MEDIO_CRIACAO_VENCIMENTO",
    "REC_VLR_CREDITO_STDDEV", "REC_TAXA_PLAT_PREPG", "REC_VLR_REAL_STDDEV",
    "REC_QTD_CARTAO_CHIPPRE", "REC_QTD_PLANOS", "REC_QTD_PLAT_AUTOC",
    "PAG_QTD_PAGAMENTOS_TOTAL", "FAT_QTD_FATURAS_PRIMEIRA", "var_73",
    "REC_QTD_STATUS_ZB1", "FAT_TAXA_PRIMEIRA_FAT", "FAT_DIAS_ATRASO_MIN",
    "PAG_TAXA_PAGAMENTOS_COM_JUROS", "FAT_DIAS_MAX_CRIACAO_VENCIMENTO",
    "REC_COEF_VARIACAO_CREDITO", "PAG_DIAS_ENTRE_FATURAS",
    "FAT_DIAS_DESDE_ATIVACAO_CONTA", "var_85", "REC_FREQ_RECARGA_DIARIA",
    "FAT_DIAS_DESDE_ULTIMA_FAT", "FAT_DIAS_DESDE_PRIMEIRA_FAT",
    "PAG_QTD_FATURAS_DISTINTAS", "var_82", "PAG_DIAS_DESDE_ULTIMA_FATURA",
    "REC_TAXA_PLAT_CONTROLE", "var_90", "PAG_TAXA_FORMA_PA",
    "PAG_QTD_PAGAMENTOS_COM_JUROS", "PAG_QTD_AREAS", "FAT_DIAS_ATRASO_MEDIO",
    "REC_QTD_RECARGAS_TOTAL", "var_28", "var_44",
    "PAG_VLR_PAGAMENTO_FATURA_STDDEV", "REC_QTD_TIPOS_RECARGA",
    "var_34",  # categorica
    "FAT_QTD_FAT_PREPG", "PAG_FLAG_ALTO_RISCO",
    "var_67",  # categorica
    "REC_QTD_PLATAFORMAS", "PAG_QTD_STATUS_R",
    "PAG_COEF_VARIACAO_PAGAMENTO", "FAT_QTD_FATURAS_ACA",
    "REC_QTD_INSTITUICOES", "FAT_QTD_SAFRAS_DISTINTAS",
]

CATEGORICAL_FEATURES = ["var_34", "var_67"]
NUMERIC_FEATURES = [f for f in FEATURE_NAMES if f not in CATEGORICAL_FEATURES]
SCORE_SCALE = 1000


# =============================================================================
# 3. FUNCOES PRINCIPAIS
# =============================================================================

def carregar_modelo(pkl_path):
    """Carrega o modelo .pkl e aplica patches de compatibilidade."""
    if not os.path.exists(pkl_path):
        raise FileNotFoundError(f"Arquivo nao encontrado: {pkl_path}")

    with open(pkl_path, "rb") as f:
        modelo = pickle.load(f)

    _patch_fill_dtype(modelo)

    if not hasattr(modelo, 'predict_proba'):
        raise TypeError(f"Objeto nao possui predict_proba(). Tipo: {type(modelo)}")

    print(f"Modelo carregado: {pkl_path}")
    if hasattr(modelo, 'steps'):
        print(f"  Pipeline steps: {[name for name, _ in modelo.steps]}")
        print(f"  Estimador: {type(modelo.steps[-1][1]).__name__}")
    return modelo


def carregar_dados(caminho):
    """Carrega dados de CSV, Parquet ou diretorio Parquet."""
    if not os.path.exists(caminho):
        raise FileNotFoundError(f"Arquivo nao encontrado: {caminho}")

    if os.path.isdir(caminho) or caminho.endswith(".parquet"):
        df = pd.read_parquet(caminho)
    elif caminho.endswith(".csv"):
        df = pd.read_csv(caminho)
    elif caminho.endswith((".xls", ".xlsx")):
        df = pd.read_excel(caminho)
    else:
        raise ValueError(f"Formato nao suportado: {caminho}. Use CSV, Parquet ou Excel.")

    print(f"Dados carregados: {caminho} ({df.shape[0]:,} linhas x {df.shape[1]} colunas)")
    return df


def preparar_features(df):
    """Seleciona as 59 features necessarias na ordem correta.

    Se var_34/var_67 contiverem strings, aplica count encoding (frequencia
    normalizada) automaticamente — o modelo foi treinado com esses campos
    ja convertidos para numerico.
    """
    faltando = [f for f in FEATURE_NAMES if f not in df.columns]
    if faltando:
        raise ValueError(f"{len(faltando)} features ausentes: {faltando[:5]}...")
    X = df[FEATURE_NAMES].copy()

    for col in CATEGORICAL_FEATURES:
        if not pd.api.types.is_numeric_dtype(X[col]):
            counts = X[col].value_counts(normalize=True)
            X[col] = X[col].map(counts).astype(float)
            print(f"  Auto-encoded {col}: {len(counts)} categorias -> numerico (count encoding)")

    return X


def escorar(modelo, X):
    """Aplica o modelo e gera scores de credito (0-1000)."""
    y_prob = modelo.predict_proba(X)[:, 1]
    y_prob = np.clip(np.nan_to_num(y_prob, nan=0.5), 0.0, 1.0)

    score = np.round(SCORE_SCALE * (1.0 - y_prob)).astype(int)

    def faixa_risco(s):
        if s < 300: return "CRITICO"
        elif s < 500: return "ALTO"
        elif s < 700: return "MEDIO"
        else: return "BAIXO"

    faixas = pd.Series([faixa_risco(s) for s in score])

    resultado = pd.DataFrame({
        "SCORE_PROB": y_prob,
        "SCORE": score,
        "FAIXA_RISCO": faixas,
    })

    print(f"\nEscoragem: {len(resultado):,} registros")
    print(f"  Score medio: {resultado['SCORE'].mean():.0f}")
    print(f"  Distribuicao:")
    for band in ["CRITICO", "ALTO", "MEDIO", "BAIXO"]:
        n = (faixas == band).sum()
        pct = n / len(faixas) * 100
        print(f"    {band:10s}: {n:>8,} ({pct:.1f}%)")

    return resultado


def calcular_metricas(y_true, y_prob):
    """Calcula KS, Gini e AUC."""
    from sklearn.metrics import roc_auc_score, roc_curve

    y_true = np.asarray(y_true, dtype=int)
    y_prob = np.asarray(y_prob, dtype=float)

    mask = ~np.isnan(y_true) & ~np.isnan(y_prob)
    y_true, y_prob = y_true[mask], y_prob[mask]

    if len(np.unique(y_true)) < 2:
        print("AVISO: Target tem apenas 1 classe. Metricas nao calculadas.")
        return None

    auc = roc_auc_score(y_true, y_prob)
    gini = (2 * auc - 1) * 100
    fpr, tpr, _ = roc_curve(y_true, y_prob)
    ks = np.max(tpr - fpr) * 100

    print(f"\nMetricas:")
    print(f"  KS:   {ks:.2f}  {'BOM' if ks >= 30 else 'MINIMO' if ks >= 20 else 'ABAIXO'}")
    print(f"  Gini: {gini:.2f}  {'BOM' if gini >= 40 else 'MINIMO' if gini >= 30 else 'ABAIXO'}")
    print(f"  AUC:  {auc:.4f}  {'BOM' if auc >= 0.70 else 'MINIMO' if auc >= 0.65 else 'ABAIXO'}")

    return {"ks": round(ks, 2), "gini": round(gini, 2), "auc": round(auc, 4)}


# =============================================================================
# 4. METRICAS DE REFERENCIA
# =============================================================================
METRICAS_REFERENCIA = {
    "lgbm_oci": {
        "ks_oos": 35.28, "auc_oos": 0.7398, "gini_oos": 47.95,
        "ks_oot": 34.03, "auc_oot": 0.7305, "gini_oot": 46.11,
        "psi": 0.001205,
    },
    "lr_l1_oci": {
        "ks_oos": 33.97, "auc_oos": 0.7293, "gini_oos": 45.85,
        "ks_oot": 32.86, "auc_oot": 0.7209, "gini_oot": 44.19,
        "psi": 0.000749,
    },
    "lgbm_fabric": {
        "ks_oot": 33.97, "auc_oot": 0.7303, "gini_oot": 46.06,
    },
    "lr_l1_fabric": {
        "ks_oot": 32.77, "auc_oot": 0.7207, "gini_oot": 44.15,
    },
}


# =============================================================================
# 5. MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Scoring Universal - Credit Risk FPD (Squad 2)",
        epilog="Funciona em qualquer plataforma: local, Docker, OCI, AWS, GCP, Azure.",
    )
    parser.add_argument("--dados", required=True, help="Base de dados (CSV, Parquet, Excel ou diretorio)")
    parser.add_argument("--modelo", required=True, help="Arquivo .pkl do modelo")
    parser.add_argument("--target", default=None, help="Coluna target (FPD) para calcular metricas")
    parser.add_argument("--output", default=None, help="Salvar scores em CSV")

    args = parser.parse_args()

    print("=" * 60)
    print("SCORING UNIVERSAL - Credit Risk FPD")
    print("Hackathon PoD Academy - Claro + Oracle (Squad 2)")
    print("=" * 60)

    modelo = carregar_modelo(args.modelo)
    df = carregar_dados(args.dados)
    X = preparar_features(df)
    resultado = escorar(modelo, X)

    metricas = None
    if args.target and args.target in df.columns:
        metricas = calcular_metricas(df[args.target].values, resultado["SCORE_PROB"].values)

    if args.output:
        cols_chave = [c for c in ["NUM_CPF", "SAFRA"] if c in df.columns]
        df_out = pd.concat([df[cols_chave].reset_index(drop=True), resultado], axis=1) if cols_chave else resultado
        df_out.to_csv(args.output, index=False)
        print(f"\nScores salvos: {args.output}")

    print("=" * 60)


if __name__ == "__main__":
    main()
