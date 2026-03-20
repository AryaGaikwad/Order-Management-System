from schemas.state import FulfillmentState
from services.model_service import call_llm
from datetime import datetime, timezone
import re


# -----------------------------
# Rule-based normalization
# -----------------------------

def normalize_order_id(order_id: str) -> str:
    value = order_id.strip().upper().replace("_", "-")

    if value.startswith("ORDER-"):
        value = value.replace("ORDER-", "", 1)
    elif value.startswith("ORD-"):
        value = value.replace("ORD-", "", 1)

    return f"ORD-{value}"


def normalize_sku(sku: str) -> str:
    value = sku.strip().upper().replace("_", "-")

    if value.startswith("SKU-"):
        value = value.replace("SKU-", "", 1)
    elif value.startswith("SKU"):
        value = value.replace("SKU", "", 1)

    return f"SKU-{value}"


# -----------------------------
# Validation
# -----------------------------

def valid_order_id(value: str) -> bool:
    # matches ORD- followed by any alphanumeric and hyphens
    return bool(re.match(r"^ORD-[A-Z0-9\-]+$", value))


def valid_sku(value: str) -> bool:
    # matches SKU- followed by any alphanumeric and hyphens e.g. SKU-ELEC-001
    return bool(re.match(r"^SKU-[A-Z0-9\-]+$", value))


# -----------------------------
# AI fallback
# -----------------------------

def ai_normalize(value: str, entity_type: str) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "You normalize identifiers into canonical format. "
                "Return only the normalized value. No explanation. No punctuation."
            )
        },
        {
            "role": "user",
            "content": f"""
            Normalize this {entity_type} identifier.

            Input: {value}

            Rules:
            - Order IDs → ORD-<original suffix preserved>
            - SKUs → SKU-<original suffix preserved>

            Examples:
            - "order #1234"   → ORD-1234
            - "ord_5678"      → ORD-5678
            - "sku.elec.001"  → SKU-ELEC-001
            - "sku_furn_101"  → SKU-FURN-101

            Return only the normalized value.
            """
                    }
    ]

    result = call_llm(messages)
    return result.strip()


# -----------------------------
# LangGraph Node
# -----------------------------

def normalization_node(state: FulfillmentState) -> FulfillmentState:

    if not state.get("order"):
        return state

    order = state["order"].copy()

    # --- Normalize order_id ---
    order_id = normalize_order_id(order["order_id"])

    if not valid_order_id(order_id):
        order_id = ai_normalize(order["order_id"], "order_id")

    # --- Normalize SKU ---
    sku = normalize_sku(order["sku"])

    if not valid_sku(sku):
        sku = ai_normalize(order["sku"], "sku")

    order["order_id"] = order_id
    order["sku"] = sku

    state["normalized_order"] = order

    return state