from fastapi import FastAPI, HTTPException
import uuid

from schemas.events import OrderEvent, InventoryEvent, ShipmentEvent
from graph.pipeline import build_graph
from services.state_store import (
    update_inventory,
    update_shipment,
    get_inventory,
    get_shipment,
)

app = FastAPI()
graph = build_graph()

METRICS = {
    "total_requests": 0,
    "risk_detected": 0,
    "high_confidence_risk": 0,
    "no_risk": 0,
    "per_risk_type": {
        "inventory_shortage": {"tp": 0, "fp": 0, "fn": 0},
        "shipment_delay":     {"tp": 0, "fp": 0, "fn": 0},
        "sla_violation":      {"tp": 0, "fp": 0, "fn": 0},
        "fulfillment_delay":  {"tp": 0, "fp": 0, "fn": 0},
        "unknown_risk":       {"tp": 0, "fp": 0, "fn": 0},
    }
}


def update_metrics(predicted_risks: list, expected_risks: list):
    predicted_types = {r["type"] for r in predicted_risks if r["type"] != "no_risk"}
    expected_types  = set(expected_risks)

    all_types = predicted_types | expected_types
    for risk_type in all_types:
        if risk_type not in METRICS["per_risk_type"]:
            METRICS["per_risk_type"][risk_type] = {"tp": 0, "fp": 0, "fn": 0}

        predicted = risk_type in predicted_types
        expected  = risk_type in expected_types

        if predicted and expected:
            METRICS["per_risk_type"][risk_type]["tp"] += 1
        elif predicted and not expected:
            METRICS["per_risk_type"][risk_type]["fp"] += 1
        elif not predicted and expected:
            METRICS["per_risk_type"][risk_type]["fn"] += 1


def compute_scores(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)
    return {
        "precision": round(precision, 3),
        "recall":    round(recall, 3),
        "f1":        round(f1, 3),
        "tp": tp, "fp": fp, "fn": fn,
    }


@app.get("/")
def root():
    return {"message": "API running"}


@app.post("/ingest/inventory")
def ingest_inventory(event: InventoryEvent):
    update_inventory(event.model_dump(mode="json"))  # ← mode=json
    return {"status": "inventory stored"}


@app.post("/ingest/shipments")
def ingest_shipment(event: ShipmentEvent):
    update_shipment(event.model_dump(mode="json"))   # ← mode=json
    return {"status": "shipment stored"}


@app.post("/ingest/orders")
def ingest_order(event: OrderEvent, expected_risks: str = None):
    try:
        audit_id   = str(uuid.uuid4())
        order_data = event.model_dump(mode="json")   # ← mode=json

        inventory = get_inventory(order_data["sku"])
        shipment  = get_shipment(order_data["order_id"])

        state = {
            "audit_id":         audit_id,
            "order":            order_data,
            "inventory":        inventory,
            "shipment":         shipment,
            "normalized_order": None,
            "risks":            None,
            "action":           None
        }

        result = graph.invoke(state)

        METRICS["total_requests"] += 1

        risks = result.get("risks", [])

        if not risks or all(r["type"] == "no_risk" for r in risks):
            METRICS["no_risk"] += 1
        else:
            METRICS["risk_detected"] += 1
            if any(r["confidence"] > 0.8 for r in risks):
                METRICS["high_confidence_risk"] += 1

        if expected_risks is not None:
            expected_list = [r.strip() for r in expected_risks.split(",") if r.strip()]
            update_metrics(risks, expected_list)

        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
def get_metrics():
    total_tp = sum(v["tp"] for v in METRICS["per_risk_type"].values())
    total_fp = sum(v["fp"] for v in METRICS["per_risk_type"].values())
    total_fn = sum(v["fn"] for v in METRICS["per_risk_type"].values())

    per_risk_scores = {
        risk_type: compute_scores(v["tp"], v["fp"], v["fn"])
        for risk_type, v in METRICS["per_risk_type"].items()
        if v["tp"] + v["fp"] + v["fn"] > 0
    }

    return {
        "summary": {
            "total_requests":       METRICS["total_requests"],
            "no_risk":              METRICS["no_risk"],
            "risk_detected":        METRICS["risk_detected"],
            "high_confidence_risk": METRICS["high_confidence_risk"],
        },
        "overall":       compute_scores(total_tp, total_fp, total_fn),
        "per_risk_type": per_risk_scores,
    }


@app.post("/metrics/reset")
def reset_metrics():
    for key in METRICS["per_risk_type"]:
        METRICS["per_risk_type"][key] = {"tp": 0, "fp": 0, "fn": 0}
    METRICS["total_requests"]       = 0
    METRICS["no_risk"]              = 0
    METRICS["risk_detected"]        = 0
    METRICS["high_confidence_risk"] = 0
    return {"status": "metrics reset"}