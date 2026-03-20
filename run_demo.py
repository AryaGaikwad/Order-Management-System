import json
import requests
from pathlib import Path

BASE_URL  = "http://127.0.0.1:8000"
DATA_FILE = Path("synthetic_data.json")


def post_inventory(records):
    print(f"\n🏭 Sending {len(records)} inventory records...\n")
    for idx, record in enumerate(records, start=1):
        r = requests.post(f"{BASE_URL}/ingest/inventory", json=record["payload"])
        print(f"  [{idx:>3}/{len(records)}] {record['scenario']:<15} → {r.status_code}")


def post_shipments(records):
    print(f"\n🚚 Sending {len(records)} shipment records...\n")
    for idx, record in enumerate(records, start=1):
        r = requests.post(f"{BASE_URL}/ingest/shipments", json=record["payload"])
        print(f"  [{idx:>3}/{len(records)}] {record['scenario']:<15} → {r.status_code}")


def post_orders(records):
    print(f"\n📦 Sending {len(records)} orders...\n")
    results = {"success": 0, "failed": 0}

    for idx, record in enumerate(records, start=1):
        scenario       = record["scenario"]
        payload        = record["payload"]
        expected_risks = record.get("expected_risks", [])

        # send expected_risks as comma-separated query param string
        # params = {}
        # if expected_risks:
        #     params["expected_risks"] = ",".join(expected_risks)
        params = {"expected_risks": ",".join(expected_risks)}


        r = requests.post(
            f"{BASE_URL}/ingest/orders",
            json=payload,
            params=params,
        )

        # if r.status_code == 200:
        #     result          = r.json()
        #     predicted_risks = [risk["type"] for risk in result.get("risks", [])]
        #     action          = result.get("action", "unknown")
        #     results["success"] += 1
        # else:
        #     predicted_risks = []
        #     action          = f"HTTP {r.status_code}"
        #     results["failed"] += 1
        if r.status_code == 200:
            result          = r.json()
            predicted_risks = [risk["type"] for risk in result.get("risks", [])]
            action          = result.get("action", "unknown")
            results["success"] += 1
        else:
            predicted_risks = []
            action          = f"HTTP {r.status_code}"
            results["failed"] += 1
            print(f"    ERROR: {r.text[:300]}")   
        expected_set  = set(expected_risks)
        predicted_set = set(predicted_risks) - {"no_risk"}
        match_icon    = "✅" if expected_set == predicted_set else "⚠️ "
        status_icon   = "✅" if r.status_code == 200 else "❌"

        print(
            f"  {status_icon} [{idx:>3}] {scenario:<22} "
            f"expected={sorted(expected_risks)} "
            f"predicted={sorted(predicted_set)} {match_icon}"
        )

    return results


def print_metrics():
    r       = requests.get(f"{BASE_URL}/metrics")
    metrics = r.json()
    summary = metrics["summary"]
    overall = metrics["overall"]

    print(f"\n{'─'*55}")
    print(f"📊  METRICS SUMMARY")
    print(f"{'─'*55}")
    print(f"  Total orders        : {summary['total_requests']}")
    print(f"  No risk             : {summary['no_risk']}")
    print(f"  Risk detected       : {summary['risk_detected']}")
    print(f"  High confidence     : {summary['high_confidence_risk']}")
    print(f"\n  Overall Precision   : {overall['precision']}")
    print(f"  Overall Recall      : {overall['recall']}")
    print(f"  Overall F1          : {overall['f1']}")
    print(f"  TP / FP / FN        : {overall['tp']} / {overall['fp']} / {overall['fn']}")

    if metrics["per_risk_type"]:
        print(f"\n  Per Risk Type:")
        print(f"  {'Risk':<25} {'P':>6} {'R':>6} {'F1':>6} {'TP':>5} {'FP':>5} {'FN':>5}")
        print(f"  {'─'*54}")
        for risk_type, scores in metrics["per_risk_type"].items():
            print(
                f"  {risk_type:<25} "
                f"{scores['precision']:>6.2f} "
                f"{scores['recall']:>6.2f} "
                f"{scores['f1']:>6.2f} "
                f"{scores['tp']:>5} "
                f"{scores['fp']:>5} "
                f"{scores['fn']:>5}"
            )
    print(f"{'─'*55}\n")


def run():
    with open(DATA_FILE) as f:
        data = json.load(f)

    inventory = data.get("inventory", [])
    shipments = data.get("shipments", [])
    orders    = data.get("orders", [])

    if not orders:
        raise ValueError("synthetic_data.json has no orders")

    # reset before each run for clean metrics
    requests.post(f"{BASE_URL}/metrics/reset")

    post_inventory(inventory)
    post_shipments(shipments)
    results = post_orders(orders)

    print(f"\n{'─'*40}")
    print(f"  ✅ Success : {results['success']}")
    print(f"  ❌ Failed  : {results['failed']}")
    print(f"{'─'*40}")

    print_metrics()


if __name__ == "__main__":
    run()