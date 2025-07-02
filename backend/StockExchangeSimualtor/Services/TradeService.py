from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from StockExchangeSimualtor.Models.Trade import Trade
from StockExchangeSimualtor.database import db
from StockExchangeSimualtor.Models.Order import Order

trades_bp = Blueprint("trades", __name__, url_prefix="/trades")
#
# @trades_bp.route("", methods=["GET"])
# @jwt_required()
# def list_trades():
#     user_id = get_jwt_identity()
#     trades = (
#         db.session.query(Trade)
#             .join(Order, (Trade.buy_order_id == Order.id) | (Trade.sell_order_id == Order.id))
#             .filter(Order.user_id == user_id)
#             .order_by(Trade.timestamp.desc())
#             .all()
#     )
#     out = []
#     for t in trades:
#         out.append({
#             "id": t.id,
#             "symbol": t.symbol,
#             "executed_qty": t.executed_qty,
#             "executed_price": t.executed_price_cents / 100.0,
#             "timestamp": t.timestamp.isoformat()
#         })
#     return jsonify(out), 200
@trades_bp.route("", methods=["GET"])
@jwt_required()
def list_trades():
    """
    GET /trades
    Returns a paginated list of the user's trades.
    Query Params:
    - page: The page number to retrieve (default: 1)
    - per_page: The number of items per page (default: 10)
    """
    user_id = get_jwt_identity()

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    # Base query to find all trades where the user was either the buyer or the seller
    trades_query = (
        db.session.query(Trade)
        .join(Order, (Trade.buy_order_id == Order.id) | (Trade.sell_order_id == Order.id))
        .filter(Order.user_id == user_id)
        .order_by(Trade.timestamp.desc())
    )


    paginated_trades = trades_query.paginate(page=page, per_page=per_page, error_out=False)
    trades = paginated_trades.items

    output_trades = []
    for t in trades:
        side = "buy" if t.buy_order and t.buy_order.user_id == int(user_id) else "sell"

        output_trades.append({
            "id": t.id,
            "symbol": t.symbol,
            "side": side,
            "quantity": t.executed_qty,
            "price": t.executed_price_cents / 100.0,
            "timestamp": t.timestamp.isoformat()
        })
    return jsonify({
        "trades": output_trades,
        "total": paginated_trades.total,
        "pages": paginated_trades.pages,
        "current_page": paginated_trades.page,
        "has_next": paginated_trades.has_next
    }), 200