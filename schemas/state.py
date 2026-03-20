from typing import TypedDict, Optional, List


class RiskItem(TypedDict):
    type: str
    confidence: float
    reason: str
    source: str


class FulfillmentState(TypedDict):
    audit_id: str

    order: Optional[dict]
    inventory: Optional[dict]
    shipment: Optional[dict]

    normalized_order: Optional[dict]
    
    risks: Optional[List[RiskItem]]
    action: Optional[str]