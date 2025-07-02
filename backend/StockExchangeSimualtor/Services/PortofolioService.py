from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from StockExchangeSimualtor.Models.Positions import Position
from StockExchangeSimualtor.Schemas.Position import PositionOut

portfolio_bp = Blueprint("portfolio", __name__, url_prefix="/portfolio")

@portfolio_bp.route("", methods=["GET"])
@jwt_required()
def get_portfolio():
    user_id = get_jwt_identity()
    positions = Position.query.filter_by(user_id=user_id).all()
    return jsonify([PositionOut.from_orm(p).dict() for p in positions]), 200


# @portfolio_bp.route("/<string:symbol>", methods=["GET"])
# @jwt_required()
# def get_position(symbol):
#     user_id = get_jwt_identity()
#     position = Position.query.filter_by(user_id=user_id, symbol=symbol).first()
#     if not position:
#         return jsonify({"error": "Position not found"}), 404
#     return jsonify(PositionOut.from_orm(position).dict()), 200

