"""
EnsembleModel — Phase 5.4
Unified ensemble model class compatible with batch_scoring.py and register_model_catalog.py.
Supports blend (weighted average) and stack (meta-learner) modes.

Usage:
    from ensemble_model import EnsembleModel
    model = EnsembleModel(base_models, weights=weights)
    proba = model.predict_proba(X)
"""
import numpy as np
import pandas as pd
import pickle
import os


class EnsembleModel:
    """Unified ensemble model with predict_proba interface.

    Compatible with existing production pipeline (batch_scoring.py).

    Modes:
        - blend: Weighted average of base model predictions
        - stack: Meta-learner on top of base model predictions

    Args:
        base_models: dict of {name: fitted_pipeline} or list of fitted pipelines
        weights: dict of {name: weight} for blend mode (optional)
        meta_learner: fitted sklearn classifier for stack mode (optional)
        meta_features: list of feature names for meta-learner input (optional)
    """

    def __init__(self, base_models, weights=None, meta_learner=None, meta_features=None):
        if isinstance(base_models, dict):
            self.base_models = base_models
            self.model_names = list(base_models.keys())
        else:
            self.base_models = {f"model_{i}": m for i, m in enumerate(base_models)}
            self.model_names = list(self.base_models.keys())

        self.weights = weights
        self.meta_learner = meta_learner
        self.meta_features = meta_features or self.model_names
        self.mode = "stack" if meta_learner is not None else "blend"

        # Validate weights
        if self.mode == "blend" and self.weights is None:
            self.weights = {name: 1.0 / len(self.model_names) for name in self.model_names}

    def predict_proba(self, X):
        """Predict class probabilities. Returns array with shape (n_samples, 2).

        Args:
            X: DataFrame or array with features (same format as individual models expect)

        Returns:
            np.ndarray with columns [P(class=0), P(class=1)]
        """
        # Get base model predictions
        base_preds = np.column_stack([
            self.base_models[name].predict_proba(X)[:, 1]
            for name in self.model_names
        ])

        if self.mode == "stack":
            # Build meta-feature matrix
            meta_df = pd.DataFrame(base_preds, columns=self.model_names)

            # Add original features if meta_features includes them
            extra_feats = [f for f in self.meta_features if f not in self.model_names]
            if extra_feats and isinstance(X, pd.DataFrame):
                for feat in extra_feats:
                    if feat in X.columns:
                        meta_df[feat] = X[feat].values

            proba = self.meta_learner.predict_proba(meta_df[self.meta_features])[:, 1]
        else:
            # Weighted blend
            w = np.array([self.weights.get(name, 0) for name in self.model_names])
            proba = np.average(base_preds, axis=1, weights=w)

        return np.column_stack([1 - proba, proba])

    def predict(self, X, threshold=0.5):
        """Predict class labels."""
        proba = self.predict_proba(X)[:, 1]
        return (proba >= threshold).astype(int)

    def get_params(self, deep=True):
        """Get model parameters (sklearn-compatible)."""
        return {
            "mode": self.mode,
            "n_base_models": len(self.base_models),
            "model_names": self.model_names,
            "weights": self.weights,
        }

    def __repr__(self):
        return (f"EnsembleModel(mode='{self.mode}', "
                f"base_models={self.model_names}, "
                f"weights={self.weights})")

    @property
    def classes_(self):
        """Compatibility with sklearn interface."""
        return np.array([0, 1])

    # ── Serialization ───────────────────────────────────────────────────────

    def save(self, path):
        """Save ensemble model to disk."""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)
        print(f"[SAVE] EnsembleModel saved to {path}")

    @classmethod
    def load(cls, path):
        """Load ensemble model from disk."""
        with open(path, "rb") as f:
            model = pickle.load(f)
        print(f"[LOAD] EnsembleModel loaded from {path} (mode={model.mode})")
        return model

    # ── Factory methods ─────────────────────────────────────────────────────

    @classmethod
    def from_blend(cls, base_models, weights):
        """Create blend ensemble."""
        return cls(base_models=base_models, weights=weights)

    @classmethod
    def from_stack(cls, base_models, meta_learner, meta_features=None):
        """Create stacking ensemble."""
        return cls(
            base_models=base_models,
            meta_learner=meta_learner,
            meta_features=meta_features,
        )

    # ── Metadata ────────────────────────────────────────────────────────────

    def metadata(self):
        """Return model metadata for catalog registration."""
        return {
            "model_type": "EnsembleModel",
            "mode": self.mode,
            "n_base_models": len(self.base_models),
            "base_model_names": self.model_names,
            "weights": self.weights if self.mode == "blend" else None,
            "meta_features": self.meta_features if self.mode == "stack" else None,
        }


if __name__ == "__main__":
    print("EnsembleModel — unified ensemble with predict_proba interface")
    print("  Modes: blend (weighted average) | stack (meta-learner)")
    print("  Compatible with batch_scoring.py and register_model_catalog.py")
    print()
    print("  Usage:")
    print("    model = EnsembleModel.from_blend(base_models, weights)")
    print("    model = EnsembleModel.from_stack(base_models, meta_learner)")
    print("    proba = model.predict_proba(X)")
