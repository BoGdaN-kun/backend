# app/account/routes.py

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from trading_app.Models.UserModel import User
from trading_app.extensions import db

account_bp = Blueprint("account", __name__, url_prefix="/account")


@account_bp.route("/balance", methods=["GET"])
@jwt_required()
def get_balance():

    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    dollars = user.account.balance_cents / 100.0
    return jsonify({"balance": dollars}), 200


@account_bp.route("/deposit", methods=["POST"])
@jwt_required()
def deposit_money():

    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    amount = data.get("amount", 0)
    if amount <= 0:
        return jsonify({"error": "Invalid amount"}), 400

    cents = int(round(amount * 100))
    user.account.balance_cents += cents
    db.session.commit()

    return jsonify({"balance": user.account.balance_cents / 100.0}), 200


@account_bp.route("/withdraw", methods=["POST"])
@jwt_required()
def withdraw_money():

    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    amount = data.get("amount", 0)
    if amount <= 0:
        return jsonify({"error": "Invalid amount"}), 400

    cents = int(round(amount * 100))
    if user.account.balance_cents < cents:
        return jsonify({"error": "Insufficient funds"}), 400

    user.account.balance_cents -= cents
    db.session.commit()
    return jsonify({"balance": user.account.balance_cents / 100.0}), 200
