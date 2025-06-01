from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime

class Side(str, Enum):
    buy = "buy"
    sell = "sell"

class OrderType(str, Enum):
    market = "market"
    limit  = "limit"

class OrderStatus(str, Enum):
    open     = "open"
    partial  = "partial"
    filled   = "filled"
    canceled = "canceled"

class OrderCreate(BaseModel):
    symbol: str = Field(..., example="AAPL")
    side: Side = Field(..., example="buy")
    type: OrderType = Field(..., example="market")
    quantity: int = Field(..., gt=0, example=10)
    limit_price: Optional[float] = Field(
        None,
        example=130.50,
        description="Required if type is 'limit', in USD"
    )
    # For market orders, the client must send the current market_price
    market_price: Optional[float] = Field(
        None,
        example=130.55,
        description="Current price in USD"
    )

class OrderOut(BaseModel):
    id: int
    user_id: int
    symbol: str
    side: Side
    type: OrderType
    quantity: int
    filled_quantity: int
    limit_price: Optional[float]
    status: OrderStatus
    created_at: datetime

    model_config = {"from_attributes": True}
