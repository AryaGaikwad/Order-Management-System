import json
import random
from datetime import datetime, timedelta, timezone

random.seed(42)

# ── Master data ────────────────────────────────────────────────────────────────

SKUS = [
    "SKU-ELEC-001", "SKU-ELEC-002", "SKU-ELEC-003",
    "SKU-FURN-101", "SKU-FURN-102",
    "SKU-APPL-201", "SKU-APPL-202", "SKU-APPL-203",
    "SKU-CLTH-301", "SKU-CLTH-302", "SKU-CLTH-303",
    "SKU-FOOD-401", "SKU-FOOD-402",
]

WAREHOUSES = ["WH-EAST-01", "WH-WEST-02", "WH-CENTRAL-03", "WH-SOUTH-04"]
CARRIERS   = ["UPS", "FedEx", "DHL", "USPS"]

SUPPLIERS = {
    "SKU-ELEC-001": "SUP-TECHCORP",    "SKU-ELEC-002": "SUP-TECHCORP",
    "SKU-ELEC-003": "SUP-DIGIWORLD",   "SKU-FURN-101": "SUP-HOMECO",
    "SKU-FURN-102": "SUP-HOMECO",      "SKU-APPL-201": "SUP-APPLIANCE-KING",
    "SKU-APPL-202": "SUP-APPLIANCE-KING", "SKU-APPL-203": "SUP-GLOBALTECH",
    "SKU-CLTH-301": "SUP-FASHIONHUB",  "SKU-CLTH-302": "SUP-FASHIONHUB",
    "SKU-CLTH-303": "SUP-TRENDSCO",    "SKU-FOOD-401": "SUP-FRESHMART",
    "SKU-FOOD-402": "SUP-FRESHMART",
}

CUSTOMERS = [f"CUST-{str(i).zfill(4)}" for i in range(1, 51)]

# ── Dirty format helpers ───────────────────────────────────────────────────────

def dirty_order_id(clean_id: str) -> str:
    return random.choice([
        clean_id, clean_id.lower(),
        clean_id.replace("ORD-", "ORDER-"),
        clean_id.replace("ORD-", "ord_"),
        clean_id.replace("ORD-", ""),
        f" {clean_id} ",
    ])


def dirty_sku(clean_sku: str) -> str:
    return random.choice([
        clean_sku, clean_sku.lower(),
        clean_sku.replace("SKU-", "sku_"),
        clean_sku.replace("SKU-", "SKU"),
        clean_sku.replace("-", "_"),
        f" {clean_sku} ",
    ])


# ── Live world state ───────────────────────────────────────────────────────────

inventory_state  = {sku: random.randint(150, 400) for sku in SKUS}
pending_units    = {sku: 0 for sku in SKUS}
order_counter    = 10000
controlled_stock = {}   # shortage/high_risk SKUs → exact stock for snapshot


def get_effective_stock(sku: str) -> int:
    return max(0, inventory_state[sku] - pending_units[sku])


def apply_restock(sku: str):
    inventory_state[sku] += random.randint(100, 300)


# ── Order generator ────────────────────────────────────────────────────────────

def make_order(scenario: str) -> dict:
    global order_counter
    now = datetime.now(timezone.utc)
    order_counter += random.randint(1, 9)
    clean_order_id = f"ORD-{order_counter}"

    if scenario in ("inventory_shortage", "high_risk", "competing_orders"):
        stressed = [s for s in SKUS if get_effective_stock(s) < 60]
        sku = random.choice(stressed) if stressed else random.choice(SKUS)
    else:
        sku = random.choice(SKUS)

    eff  = get_effective_stock(sku)
    cur  = inventory_state[sku]
    pend = pending_units[sku]

    expected_risks = []
    payload = {
        "order_id":    dirty_order_id(clean_order_id),
        "customer_id": random.choice(CUSTOMERS),
        "sku":         dirty_sku(sku),
        "order_date":  now.isoformat(),
    }

    if scenario == "normal":
        quantity = random.randint(1, max(1, eff // 4))
        payload["quantity"] = quantity
        payload["expected_ship_date"] = (now + timedelta(days=random.randint(3, 7))).isoformat()
        pending_units[sku] += quantity

    elif scenario == "inventory_shortage":
        stock = random.randint(10, 50)
        inventory_state[sku] = stock
        controlled_stock[sku] = stock
        quantity = stock + random.randint(20, 100)
        payload["quantity"] = quantity
        # wide ship window — no shipment_delay expected
        payload["expected_ship_date"] = (now + timedelta(days=5)).isoformat()
        expected_risks.append("inventory_shortage")

    elif scenario == "shipment_delay":
        quantity = random.randint(1, max(1, eff // 4))
        payload["quantity"] = quantity
        past_date = now - timedelta(days=random.randint(1, 4))
        payload["expected_ship_date"] = past_date.isoformat()
        expected_risks.append("shipment_delay")
        expected_risks.append("sla_violation")
        pending_units[sku] += quantity

    elif scenario == "sla_breach":
        quantity = random.randint(1, 5)
        payload["quantity"] = quantity
        tight_date = now + timedelta(hours=random.randint(1, 3))
        payload["expected_ship_date"] = tight_date.isoformat()
        expected_risks.append("sla_violation")
        expected_risks.append("shipment_delay")
        pending_units[sku] += quantity

    elif scenario == "high_risk":
        stock = random.randint(10, 50)
        inventory_state[sku] = stock
        controlled_stock[sku] = stock
        quantity = stock + random.randint(50, 200)
        payload["quantity"] = quantity
        tight_date = now + timedelta(hours=random.randint(1, 3))
        payload["expected_ship_date"] = tight_date.isoformat()
        expected_risks.append("inventory_shortage")
        expected_risks.append("sla_violation")
        expected_risks.append("shipment_delay")

    elif scenario == "competing_orders":
        quantity = eff + random.randint(5, 30)
        payload["quantity"] = quantity
        payload["expected_ship_date"] = (now + timedelta(days=3)).isoformat()
        expected_risks.append("inventory_shortage")

    elif scenario == "post_restock":
        apply_restock(sku)
        eff = get_effective_stock(sku)
        quantity = random.randint(1, max(1, eff // 5))
        payload["quantity"] = quantity
        payload["expected_ship_date"] = (now + timedelta(days=3)).isoformat()
        pending_units[sku] += quantity

    elif scenario == "dirty_data":
        payload["order_id"] = f"order #{random.randint(1000, 9999)}"
        payload["sku"] = f"sku.{random.choice(['elec','furn','appl'])}.{random.randint(1,3)}"
        payload["quantity"] = random.randint(1, 15)
        payload["expected_ship_date"] = (now + timedelta(days=3)).isoformat()

    elif scenario == "duplicate":
        payload["order_id"]    = "ORD-99999"
        payload["customer_id"] = "CUST-0001"
        payload["sku"]         = "SKU-ELEC-001"
        payload["quantity"]    = 5
        payload["expected_ship_date"] = (now + timedelta(days=3)).isoformat()

    context = {
        "stock_at_time_of_order":  cur,
        "pending_units_at_time":   pend,
        "effective_stock_at_time": eff,
    }

    return {
        "scenario":       scenario,
        "expected_risks": expected_risks,
        "context":        context,
        "payload":        payload,
    }


# ── Inventory snapshot ─────────────────────────────────────────────────────────

def make_inventory_snapshot() -> list:
    now = datetime.now(timezone.utc)
    records = []

    for sku in SKUS:
        stock   = controlled_stock.get(sku, inventory_state[sku])
        reorder = random.randint(20, 60)

        if stock == 0:
            inv_scenario = "out_of_stock"
            eta = (now + timedelta(days=random.randint(5, 14))).isoformat()
        elif stock < 30:
            inv_scenario = "low_stock"
            eta = (now + timedelta(days=random.randint(3, 10))).isoformat()
        else:
            inv_scenario = "normal"
            eta = None

        records.append({
            "scenario": inv_scenario,
            "payload": {
                "sku":               dirty_sku(sku),
                "warehouse_id":      random.choice(WAREHOUSES),
                "stock_level":       stock,
                "reorder_threshold": reorder,
                "supplier_eta":      eta,
            }
        })

    return records


# ── Shipment generator ─────────────────────────────────────────────────────────

def make_shipment(order_record: dict) -> dict:
    now      = datetime.now(timezone.utc)
    payload  = order_record["payload"]
    scenario = order_record["scenario"]
    order_id = payload["order_id"]

    status = random.choice(["processing", "picked", "in_transit"])

    if scenario in ("shipment_delay", "high_risk"):
        try:
            expected = datetime.fromisoformat(payload["expected_ship_date"])
        except Exception:
            expected = now
        # ETA guaranteed meaningfully AFTER expected (>1 day)
        eta = expected + timedelta(days=random.randint(2, 5))

    elif scenario == "sla_breach":
        # ETA 3-6 days — always far past the 1-3 hour window
        eta = now + timedelta(days=random.randint(3, 6))

    elif scenario == "inventory_shortage":
        # wide window (5 days) — ETA guaranteed before expected, no shipment_delay
        try:
            expected = datetime.fromisoformat(payload["expected_ship_date"])
            eta = expected - timedelta(hours=random.randint(12, 48))
            if eta < now:
                eta = now + timedelta(hours=random.randint(6, 24))
        except Exception:
            eta = now + timedelta(days=2)

    else:
        # normal/post_restock/competing_orders/dirty_data/duplicate
        # ETA guaranteed at least 12 hours BEFORE expected — no false shipment_delay
        try:
            expected = datetime.fromisoformat(payload["expected_ship_date"])
            eta = expected - timedelta(hours=random.randint(12, 48))
            if eta < now:
                eta = now + timedelta(hours=random.randint(6, 24))
        except Exception:
            eta = now + timedelta(days=2)

    return {
        "scenario": scenario,
        "payload": {
            "shipment_id": f"SHP-{random.randint(100000, 999999)}",
            "order_id":    order_id,
            "carrier":     random.choice(CARRIERS),
            "status":      status,
            "eta":         eta.isoformat(),
        }
    }


# ── Dataset builder ────────────────────────────────────────────────────────────

def generate_dataset():
    order_scenarios = [
        ("normal",             35),
        ("inventory_shortage", 12),
        ("shipment_delay",     12),
        ("sla_breach",          8),
        ("high_risk",           8),
        ("competing_orders",    8),
        ("post_restock",        5),
        ("dirty_data",          8),
        ("duplicate",           2),
    ]

    orders = []
    for scenario, count in order_scenarios:
        for _ in range(count):
            orders.append(make_order(scenario))

    random.shuffle(orders)

    inventory = make_inventory_snapshot()
    shipments = [make_shipment(o) for o in orders]

    return {
        "orders":    orders,
        "inventory": inventory,
        "shipments": shipments,
    }


# ── Save ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    dataset = generate_dataset()

    with open("synthetic_data.json", "w") as f:
        json.dump(dataset, f, indent=2)

    from collections import Counter
    scenario_counts = Counter(o["scenario"] for o in dataset["orders"])
    risk_counts     = Counter(r for o in dataset["orders"] for r in o["expected_risks"])
    no_risk_count   = sum(1 for o in dataset["orders"] if not o["expected_risks"])

    print("✅  synthetic_data.json generated\n")
    print("📦  Orders by scenario:")
    for s, c in scenario_counts.most_common():
        print(f"    {s:<25} → {c}")

    print("\n⚠️   Expected risks distribution:")
    for r, c in risk_counts.most_common():
        print(f"    {r:<25} → {c}")
    print(f"    {'no_risk':<25} → {no_risk_count}")

    print(f"\n    Total orders    : {len(dataset['orders'])}")
    print(f"    Total inventory : {len(dataset['inventory'])}")
    print(f"    Total shipments : {len(dataset['shipments'])}")