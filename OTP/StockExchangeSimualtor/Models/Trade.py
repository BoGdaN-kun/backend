from StockExchangeSimualtor.database import db
from datetime import datetime

class Trade(db.Model):
    __tablename__ = "trades"

    id = db.Column(db.Integer, primary_key=True, index=True)

    buy_order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=True)
    sell_order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=True)

    symbol = db.Column(db.String(20), nullable=False)
    executed_qty = db.Column(db.Integer, nullable=False)
    executed_price_cents = db.Column(db.Integer, nullable=False)  # per share, in cents

    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    buy_order = db.relationship("Order", foreign_keys=[buy_order_id], back_populates="buy_trades")
    sell_order = db.relationship("Order", foreign_keys=[sell_order_id], back_populates="sell_trades")