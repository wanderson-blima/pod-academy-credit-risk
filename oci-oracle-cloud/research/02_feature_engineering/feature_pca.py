"""
PCA Features — Phase 2.6
PCA on domain subsets (REC_, PAG_, FAT_) for orthogonal representations.

Usage: Import create_pca_features(df) and PCAFeatureTransformer from pipeline scripts.
"""
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline


# Domain feature lists for PCA
PCA_DOMAINS = {
    "REC": [
        "REC_SCORE_RISCO", "REC_TAXA_STATUS_A", "REC_QTD_LINHAS",
        "REC_DIAS_ENTRE_RECARGAS", "REC_QTD_INST_DIST_REG",
        "REC_DIAS_DESDE_ULTIMA_RECARGA", "REC_TAXA_CARTAO_ONLINE",
        "REC_QTD_STATUS_ZB2", "REC_QTD_CARTAO_ONLINE",
        "REC_COEF_VARIACAO_REAL", "REC_VLR_CREDITO_STDDEV",
        "REC_TAXA_PLAT_PREPG", "REC_VLR_REAL_STDDEV",
        "REC_QTD_CARTAO_CHIPPRE", "REC_QTD_PLANOS", "REC_QTD_PLAT_AUTOC",
        "REC_QTD_STATUS_ZB1", "REC_COEF_VARIACAO_CREDITO",
        "REC_FREQ_RECARGA_DIARIA", "REC_TAXA_PLAT_CONTROLE",
        "REC_QTD_RECARGAS_TOTAL", "REC_QTD_TIPOS_RECARGA",
        "REC_QTD_PLATAFORMAS", "REC_QTD_INSTITUICOES",
    ],
    "PAG": [
        "PAG_QTD_PAGAMENTOS_TOTAL", "PAG_TAXA_PAGAMENTOS_COM_JUROS",
        "PAG_DIAS_ENTRE_FATURAS", "PAG_QTD_FATURAS_DISTINTAS",
        "PAG_DIAS_DESDE_ULTIMA_FATURA", "PAG_TAXA_FORMA_PA",
        "PAG_QTD_PAGAMENTOS_COM_JUROS", "PAG_QTD_AREAS",
        "PAG_VLR_PAGAMENTO_FATURA_STDDEV", "PAG_FLAG_ALTO_RISCO",
        "PAG_QTD_STATUS_R", "PAG_COEF_VARIACAO_PAGAMENTO",
    ],
    "FAT": [
        "FAT_DIAS_MEDIO_CRIACAO_VENCIMENTO", "FAT_QTD_FATURAS_PRIMEIRA",
        "FAT_TAXA_PRIMEIRA_FAT", "FAT_DIAS_ATRASO_MIN",
        "FAT_DIAS_MAX_CRIACAO_VENCIMENTO", "FAT_DIAS_DESDE_ATIVACAO_CONTA",
        "FAT_DIAS_DESDE_ULTIMA_FAT", "FAT_DIAS_DESDE_PRIMEIRA_FAT",
        "FAT_DIAS_ATRASO_MEDIO", "FAT_QTD_FAT_PREPG",
        "FAT_QTD_FATURAS_ACA", "FAT_QTD_SAFRAS_DISTINTAS",
    ],
}

DEFAULT_N_COMPONENTS = {"REC": 5, "PAG": 4, "FAT": 4}


class PCAFeatureTransformer:
    """Fitted PCA transformer for domain feature subsets.

    Fit on training data, then transform train/test consistently.
    """

    def __init__(self, n_components=None):
        self.n_components = n_components or DEFAULT_N_COMPONENTS
        self.pipelines = {}
        self.feature_names_out = []
        self.is_fitted = False

    def fit(self, df):
        """Fit PCA pipelines on training data."""
        self.pipelines = {}
        self.feature_names_out = []

        for domain, features in PCA_DOMAINS.items():
            available = [f for f in features if f in df.columns]
            if len(available) < 3:
                print(f"  [SKIP] {domain}: only {len(available)} features available")
                continue

            n_comp = min(self.n_components.get(domain, 4), len(available))

            pipe = Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("pca", PCA(n_components=n_comp, random_state=42)),
            ])

            pipe.fit(df[available])
            self.pipelines[domain] = {
                "pipeline": pipe,
                "features": available,
                "n_components": n_comp,
            }

            explained = pipe.named_steps["pca"].explained_variance_ratio_
            total_explained = sum(explained)
            print(f"  {domain}: {n_comp} components, {total_explained:.2%} variance explained")

            for i in range(n_comp):
                self.feature_names_out.append(f"PCA_{domain}_{i+1}")

        self.is_fitted = True
        return self

    def transform(self, df):
        """Transform using fitted PCA pipelines."""
        if not self.is_fitted:
            raise RuntimeError("Call fit() before transform()")

        result = df.copy()

        for domain, info in self.pipelines.items():
            pipe = info["pipeline"]
            features = info["features"]
            n_comp = info["n_components"]

            components = pipe.transform(df[features])
            for i in range(n_comp):
                result[f"PCA_{domain}_{i+1}"] = components[:, i]

        return result

    def fit_transform(self, df):
        """Fit and transform in one step."""
        self.fit(df)
        return self.transform(df)


def create_pca_features(df, pca_transformer=None):
    """Create PCA features from domain subsets.

    If pca_transformer is provided, uses it (for test data).
    Otherwise, fits a new transformer (for training data).

    Returns (result_df, pca_transformer).
    """
    if pca_transformer is None:
        pca_transformer = PCAFeatureTransformer()
        result = pca_transformer.fit_transform(df)
    else:
        result = pca_transformer.transform(df)

    new_cols = [c for c in result.columns if c not in df.columns]
    print(f"[PCA] Created {len(new_cols)} PCA features: {new_cols}")

    return result, pca_transformer


def get_pca_feature_names():
    """Return list of all possible PCA feature names."""
    names = []
    for domain, n_comp in DEFAULT_N_COMPONENTS.items():
        for i in range(n_comp):
            names.append(f"PCA_{domain}_{i+1}")
    return names


if __name__ == "__main__":
    print("PCA Features Module — use create_pca_features(df)")
    print(f"Expected output features: {get_pca_feature_names()}")
