#!/bin/bash
# Orchestrator Lifecycle Management
# Start, stop, or recreate the orchestrator instance
#
# Usage:
#   bash orchestrator-lifecycle.sh start    # Start stopped instance
#   bash orchestrator-lifecycle.sh stop     # Stop instance (preserves boot volume, $0 while stopped)
#   bash orchestrator-lifecycle.sh status   # Check current state
#   bash orchestrator-lifecycle.sh destroy  # Destroy instance (terraform destroy)
#   bash orchestrator-lifecycle.sh create   # Create from scratch (terraform apply)
#   bash orchestrator-lifecycle.sh resize-up   # Scale to 4 OCPUs / 64 GB for ML
#   bash orchestrator-lifecycle.sh resize-down # Scale back to 2 OCPUs / 16 GB
#   bash orchestrator-lifecycle.sh cost     # Show estimated cost so far
#
# Cost: VM.Standard.E3.Flex 2 OCPUs / 16 GB = ~$0.074/hr = ~$1.78/day
# ML mode: VM.Standard.E3.Flex 4 OCPUs / 64 GB = ~$0.148/hr = ~$3.55/day
# Stopped instance: $0 (only boot volume storage, negligible)

set -euo pipefail

COMPARTMENT_OCID="${COMPARTMENT_OCID:-ocid1.compartment.oc1..aaaaaaaa7uh2lfpsc6qf73g7zalgbr262a2v6veb4lreykqn57gtjvoojeuq}"
TERRAFORM_DIR="$(cd "$(dirname "$0")/../terraform" && pwd)"
TFVARS_FILE="terraform.tfvars.dev"

ACTION="${1:-status}"

get_instance_id() {
  oci compute instance list \
    --compartment-id "$COMPARTMENT_OCID" \
    --display-name "pod-academy-orchestrator" \
    --query 'data[?!"lifecycle-state"==`TERMINATED`] | [0].id' \
    --raw-output 2>/dev/null || echo ""
}

get_instance_state() {
  local ocid="$1"
  oci compute instance get \
    --instance-id "$ocid" \
    --query 'data."lifecycle-state"' \
    --raw-output 2>/dev/null || echo "UNKNOWN"
}

case "$ACTION" in
  start)
    INSTANCE_ID=$(get_instance_id)
    if [ -z "$INSTANCE_ID" ] || [ "$INSTANCE_ID" == "null" ]; then
      echo "No orchestrator instance found. Use 'create' to provision one."
      exit 1
    fi
    STATE=$(get_instance_state "$INSTANCE_ID")
    if [ "$STATE" == "RUNNING" ]; then
      echo "Instance already RUNNING."
      exit 0
    fi
    echo "Starting orchestrator instance..."
    oci compute instance action --action START --instance-id "$INSTANCE_ID" --wait-for-state RUNNING
    echo "Orchestrator RUNNING. Cost: ~\$0.074/hr"
    echo "Private IP: $(oci compute instance list-vnics --instance-id "$INSTANCE_ID" --query 'data[0]."private-ip"' --raw-output)"
    ;;

  stop)
    INSTANCE_ID=$(get_instance_id)
    if [ -z "$INSTANCE_ID" ] || [ "$INSTANCE_ID" == "null" ]; then
      echo "No orchestrator instance found."
      exit 1
    fi
    STATE=$(get_instance_state "$INSTANCE_ID")
    if [ "$STATE" == "STOPPED" ]; then
      echo "Instance already STOPPED."
      exit 0
    fi
    echo "Stopping orchestrator instance... (cost drops to ~\$0)"
    oci compute instance action --action SOFTSTOP --instance-id "$INSTANCE_ID" --wait-for-state STOPPED
    echo "Orchestrator STOPPED. No compute charges while stopped."
    ;;

  status)
    INSTANCE_ID=$(get_instance_id)
    if [ -z "$INSTANCE_ID" ] || [ "$INSTANCE_ID" == "null" ]; then
      echo "No orchestrator instance found."
      exit 0
    fi
    STATE=$(get_instance_state "$INSTANCE_ID")
    echo "Orchestrator: $STATE"
    echo "Instance ID: $INSTANCE_ID"
    if [ "$STATE" == "RUNNING" ]; then
      echo "Private IP: $(oci compute instance list-vnics --instance-id "$INSTANCE_ID" --query 'data[0]."private-ip"' --raw-output)"
      echo "Cost: ~\$0.074/hr (~\$1.78/day)"
    else
      echo "Cost: \$0 (stopped)"
    fi
    ;;

  destroy)
    echo "Destroying orchestrator via Terraform..."
    echo "This will delete the instance and boot volume."
    cd "$TERRAFORM_DIR"
    terraform destroy -target=module.orchestrator -var-file="$TFVARS_FILE" -auto-approve
    echo "Orchestrator destroyed. Cost: \$0"
    echo "To recreate: bash orchestrator-lifecycle.sh create"
    ;;

  create)
    echo "Creating orchestrator via Terraform (cloud-init auto-configures Docker + Airflow)..."
    cd "$TERRAFORM_DIR"
    terraform apply -target=module.orchestrator -var-file="$TFVARS_FILE" -auto-approve
    echo ""
    INSTANCE_ID=$(get_instance_id)
    if [ -n "$INSTANCE_ID" ] && [ "$INSTANCE_ID" != "null" ]; then
      echo "Orchestrator RUNNING."
      echo "Instance ID: $INSTANCE_ID"
      echo "Private IP: $(oci compute instance list-vnics --instance-id "$INSTANCE_ID" --query 'data[0]."private-ip"' --raw-output)"
      echo "Cloud-init will install Docker + Airflow (~5 min)."
      echo "Cost: ~\$0.074/hr (~\$1.78/day)"
    fi
    ;;

  resize-up)
    INSTANCE_ID=$(get_instance_id)
    if [ -z "$INSTANCE_ID" ] || [ "$INSTANCE_ID" == "null" ]; then
      echo "No orchestrator instance found."
      exit 1
    fi
    STATE=$(get_instance_state "$INSTANCE_ID")
    if [ "$STATE" == "RUNNING" ]; then
      echo "Instance must be STOPPED before resizing. Stopping now..."
      oci compute instance action --action SOFTSTOP --instance-id "$INSTANCE_ID" --wait-for-state STOPPED
    fi
    echo "Resizing to 4 OCPUs / 64 GB (ML mode)..."
    oci compute instance update \
      --instance-id "$INSTANCE_ID" \
      --shape-config '{"ocpus":4,"memoryInGBs":64}' \
      --force
    echo "Starting resized instance..."
    oci compute instance action --action START --instance-id "$INSTANCE_ID" --wait-for-state RUNNING
    echo "Orchestrator RUNNING at 4 OCPUs / 64 GB. Cost: ~\$0.148/hr"
    echo "After ML pipeline, run: bash orchestrator-lifecycle.sh resize-down"
    ;;

  resize-down)
    INSTANCE_ID=$(get_instance_id)
    if [ -z "$INSTANCE_ID" ] || [ "$INSTANCE_ID" == "null" ]; then
      echo "No orchestrator instance found."
      exit 1
    fi
    STATE=$(get_instance_state "$INSTANCE_ID")
    if [ "$STATE" == "RUNNING" ]; then
      echo "Instance must be STOPPED before resizing. Stopping now..."
      oci compute instance action --action SOFTSTOP --instance-id "$INSTANCE_ID" --wait-for-state STOPPED
    fi
    echo "Resizing back to 2 OCPUs / 16 GB (normal mode)..."
    oci compute instance update \
      --instance-id "$INSTANCE_ID" \
      --shape-config '{"ocpus":2,"memoryInGBs":16}' \
      --force
    echo "Starting resized instance..."
    oci compute instance action --action START --instance-id "$INSTANCE_ID" --wait-for-state RUNNING
    echo "Orchestrator RUNNING at 2 OCPUs / 16 GB. Cost: ~\$0.074/hr"
    ;;

  cost)
    INSTANCE_ID=$(get_instance_id)
    if [ -z "$INSTANCE_ID" ] || [ "$INSTANCE_ID" == "null" ]; then
      echo "No orchestrator instance found. Cost: \$0"
      exit 0
    fi
    CREATED=$(oci compute instance get --instance-id "$INSTANCE_ID" --query 'data."time-created"' --raw-output)
    STATE=$(get_instance_state "$INSTANCE_ID")
    echo "Instance created: $CREATED"
    echo "Current state: $STATE"
    echo ""
    echo "Shape: VM.Standard.E4.Flex (2 OCPUs, 16 GB)"
    echo "Rate: ~\$0.074/hr = ~\$1.78/day"
    echo ""
    echo "Note: Charges only accrue while RUNNING."
    echo "Use 'stop' to pause charges, 'destroy' to eliminate."
    ;;

  *)
    echo "Usage: $0 {start|stop|status|destroy|create|resize-up|resize-down|cost}"
    exit 1
    ;;
esac
