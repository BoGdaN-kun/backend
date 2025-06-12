
from pydantic import BaseModel

class PositionOut(BaseModel):
    symbol: str
    quantity: int
    total_cost_cents: int = 0
    average_cost_price_cents: int = 0
    model_config = {"from_attributes": True}
