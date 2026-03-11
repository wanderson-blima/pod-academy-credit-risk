"""
Model Monitoring — OCI Data Science (Post-Deployment)
Standalone monitoring script for the champion ensemble model.

Implements:
  1. PSI monitoring per SAFRA (score distribution stability)
  2. Feature drift: PSI per top-20 feature (train vs OOT)
  3. Backtesting: ensemble vs baseline KS/AUC per SAFRA
  4. Base model monitoring: PSI of predictions + agreement rate between models
  5. OCI Model Catalog registration attempt (handles trial limitations)
  6. Final report with overall_status (STABLE/WARNING/RETRAIN) and recommendations

Usage:
    python monitoring.py

Requires:
    - Champion ensemble model in ARTIFACT_DIR/champion_ensemble.pkl
    - Gold final data (Parquet) in LOCAL_DATA_PATH
    - Selected features in ARTIFACT_DIR/selected_features.json
"""
import os
import sys
import json
import pickle
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp
from sklearn.metrics import roc_auc_score

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

# sklearn compat patch (same as other oci/model scripts)
import sklearn.utils.validation as _val
_original_check = _val.check_array
def _patched_check(*a, **kw):
    kw.pop("force_all_finite", None)
    kw.pop("ensure_all_finite", None)
    return _original_check(*a, **kw)
_val.check_array = _patched_check

# =============================================================================
# CONFIGURATION
# =============================================================================
TARGET = "FPD"
TRAIN_SAFRAS = [202410, 202411, 202412, 202501]
OOT_SAFRAS = [202502, 202503]
NAMESPACE = "grlxi07jz1mo"
ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", "/home/datascience/artifacts")
LOCAL_DATA_PATH = os.environ.get("DATA_PATH", "/home/datascience/data/clientes_final/")


# =============================================================================
# UTILITY FUNCTIONS (inline — reused from ensemble.py)
# =============================================================================

def compute_ks(y_true, y_prob):
    """KS statistic — separation between good and bad distributions."""
    prob_good = y_prob[y_true == 0]
    prob_bad = y_prob[y_true == 1]
    ks_stat, _ = ks_2samp(prob_good, prob_bad)
    return ks_stat


def compute_gini(auc):
    """Gini coefficient derived from AUC."""
    return (2 * auc - 1) * 100


def compute_psi(expected, actual, bins=10):
    """Population Stability Index between two distributions."""
    breakpoints = np.percentile(expected, np.linspace(0, 100, bins + 1))
    breakpoints = np.unique(breakpoints)
    breakpoints[0] = -np.inf
    breakpoints[-1] = np.inf
    expected_counts = np.histogram(expected, bins=breakpoints)[0]
    actual_counts = np.histogram(actual, bins=breakpoints)[0]
    expected_pct = (expected_counts + 1) / (len(expected) + len(breakpoints) - 1)
    actual_pct = (actual_counts + 1) / (len(actual) + len(breakpoints) - 1)
    psi = np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct))
    return round(psi, 6)


def psi_alert(psi_value):
    """Stability classification based on PSI thresholds."""
    if psi_value < 0.10:
        return "GREEN"
    elif psi_value < 0.25:
        return "YELLOW"
    else:
        return "RED"


def log(msg):
    """Log with timestamp."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# =============================================================================
# 1. PSI MONITORING — Score Distribution Stability per SAFRA
# =============================================================================

def run_psi_monitoring(ensemble_model, df, selected_features):
    """Compute PSI of ensemble scores between train and each SAFRA."""
    log("PSI Monitoring — Score Distribution Stability")

    df_train = df[df["SAFRA"].isin(TRAIN_SAFRAS)]
    X_train = df_train[selected_features].fillna(0)
    train_scores = ensemble_model.predict_proba(X_train)[:, 1]

    print(f"\n{'='*60}")
    print("  PSI MONITORING — Ensemble Score per SAFRA")
    print(f"{'='*60}")
    print(f"  Train samples: {len(train_scores):,}")
    print(f"  {'SAFRA':<12} {'N':>10} {'PSI':>10} {'Status':>10}")
    print(f"  {'-'*44}")

    psi_results = []
    for safra in sorted(df["SAFRA"].unique()):
        df_safra = df[df["SAFRA"] == safra]
        X_safra = df_safra[selected_features].fillna(0)
        safra_scores = ensemble_model.predict_proba(X_safra)[:, 1]
        psi_val = compute_psi(train_scores, safra_scores)
        status = psi_alert(psi_val)
        psi_results.append({
            "safra": int(safra),
            "n_records": len(safra_scores),
            "psi": round(psi_val, 6),
            "status": status,
        })
        print(f"  {safra:<12} {len(safra_scores):>10,} {psi_val:>10.4f} {status:>10}")

    return psi_results


# =============================================================================
# 2. FEATURE DRIFT — PSI per Top-20 Feature (Train vs OOT)
# =============================================================================

def run_feature_drift(df, selected_features):
    """Compute PSI per top-20 feature between train and OOT periods."""
    log("Feature Drift — Top 20 Features")

    top_features = selected_features[:20]
    df_train = df[df["SAFRA"].isin(TRAIN_SAFRAS)]
    df_oot = df[df["SAFRA"].isin(OOT_SAFRAS)]

    print(f"\n{'='*60}")
    print("  FEATURE DRIFT — Top 20 Features (Train vs OOT)")
    print(f"{'='*60}")
    print(f"  Train: {len(df_train):,} | OOT: {len(df_oot):,}")
    print(f"  {'Feature':<40} {'PSI':>8} {'Status':>10}")
    print(f"  {'-'*60}")

    drift_results = []
    drift_flags = []

    for feat in top_features:
        train_vals = df_train[feat].dropna().values.astype(float)
        oot_vals = df_oot[feat].dropna().values.astype(float)

        if len(train_vals) == 0 or len(oot_vals) == 0:
            psi_val = None
            status = "N/A"
        else:
            psi_val = compute_psi(train_vals, oot_vals)
            status = psi_alert(psi_val)

        drift_results.append({
            "feature": feat,
            "psi": round(psi_val, 6) if psi_val is not None else None,
            "status": status,
        })

        if psi_val is not None and psi_val > 0.25:
            drift_flags.append(feat)

        psi_display = f"{psi_val:.4f}" if psi_val is not None else "N/A"
        print(f"  {feat:<40} {psi_display:>8} {status:>10}")

    if drift_flags:
        print(f"\n  ALERT: {len(drift_flags)} feature(s) with significant drift (PSI > 0.25):")
        for f in drift_flags:
            print(f"    - {f}")
    else:
        print("\n  No features with significant drift.")

    return drift_results, drift_flags


# =============================================================================
# 3. BACKTESTING — Ensemble vs Baseline KS/AUC per SAFRA
# =============================================================================

def run_backtesting(ensemble_model, baseline_model, baseline_name, df, selected_features):
    """Compare ensemble KS/AUC vs first base model per SAFRA."""
    log(f"Backtesting — Ensemble vs {baseline_name}")

    print(f"\n{'='*60}")
    print(f"  BACKTESTING — Ensemble vs {baseline_name}")
    print(f"{'='*60}")
    print(f"  {'SAFRA':<10} {'KS_Ens':>8} {'AUC_Ens':>8} {'KS_Base':>8} {'AUC_Base':>9} {'Delta_KS':>9}")
    print(f"  {'-'*55}")

    backtest_results = []

    for safra in sorted(df["SAFRA"].unique()):
        df_safra = df[df["SAFRA"] == safra].dropna(subset=[TARGET])
        if len(df_safra) < 100:
            continue

        X_safra = df_safra[selected_features].fillna(0)
        y_safra = df_safra[TARGET].values

        # Ensemble predictions
        pred_ens = ensemble_model.predict_proba(X_safra)[:, 1]
        ks_ens = compute_ks(y_safra, pred_ens)
        auc_ens = roc_auc_score(y_safra, pred_ens)

        # Baseline predictions
        pred_base = baseline_model.predict_proba(X_safra)[:, 1]
        ks_base = compute_ks(y_safra, pred_base)
        auc_base = roc_auc_score(y_safra, pred_base)

        delta_ks = ks_ens - ks_base

        backtest_results.append({
            "safra": int(safra),
            "ks_ensemble": round(ks_ens, 6),
            "auc_ensemble": round(auc_ens, 6),
            "ks_baseline": round(ks_base, 6),
            "auc_baseline": round(auc_base, 6),
            "delta_ks": round(delta_ks, 6),
        })
        print(f"  {safra:<10} {ks_ens:>8.4f} {auc_ens:>8.4f} {ks_base:>8.4f} {auc_base:>9.4f} {delta_ks:>+9.4f}")

    return backtest_results


# =============================================================================
# 4. BASE MODEL MONITORING — PSI of Predictions + Agreement Rate
# =============================================================================

def run_base_model_monitoring(ensemble_model, df, selected_features):
    """Compute PSI of each base model's predictions (train vs OOT) and agreement rate."""
    log("Base Model Monitoring — PSI + Agreement Rate")

    df_train = df[df["SAFRA"].isin(TRAIN_SAFRAS)]
    df_oot = df[df["SAFRA"].isin(OOT_SAFRAS)]
    X_train = df_train[selected_features].fillna(0)
    X_oot = df_oot[selected_features].fillna(0)

    # Discover base models from ensemble or load from artifact dir
    base_models = {}
    if hasattr(ensemble_model, "base_models"):
        base_models = ensemble_model.base_models
    elif hasattr(ensemble_model, "estimators_") or hasattr(ensemble_model, "named_estimators_"):
        # VotingClassifier or similar
        if hasattr(ensemble_model, "named_estimators_"):
            base_models = dict(ensemble_model.named_estimators_)
        elif hasattr(ensemble_model, "estimators_"):
            base_models = {f"model_{i}": m for i, m in enumerate(ensemble_model.estimators_)}
    else:
        # Fallback: load individual .pkl files from models dir
        model_dir = os.path.join(ARTIFACT_DIR, "models")
        if os.path.isdir(model_dir):
            for mf in sorted(os.listdir(model_dir)):
                if mf.endswith(".pkl") and "ensemble" not in mf and "champion" not in mf:
                    name = mf.replace(".pkl", "")
                    with open(os.path.join(model_dir, mf), "rb") as fh:
                        base_models[name] = pickle.load(fh)

    if not base_models:
        log("  No base models found. Skipping base model monitoring.")
        return [], []

    print(f"\n{'='*60}")
    print("  BASE MODEL MONITORING — Prediction PSI (Train vs OOT)")
    print(f"{'='*60}")
    print(f"  {'Model':<30} {'PSI':>8} {'Status':>10}")
    print(f"  {'-'*50}")

    base_psi_results = []
    base_preds_oot = {}

    for name, model in base_models.items():
        try:
            pred_train = model.predict_proba(X_train)[:, 1]
            pred_oot = model.predict_proba(X_oot)[:, 1]
            psi_val = compute_psi(pred_train, pred_oot)
            status = psi_alert(psi_val)
            base_preds_oot[name] = (pred_oot > 0.5).astype(int)
            base_psi_results.append({
                "model": name,
                "psi": round(psi_val, 6),
                "status": status,
            })
            print(f"  {name:<30} {psi_val:>8.4f} {status:>10}")
        except Exception as e:
            print(f"  {name:<30} {'ERROR':>8} — {e}")
            base_psi_results.append({
                "model": name,
                "psi": None,
                "status": "ERROR",
                "error": str(e),
            })

    # Agreement rate between model pairs
    agreement_results = []
    if len(base_preds_oot) > 1:
        model_names = list(base_preds_oot.keys())
        print(f"\n  === Agreement Rate between Base Models (OOT) ===")
        for i in range(len(model_names)):
            for j in range(i + 1, len(model_names)):
                agreement = float(np.mean(
                    base_preds_oot[model_names[i]] == base_preds_oot[model_names[j]]
                ))
                pair = f"{model_names[i]} vs {model_names[j]}"
                agreement_results.append({
                    "pair": pair,
                    "agreement_rate": round(agreement, 4),
                })
                print(f"    {pair}: {agreement:.2%}")

    return base_psi_results, agreement_results


# =============================================================================
# 5. OCI MODEL CATALOG REGISTRATION (handles trial limitations)
# =============================================================================

def try_catalog_registration(selected_features, monitoring_report):
    """Attempt OCI Model Catalog registration; document limitation if it fails."""
    log("OCI Model Catalog — Registration Attempt")

    catalog_metadata = {
        "model_name": "fpd-credit-risk-ensemble-monitored",
        "model_version": "v1.0",
        "framework": "scikit-learn+lightgbm+xgboost+catboost",
        "target": TARGET,
        "n_features": len(selected_features),
        "train_safras": TRAIN_SAFRAS,
        "oot_safras": OOT_SAFRAS,
        "monitoring_status": monitoring_report.get("overall_status", "UNKNOWN"),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    catalog_status = {
        "attempted": True,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        import oci
        from oci.data_science import DataScienceClient
        from oci.data_science.models import CreateModelDetails, Metadata

        config = oci.config.from_file()
        ds_client = DataScienceClient(config)

        compartment_id = os.environ.get(
            "COMPARTMENT_OCID",
            config.get("compartment_id", ""),
        )

        custom_metadata = [
            Metadata(key=k, value=str(v)[:255])
            for k, v in catalog_metadata.items()
            if isinstance(v, (str, int, float))
        ]

        model_details = CreateModelDetails(
            compartment_id=compartment_id,
            project_id=os.environ.get("OCI_PROJECT_ID", "hackathon-pod-academy"),
            display_name="FPD Credit Risk Ensemble — Monitored",
            description=(
                "Champion ensemble model with post-deployment monitoring. "
                f"Status: {monitoring_report.get('overall_status', 'N/A')}."
            ),
            custom_metadata_list=custom_metadata,
        )

        response = ds_client.create_model(model_details)
        catalog_status["registered"] = True
        catalog_status["model_ocid"] = response.data.id
        print(f"  Model registered in OCI Model Catalog!")
        print(f"  Model OCID: {response.data.id}")

    except ImportError:
        catalog_status["registered"] = False
        catalog_status["reason"] = "OCI SDK (oci) not installed in current environment."
        print(f"  [SKIP] OCI SDK not available. Trial limitation documented.")

    except Exception as e:
        catalog_status["registered"] = False
        catalog_status["reason"] = str(e)
        print(f"  [SKIP] Catalog registration failed: {e}")
        print(f"  Trial limitation documented.")

    # Save catalog status alongside monitoring artifacts
    catalog_status["metadata"] = catalog_metadata
    catalog_path = os.path.join(ARTIFACT_DIR, "monitoring", "catalog_registration.json")
    with open(catalog_path, "w") as fh:
        json.dump(catalog_status, fh, indent=2, default=str)
    print(f"  Catalog status saved: {catalog_path}")

    return catalog_status


# =============================================================================
# 6. FINAL REPORT — overall_status + recommendations
# =============================================================================

def build_report(psi_results, drift_results, drift_flags, backtest_results,
                 base_psi_results, agreement_results, catalog_status):
    """Generate monitoring report JSON with status and recommendations."""

    # Determine overall status
    psi_statuses = [r["status"] for r in psi_results]
    drift_statuses = [r["status"] for r in drift_results if r["status"] != "N/A"]
    base_statuses = [r["status"] for r in base_psi_results if r.get("status") not in ("N/A", "ERROR")]
    all_statuses = psi_statuses + drift_statuses + base_statuses

    if "RED" in all_statuses:
        overall_status = "RETRAIN"
    elif "YELLOW" in all_statuses:
        overall_status = "WARNING"
    else:
        overall_status = "STABLE"

    # Build recommendations
    recommendations = []

    if overall_status == "RETRAIN":
        recommendations.append(
            "RETRAIN: Significant drift detected (PSI >= 0.25). "
            "Retrain the model with recent data."
        )
    if drift_flags:
        recommendations.append(
            f"FEATURE_DRIFT: {len(drift_flags)} feature(s) with drift > 0.25. "
            f"Investigate root cause: {', '.join(drift_flags[:5])}"
            + ("..." if len(drift_flags) > 5 else "")
        )
    if backtest_results:
        avg_delta = np.mean([r["delta_ks"] for r in backtest_results])
        if avg_delta < -0.05:
            recommendations.append(
                f"DEGRADATION: Average ensemble KS dropped {abs(avg_delta):.4f} "
                f"vs baseline. Evaluate retraining."
            )
    # Check OOT-specific PSI
    oot_psi = [r for r in psi_results if r["safra"] in OOT_SAFRAS]
    for r in oot_psi:
        if r["status"] == "YELLOW":
            recommendations.append(
                f"WATCH: SAFRA {r['safra']} shows moderate score drift (PSI={r['psi']:.4f}). "
                f"Monitor next SAFRA closely."
            )

    if not recommendations:
        recommendations.append("Model is stable. No action required.")

    report = {
        "report_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": overall_status,
        "config": {
            "target": TARGET,
            "train_safras": TRAIN_SAFRAS,
            "oot_safras": OOT_SAFRAS,
            "artifact_dir": ARTIFACT_DIR,
            "data_path": LOCAL_DATA_PATH,
        },
        "score_psi": psi_results,
        "feature_drift": drift_results,
        "features_with_drift": drift_flags,
        "backtesting": backtest_results,
        "base_model_psi": base_psi_results,
        "base_model_agreement": agreement_results,
        "catalog_registration": catalog_status,
        "overall_status": overall_status,
        "recommendations": recommendations,
    }

    return report


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("  MODEL MONITORING — OCI Data Science (Post-Deployment)")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # ── Load artifacts ────────────────────────────────────────────────────
    log("Loading artifacts...")

    # Selected features
    sf_path = os.path.join(ARTIFACT_DIR, "selected_features.json")
    with open(sf_path, "r") as fh:
        sf_data = json.load(fh)
    # Handle both formats: list or dict with "selected_features" key
    if isinstance(sf_data, dict):
        selected_features = sf_data.get("selected_features", sf_data.get("features", []))
    else:
        selected_features = sf_data
    log(f"  Selected features: {len(selected_features)} loaded from {sf_path}")

    # Champion ensemble model
    champion_path = os.path.join(ARTIFACT_DIR, "models", "champion_ensemble.pkl")
    # Import ensemble class for pickle deserialization
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    if _script_dir not in sys.path:
        sys.path.insert(0, _script_dir)
    try:
        import ensemble as _ens_mod
        # Register class in __main__ so pickle can find it
        import __main__
        __main__._EnsembleModel = _ens_mod._EnsembleModel
    except ImportError:
        pass
    with open(champion_path, "rb") as fh:
        ensemble_model = pickle.load(fh)
    log(f"  Champion ensemble loaded from {champion_path}")

    # Baseline model (first non-ensemble .pkl in models/ dir)
    baseline_model = None
    baseline_name = "N/A"
    model_dir = os.path.join(ARTIFACT_DIR, "models")
    if os.path.isdir(model_dir):
        baseline_files = sorted([
            f for f in os.listdir(model_dir)
            if f.endswith(".pkl") and "ensemble" not in f and "champion" not in f
        ])
        if baseline_files:
            baseline_path = os.path.join(model_dir, baseline_files[0])
            with open(baseline_path, "rb") as fh:
                baseline_model = pickle.load(fh)
            baseline_name = baseline_files[0].replace(".pkl", "")
            log(f"  Baseline model loaded: {baseline_name}")

    # Gold final data
    log(f"  Loading Gold data from {LOCAL_DATA_PATH}")
    cols_needed = ["SAFRA", TARGET] + selected_features
    if os.path.isdir(LOCAL_DATA_PATH):
        df = pd.read_parquet(LOCAL_DATA_PATH, columns=cols_needed)
    else:
        df = pd.read_parquet(LOCAL_DATA_PATH, columns=cols_needed)
    # Drop NaN target rows
    nan_target = df[TARGET].isna().sum()
    if nan_target > 0:
        log(f"  Dropping {nan_target:,} rows with NaN target")
        df = df.dropna(subset=[TARGET])
    log(f"  Gold data: {len(df):,} rows x {len(df.columns)} cols")

    # ── Create monitoring output dir ──────────────────────────────────────
    monitoring_dir = os.path.join(ARTIFACT_DIR, "monitoring")
    os.makedirs(monitoring_dir, exist_ok=True)

    # ── 1. PSI Monitoring ─────────────────────────────────────────────────
    psi_results = run_psi_monitoring(ensemble_model, df, selected_features)

    # ── 2. Feature Drift ──────────────────────────────────────────────────
    drift_results, drift_flags = run_feature_drift(df, selected_features)

    # ── 3. Backtesting ────────────────────────────────────────────────────
    backtest_results = []
    if baseline_model is not None:
        backtest_results = run_backtesting(
            ensemble_model, baseline_model, baseline_name, df, selected_features,
        )
    else:
        log("  [SKIP] No baseline model found. Skipping backtesting.")

    # ── 4. Base Model Monitoring ──────────────────────────────────────────
    base_psi_results, agreement_results = run_base_model_monitoring(
        ensemble_model, df, selected_features,
    )

    # ── 5. OCI Model Catalog Registration ─────────────────────────────────
    # Build partial report for catalog metadata
    partial_report = {
        "overall_status": "RETRAIN" if any(r["status"] == "RED" for r in psi_results) else
                          "WARNING" if any(r["status"] == "YELLOW" for r in psi_results) else
                          "STABLE"
    }
    catalog_status = try_catalog_registration(selected_features, partial_report)

    # ── 6. Final Report ───────────────────────────────────────────────────
    report = build_report(
        psi_results, drift_results, drift_flags, backtest_results,
        base_psi_results, agreement_results, catalog_status,
    )

    # Save report
    report_path = os.path.join(monitoring_dir, "monitoring_report.json")
    with open(report_path, "w") as fh:
        json.dump(report, fh, indent=2, default=str)

    # ── Summary ───────────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print("  MONITORING REPORT SUMMARY")
    print(f"{'='*70}")
    print(f"  Date:              {report['report_date']}")
    print(f"  Overall Status:    {report['overall_status']}")
    print(f"  Score PSI SAFRAs:  {len(psi_results)}")
    print(f"  Features w/ drift: {len(drift_flags)}")
    print(f"  Backtesting SAFRAs: {len(backtest_results)}")
    print(f"  Base models:       {len(base_psi_results)}")
    print(f"  Catalog registered: {catalog_status.get('registered', False)}")
    print(f"\n  Recommendations:")
    for rec in report["recommendations"]:
        print(f"    - {rec}")
    print(f"\n  Report saved: {report_path}")
    print(f"{'='*70}")

    log(f"monitoring | Status: {report['overall_status']} | "
        f"Drift features: {len(drift_flags)} | Report: {report_path}")

    return report


if __name__ == "__main__":
    main()
