# -*- coding: utf-8 -*-
from schemas.state import FulfillmentState
from services.model_service import call_llm
from services.state_store import get_inventory
from datetime import datetime, timezone
import json


VALID_RISK_TYPES = {
    "inventory_shortage",
    "shipment_delay",
    "sla_violation",
    "fulfillment_delay",
    "no_risk"
}


def parse_llm_response(response: str) -> dict:
    response = response.strip()
    if response.startswith("```"):
        parts = response.split("```")
        response = parts[1]
        if response.startswith("json"):
            response = response[4:]
    return json.loads(response.strip())


def parse_dt(value) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    dt = datetime.fromisoformat(str(value))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def build_context(order: dict, inventory: dict, shipment: dict, now: datetime) -> dict:
    """Build clean structured context for the AI - all values are JSON serializable."""

    # order context
    try:
        exp = parse_dt(order["expected_ship_date"])
        hours_to_ship = (exp - now).total_seconds() / 3600
        ship_date_status = (
            f"already passed by {abs(hours_to_ship):.1f} hours"
            if hours_to_ship < 0
            else f"{hours_to_ship:.1f} hours from now"
        )
    except Exception:
        ship_date_status = "unknown"

    order_ctx = {
        "order_id":           str(order.get("order_id", "")),
        "sku":                str(order.get("sku", "")),
        "quantity_ordered":   order.get("quantity"),
        "expected_ship_date": ship_date_status,
    }

    # inventory context
    if inventory:
        inv_ctx = {
            "stock_level":       inventory.get("stock_level"),
            "reorder_threshold": inventory.get("reorder_threshold"),
            "supplier_eta":      str(inventory.get("supplier_eta") or "none"),
            "stock_vs_order": (
                f"sufficient ({inventory['stock_level']} >= {order.get('quantity')})"
                if inventory["stock_level"] >= (order.get("quantity") or 0)
                else f"INSUFFICIENT ({inventory['stock_level']} < {order.get('quantity')})"
            )
        }
    else:
        inv_ctx = "NOT AVAILABLE"

    # shipment context
    if shipment:
        try:
            eta = parse_dt(shipment["eta"])
            exp = parse_dt(order["expected_ship_date"])
            eta_vs_exp = (
                f"ON TIME - arrives {(exp - eta).days} days before expected"
                if eta <= exp
                else f"LATE - arrives {(eta - exp).days} days after expected"
            )
        except Exception:
            eta_vs_exp = "unable to compare"

        ship_ctx = {
            "status":          str(shipment.get("status", "")),
            "carrier":         str(shipment.get("carrier", "")),
            "eta":             str(shipment.get("eta", "")),
            "eta_vs_expected": eta_vs_exp,
        }
    else:
        ship_ctx = "NOT AVAILABLE"

    return {
        "order":     order_ctx,
        "inventory": inv_ctx,
        "shipment":  ship_ctx,
    }


def risk_node(state: FulfillmentState) -> FulfillmentState:

    order = state.get("normalized_order")

    if not order:
        return state

    inventory = get_inventory(order["sku"])
    shipment  = state.get("shipment")
    now       = datetime.now(timezone.utc)

    try:
        # everything inside try — catches any serialization or AI errors
        context = build_context(order, inventory, shipment, now)

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a supply chain risk analyst for an Order Management System.\n\n"
                    "Your job is to analyze each order and identify ALL fulfillment risks present.\n"
                    "You must reason carefully from the data - do not guess or assume.\n\n"
                    "RISK TYPES you can detect:\n"
                    "- inventory_shortage : stock on hand is insufficient to fulfill the order\n"
                    "- sla_violation      : expected ship date is under 4 hours away or already passed\n"
                    "- shipment_delay     : shipment ETA is after the expected ship date\n"
                    "- fulfillment_delay  : complex multi-factor risk with multiple simultaneous signals\n"
                    "- no_risk            : everything looks fine\n\n"
                    "REASONING RULES:\n"
                    "- inventory NOT AVAILABLE means no inventory data - do NOT flag as shortage\n"
                    "- shipment NOT AVAILABLE means no shipment yet - do NOT flag as delay\n"
                    "- stock_vs_order = sufficient -> no inventory_shortage\n"
                    "- stock_vs_order = INSUFFICIENT -> inventory_shortage\n"
                    "- eta_vs_expected = ON TIME -> no shipment_delay\n"
                    "- eta_vs_expected = LATE -> shipment_delay\n"
                    "- expected_ship_date already passed -> sla_violation\n"
                    "- expected_ship_date under 4 hours from now -> sla_violation\n"
                    "- fulfillment_delay only when 2+ risk signals overlap in a complex way\n"
                    "- You can return multiple risks if more than one is present\n"
                    "- If nothing is wrong, return no_risk only\n\n"
                    "Return raw JSON only. No markdown. No explanation outside the JSON."
                )
            },
            {
                "role": "user",
                "content": (
                    "Analyze this order for fulfillment risks.\n\n"
                    + json.dumps(context, indent=2)
                    + "\n\nReturn ONLY this JSON - one object per risk found:\n"
                    "{\n"
                    '    "risks": [\n'
                    "        {\n"
                    '            "type": "<exactly one of: inventory_shortage, shipment_delay, sla_violation, fulfillment_delay, no_risk>",\n'
                    '            "confidence": <float 0.0-1.0>,\n'
                    '            "reason": "<one concise sentence explaining why this risk was detected>",\n'
                    '            "source": "ai"\n'
                    "        }\n"
                    "    ]\n"
                    "}\n\n"
                    "If multiple risks exist, include all of them in the array.\n"
                    "If no risk exists, return a single entry with type no_risk and confidence 1.0."
                )
            }
        ]

        response = call_llm(messages)
        parsed   = parse_llm_response(response)

        raw_risks = parsed.get("risks", [])
        risks     = []

        for item in raw_risks:
            risk_type  = item.get("type", "").strip().lower()
            confidence = float(item.get("confidence", 0.5))
            reason     = item.get("reason", "AI-detected")

            if risk_type not in VALID_RISK_TYPES:
                risk_type = "unknown_risk"

            risks.append({
                "type":       risk_type,
                "confidence": confidence,
                "reason":     reason,
                "source":     "ai"
            })

        # deduplicate - keep highest confidence per type
        unique = {}
        for r in risks:
            if r["type"] not in unique or r["confidence"] > unique[r["type"]]["confidence"]:
                unique[r["type"]] = r

        if not unique or list(unique.keys()) == ["unknown_risk"]:
            state["risks"] = [{
                "type":       "no_risk",
                "confidence": 1.0,
                "reason":     "no issues detected",
                "source":     "ai"
            }]
        else:
            state["risks"] = list(unique.values())

    except Exception:
        # use unknown_risk so failures are visible in metrics
        state["risks"] = [{
            "type":       "unknown_risk",
            "confidence": 0.0,
            "reason":     "risk analysis failed",
            "source":     "system"
        }]

    return state