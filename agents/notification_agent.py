import os
import requests
from schemas.state import FulfillmentState
from dotenv import load_dotenv

load_dotenv()

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")


def send_slack_message(message: str):
    if not SLACK_WEBHOOK_URL:
        return

    requests.post(SLACK_WEBHOOK_URL, json={"text": message})


def notification_node(state: FulfillmentState) -> FulfillmentState:

    risks = state.get("risks")

    # 🚫 DO NOT SEND if no real risk
    if not risks:
        return state

    if all(r["type"] == "no_risk" for r in risks):
        return state

    order = state.get("normalized_order")
    action = state.get("action")
    audit_id = state.get("audit_id")

    message = f"""
    🚨 *Risk Detected*

    🆔 Audit ID: {audit_id}

    📦 Order:
    {order}

    ⚠️ Risks:
    {risks}

    🎯 Action:
    {action}
    """

    send_slack_message(message)

    return state