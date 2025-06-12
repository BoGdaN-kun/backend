# trading_app/__init__

from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from datetime import timedelta
from trading_app.Models.AccountModel import Account
from trading_app.Models.UserModel import User
from trading_app.Models.WatchlistModel import Watchlist
from trading_app.extensions import db
from trading_app.Utils import TimeOtpGenerator

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

@auth_bp.route("/register", methods=["POST"])
def register():
    """
    Expected JSON body:
      {
        "email": "...",
        "password": "...",
        "enable_2fa": true/false
      }
    """

    # Parse JSON body
    data = request.get_json()

    # Extract fields from JSON
    email = data.get("email")
    password = data.get("password")
    enable_2fa = data.get("enable_2fa", False)

    # Validate existence of email and password
    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    # Check existence
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "User already exists"}), 400

    # Create user
    user = User(email=email, otp_enabled=enable_2fa)
    user.set_password(password)

    if enable_2fa:
        secret = user.generate_otp_secret()
    else:
        secret = None

    # Create related rows: Account + default watchlist
    account = Account(user=user, balance_cents=0)
    default_wl = Watchlist(user=user, name="My Watchlist")

    db.session.add(user)
    db.session.add(account)
    db.session.add(default_wl)
    db.session.commit()

    # If 2FA, return provisioning URI so front-end can render a QR code
    if enable_2fa and secret:
        uri = TimeOtpGenerator.create_totp_uri(email=email, secret=secret, issuer_name="MyFlaskApp")
        return jsonify({"qr_uri": uri, "secret": secret}), 201

    return jsonify({"message": "User registered"}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Expected JSON body:
      {
        "email": "...",
        "password": "..."
      }
    """
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid credentials"}), 401

    if user.otp_enabled:
        # Signal front-end that OTP is required
        return jsonify({"message": "OTP required", "otp_required": True}), 200

    # No 2FA ⇒ issue JWT
    access_token = create_access_token(
        identity=str(user.id),
        expires_delta=timedelta(hours=2)
    )
    return jsonify({"access_token": access_token, "message": "Login successful"}), 200


@auth_bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    """
    Front-end will POST:
      {
        "email": "...",
        "otp": "123456"
      }
    If valid, issue JWT.
    """
    data = request.get_json()
    email = data.get("email")
    otp_code = data.get("otp")

    if not email or not otp_code:
        return jsonify({"error": "Email and OTP required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    if not user.verify_otp(otp_code):
        return jsonify({"error": "Invalid OTP"}), 401

    access_token = create_access_token(
        identity=str(user.id),
        expires_delta=timedelta(hours=2)
    )
    return jsonify({"access_token": access_token, "message": "OTP verified, login successful"}), 200
