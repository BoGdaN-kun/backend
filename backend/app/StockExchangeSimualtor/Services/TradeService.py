# app/routes/trades.py

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from StockExchangeSimualtor.Models.Trade import Trade
from StockExchangeSimualtor.database import db
from StockExchangeSimualtor.Models.Order import Order

trades_bp = Blueprint("trades", __name__, url_prefix="/trades")

@trades_bp.route("", methods=["GET"])
@jwt_required()
def list_trades():
    user_id = get_jwt_identity()
    trades = (
        db.session.query(Trade)
            .join(Order, (Trade.buy_order_id == Order.id) | (Trade.sell_order_id == Order.id))
            .filter(Order.user_id == user_id)
            .order_by(Trade.timestamp.desc())
            .all()
    )
    out = []
    for t in trades:
        out.append({
            "id": t.id,
            "symbol": t.symbol,
            "executed_qty": t.executed_qty,
            "executed_price": t.executed_price_cents / 100.0,
            "timestamp": t.timestamp.isoformat()
        })
    return jsonify(out), 200
