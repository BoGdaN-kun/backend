from sqlalchemy.orm import relationship

from trading_app.extensions import db

class Account(db.Model):
    __tablename__ = "accounts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    balance_cents = db.Column(db.Integer, default=0)

    user = relationship("User", back_populates="account")