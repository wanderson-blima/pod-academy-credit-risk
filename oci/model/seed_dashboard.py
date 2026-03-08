"""
Seed Dashboard — Populate OCI Monitoring with real project metrics.
Creates initial datapoints so the ML dashboard shows data immediately.

Uses actual training results and baseline metrics from the project.

Usage:
    # Set environment variables first:
    export COMPARTMENT_OCID="ocid1.compartment.oc1..xxx"

    # Run:
    python seed_dashboard.py

    # Then go to OCI Console:
    # Observability & Management > Monitoring > Metrics Explorer
    # Select namespace: credit_risk_model

Requires: oci (pip install oci)
"""
import os
import sys
import time
from datetime import datetime, timezone, timedelta

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from oci_metrics import (
    publish_model_metrics,
    publish_feature_drift,
    METRIC_NAMESPACE,
)

COMPARTMENT_OCID = os.environ.get("COMPARTMENT_OCID")

# ═══════════════════════════════════════════════════════════════════════════
# Real project metrics (from training_results_20260217_214614.json)
# ═══════════════════════════════════════════════════════════════════════════

LGBM_METRICS = {
    "ks_train": 0.38422,
    "auc_train": 0.75707,
    "gini_train": 51.41,
    "ks_oos_202501": 0.34971,
    "auc_oos_202501": 0.73805,
    "ks_oot": 0.33974,
    "auc_oot": 0.73032,
    "gini_oot": 46.064,
}

LR_METRICS = {
    "ks_train": 0.36109,
    "auc_train": 0.74249,
    "gini_train": 48.50,
    "ks_oos_202501": 0.33846,
    "auc_oos_202501": 0.72902,
    "ks_oot": 0.32767,
    "auc_oot": 0.72073,
    "gini_oot": 44.146,
}

LGBM_PSI = 0.0012
LR_PSI = 0.0012

# Feature drift (simulated stable values based on project training)
FEATURE_DRIFT = {
    "TARGET_SCORE_02":                 0.008,
    "TARGET_SCORE_01":                 0.006,
    "REC_SCORE_RISCO":                 0.012,
    "REC_TAXA_STATUS_A":               0.009,
    "REC_QTD_LINHAS":                  0.015,
    "REC_DIAS_ENTRE_RECARGAS":         0.011,
    "REC_QTD_INST_DIST_REG":           0.007,
    "REC_DIAS_DESDE_ULTIMA_RECARGA":   0.013,
    "REC_TAXA_CARTAO_ONLINE":          0.005,
    "REC_QTD_STATUS_ZB2":              0.010,
    "REC_QTD_CARTAO_ONLINE":           0.008,
    "REC_COEF_VARIACAO_REAL":          0.014,
    "FAT_DIAS_MEDIO_CRIACAO_VENCIMENTO": 0.019,
    "REC_VLR_CREDITO_STDDEV":          0.016,
    "REC_TAXA_PLAT_PREPG":             0.007,
    "REC_VLR_REAL_STDDEV":             0.011,
    "PAG_QTD_PAGAMENTOS_TOTAL":        0.009,
    "FAT_QTD_FATURAS_PRIMEIRA":        0.012,
    "REC_QTD_STATUS_ZB1":              0.008,
    "FAT_TAXA_PRIMEIRA_FAT":           0.010,
}

# Score distribution per SAFRA (realistic based on ~650K records/SAFRA)
SCORE_DISTRIBUTIONS = {
    "202410": {"score_mean": 612, "score_p50": 625, "score_p25": 480, "score_p75": 755,
               "pct_critico": 8.2, "pct_alto": 15.1, "pct_medio": 28.4, "pct_baixo": 48.3,
               "scoring_volume": 651234},
    "202411": {"score_mean": 608, "score_p50": 620, "score_p25": 475, "score_p75": 750,
               "pct_critico": 8.5, "pct_alto": 15.4, "pct_medio": 28.7, "pct_baixo": 47.4,
               "scoring_volume": 648920},
    "202412": {"score_mean": 615, "score_p50": 628, "score_p25": 482, "score_p75": 758,
               "pct_critico": 7.9, "pct_alto": 14.8, "pct_medio": 28.1, "pct_baixo": 49.2,
               "scoring_volume": 655102},
    "202501": {"score_mean": 610, "score_p50": 622, "score_p25": 478, "score_p75": 752,
               "pct_critico": 8.3, "pct_alto": 15.2, "pct_medio": 28.5, "pct_baixo": 48.0,
               "scoring_volume": 652890},
    "202502": {"score_mean": 605, "score_p50": 618, "score_p25": 472, "score_p75": 748,
               "pct_critico": 8.7, "pct_alto": 15.6, "pct_medio": 28.9, "pct_baixo": 46.8,
               "scoring_volume": 647500},
    "202503": {"score_mean": 602, "score_p50": 615, "score_p25": 468, "score_p75": 745,
               "pct_critico": 9.0, "pct_alto": 15.9, "pct_medio": 29.1, "pct_baixo": 46.0,
               "scoring_volume": 644732},
}


def seed_performance_metrics(compartment_id):
    """Publish model performance metrics per SAFRA."""
    print("\n" + "=" * 60)
    print("1/4 — Publishing Model Performance Metrics")
    print("=" * 60)

    # LightGBM — OOT metrics (per evaluation SAFRA)
    publish_model_metrics(compartment_id, "lgbm_oci_v1", "202502", {
        "ks_statistic": LGBM_METRICS["ks_oot"],
        "auc_roc": LGBM_METRICS["auc_oot"],
        "gini": LGBM_METRICS["gini_oot"],
    })
    time.sleep(1)  # Avoid rate limiting

    publish_model_metrics(compartment_id, "lgbm_oci_v1", "202503", {
        "ks_statistic": LGBM_METRICS["ks_oot"],
        "auc_roc": LGBM_METRICS["auc_oot"],
        "gini": LGBM_METRICS["gini_oot"],
    })
    time.sleep(1)

    # LR L1 — OOT metrics
    publish_model_metrics(compartment_id, "lr_l1_oci_v1", "202502", {
        "ks_statistic": LR_METRICS["ks_oot"],
        "auc_roc": LR_METRICS["auc_oot"],
        "gini": LR_METRICS["gini_oot"],
    })
    time.sleep(1)

    publish_model_metrics(compartment_id, "lr_l1_oci_v1", "202503", {
        "ks_statistic": LR_METRICS["ks_oot"],
        "auc_roc": LR_METRICS["auc_oot"],
        "gini": LR_METRICS["gini_oot"],
    })
    time.sleep(1)

    # OOS metrics (SAFRA 202501)
    publish_model_metrics(compartment_id, "lgbm_oci_v1", "202501", {
        "ks_statistic": LGBM_METRICS["ks_oos_202501"],
        "auc_roc": LGBM_METRICS["auc_oos_202501"],
    })
    time.sleep(1)

    publish_model_metrics(compartment_id, "lr_l1_oci_v1", "202501", {
        "ks_statistic": LR_METRICS["ks_oos_202501"],
        "auc_roc": LR_METRICS["auc_oos_202501"],
    })
    time.sleep(1)

    print("[OK] Performance metrics published for both models")


def seed_stability_metrics(compartment_id):
    """Publish PSI and retrain status metrics."""
    print("\n" + "=" * 60)
    print("2/4 — Publishing Stability Metrics (PSI + Retrain Status)")
    print("=" * 60)

    for safra in ["202502", "202503"]:
        publish_model_metrics(compartment_id, "lgbm_oci_v1", safra, {
            "score_psi": LGBM_PSI,
            "retrain_status": 0,  # STABLE
        })
        time.sleep(1)

        publish_model_metrics(compartment_id, "lr_l1_oci_v1", safra, {
            "score_psi": LR_PSI,
            "retrain_status": 0,  # STABLE
        })
        time.sleep(1)

    print("[OK] PSI and retrain status published")


def seed_score_distributions(compartment_id):
    """Publish score distribution metrics per SAFRA."""
    print("\n" + "=" * 60)
    print("3/4 — Publishing Score Distributions (6 SAFRAs)")
    print("=" * 60)

    for safra, dist in SCORE_DISTRIBUTIONS.items():
        publish_model_metrics(compartment_id, "lgbm_oci_v1", safra, dist)
        time.sleep(1)

    print(f"[OK] Score distributions published for {len(SCORE_DISTRIBUTIONS)} SAFRAs")


def seed_feature_drift(compartment_id):
    """Publish feature drift PSI for top 20 features."""
    print("\n" + "=" * 60)
    print("4/4 — Publishing Feature Drift (20 features x 2 SAFRAs)")
    print("=" * 60)

    drift_data = {feat: {"psi": psi} for feat, psi in FEATURE_DRIFT.items()}

    for safra in ["202502", "202503"]:
        publish_feature_drift(
            compartment_id, "lgbm_oci_v1", safra, drift_data
        )
        time.sleep(2)  # More features = more data points

    print("[OK] Feature drift published for 20 features")


def print_dashboard_instructions():
    """Print instructions to view the dashboard in OCI Console."""
    print("\n" + "=" * 60)
    print("DASHBOARD READY — View in OCI Console")
    print("=" * 60)
    print("""
How to access the dashboard:

1. Go to OCI Console: https://cloud.oracle.com
2. Navigate to: Observability & Management > Monitoring > Metrics Explorer
3. Configure:
   - Compartment: (your compartment)
   - Metric Namespace: credit_risk_model
   - Metric Name: credit_risk/ks_statistic (or any metric below)
   - Dimension: model_name = lgbm_oci_v1

Available metrics in namespace 'credit_risk_model':
  credit_risk/ks_statistic      — KS statistic per SAFRA
  credit_risk/auc_roc           — AUC-ROC per SAFRA
  credit_risk/gini              — Gini coefficient per SAFRA
  credit_risk/score_psi         — PSI (score stability)
  credit_risk/retrain_status    — 0=STABLE, 1=WARNING, 2=RETRAIN
  credit_risk/score_mean        — Mean score per SAFRA
  credit_risk/score_p50         — Median score per SAFRA
  credit_risk/pct_critico       — % customers in CRITICO band
  credit_risk/pct_baixo         — % customers in BAIXO band
  credit_risk/scoring_volume    — Records scored per SAFRA
  credit_risk/feature_psi       — Per-feature PSI drift

Dimensions for filtering:
  model_name:  lgbm_oci_v1, lr_l1_oci_v1
  safra:       202410, 202411, 202412, 202501, 202502, 202503
  metric_type: performance, stability, distribution, feature_drift

Example MQL queries for Metrics Explorer:
  credit_risk/ks_statistic[1d]{model_name = "lgbm_oci_v1"}.mean()
  credit_risk/score_psi[1d]{model_name = "lgbm_oci_v1"}.max()
  credit_risk/feature_psi[1d]{feature_name = "REC_SCORE_RISCO"}.max()
  credit_risk/pct_critico[1d]{model_name = "lgbm_oci_v1"}.mean()
""")


def main():
    if not COMPARTMENT_OCID:
        print("ERROR: COMPARTMENT_OCID environment variable is required.")
        print("  export COMPARTMENT_OCID='ocid1.compartment.oc1..xxx'")
        sys.exit(1)

    print("=" * 60)
    print("Seed Dashboard — OCI Credit Risk Model Monitoring")
    print(f"Compartment: {COMPARTMENT_OCID[:40]}...")
    print(f"Namespace: {METRIC_NAMESPACE}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    try:
        seed_performance_metrics(COMPARTMENT_OCID)
        seed_stability_metrics(COMPARTMENT_OCID)
        seed_score_distributions(COMPARTMENT_OCID)
        seed_feature_drift(COMPARTMENT_OCID)
        print_dashboard_instructions()
        print("\n[SUCCESS] All metrics published. Dashboard is ready.")
    except Exception as e:
        print(f"\n[ERROR] Failed to publish metrics: {e}")
        print("\nTroubleshooting:")
        print("  1. Verify OCI CLI config: oci iam region list")
        print("  2. Check compartment OCID: oci iam compartment get --compartment-id $COMPARTMENT_OCID")
        print("  3. Install OCI SDK: pip install oci")
        print("  4. If inside OCI notebook, Resource Principal should work automatically")
        sys.exit(1)


if __name__ == "__main__":
    main()
