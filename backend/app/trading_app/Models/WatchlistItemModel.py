from trading_app.extensions import db
from sqlalchemy.orm import relationship

class WatchlistItem(db.Model):
    __tablename__ = "watchlist_items"

    id = db.Column(db.Integer, primary_key=True)
    watchlist_id = db.Column(db.Integer, db.ForeignKey("watchlists.id"), nullable=False)
    symbol = db.Column(db.String(20), nullable=False)

    watchlist = relationship("Watchlist", back_populates="items")