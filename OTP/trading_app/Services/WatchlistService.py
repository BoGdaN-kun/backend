from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from trading_app.Models.UserModel import User
from trading_app.Models.WatchlistItemModel import WatchlistItem
from trading_app.Models.WatchlistModel import Watchlist
from trading_app.extensions import db

watchlists_bp = Blueprint("watchlists", __name__, url_prefix="/watchlists")


@watchlists_bp.route("", methods=["GET"])
@jwt_required()
def list_watchlists():
    """
    GET /watchlists
    Returns JSON array of all the user’s watchlists,
    each element: { "id": <id>, "name": "<name>", "item_count": <n> }
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    output = []
    for wl in user.watchlists:
        output.append({
            "id": wl.id,
            "name": wl.name,
            "item_count": len(wl.items)
        })
    return jsonify(output), 200


@watchlists_bp.route("", methods=["POST"])
@jwt_required()
def create_watchlist():
    """
    POST /watchlists
    Body: { "name": "Tech Stocks" }
    Returns: { "id": <new_id>, "name": "<name>" }
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Watchlist name is required"}), 400

    # Optionally: enforce per‐user unique names
    if Watchlist.query.filter_by(user_id=user_id, name=name).first():
        return jsonify({"error": "You already have a watchlist with that name"}), 400

    new_wl = Watchlist(name=name, user=user)
    db.session.add(new_wl)
    db.session.commit()
    return jsonify({"id": new_wl.id, "name": new_wl.name}), 201


@watchlists_bp.route("/<int:wl_id>", methods=["GET"])
@jwt_required()
def get_watchlist(wl_id):
    """
    GET /watchlists/<wl_id>
    Returns: { "id": <id>, "name": "<name>", "items": [ { "id": <item_id>, "symbol": "<SYM>" }, ... ] }
    """
    user_id = get_jwt_identity()
    wl = Watchlist.query.filter_by(id=wl_id, user_id=user_id).first()
    if not wl:
        return jsonify({"error": "Watchlist not found"}), 404

    items = []
    for item in wl.items:
        items.append({"id": item.id, "symbol": item.symbol})
    return jsonify({"id": wl.id, "name": wl.name, "items": items}), 200


@watchlists_bp.route("/<int:wl_id>/items", methods=["POST"])
@jwt_required()
def add_watchlist_item(wl_id):
    """
    POST /watchlists/<wl_id>/items
    Body: { "symbol": "AAPL" }
    Returns: { "id": <item_id>, "symbol": "<SYM>" }
    """
    user_id = get_jwt_identity()
    wl = Watchlist.query.filter_by(id=wl_id, user_id=user_id).first()
    if not wl:
        return jsonify({"error": "Watchlist not found"}), 404

    data = request.get_json()
    symbol = data.get("symbol", "").upper().strip()
    if not symbol:
        return jsonify({"error": "Symbol is required"}), 400

    # Optionally: no duplicates
    if WatchlistItem.query.filter_by(watchlist_id=wl.id, symbol=symbol).first():
        return jsonify({"error": "Symbol already in watchlist"}), 400

    item = WatchlistItem(watchlist=wl, symbol=symbol)
    db.session.add(item)
    db.session.commit()
    return jsonify({"id": item.id, "symbol": item.symbol}), 201


@watchlists_bp.route("/<int:wl_id>/items/<int:item_id>", methods=["DELETE"])
@jwt_required()
def delete_watchlist_item(wl_id, item_id):
    """
    DELETE /watchlists/<wl_id>/items/<item_id>
    """
    user_id = get_jwt_identity()
    wl = Watchlist.query.filter_by(id=wl_id, user_id=user_id).first()
    if not wl:
        return jsonify({"error": "Watchlist not found"}), 404

    item = WatchlistItem.query.filter_by(id=item_id, watchlist_id=wl_id).first()
    if not item:
        return jsonify({"error": "Watchlist item not found"}), 404

    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "Item removed"}), 200
