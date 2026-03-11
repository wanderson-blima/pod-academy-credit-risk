"""Sync OCI costs to ADW COST_TRACKING table via Usage API + ORDS.

Run on orchestrator VM (instance_principal auth) or locally (config auth).
Queries OCI Usage API for current month costs and pushes to ADW.

Usage:
  python3 sync_oci_costs.py              # instance_principal (on OCI VM)
  python3 sync_oci_costs.py --config     # ~/.oci/config (local)
"""
import sys
import json
import datetime
import requests

# ---------- ADW ORDS config ----------
ORDS_URL = "https://G95D3985BD0D2FD-PODACADEMY.adb.sa-saopaulo-1.oraclecloudapps.com/ords/mlmonitor/_/sql"
AUTH = ("MLMONITOR", "CreditRisk2026#ML")
HEADERS = {"Content-Type": "application/sql"}

# ---------- OCI config ----------
COMPARTMENT_ID = "ocid1.compartment.oc1..aaaaaaaa7uh2lfpsc6qf73g7zalgbr262a2v6veb4lreykqn57gtjvoojeuq"
TENANCY_ID = "ocid1.tenancy.oc1..aaaaaaaahse5thvzinsvm7bkyrd3zravzao2i6kpfl4bfxkplbu7ppla5x5a"


def get_oci_costs(use_config=False):
    """Query OCI Usage API for current month costs."""
    try:
        import oci
    except ImportError:
        print("ERROR: oci SDK not installed. Install with: pip3 install oci")
        return None

    if use_config:
        config = oci.config.from_file()
        client = oci.usage_api.UsageapiClient(config)
    else:
        signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        client = oci.usage_api.UsageapiClient({}, signer=signer)

    now = datetime.datetime.utcnow()
    start = datetime.datetime(now.year, now.month, 1)
    end = now

    request = oci.usage_api.models.RequestSummarizedUsagesDetails(
        tenant_id=TENANCY_ID,
        time_usage_started=start.strftime("%Y-%m-%dT00:00:00.000Z"),
        time_usage_ended=end.strftime("%Y-%m-%dT23:59:59.999Z"),
        granularity="MONTHLY",
        query_type="COST",
        compartment_depth=2,
        group_by=["service"],
        filter=oci.usage_api.models.Filter(
            operator="AND",
            dimensions=[
                oci.usage_api.models.Dimension(
                    key="compartmentId",
                    value=COMPARTMENT_ID
                )
            ]
        )
    )

    try:
        resp = client.request_summarized_usages(request)
        costs = []
        for item in resp.data.items:
            svc = item.service or "Unknown"
            amount = item.computed_amount or 0
            currency = item.currency or "BRL"
            costs.append({
                "service": svc,
                "cost": round(amount, 2),
                "currency": currency
            })
        return costs
    except Exception as e:
        print(f"ERROR querying Usage API: {e}")
        return None


def push_costs_to_adw(costs, period=None):
    """Push cost data to ADW COST_TRACKING table via ORDS."""
    if not period:
        now = datetime.datetime.utcnow()
        period = now.strftime("%Y-%m")

    # Delete existing data for this period (live refresh)
    del_sql = f"DELETE FROM cost_tracking WHERE period = '{period}'"
    resp = requests.post(ORDS_URL, auth=AUTH, headers=HEADERS, data=del_sql)
    print(f"Deleted existing {period} costs: {resp.status_code}")

    total_cost = sum(c["cost"] for c in costs)
    inserted = 0

    for c in costs:
        svc = c["service"].replace("'", "''")
        cost_val = c["cost"]
        pct = round((cost_val / total_cost * 100) if total_cost > 0 else 0, 1)
        notes = "Live from OCI Usage API"

        sql = (
            f"INSERT INTO cost_tracking (period, service_name, cost_brl, pct_of_total, notes) "
            f"VALUES ('{period}', '{svc}', {cost_val}, {pct}, '{notes}')"
        )
        resp = requests.post(ORDS_URL, auth=AUTH, headers=HEADERS, data=sql)
        result = resp.json()
        err = any(it.get("errorCode") for it in result.get("items", []))
        if err:
            for it in result.get("items", []):
                if it.get("errorCode"):
                    print(f"  ERROR inserting {svc}: {it.get('errorDetails', '')[:100]}")
        else:
            inserted += 1

    # Commit
    requests.post(ORDS_URL, auth=AUTH, headers=HEADERS, data="COMMIT")
    print(f"Inserted {inserted}/{len(costs)} cost records for {period}")
    print(f"Total cost: R$ {total_cost:.2f}")
    return inserted


def get_fallback_costs():
    """Fallback: estimate costs from known OCI resources when API unavailable."""
    now = datetime.datetime.utcnow()
    day = now.day
    days_in_month = 30

    # E3.Flex 4 OCPU 64GB: ~$0.065/OCPU/hr = $0.26/hr * 24 * days
    compute_hourly = 0.26
    compute_cost = round(compute_hourly * 24 * day * 5.5, 2)  # BRL rate ~5.5

    # Object Storage: ~$0.0255/GB/month, 4 buckets ~30GB
    storage_cost = round(0.0255 * 30 * 5.5, 2)

    return [
        {"service": "Compute E3.Flex 4 OCPU 64GB", "cost": compute_cost, "currency": "BRL"},
        {"service": "Object Storage 4 buckets", "cost": storage_cost, "currency": "BRL"},
        {"service": "ADW Always Free", "cost": 0.0, "currency": "BRL"},
        {"service": "Data Catalog Always Free", "cost": 0.0, "currency": "BRL"},
        {"service": "VCN + Subnets", "cost": 0.0, "currency": "BRL"},
    ]


if __name__ == "__main__":
    use_config = "--config" in sys.argv
    use_fallback = "--fallback" in sys.argv

    print(f"=== OCI Cost Sync ({datetime.datetime.utcnow().isoformat()}) ===")

    if use_fallback:
        print("Using fallback cost estimation...")
        costs = get_fallback_costs()
    else:
        auth_mode = "config" if use_config else "instance_principal"
        print(f"Auth: {auth_mode}")
        costs = get_oci_costs(use_config=use_config)

    if costs is None:
        print("OCI API failed. Using fallback estimates...")
        costs = get_fallback_costs()

    if costs:
        print(f"\nCosts found: {len(costs)} services")
        for c in costs:
            print(f"  {c['service']}: R$ {c['cost']:.2f}")
        push_costs_to_adw(costs)
    else:
        print("No cost data available.")
