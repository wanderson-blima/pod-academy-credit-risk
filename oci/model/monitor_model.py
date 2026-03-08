"""
Model Monitoring — Phase 6.2
Monitors credit risk model stability by computing PSI between training
and current scoring distributions, and checking feature drift.

Usage:
    python monitor_model.py [--scores-path PATH] [--output-dir PATH]

    Requires: numpy, pandas, pyarrow
"""
import os
import json
import argparse
import numpy as np
import pandas as pd
from datetime import datetime

# ── Configuration ─────────────────────────────────────────────────────────

NAMESPACE = os.environ.get("OCI_NAMESPACE", "grlxi07jz1mo")
GOLD_BUCKET = "pod-academy-gold"

# Default paths
DEFAULT_SCORES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "artifacts", "scoring"
)
DEFAULT_OUTPUT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "artifacts", "monitoring"
)
METRICS_FILE = os.path.join(
    os.path.dirname(__file__), "..", "artifacts", "metrics",
    "training_results_20260217_214614.json",
)

# Thresholds
PSI_OK = 0.10
PSI_WARNING = 0.25

# Top features to monitor for drift
TOP_FEATURES = [
    "TARGET_SCORE_02", "TARGET_SCORE_01", "REC_SCORE_RISCO",
    "REC_TAXA_STATUS_A", "REC_QTD_LINHAS", "REC_DIAS_ENTRE_RECARGAS",
    "REC_QTD_INST_DIST_REG", "REC_DIAS_DESDE_ULTIMA_RECARGA",
    "REC_TAXA_CARTAO_ONLINE", "REC_QTD_STATUS_ZB2",
    "REC_QTD_CARTAO_ONLINE", "REC_COEF_VARIACAO_REAL",
    "FAT_DIAS_MEDIO_CRIACAO_VENCIMENTO", "REC_VLR_CREDITO_STDDEV",
    "REC_TAXA_PLAT_PREPG", "REC_VLR_REAL_STDDEV",
    "PAG_QTD_PAGAMENTOS_TOTAL", "FAT_QTD_FATURAS_PRIMEIRA",
    "REC_QTD_STATUS_ZB1", "FAT_TAXA_PRIMEIRA_FAT",
]

TRAIN_SAFRAS = [202410, 202411, 202412, 202501]
OOT_SAFRAS = [202502, 202503]


def compute_psi(expected, actual, bins=10):
    """Population Stability Index between two score distributions.
    Reused from train_credit_risk.py with identical logic.
    """
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


def classify_psi(psi_value):
    """Classify PSI into action categories."""
    if psi_value < PSI_OK:
        return "OK"
    elif psi_value < PSI_WARNING:
        return "WARNING"
    else:
        return "RETRAIN"


def load_scores(scores_path):
    """Load batch scoring results."""
    if os.path.isdir(scores_path):
        files = [f for f in os.listdir(scores_path) if f.endswith(".parquet")]
        if not files:
            raise FileNotFoundError(f"No parquet files in {scores_path}")
        df = pd.concat(
            [pd.read_parquet(os.path.join(scores_path, f)) for f in files],
            ignore_index=True,
        )
    else:
        df = pd.read_parquet(scores_path)
    print(f"[MONITOR] Loaded scores: {len(df):,} records, {df.shape[1]} columns")
    return df


def load_training_metrics():
    """Load reference training metrics."""
    with open(METRICS_FILE, "r") as f:
        return json.load(f)


def monitor_score_psi(df):
    """Compute PSI between training and scoring score distributions."""
    results = {}

    # Split by SAFRA into train-period and scoring-period
    if "SAFRA" in df.columns:
        train_mask = df["SAFRA"].isin(TRAIN_SAFRAS)
        oot_mask = df["SAFRA"].isin(OOT_SAFRAS)
    else:
        # If no SAFRA, use first 70% as reference, rest as scoring
        split = int(len(df) * 0.7)
        train_mask = pd.Series([True] * split + [False] * (len(df) - split))
        oot_mask = ~train_mask

    # Check for score columns
    score_cols = [c for c in df.columns if "score" in c.lower() or "prob" in c.lower()]

    for col in score_cols:
        train_scores = df.loc[train_mask, col].dropna().values
        oot_scores = df.loc[oot_mask, col].dropna().values

        if len(train_scores) < 100 or len(oot_scores) < 100:
            continue

        psi = compute_psi(train_scores, oot_scores)
        status = classify_psi(psi)
        results[col] = {
            "psi": psi,
            "status": status,
            "train_n": len(train_scores),
            "scoring_n": len(oot_scores),
            "train_mean": round(float(np.mean(train_scores)), 6),
            "scoring_mean": round(float(np.mean(oot_scores)), 6),
        }
        print(f"  Score PSI ({col}): {psi:.6f} [{status}]")

    return results


def monitor_feature_drift(df):
    """Check PSI drift for top 20 features."""
    results = {}

    if "SAFRA" not in df.columns:
        print("[WARN] No SAFRA column — skipping feature drift")
        return results

    train_df = df[df["SAFRA"].isin(TRAIN_SAFRAS)]
    oot_df = df[df["SAFRA"].isin(OOT_SAFRAS)]

    available_features = [f for f in TOP_FEATURES if f in df.columns]
    drifted_count = 0

    for feat in available_features:
        train_vals = train_df[feat].dropna().values
        oot_vals = oot_df[feat].dropna().values

        if len(train_vals) < 100 or len(oot_vals) < 100:
            results[feat] = {"psi": None, "status": "INSUFFICIENT_DATA"}
            continue

        psi = compute_psi(train_vals, oot_vals)
        status = classify_psi(psi)
        if status != "OK":
            drifted_count += 1

        results[feat] = {
            "psi": psi,
            "status": status,
            "train_mean": round(float(np.mean(train_vals)), 4),
            "oot_mean": round(float(np.mean(oot_vals)), 4),
            "train_std": round(float(np.std(train_vals)), 4),
            "oot_std": round(float(np.std(oot_vals)), 4),
        }

    print(f"\n[DRIFT] {len(available_features)} features checked, {drifted_count} drifted")
    return results


def monitor_ensemble_base_models(df, ensemble_model_path=None):
    """Monitor PSI for individual base models within the ensemble.

    Early warning: if any base model shows PSI > 0.15, flag it.
    Also checks model agreement rate between ensemble members.
    """
    import pickle

    if ensemble_model_path is None:
        ensemble_model_path = os.path.join(
            os.path.dirname(__file__), "..", "artifacts", "ensemble", "ensemble_model.pkl"
        )

    if not os.path.exists(ensemble_model_path):
        print("[ENSEMBLE MONITOR] No ensemble model found — skipping base model monitoring")
        return {}

    with open(ensemble_model_path, "rb") as f:
        ensemble = pickle.load(f)

    if not hasattr(ensemble, "base_models"):
        print("[ENSEMBLE MONITOR] Model is not an EnsembleModel — skipping")
        return {}

    results = {"base_model_psi": {}, "agreement_rate": None}

    if "SAFRA" not in df.columns:
        return results

    train_df = df[df["SAFRA"].isin(TRAIN_SAFRAS)]
    oot_df = df[df["SAFRA"].isin(OOT_SAFRAS)]

    if len(train_df) < 100 or len(oot_df) < 100:
        return results

    # Check available features — use features from first base model
    first_model = list(ensemble.base_models.values())[0]
    try:
        prep = first_model.named_steps["prep"]
        num_feats = list(prep.transformers[0][2])
        cat_feats = list(prep.transformers[1][2]) if len(prep.transformers) > 1 else []
        features = num_feats + cat_feats
    except Exception:
        features = [f for f in TOP_FEATURES if f in df.columns]

    # Per base model PSI
    predictions_train = {}
    predictions_oot = {}

    for name, model in ensemble.base_models.items():
        try:
            train_probs = model.predict_proba(train_df[features])[:, 1]
            oot_probs = model.predict_proba(oot_df[features])[:, 1]
            psi = compute_psi(train_probs, oot_probs)
            status = classify_psi(psi)

            # Early warning at lower threshold (0.15)
            if psi > 0.15:
                print(f"  [EARLY WARNING] Base model '{name}' PSI={psi:.6f} > 0.15")

            results["base_model_psi"][name] = {"psi": psi, "status": status}
            predictions_train[name] = train_probs
            predictions_oot[name] = oot_probs
        except Exception as e:
            results["base_model_psi"][name] = {"psi": None, "status": "ERROR", "error": str(e)}

    # Model agreement rate (OOT) — % of cases where all models agree on decile
    if len(predictions_oot) >= 2:
        import pandas as pd
        decile_dfs = {}
        for name, probs in predictions_oot.items():
            decile_dfs[name] = pd.qcut(probs, q=10, labels=False, duplicates="drop")

        decile_matrix = pd.DataFrame(decile_dfs)
        agreement = (decile_matrix.nunique(axis=1) == 1).mean()
        results["agreement_rate"] = round(float(agreement), 4)
        print(f"  Model agreement rate (exact decile match): {agreement:.2%}")

    # Weight stability — check if weights are still appropriate
    if hasattr(ensemble, "weights") and ensemble.weights:
        results["current_weights"] = ensemble.weights

    return results


def generate_report(score_psi, feature_drift, training_metrics, output_dir,
                    ensemble_monitoring=None):
    """Generate monitoring report JSON."""
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d")

    # Overall status
    all_score_statuses = [v["status"] for v in score_psi.values()]
    all_drift_statuses = [v["status"] for v in feature_drift.values() if v["status"] != "INSUFFICIENT_DATA"]

    if "RETRAIN" in all_score_statuses or "RETRAIN" in all_drift_statuses:
        overall = "RETRAIN_REQUIRED"
    elif "WARNING" in all_score_statuses or "WARNING" in all_drift_statuses:
        overall = "WARNING"
    else:
        overall = "STABLE"

    # Check ensemble base models for early warning
    if ensemble_monitoring:
        base_psi = ensemble_monitoring.get("base_model_psi", {})
        for name, info in base_psi.items():
            if info.get("psi") and info["psi"] > 0.15:
                if overall == "STABLE":
                    overall = "WARNING"

    report = {
        "report_date": datetime.now().isoformat(),
        "run_id": training_metrics.get("run_id", "unknown"),
        "overall_status": overall,
        "thresholds": {
            "psi_ok": PSI_OK,
            "psi_warning": PSI_WARNING,
        },
        "score_psi": score_psi,
        "feature_drift": feature_drift,
        "ensemble_monitoring": ensemble_monitoring or {},
        "reference_metrics": {
            "lgbm": training_metrics.get("lgbm_metrics", {}),
            "lr": training_metrics.get("lr_metrics", {}),
            "lgbm_psi": training_metrics.get("lgbm_psi"),
            "lr_psi": training_metrics.get("lr_psi"),
        },
        "recommendations": [],
    }

    # Add recommendations
    if overall == "RETRAIN_REQUIRED":
        report["recommendations"].append("One or more scores/features have PSI > 0.25. Model retraining is required.")
    elif overall == "WARNING":
        report["recommendations"].append("Some features show moderate drift (PSI 0.10-0.25). Monitor closely and consider retraining.")
    else:
        report["recommendations"].append("Model is stable. Continue monitoring on next scoring batch.")

    drifted = [f for f, v in feature_drift.items() if v.get("status") in ("WARNING", "RETRAIN")]
    if drifted:
        report["recommendations"].append(f"Drifted features: {', '.join(drifted)}")

    output_path = os.path.join(output_dir, f"monitoring_report_{timestamp}.json")
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"Model Monitoring Report: {overall}")
    print(f"Output: {output_path}")
    print(f"{'=' * 60}")

    return output_path


def publish_to_oci_dashboard(report, score_psi, feature_drift):
    """Publish monitoring results to OCI Monitoring custom metrics (dashboard).
    Requires: COMPARTMENT_OCID env var and oci SDK installed.
    Silently skips if not configured.
    """
    compartment_id = os.environ.get("COMPARTMENT_OCID")
    if not compartment_id:
        print("[METRICS] COMPARTMENT_OCID not set — skipping OCI dashboard publish")
        return

    try:
        from oci_metrics import publish_monitoring_report
        safra = str(max(OOT_SAFRAS))
        publish_monitoring_report(compartment_id, "lgbm_oci_v1", safra, report)
        print(f"[METRICS] Dashboard metrics published for SAFRA {safra}")
    except ImportError:
        print("[METRICS] oci SDK not installed — skipping dashboard publish (pip install oci)")
    except Exception as e:
        print(f"[METRICS] Failed to publish to dashboard: {e}")


def main():
    parser = argparse.ArgumentParser(description="Credit Risk Model Monitoring")
    parser.add_argument("--scores-path", default=DEFAULT_SCORES_PATH, help="Path to scoring parquet files")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Output directory for reports")
    parser.add_argument("--publish-metrics", action="store_true", help="Publish metrics to OCI Monitoring dashboard")
    args = parser.parse_args()

    print("=" * 60)
    print("Credit Risk Model Monitoring — Phase 6.2")
    print("=" * 60)

    # Load data
    training_metrics = load_training_metrics()
    print(f"[REF] Training run: {training_metrics['run_id']}")
    print(f"[REF] LGBM baseline PSI: {training_metrics['lgbm_psi']}")
    print(f"[REF] LR baseline PSI: {training_metrics['lr_psi']}")

    df = load_scores(args.scores_path)

    # Run monitoring
    print("\n--- Score Distribution PSI ---")
    score_psi = monitor_score_psi(df)

    print("\n--- Feature Drift Analysis ---")
    feature_drift = monitor_feature_drift(df)

    # Ensemble base model monitoring
    print("\n--- Ensemble Base Model Monitoring ---")
    ensemble_monitoring = monitor_ensemble_base_models(df)

    # Generate report
    report_path = generate_report(score_psi, feature_drift, training_metrics, args.output_dir,
                                  ensemble_monitoring=ensemble_monitoring)

    # Publish to OCI Monitoring dashboard
    if args.publish_metrics:
        report = json.load(open(report_path))
        publish_to_oci_dashboard(report, score_psi, feature_drift)


if __name__ == "__main__":
    main()
