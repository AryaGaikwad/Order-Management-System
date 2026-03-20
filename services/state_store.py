from agents.normalization_agent import normalize_sku, normalize_order_id

orders = {}
inventory = {}
shipments = {}


def update_order(order: dict):
    clean_id = normalize_order_id(order["order_id"])
    orders[clean_id] = order


def update_inventory(inv: dict):
    clean_sku = normalize_sku(inv["sku"])
    inventory[clean_sku] = inv


def update_shipment(shipment: dict):
    clean_id = normalize_order_id(shipment["order_id"])
    shipments[clean_id] = shipment


def get_order(order_id: str):
    clean_id = normalize_order_id(order_id)
    return orders.get(clean_id)


def get_inventory(sku: str):
    clean_sku = normalize_sku(sku)
    return inventory.get(clean_sku)


def get_shipment(order_id: str):
    clean_id = normalize_order_id(order_id)
    return shipments.get(clean_id)