"""
Scoring & Validacao Standalone — Credit Risk FPD (Hackathon PoD Academy / Squad 2)

Script 100% standalone para carregar o modelo .pkl, escorar uma base de dados
e calcular metricas de discriminacao (KS, Gini, AUC).

Nao requer MLflow, Microsoft Fabric, PySpark ou qualquer infra cloud.
Funciona em qualquer ambiente Python 3.8+ com as dependencias do requirements.txt.

Uso:
    python scoring_validacao.py --dados caminho/para/base.csv --modelo modelos/lgbm_baseline_v6.pkl

    Ou importar como modulo:
        from scoring_validacao import carregar_modelo, escorar, calcular_metricas
"""

import argparse
import json
import os
import sys
import warnings

# Suprimir warnings de versao sklearn (modelo foi salvo com 1.2.2, compativel com 1.2-1.3.x)
warnings.filterwarnings("ignore", category=UserWarning, message=".*InconsistentVersionWarning.*")
warnings.filterwarnings("ignore", message=".*Trying to unpickle estimator.*")

import joblib
import numpy as np
import pandas as pd

# =============================================================================
# 1. PATCH DE COMPATIBILIDADE sklearn/LightGBM
# =============================================================================
# O LightGBM sklearn wrapper usa check_array() com parametro 'force_all_finite'
# que foi renomeado para 'ensure_all_finite' no sklearn >= 1.4.
# Este patch garante que o modelo funcione independente da versao do sklearn.

try:
    import lightgbm.sklearn as _lgbm_sklearn
    if hasattr(_lgbm_sklearn, '_LGBMCheckArray'):
        _orig_check = _lgbm_sklearn._LGBMCheckArray
        def _patched_lgbm_check(*args, **kwargs):
            kwargs.pop('force_all_finite', None)
            kwargs.pop('ensure_all_finite', None)
            return _orig_check(*args, **kwargs)
        _lgbm_sklearn._LGBMCheckArray = _patched_lgbm_check
except Exception:
    pass  # LightGBM nao instalado ou versao sem _LGBMCheckArray

# Patch SimpleImputer._fill_dtype para sklearn >= 1.4
try:
    from sklearn.impute import SimpleImputer as _SI
    def _patch_fill_dtype(obj):
        """Recursivamente corrige _fill_dtype em todos os SimpleImputer do pipeline."""
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
# 2. LISTA DE FEATURES (59 variaveis selecionadas via SHAP)
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

# Features categoricas (tratadas pelo CountEncoder dentro do pipeline)
CATEGORICAL_FEATURES = ["var_34", "var_67"]

# Features numericas (tratadas pelo SimpleImputer(median) dentro do pipeline)
NUMERIC_FEATURES = [f for f in FEATURE_NAMES if f not in CATEGORICAL_FEATURES]

# Escala do score de credito (0 = alto risco, 1000 = baixo risco)
SCORE_SCALE = 1000


# =============================================================================
# 3. FUNCOES PRINCIPAIS
# =============================================================================

def carregar_modelo(pkl_path):
    """Carrega o modelo .pkl e aplica patches de compatibilidade.

    Args:
        pkl_path: Caminho para o arquivo .pkl do modelo.

    Returns:
        Pipeline sklearn carregada e pronta para predict_proba().
    """
    if not os.path.exists(pkl_path):
        raise FileNotFoundError(f"Arquivo .pkl nao encontrado: {pkl_path}")

    modelo = joblib.load(pkl_path)
    _patch_fill_dtype(modelo)

    # Validar que e um pipeline sklearn com predict_proba
    if not hasattr(modelo, 'predict_proba'):
        raise TypeError(f"Objeto carregado nao possui predict_proba(). Tipo: {type(modelo)}")
    if not hasattr(modelo, 'steps'):
        raise TypeError(f"Objeto carregado nao e um sklearn Pipeline. Tipo: {type(modelo)}")

    print(f"Modelo carregado: {pkl_path}")
    print(f"  Pipeline steps: {[name for name, _ in modelo.steps]}")
    print(f"  Tipo estimador: {type(modelo.steps[-1][1]).__name__}")
    return modelo


def carregar_dados(caminho, sep=",", encoding="utf-8"):
    """Carrega dados de CSV ou Parquet.

    Args:
        caminho: Caminho do arquivo (CSV, Parquet, ou diretorio Parquet).
        sep: Separador CSV (default: ',').
        encoding: Encoding CSV (default: 'utf-8').

    Returns:
        DataFrame pandas com os dados carregados.
    """
    if not os.path.exists(caminho):
        raise FileNotFoundError(f"Arquivo de dados nao encontrado: {caminho}")

    ext = os.path.splitext(caminho)[1].lower()
    if ext == ".parquet" or os.path.isdir(caminho):
        df = pd.read_parquet(caminho)
    elif ext == ".csv":
        df = pd.read_csv(caminho, sep=sep, encoding=encoding)
    elif ext in (".xls", ".xlsx"):
        df = pd.read_excel(caminho)
    else:
        raise ValueError(f"Formato nao suportado: {ext}. Use CSV, Parquet ou Excel.")

    print(f"Dados carregados: {caminho}")
    print(f"  Shape: {df.shape[0]:,} linhas x {df.shape[1]} colunas")
    return df


def preparar_features(df, feature_names=None):
    """Seleciona e valida as 59 features necessarias para escoragem.

    O pipeline sklearn interno ja trata missing values e encoding.
    Esta funcao apenas seleciona as colunas corretas na ordem correta.

    Args:
        df: DataFrame com os dados (deve conter as 59 colunas).
        feature_names: Lista de features (default: FEATURE_NAMES global).

    Returns:
        DataFrame com as 59 features na ordem correta.
    """
    if feature_names is None:
        feature_names = FEATURE_NAMES

    # Verificar colunas presentes
    colunas_disponiveis = set(df.columns)
    colunas_faltando = [f for f in feature_names if f not in colunas_disponiveis]

    if colunas_faltando:
        print(f"\nERRO: {len(colunas_faltando)} features ausentes na base de dados:")
        for f in colunas_faltando:
            print(f"  - {f}")
        print(f"\nFeatures disponiveis na base ({len(colunas_disponiveis)}):")
        for f in sorted(colunas_disponiveis):
            print(f"  {f}")
        raise ValueError(
            f"{len(colunas_faltando)} features obrigatorias nao encontradas. "
            f"Verifique se a base contem todas as 59 variaveis do modelo."
        )

    X = df[feature_names].copy()
    print(f"Features selecionadas: {len(feature_names)} colunas")
    return X


def escorar(modelo, X):
    """Aplica o modelo e gera scores de credito.

    Args:
        modelo: Pipeline sklearn carregada via carregar_modelo().
        X: DataFrame com as 59 features (output de preparar_features()).

    Returns:
        DataFrame com colunas:
            - SCORE_PROB: Probabilidade de default (0-1, maior = mais risco)
            - SCORE: Score de credito (0-1000, maior = menos risco)
            - FAIXA_RISCO: Faixa de risco 1-5 (1=maior risco, 5=menor risco)
    """
    # Gerar probabilidade de default (classe 1 = FPD)
    y_prob = modelo.predict_proba(X)[:, 1]

    # Validar range
    if np.any(np.isnan(y_prob)):
        n_nan = np.isnan(y_prob).sum()
        warnings.warn(f"{n_nan} scores NaN detectados — substituindo por 0.5")
        y_prob = np.nan_to_num(y_prob, nan=0.5)

    y_prob = np.clip(y_prob, 0.0, 1.0)

    # Score invertido: 0-1000 (padrao mercado credito — maior score = menor risco)
    score = np.round(SCORE_SCALE * (1.0 - y_prob)).astype(int)

    # Faixa de risco por quintil
    try:
        faixa = pd.qcut(y_prob, q=5, labels=[1, 2, 3, 4, 5], duplicates="drop").astype(int)
    except ValueError:
        faixa = pd.cut(
            pd.Series(y_prob).rank(pct=True), bins=5, labels=[1, 2, 3, 4, 5]
        ).astype(int)

    resultado = pd.DataFrame({
        "SCORE_PROB": y_prob,
        "SCORE": score,
        "FAIXA_RISCO": faixa,
    })

    print(f"\nResultados da escoragem:")
    print(f"  Registros escorados: {len(resultado):,}")
    print(f"  Score medio: {resultado['SCORE'].mean():.0f}")
    print(f"  Score min/max: {resultado['SCORE'].min()} / {resultado['SCORE'].max()}")
    print(f"  Distribuicao por faixa:")
    print(resultado["FAIXA_RISCO"].value_counts().sort_index().to_string())

    return resultado


def calcular_metricas(y_true, y_prob):
    """Calcula KS, Gini e AUC a partir de labels reais e probabilidades preditas.

    Args:
        y_true: Array com target real (0/1 — FPD).
        y_prob: Array com probabilidades preditas (output de predict_proba[:, 1]).

    Returns:
        Dict com metricas: ks, gini, auc.
    """
    from sklearn.metrics import roc_auc_score, roc_curve

    y_true = np.asarray(y_true, dtype=int)
    y_prob = np.asarray(y_prob, dtype=float)

    if len(np.unique(y_true)) < 2:
        raise ValueError(
            f"y_true deve ter ao menos 2 classes (0 e 1). "
            f"Valores unicos encontrados: {np.unique(y_true)}"
        )

    # AUC
    auc = roc_auc_score(y_true, y_prob)

    # Gini
    gini = (2 * auc - 1) * 100

    # KS (Kolmogorov-Smirnov)
    fpr, tpr, _ = roc_curve(y_true, y_prob)
    ks = np.max(tpr - fpr) * 100

    metricas = {"ks": ks, "auc": auc, "gini": gini}

    print(f"\nMetricas de Discriminacao:")
    print(f"  KS:   {ks:.2f}")
    print(f"  Gini: {gini:.2f}")
    print(f"  AUC:  {auc:.4f}")

    # Referencia de qualidade
    print(f"\nReferencia (thresholds do projeto):")
    print(f"  KS:   {'BOM' if ks >= 30 else 'MINIMO' if ks >= 20 else 'ABAIXO'} (minimo=20, bom=30, excelente=40+)")
    print(f"  Gini: {'BOM' if gini >= 40 else 'MINIMO' if gini >= 30 else 'ABAIXO'} (minimo=30, bom=40, excelente=50+)")
    print(f"  AUC:  {'BOM' if auc >= 0.70 else 'MINIMO' if auc >= 0.65 else 'ABAIXO'} (minimo=0.65, bom=0.70, excelente=0.75+)")

    return metricas


def gerar_relatorio(df_dados, resultado, metricas=None, output_path=None):
    """Gera relatorio completo da escoragem em formato texto e CSV.

    Args:
        df_dados: DataFrame original com NUM_CPF e SAFRA.
        resultado: DataFrame de output da funcao escorar().
        metricas: Dict com metricas (output de calcular_metricas, opcional).
        output_path: Caminho para salvar CSV de scores (opcional).

    Returns:
        DataFrame consolidado com chaves + scores.
    """
    # Montar output final
    colunas_chave = []
    if "NUM_CPF" in df_dados.columns:
        colunas_chave.append("NUM_CPF")
    if "SAFRA" in df_dados.columns:
        colunas_chave.append("SAFRA")

    if colunas_chave:
        df_output = pd.concat([
            df_dados[colunas_chave].reset_index(drop=True),
            resultado.reset_index(drop=True)
        ], axis=1)
    else:
        df_output = resultado.copy()

    # Resumo
    print(f"\n{'='*60}")
    print(f"RELATORIO DE ESCORAGEM — Credit Risk FPD")
    print(f"{'='*60}")
    print(f"Total de registros: {len(df_output):,}")

    if "SAFRA" in df_output.columns:
        print(f"\nVolumetria por SAFRA:")
        print(df_output.groupby("SAFRA").size().to_string())

    print(f"\nDistribuicao de scores:")
    print(df_output["SCORE"].describe().to_string())

    print(f"\nDistribuicao por faixa de risco:")
    faixa_stats = df_output.groupby("FAIXA_RISCO").agg(
        qtd=("SCORE", "count"),
        score_medio=("SCORE", "mean"),
        prob_media=("SCORE_PROB", "mean"),
    )
    print(faixa_stats.to_string())

    if metricas:
        print(f"\nMetricas do modelo:")
        for k, v in metricas.items():
            print(f"  {k.upper()}: {v:.4f}")

    # Salvar CSV
    if output_path:
        df_output.to_csv(output_path, index=False)
        print(f"\nScores salvos em: {output_path}")

    print(f"{'='*60}")
    return df_output


# =============================================================================
# 4. METRICAS DE REFERENCIA (treinamento original)
# =============================================================================
METRICAS_REFERENCIA = {
    "lgbm_baseline_v6": {
        "ks_oos": 35.89, "auc_oos": 0.7437, "gini_oos": 48.75,
        "ks_oot": 33.97, "auc_oot": 0.7303, "gini_oot": 46.06,
    },
    "lr_l1_v6": {
        "ks_oos": 34.79, "auc_oos": 0.7347, "gini_oos": 46.94,
        "ks_oot": 32.77, "auc_oot": 0.7207, "gini_oot": 44.15,
    },
}


# =============================================================================
# 5. EXECUCAO VIA LINHA DE COMANDO
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Scoring & Validacao — Credit Risk FPD (Squad 2)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Escorar base sem target (apenas gerar scores):
  python scoring_validacao.py --dados base_clientes.csv --modelo modelos/lgbm_baseline_v6.pkl

  # Escorar base COM target (gerar scores + calcular metricas):
  python scoring_validacao.py --dados base_clientes.csv --modelo modelos/lgbm_baseline_v6.pkl --target FPD

  # Salvar resultado em CSV:
  python scoring_validacao.py --dados base.csv --modelo modelos/lgbm_baseline_v6.pkl --output scores.csv

  # Usar modelo LR:
  python scoring_validacao.py --dados base.csv --modelo modelos/lr_l1_v6.pkl
        """,
    )
    parser.add_argument("--dados", required=True, help="Caminho para base de dados (CSV ou Parquet)")
    parser.add_argument("--modelo", required=True, help="Caminho para .pkl do modelo")
    parser.add_argument("--target", default=None, help="Nome da coluna target (FPD) para calcular metricas")
    parser.add_argument("--output", default=None, help="Caminho para salvar CSV de scores")
    parser.add_argument("--sep", default=",", help="Separador CSV (default: ',')")
    parser.add_argument("--encoding", default="utf-8", help="Encoding CSV (default: utf-8)")

    args = parser.parse_args()

    print("=" * 60)
    print("SCORING STANDALONE — Credit Risk FPD (Squad 2)")
    print("Hackathon PoD Academy — Claro + Oracle")
    print("=" * 60)

    # Carregar modelo
    modelo = carregar_modelo(args.modelo)

    # Carregar dados
    df = carregar_dados(args.dados, sep=args.sep, encoding=args.encoding)

    # Preparar features
    X = preparar_features(df)

    # Escorar
    resultado = escorar(modelo, X)

    # Calcular metricas (se target disponivel)
    metricas = None
    if args.target:
        if args.target not in df.columns:
            print(f"\nWARNING: Coluna target '{args.target}' nao encontrada. Metricas nao serao calculadas.")
        else:
            y_true = df[args.target].values
            metricas = calcular_metricas(y_true, resultado["SCORE_PROB"].values)

    # Gerar relatorio
    gerar_relatorio(df, resultado, metricas=metricas, output_path=args.output)


if __name__ == "__main__":
    main()
