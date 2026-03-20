from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class OrderEvent(BaseModel):
    order_id: str
    customer_id: str
    sku: str
    quantity: int
    order_date: datetime
    expected_ship_date: datetime


class InventoryEvent(BaseModel):
    sku: str
    warehouse_id: str
    stock_level: int
    reorder_threshold: int
    supplier_eta: Optional[datetime] = None


class ShipmentEvent(BaseModel):
    shipment_id: str
    order_id: str
    carrier: str
    status: str
    eta: Optional[datetime] = None