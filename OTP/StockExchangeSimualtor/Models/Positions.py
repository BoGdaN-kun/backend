from StockExchangeSimualtor.database import db

class Position(db.Model):
    __tablename__ = "positions"

    id = db.Column(db.Integer, primary_key=True, index=True)
    user_id = db.Column(db.Integer, index=True)
    symbol = db.Column(db.String(20), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (
        db.UniqueConstraint("user_id", "symbol", name="uix_user_symbol"),
    )