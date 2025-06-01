
from pydantic import BaseModel

class PositionOut(BaseModel):
    symbol: str
    quantity: int
    model_config = {"from_attributes": True}
