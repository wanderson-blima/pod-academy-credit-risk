"""
Temporal Cross-Validation — Phase 3.1
Expanding window temporal CV for credit risk models.

Usage: Import TemporalCV from pipeline scripts.
"""
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from scipy.stats import ks_2samp


def compute_ks(y_true, y_prob):
    """KS statistic — max separation between cumulative distributions."""
    prob_good = y_prob[y_true == 0]
    prob_bad = y_prob[y_true == 1]
    ks_stat, _ = ks_2samp(prob_good, prob_bad)
    return ks_stat


class TemporalCV:
    """Expanding window temporal cross-validation.

    Ensures no temporal leakage by using only past data for training
    and future data for validation.

    Folds:
        Fold 1: Train=202410          | Val=202411
        Fold 2: Train=202410-11       | Val=202412
        Fold 3: Train=202410-12       | Val=202501
        Final:  Train=202410-202501   | OOT=202502-03 (holdout, never touched during HPO)
    """

    def __init__(self, safra_col="SAFRA",
                 train_safras=None, val_safras=None,
                 oot_safras=None):
        self.safra_col = safra_col
        self.train_safras = train_safras or [202410, 202411, 202412, 202501]
        self.val_safras = val_safras  # If None, uses expanding window
        self.oot_safras = oot_safras or [202502, 202503]

    def get_folds(self, df):
        """Generate expanding window train/val splits.

        Yields: (fold_idx, train_indices, val_indices, fold_info)
        """
        sorted_safras = sorted(self.train_safras)

        for i in range(1, len(sorted_safras)):
            train_safras = sorted_safras[:i]
            val_safra = sorted_safras[i]

            train_mask = df[self.safra_col].isin(train_safras)
            val_mask = df[self.safra_col] == val_safra

            train_idx = df.index[train_mask].values
            val_idx = df.index[val_mask].values

            if len(train_idx) == 0 or len(val_idx) == 0:
                continue

            fold_info = {
                "fold": i,
                "train_safras": train_safras,
                "val_safra": val_safra,
                "train_n": len(train_idx),
                "val_n": len(val_idx),
            }

            yield i, train_idx, val_idx, fold_info

    def get_oot_split(self, df):
        """Get final OOT holdout split (all train SAFRAs vs OOT)."""
        train_mask = df[self.safra_col].isin(self.train_safras)
        oot_mask = df[self.safra_col].isin(self.oot_safras)

        return df.index[train_mask].values, df.index[oot_mask].values

    def evaluate_cv(self, model_class, model_params, df, features, target,
                    fit_params=None):
        """Run temporal CV and return per-fold metrics.

        Args:
            model_class: sklearn-compatible model class
            model_params: dict of model parameters
            df: DataFrame with features + target + SAFRA
            features: list of feature column names
            target: target column name
            fit_params: optional dict passed to model.fit()

        Returns: dict with per-fold metrics and mean metrics
        """
        if fit_params is None:
            fit_params = {}

        fold_metrics = []

        for fold_idx, train_idx, val_idx, fold_info in self.get_folds(df):
            X_train = df.loc[train_idx, features]
            y_train = df.loc[train_idx, target].astype(int)
            X_val = df.loc[val_idx, features]
            y_val = df.loc[val_idx, target].astype(int)

            model = model_class(**model_params)
            model.fit(X_train, y_train, **fit_params)

            y_prob = model.predict_proba(X_val)[:, 1]
            auc = roc_auc_score(y_val, y_prob)
            ks = compute_ks(y_val.values, y_prob)
            gini = (2 * auc - 1) * 100

            metrics = {
                **fold_info,
                "auc": round(auc, 5),
                "ks": round(ks, 5),
                "gini": round(gini, 2),
            }
            fold_metrics.append(metrics)

            print(f"  Fold {fold_idx}: Train={fold_info['train_safras']} "
                  f"Val={fold_info['val_safra']} | "
                  f"KS={ks:.4f} AUC={auc:.4f}")

        if not fold_metrics:
            return {"folds": [], "mean_ks": 0, "mean_auc": 0, "mean_gini": 0}

        return {
            "folds": fold_metrics,
            "mean_ks": round(np.mean([m["ks"] for m in fold_metrics]), 5),
            "mean_auc": round(np.mean([m["auc"] for m in fold_metrics]), 5),
            "mean_gini": round(np.mean([m["gini"] for m in fold_metrics]), 2),
            "std_ks": round(np.std([m["ks"] for m in fold_metrics]), 5),
            "std_auc": round(np.std([m["auc"] for m in fold_metrics]), 5),
        }


def optuna_objective_factory(model_class, df, features, target,
                             temporal_cv, build_params_fn,
                             preprocessing_pipeline=None):
    """Factory for Optuna objective functions with temporal CV.

    Args:
        model_class: sklearn model class
        df: DataFrame
        features: feature column names
        target: target column name
        temporal_cv: TemporalCV instance
        build_params_fn: function(trial) -> model_params dict
        preprocessing_pipeline: optional sklearn Pipeline for preprocessing

    Returns: objective function for Optuna
    """
    def objective(trial):
        params = build_params_fn(trial)

        fold_ks = []
        for fold_idx, train_idx, val_idx, fold_info in temporal_cv.get_folds(df):
            X_train = df.loc[train_idx, features].copy()
            y_train = df.loc[train_idx, target].astype(int)
            X_val = df.loc[val_idx, features].copy()
            y_val = df.loc[val_idx, target].astype(int)

            if preprocessing_pipeline is not None:
                X_train = preprocessing_pipeline.fit_transform(X_train)
                X_val = preprocessing_pipeline.transform(X_val)

            model = model_class(**params)
            model.fit(X_train, y_train)

            y_prob = model.predict_proba(X_val)[:, 1]
            ks = compute_ks(y_val.values, y_prob)
            fold_ks.append(ks)

        return np.mean(fold_ks)

    return objective


if __name__ == "__main__":
    print("Temporal CV Module")
    print("Folds: expanding window over SAFRAs 202410-202501")
    print("OOT holdout: 202502-202503 (never touched during HPO)")
