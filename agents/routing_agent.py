from schemas.state import FulfillmentState


def routing_node(state: FulfillmentState) -> FulfillmentState:

    risks = state.get("risks")

    if not risks:
        state["action"] = "no_action"
        return state

    # ------------------------
    # Priority-based routing
    # ------------------------

    for risk in risks:

        risk_type = risk["type"]
        confidence = risk["confidence"]

        # High confidence threshold
        if confidence < 0.6:
            continue

        if risk_type == "inventory_shortage":
            state["action"] = "alert_inventory_team"
            return state

        if risk_type == "shipment_delay":
            state["action"] = "alert_logistics_team"
            return state

        if risk_type == "fulfillment_delay":
            state["action"] = "alert_operations_team"
            return state

        if risk_type == "sla_violation":
            state["action"] = "alert_customer_success"
            return state

        if risk_type == "unknown_risk":
            state["action"] = "review_required"
            return state

    # fallback
    state["action"] = "no_action"

    return state