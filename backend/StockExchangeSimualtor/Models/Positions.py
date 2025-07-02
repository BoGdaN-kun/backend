from StockExchangeSimualtor.database import db

class Position(db.Model):
    __tablename__ = "positions"

    id = db.Column(db.Integer, primary_key=True, index=True)
    user_id = db.Column(db.Integer, index=True)
    symbol = db.Column(db.String(20), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)

    total_cost_cents = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (
        db.UniqueConstraint("user_id", "symbol", name="uix_user_symbol"),
    )

    @property
    def average_cost_price_cents(self):
        """
        Calculates the average cost price per share in cents.
        Returns 0 if quantity is 0 to avoid division by zero.
        """
        if self.quantity == 0:
            return 0
        return self.total_cost_cents // self.quantity

    def __repr__(self):
        return f"<Position user_id={self.user_id} symbol='{self.symbol}' quantity={self.quantity} avg_cost={self.average_cost_price_cents / 100.0 if self.quantity > 0 else 0}>"
