"""
OCI Custom Metrics — Credit Risk Model Monitoring
Publishes ML metrics to OCI Monitoring Service for dashboard visualization.

Namespace: credit_risk_model
Metrics: score_psi, ks_statistic, auc_roc, gini, feature_psi, retrain_status,
         score_mean, score_p50, pct_critico, pct_baixo, scoring_volume

Usage:
    # Inside OCI (Resource Principal):
    from oci_metrics import publish_model_metrics, publish_score_distribution

    # Local development (API key from ~/.oci/config):
    from oci_metrics import publish_model_metrics
    publish_model_metrics(compartment_id, "lgbm_oci_v1", "202503", {"score_psi": 0.0012})

Requires: oci (pip install oci)
"""
import os
from datetime import datetime, timezone

METRIC_NAMESPACE = "credit_risk_model"


def _get_monitoring_client():
    """Initialize OCI MonitoringClient with telemetry-ingestion endpoint.
    PostMetricData requires the ingestion endpoint, not the default telemetry one.
    """
    import oci

    try:
        signer = oci.auth.signers.get_resource_principals_signer()
        config = {}
        region = os.environ.get("OCI_REGION", "sa-saopaulo-1")
    except Exception:
        config = oci.config.from_file()
        region = config.get("region", "sa-saopaulo-1")
        signer = None

    # PostMetricData requires telemetry-ingestion endpoint
    ingestion_endpoint = f"https://telemetry-ingestion.{region}.oraclecloud.com"

    if signer:
        return oci.monitoring.MonitoringClient(
            config, signer=signer, service_endpoint=ingestion_endpoint
        )
    else:
        return oci.monitoring.MonitoringClient(
            config, service_endpoint=ingestion_endpoint
        )


def _classify_metric(name):
    """Classify metric by type for dimension filtering."""
    if "psi" in name:
        return "stability"
    elif name in ("ks_statistic", "auc_roc", "gini"):
        return "performance"
    elif "score" in name or "pct" in name:
        return "distribution"
    elif "feature" in name:
        return "feature_drift"
    else:
        return "operational"


def _get_unit(name):
    """Return metric unit."""
    if "psi" in name:
        return "index"
    elif "latency" in name:
        return "milliseconds"
    elif "volume" in name or "count" in name:
        return "count"
    elif "pct" in name:
        return "percent"
    else:
        return "ratio"


def publish_model_metrics(compartment_id, model_name, safra, metrics):
    """
    Publish custom metrics to OCI Monitoring.

    Args:
        compartment_id: OCID of the compartment
        model_name: Model identifier (e.g., "lgbm_oci_v1")
        safra: SAFRA period (e.g., "202503")
        metrics: Dict of metric_name -> value
            Example: {"score_psi": 0.0012, "ks_statistic": 0.3397}

    Returns:
        OCI API response
    """
    import oci

    client = _get_monitoring_client()
    timestamp = datetime.now(timezone.utc)

    metric_data_list = []
    for metric_name, value in metrics.items():
        if value is None:
            continue
        metric_data_list.append(
            oci.monitoring.models.MetricDataDetails(
                namespace=METRIC_NAMESPACE,
                compartment_id=compartment_id,
                name=f"credit_risk.{metric_name}",
                dimensions={
                    "model_name": str(model_name),
                    "safra": str(safra),
                    "metric_type": _classify_metric(metric_name),
                },
                datapoints=[
                    oci.monitoring.models.Datapoint(
                        timestamp=timestamp,
                        value=float(value),
                    )
                ],
                metadata={"unit": _get_unit(metric_name)},
            )
        )

    if not metric_data_list:
        print("[METRICS] No metrics to publish")
        return None

    request = oci.monitoring.models.PostMetricDataDetails(
        metric_data=metric_data_list,
    )

    response = client.post_metric_data(
        post_metric_data_details=request,
    )

    print(f"[METRICS] Published {len(metric_data_list)} metrics — "
          f"model={model_name}, safra={safra}, status={response.status}")

    return response


def publish_score_distribution(compartment_id, model_name, safra, scores):
    """
    Publish score distribution metrics (from batch scoring output).

    Args:
        scores: numpy array or list of integer scores (0-1000)
    """
    import numpy as np

    scores = np.asarray(scores)
    total = len(scores)

    metrics = {
        "score_mean": float(np.mean(scores)),
        "score_p25": float(np.percentile(scores, 25)),
        "score_p50": float(np.percentile(scores, 50)),
        "score_p75": float(np.percentile(scores, 75)),
        "score_std": float(np.std(scores)),
        "pct_critico": float((scores < 300).sum() / total * 100),
        "pct_alto": float(((scores >= 300) & (scores < 500)).sum() / total * 100),
        "pct_medio": float(((scores >= 500) & (scores < 700)).sum() / total * 100),
        "pct_baixo": float((scores >= 700).sum() / total * 100),
        "scoring_volume": float(total),
    }

    return publish_model_metrics(compartment_id, model_name, safra, metrics)


def publish_feature_drift(compartment_id, model_name, safra, feature_drift_results):
    """
    Publish per-feature PSI drift metrics.

    Args:
        feature_drift_results: Dict from monitor_model.monitor_feature_drift()
            {feature_name: {"psi": 0.05, "status": "OK", ...}}
    """
    import oci

    client = _get_monitoring_client()
    timestamp = datetime.now(timezone.utc)

    metric_data_list = []
    for feature_name, data in feature_drift_results.items():
        psi = data.get("psi")
        if psi is None:
            continue

        metric_data_list.append(
            oci.monitoring.models.MetricDataDetails(
                namespace=METRIC_NAMESPACE,
                compartment_id=compartment_id,
                name="credit_risk.feature_psi",
                dimensions={
                    "model_name": str(model_name),
                    "safra": str(safra),
                    "feature_name": feature_name,
                    "metric_type": "feature_drift",
                },
                datapoints=[
                    oci.monitoring.models.Datapoint(
                        timestamp=timestamp,
                        value=float(psi),
                    )
                ],
                metadata={"unit": "index"},
            )
        )

    if not metric_data_list:
        print("[METRICS] No feature drift metrics to publish")
        return None

    request = oci.monitoring.models.PostMetricDataDetails(
        metric_data=metric_data_list,
    )

    response = client.post_metric_data(
        post_metric_data_details=request,
    )

    print(f"[METRICS] Published {len(metric_data_list)} feature drift metrics — "
          f"model={model_name}, safra={safra}")

    return response


def publish_monitoring_report(compartment_id, model_name, safra, report):
    """
    Publish all metrics from a monitoring report (output of monitor_model.py).

    Args:
        report: Dict loaded from monitoring_report_YYYYMMDD.json
    """
    # Score PSI
    metrics = {}
    for col, data in report.get("score_psi", {}).items():
        metrics["score_psi"] = data["psi"]

    # Retrain status
    status_map = {"STABLE": 0, "WARNING": 1, "RETRAIN_REQUIRED": 2}
    overall = report.get("overall_status", "STABLE")
    metrics["retrain_status"] = status_map.get(overall, 0)

    # Reference performance metrics (if available)
    ref = report.get("reference_metrics", {})
    lgbm = ref.get("lgbm", {})
    if lgbm:
        if "ks_oot" in lgbm:
            metrics["ks_statistic"] = lgbm["ks_oot"]
        if "auc_oot" in lgbm:
            metrics["auc_roc"] = lgbm["auc_oot"]
        if "gini_oot" in lgbm:
            metrics["gini"] = lgbm["gini_oot"]

    # Publish aggregated metrics
    publish_model_metrics(compartment_id, model_name, safra, metrics)

    # Publish per-feature drift
    feature_drift = report.get("feature_drift", {})
    if feature_drift:
        publish_feature_drift(compartment_id, model_name, safra, feature_drift)
