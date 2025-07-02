

from StockExchangeSimualtor.database import db
from datetime import datetime
import enum


class SideEnum(enum.Enum):
    BUY = "buy"
    SELL = "sell"


class OrderTypeEnum(enum.Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatusEnum(enum.Enum):
    OPEN = "open"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELED = "canceled"


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True, index=True)
    user_id = db.Column(db.Integer, index=True)  # from JWT
    symbol = db.Column(db.String(20), nullable=False, index=True)
    side = db.Column(db.Enum(SideEnum), nullable=False)
    type = db.Column(db.Enum(OrderTypeEnum), nullable=False, default=OrderTypeEnum.MARKET)

    quantity = db.Column(db.Integer, nullable=False)
    filled_quantity = db.Column(db.Integer, nullable=False, default=0)

    limit_price_cents = db.Column(db.Integer, nullable=True)

    @property
    def limit_price(self) -> float:
        if self.limit_price_cents is None:
            return None
        return self.limit_price_cents / 100.0

    status = db.Column(db.Enum(OrderStatusEnum), nullable=False, default=OrderStatusEnum.OPEN)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # relationships
    buy_trades = db.relationship("Trade", back_populates="buy_order", foreign_keys="Trade.buy_order_id")
    sell_trades = db.relationship("Trade", back_populates="sell_order", foreign_keys="Trade.sell_order_id")

    @property
    def remaining_qty(self) -> int:
        return self.quantity - self.filled_quantity
