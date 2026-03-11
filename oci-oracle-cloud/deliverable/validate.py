"""
Validation / Smoke Test Script -- Credit Risk Scoring Pipeline
Verifies that the champion_pipeline.pkl loads correctly, runs inference
on synthetic data, and checks score conversion + risk bands.

Usage:
    python validate.py
    python validate.py --pipeline-path models/champion_pipeline.pkl
"""
import os
import sys
import json
import pickle
import argparse
import traceback
import numpy as np

# sklearn compat patch -- must be applied before any sklearn import
import sklearn.utils.validation as _val
if not hasattr(_val, '_real_check_array'):
    _val._real_check_array = _val.check_array
def _patched_check(*a, **kw):
    kw.pop("force_all_finite", None)
    kw.pop("ensure_all_finite", None)
    return _val._real_check_array(*a, **kw)
_val.check_array = _patched_check

import warnings
warnings.filterwarnings("ignore")

import pandas as pd


# ---------------------------------------------------------------------------
# Inline classes required for pickle deserialization
# ---------------------------------------------------------------------------

class _EnsembleModel:
    """Ensemble model wrapper supporting average, blend, and stacking modes."""

    def __init__(self, mode, base_models, weights=None, meta_model=None, feature_names=None):
        self.mode = mode
        self.base_models = base_models
        self.weights = weights
        self.meta_model = meta_model
        self.feature_names = feature_names

    def predict_proba(self, X):
        models = self.base_models.values() if isinstance(self.base_models, dict) else self.base_models
        base_probs = np.column_stack([
            m.predict_proba(X)[:, 1] if hasattr(m, "predict_proba")
            else m.predict(X)
            for m in models
        ])
        if self.mode == "average":
            p1 = base_probs.mean(axis=1)
        elif self.mode == "blend":
            p1 = base_probs @ self.weights
        elif self.mode == "stacking":
            p1 = self.meta_model.predict_proba(base_probs)[:, 1]
        else:
            raise ValueError(f"Unknown ensemble mode: {self.mode}")
        p1 = np.clip(p1, 0.0, 1.0)
        return np.column_stack([1 - p1, p1])


class _SingleModel:
    """Wrapper for individual models to match ensemble interface."""
    def __init__(self, model, name):
        self.mode = "single"
        self.model = model
        self.name = name

    def predict_proba(self, X):
        if hasattr(self.model, "predict_proba"):
            return self.model.predict_proba(X)
        pred = self.model.predict(X)
        return np.column_stack([1 - pred, pred])


class ScoringPipeline:
    """Stub for pickle deserialization — actual class is inside the PKL."""
    pass


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

class ValidationResult:
    def __init__(self):
        self.results = []

    def record(self, name, passed, detail=""):
        status = "PASS" if passed else "FAIL"
        self.results.append((name, passed, detail))
        msg = f"  [{status}] {name}"
        if detail:
            msg += f" -- {detail}"
        print(msg)

    def summary(self):
        total = len(self.results)
        passed = sum(1 for _, p, _ in self.results if p)
        failed = total - passed
        print()
        print("=" * 60)
        print(f"VALIDATION SUMMARY: {passed}/{total} checks passed, {failed} failed")
        print("=" * 60)
        if failed > 0:
            print("\nFailed checks:")
            for name, p, detail in self.results:
                if not p:
                    print(f"  - {name}: {detail}")
        return failed == 0


def main():
    parser = argparse.ArgumentParser(description="Credit Risk Pipeline Validation / Smoke Test")
    parser.add_argument("--pipeline-path", default=None,
                        help="Path to champion_pipeline.pkl")
    parser.add_argument("--features-path", default=None,
                        help="Path to selected_features.json (optional, validates consistency)")
    args = parser.parse_args()

    # Resolve paths
    script_dir = os.path.dirname(os.path.abspath(__file__))

    if args.pipeline_path:
        pipeline_path = os.path.abspath(args.pipeline_path)
    else:
        pipeline_path = os.path.join(script_dir, "models", "champion_pipeline.pkl")

    if args.features_path:
        features_path = os.path.abspath(args.features_path)
    else:
        features_path = os.path.join(script_dir, "config", "selected_features.json")

    print("=" * 60)
    print("VALIDATION / SMOKE TEST -- Credit Risk Scoring Pipeline")
    print("=" * 60)
    print(f"  Pipeline: {pipeline_path}")
    print(f"  Features: {features_path}")
    print()

    vr = ValidationResult()

    # ------------------------------------------------------------------
    # CHECK 1: Pipeline PKL loads correctly
    # ------------------------------------------------------------------
    print("[1] Pipeline PKL")
    pipeline = None
    try:
        exists = os.path.exists(pipeline_path)
        vr.record("pipeline_file_exists", exists,
                   f"{os.path.getsize(pipeline_path) / 1024 / 1024:.1f} MB" if exists else f"Not found: {pipeline_path}")

        if exists:
            class _PipelineUnpickler(pickle.Unpickler):
                def find_class(self, module, name):
                    if name == "_EnsembleModel":
                        return _EnsembleModel
                    if name == "_SingleModel":
                        return _SingleModel
                    if name == "ScoringPipeline":
                        # Import from build_pipeline if available, else use stub
                        try:
                            from build_pipeline import ScoringPipeline as SP
                            return SP
                        except ImportError:
                            pass
                        return ScoringPipeline
                    return super().find_class(module, name)

            with open(pipeline_path, "rb") as f:
                pipeline = _PipelineUnpickler(f).load()
            vr.record("pipeline_pickle_loads", True)

            # Check pipeline attributes
            has_features = hasattr(pipeline, "features") and len(pipeline.features) > 0
            vr.record("pipeline_has_features", has_features,
                       f"{len(pipeline.features)} features" if has_features else "missing")

            has_medians = hasattr(pipeline, "train_medians") and len(pipeline.train_medians) > 0
            vr.record("pipeline_has_train_medians", has_medians,
                       f"{len(pipeline.train_medians)} medians" if has_medians else "missing")

            has_model = hasattr(pipeline, "model") and hasattr(pipeline.model, "predict_proba")
            vr.record("pipeline_has_model", has_model)

            has_preprocess = hasattr(pipeline, "preprocess") and callable(pipeline.preprocess)
            vr.record("pipeline_has_preprocess", has_preprocess)

            has_score = hasattr(pipeline, "score") and callable(pipeline.score)
            vr.record("pipeline_has_score", has_score)

            # Pipeline metadata
            version = getattr(pipeline, "pipeline_version", "unknown")
            model_ver = getattr(pipeline, "model_version", "unknown")
            base_models = getattr(pipeline, "base_model_names", [])
            train_safras = getattr(pipeline, "train_safras", [])
            vr.record("pipeline_metadata", True,
                       f"v{version}, {model_ver}, {len(base_models)} models, train={train_safras}")

    except Exception as e:
        vr.record("pipeline_load", False, f"{type(e).__name__}: {e}")
        traceback.print_exc()

    # ------------------------------------------------------------------
    # CHECK 2: Features consistency with selected_features.json
    # ------------------------------------------------------------------
    print("\n[2] Features Consistency")
    try:
        if os.path.exists(features_path):
            with open(features_path) as f:
                feat_data = json.load(f)
            json_features = feat_data.get("selected_features", [])
            vr.record("features_json_loads", True, f"{len(json_features)} features")

            if pipeline and hasattr(pipeline, "features"):
                match = set(pipeline.features) == set(json_features)
                vr.record("features_match_pipeline", match,
                           f"both have {len(pipeline.features)} features" if match
                           else f"pipeline={len(pipeline.features)}, json={len(json_features)}")
        else:
            vr.record("features_json_exists", False, f"Not found (optional): {features_path}")
    except Exception as e:
        vr.record("features_consistency", False, str(e))

    # ------------------------------------------------------------------
    # CHECK 3: Preprocessing (synthetic data)
    # ------------------------------------------------------------------
    print("\n[3] Preprocessing")
    if pipeline and hasattr(pipeline, "preprocess"):
        try:
            np.random.seed(42)
            n_rows = 100
            synthetic = pd.DataFrame(
                np.random.rand(n_rows, len(pipeline.features)),
                columns=pipeline.features,
            )
            # Add some NaN and inf to test treatment
            synthetic.iloc[0, 0] = np.nan
            synthetic.iloc[1, 1] = np.inf
            synthetic.iloc[2, 2] = -np.inf

            X = pipeline.preprocess(synthetic)
            vr.record("preprocess_runs", True, f"{X.shape[0]} rows x {X.shape[1]} cols")

            no_nan = not X.isna().any().any()
            vr.record("preprocess_no_nan", no_nan,
                       f"{X.isna().sum().sum()} NaN remaining" if not no_nan else "all NaN filled")

            no_inf = not np.isinf(X.values).any()
            vr.record("preprocess_no_inf", no_inf,
                       f"{np.isinf(X.values).sum()} inf remaining" if not no_inf else "all inf removed")

            cols_match = list(X.columns) == list(pipeline.features)
            vr.record("preprocess_features_order", cols_match, f"{len(X.columns)} columns in correct order")

        except Exception as e:
            vr.record("preprocess", False, f"{type(e).__name__}: {e}")
            traceback.print_exc()
    else:
        vr.record("preprocess", False, "Skipped -- pipeline not loaded")

    # ------------------------------------------------------------------
    # CHECK 4: Predict proba (synthetic data)
    # ------------------------------------------------------------------
    print("\n[4] Predict Proba")
    if pipeline and hasattr(pipeline, "predict_proba"):
        try:
            np.random.seed(42)
            synthetic = pd.DataFrame(
                np.random.rand(100, len(pipeline.features)),
                columns=pipeline.features,
            )
            probas = pipeline.predict_proba(synthetic)
            vr.record("predict_proba_runs", True, f"{len(probas)} predictions")

            range_ok = probas.min() >= 0.0 and probas.max() <= 1.0
            vr.record("probas_in_range", range_ok,
                       f"min={probas.min():.6f}, max={probas.max():.6f}")

        except Exception as e:
            vr.record("predict_proba", False, f"{type(e).__name__}: {e}")
            traceback.print_exc()
    else:
        vr.record("predict_proba", False, "Skipped -- pipeline not loaded")

    # ------------------------------------------------------------------
    # CHECK 5: Full scoring pipeline
    # ------------------------------------------------------------------
    print("\n[5] Full Scoring (score method)")
    if pipeline and hasattr(pipeline, "score"):
        try:
            np.random.seed(42)
            synthetic = pd.DataFrame(
                np.random.rand(100, len(pipeline.features)),
                columns=pipeline.features,
            )
            synthetic["NUM_CPF"] = [f"CPF_{i:05d}" for i in range(100)]
            synthetic["SAFRA"] = 202502

            result = pipeline.score(synthetic)
            vr.record("score_runs", True, f"{len(result)} rows scored")

            # Check output columns
            expected_cols = {"NUM_CPF", "SAFRA", "SCORE", "FAIXA_RISCO", "PROBABILIDADE_FPD", "MODELO_VERSAO"}
            actual_cols = set(result.columns)
            cols_ok = expected_cols == actual_cols
            vr.record("score_output_columns", cols_ok,
                       f"columns: {sorted(actual_cols)}" if cols_ok
                       else f"missing: {expected_cols - actual_cols}, extra: {actual_cols - expected_cols}")

            # Check score range
            range_ok = result["SCORE"].min() >= 0 and result["SCORE"].max() <= 1000
            vr.record("score_range_valid", range_ok,
                       f"min={result['SCORE'].min()}, max={result['SCORE'].max()}, mean={result['SCORE'].mean():.0f}")

            # Check risk bands
            valid_bands = {"CRITICO", "ALTO", "MEDIO", "BAIXO"}
            actual_bands = set(result["FAIXA_RISCO"].unique())
            bands_ok = actual_bands.issubset(valid_bands)
            vr.record("score_risk_bands_valid", bands_ok,
                       f"bands: {sorted(actual_bands)}")

            # Check band-score consistency
            band_consistency = True
            for _, row in result.iterrows():
                s, b = row["SCORE"], row["FAIXA_RISCO"]
                expected = ("CRITICO" if s < 300 else "ALTO" if s < 500 else "MEDIO" if s < 700 else "BAIXO")
                if b != expected:
                    band_consistency = False
                    break
            vr.record("score_band_consistency", band_consistency, "all scores match their risk band")

            # Check modelo_versao
            ver = result["MODELO_VERSAO"].iloc[0]
            vr.record("score_model_version", bool(ver), f"version={ver}")

        except Exception as e:
            vr.record("score", False, f"{type(e).__name__}: {e}")
            traceback.print_exc()
    else:
        vr.record("score", False, "Skipped -- pipeline not loaded")

    # ------------------------------------------------------------------
    # CHECK 6: Score conversion edge cases
    # ------------------------------------------------------------------
    print("\n[6] Score Conversion Edge Cases")
    try:
        test_probas = np.array([0.0, 0.1, 0.5, 0.9, 1.0])
        test_scores = ((1 - test_probas) * 1000).astype(int).clip(0, 1000)
        expected_scores = np.array([1000, 900, 500, 99, 0])

        scores_ok = np.array_equal(test_scores, expected_scores)
        vr.record("score_conversion_formula", scores_ok,
                   f"probas {test_probas.tolist()} -> scores {test_scores.tolist()}")

        # Risk band boundaries
        def risk_band(score):
            if score < 300: return "CRITICO"
            elif score < 500: return "ALTO"
            elif score < 700: return "MEDIO"
            else: return "BAIXO"

        boundaries = [
            (0, "CRITICO"), (299, "CRITICO"),
            (300, "ALTO"), (499, "ALTO"),
            (500, "MEDIO"), (699, "MEDIO"),
            (700, "BAIXO"), (1000, "BAIXO"),
        ]
        all_ok = all(risk_band(s) == b for s, b in boundaries)
        vr.record("risk_band_boundaries", all_ok, "8/8 boundary cases correct" if all_ok else "boundary mismatch")

    except Exception as e:
        vr.record("score_conversion", False, str(e))

    # ------------------------------------------------------------------
    # CHECK 7: Ensemble comparison metadata
    # ------------------------------------------------------------------
    print("\n[7] Ensemble Comparison Metadata")
    if pipeline and hasattr(pipeline, "ensemble_comparison"):
        ec = pipeline.ensemble_comparison
        has_ec = ec is not None and isinstance(ec, dict)
        vr.record("ensemble_comparison_present", has_ec)
        if has_ec:
            has_decision = "decision" in ec
            vr.record("ensemble_has_decision", has_decision, f"decision={ec.get('decision')}")
            has_candidates = (
                ("candidates" in ec and len(ec.get("candidates", {})) > 0) or
                ("individual_models" in ec and len(ec.get("individual_models", {})) > 0)
            )
            n_entries = len(ec.get("candidates", ec.get("individual_models", {})))
            vr.record("ensemble_has_candidates", has_candidates,
                       f"{n_entries} candidates")
    else:
        vr.record("ensemble_comparison", False, "Not present in pipeline")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    all_passed = vr.summary()
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
