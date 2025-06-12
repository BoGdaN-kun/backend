# app/schemas/trade.py

from pydantic import BaseModel
from datetime import datetime

class TradeOut(BaseModel):
    id: int
    symbol: str
    executed_qty: int
    executed_price: float
    timestamp: datetime
    model_config = {"from_attributes": True}