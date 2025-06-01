# app/routes/orders.py

from flask import Blueprint, request, jsonify, current_app  # Added current_app for logging
from flask_jwt_extended import jwt_required, get_jwt_identity
from StockExchangeSimualtor.database import db
from StockExchangeSimualtor.Models.Order import Order, SideEnum, OrderTypeEnum, OrderStatusEnum
from StockExchangeSimualtor.Schemas.order import OrderCreate, OrderOut  # Assuming OrderOut is pydantic model
from StockExchangeSimualtor.Services.Matching import execute_market_order, match_limit_order
from StockExchangeSimualtor.Models.Positions import Position

orders_bp = Blueprint("orders", __name__, url_prefix="/orders")


@orders_bp.route("", methods=["POST"])
@jwt_required()
def place_order():
    user_id = get_jwt_identity()
    body = request.get_json() or {}
    try:
        oc = OrderCreate(**body)  # Validate payload using pydantic schema
    except Exception as e:
        # Consider using pydantic's ValidationError for more specific error messages
        return jsonify({"error": f"Invalid payload: {str(e)}"}), 400

    symbol = oc.symbol.upper().strip()
    side = SideEnum(oc.side)
    otype = OrderTypeEnum(oc.type)
    qty = oc.quantity

    if qty <= 0:
        return jsonify({"error": "Quantity must be a positive integer"}), 400

    limit_price_cents = None
    if otype == OrderTypeEnum.LIMIT:
        if oc.limit_price is None or oc.limit_price <= 0:
            return jsonify({"error": "limit_price must be > 0 for limit orders"}), 400
        limit_price_cents = int(round(oc.limit_price * 100))
    elif otype == OrderTypeEnum.MARKET and side == SideEnum.BUY:
        # For market buys, market_price might be used as a spending cap estimate if provided
        if oc.market_price is not None and oc.market_price <= 0:
            return jsonify({"error": "market_price, if provided for market buy, must be > 0"}), 400
        # Actual execution price for market orders is determined by the market_feed or matching logic

    # --- Side-specific checks and locking ---
    if side == SideEnum.SELL:
        try:
            # Lock the Position row for this user and symbol for the duration of this transaction block.
            # This makes the check-then-act atomic regarding share quantity.
            pos = db.session.query(Position).filter_by(user_id=user_id, symbol=symbol).with_for_update().first()

            total_owned = pos.quantity if pos else 0

            if not pos and qty > 0:  # No position record implies 0 shares owned
                db.session.rollback()  # Release lock
                return jsonify({"error": f"Insufficient free shares (0) for {symbol} to sell {qty}"}), 400

            # Calculate shares already committed in other open/partial sell orders
            committed_in_open_orders = sum(
                o.quantity - o.filled_quantity for o in db.session.query(Order)
                .filter_by(user_id=user_id, symbol=symbol, side=SideEnum.SELL)
                .filter(Order.status.in_([OrderStatusEnum.OPEN, OrderStatusEnum.PARTIAL]))
                .all()
            )

            free_shares = total_owned - committed_in_open_orders

            if free_shares < qty:
                db.session.rollback()  # Release lock
                return jsonify({"error": f"Insufficient free shares ({free_shares}) for {symbol} to sell {qty}"}), 400

            # If we reach here, share check is OK. Lock is still held.
            # The new order will be created and committed as part of this transaction.

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"SELL order pre-check error for user {user_id}, symbol {symbol}: {str(e)}",
                                     exc_info=True)
            return jsonify({"error": "Server error during share availability check."}), 500

    elif side == SideEnum.BUY:
        # TODO: Implement cash availability check for BUY orders.
        # This would involve locking the user's account/cash balance row with_for_update(),
        # checking if cash is sufficient, and then "reserving" or debiting it.
        # Example:
        # try:
        #   user_account = db.session.query(UserAccount).filter_by(user_id=user_id).with_for_update().first()
        #   required_cash = ... calculate based on order type, qty, price ...
        #   if user_account.cash_balance < required_cash:
        #       db.session.rollback()
        #       return jsonify({"error": "Insufficient cash"}), 400
        #   # If reserving: user_account.reserved_cash += required_cash
        # except Exception as e:
        #   db.session.rollback()
        #   current_app.logger.error(f"BUY order pre-check error: {str(e)}", exc_info=True)
        #   return jsonify({"error": "Server error during cash availability check."}), 500
        pass  # Assuming cash check passes for now

    # --- Create and commit the order ---
    # This happens after all side-specific checks have passed and locks (if any) are held.
    order_to_place = Order(
        user_id=user_id,
        symbol=symbol,
        side=side,
        type=otype,
        quantity=qty,
        filled_quantity=0,
        limit_price_cents=limit_price_cents,
        status=OrderStatusEnum.OPEN  # Initial status
    )
    db.session.add(order_to_place)

    try:
        db.session.commit()  # Commits the new Order. If SELL, also releases the Position lock.
        # If BUY, would release lock on cash balance if that was implemented.
        db.session.refresh(order_to_place)  # To get DB-generated values like ID, created_at
    except Exception as e:
        db.session.rollback()  # Rollback on commit failure
        current_app.logger.error(f"Error committing new order for user {user_id}, symbol {symbol}: {str(e)}",
                                 exc_info=True)
        return jsonify({"error": "Failed to save order to database."}), 500

    # --- Proceed to Matching Logic ---
    try:
        if otype == OrderTypeEnum.MARKET:
            execute_market_order(order_to_place)  # This function handles its own DB commits for fills
        else:  # LIMIT order
            match_limit_order(order_to_place)  # This function handles its own DB commits for fills

        db.session.refresh(order_to_place)  # Get the final state of the order after matching attempts
        return jsonify(OrderOut.from_orm(order_to_place).dict()), 201

    except RuntimeError as e:  # Catch specific errors from matching logic like "Seller has insufficient shares"
        current_app.logger.warning(
            f"Matching logic runtime error for order {order_to_place.id} (user {user_id}): {str(e)}", exc_info=True)
        # The order was placed successfully. The error is from the matching attempt.
        # The client should be informed that the order is on the book (if not fully filled and errored).
        db.session.refresh(order_to_place)  # Get current state of the order
        # Return 201 (created) because the order *is* on the books, but include matching issue info.
        # Alternatively, a 207 Multi-Status or a custom error structure.
        response_data = OrderOut.from_orm(order_to_place).dict()
        response_data["matching_error"] = str(e)
        return jsonify(response_data), 201  # Or 400/500 if matching error implies order should not have been accepted

    except Exception as e:  # Catch any other unexpected errors during matching
        db.session.rollback()  # Rollback any uncommitted changes from this request's matching attempt
        current_app.logger.error(
            f"Unexpected error during matching for order {order_to_place.id} (user {user_id}): {str(e)}", exc_info=True)
        # Order was placed, but matching failed catastrophically.
        # It's hard to recover state here perfectly without more complex transaction management.
        # The order remains as it was before matching was called.
        return jsonify(
            {"error": f"Order {order_to_place.id} placed, but an unexpected error occurred during matching."}), 500

# ... (rest of your orders_bp routes: list_orders, get_order, cancel_order)
# Ensure cancel_order also handles Position updates correctly if it frees up shares/cash.
# For example, when a SELL order is cancelled, the `committed_in_open_orders` effectively decreases.
# No direct Position table update is needed for cancellation of an un-filled order based on current logic,
# as `committed_in_open_orders` is dynamically calculated.
# # app/routes/orders.py
#
# from flask import Blueprint, request, jsonify
# from flask_jwt_extended import jwt_required, get_jwt_identity
# from StockExchangeSimualtor.database import db
# from StockExchangeSimualtor.Models.Order import Order, SideEnum, OrderTypeEnum, OrderStatusEnum
# from StockExchangeSimualtor.Schemas.order import OrderCreate, OrderOut
# from StockExchangeSimualtor.Services.Matching import execute_market_order, match_limit_order
# from StockExchangeSimualtor.Models.Positions import Position
#
# orders_bp = Blueprint("orders", __name__, url_prefix="/orders")
#
# @orders_bp.route("", methods=["POST"])
# @jwt_required()
# def place_order():
#     """
#     Place a new order (market or limit). The decorator @jwt_required() ensures
#     a valid JWT is present, and get_jwt_identity() returns the user_id.
#     """
#     user_id = get_jwt_identity()  # integer "sub" from the JWT
#
#     body = request.get_json() or {}
#     try:
#         oc = OrderCreate(**body)
#     except Exception as e:
#         return jsonify({"error": f"Invalid payload: {e}"}), 400
#
#     symbol = oc.symbol.upper().strip()
#     side = SideEnum(oc.side)
#     otype = OrderTypeEnum(oc.type)
#     qty = oc.quantity
#
#     limit_price_cents = None
#     if otype == OrderTypeEnum.LIMIT:
#         if oc.limit_price is None or oc.limit_price <= 0:
#             return jsonify({"error": "limit_price must be > 0 for limit orders"}), 400
#         limit_price_cents = int(round(oc.limit_price * 100))
#
#     if side == SideEnum.BUY:
#         if otype == OrderTypeEnum.MARKET:
#             if oc.market_price is None or oc.market_price <= 0:
#                 return jsonify({"error": "market_price is required for market orders"}), 400
#             market_price_cents = int(round(oc.market_price * 100))
#             total_cost = market_price_cents * qty
#         else:
#             total_cost = limit_price_cents * qty
#         # TODO: verify user has at least total_cost in cash via your account service
#     else:  # SELL
#         # 1) How many shares does the user own in total?
#         pos = Position.query.filter_by(user_id=user_id, symbol=symbol).first()
#         total_owned = pos.quantity if pos else 0
#
#         # 2) Sum up how many of those are already committed to open/partial sell orders
#         committed = 0
#         open_sells = (
#             Order.query
#             .filter_by(user_id=user_id, symbol=symbol, side=SideEnum.SELL)
#             .filter(Order.status.in_([OrderStatusEnum.OPEN, OrderStatusEnum.PARTIAL]))
#             .all()
#         )
#         for o in open_sells:
#             committed += (o.quantity - o.filled_quantity)
#
#         # 3) Compute how many “free” shares remain
#         free_shares = total_owned - committed
#
#         if free_shares < qty:
#             return jsonify({"error": f"Insufficient free shares ({free_shares}) to sell"}), 400
#
#     new_order = Order(
#         user_id=user_id,
#         symbol=symbol,
#         side=side,
#         type=otype,
#         quantity=qty,
#         filled_quantity=0,
#         limit_price_cents=limit_price_cents,
#         status=OrderStatusEnum.OPEN
#     )
#     db.session.add(new_order)
#     db.session.commit()
#     db.session.refresh(new_order)
#
#     try:
#         if otype == OrderTypeEnum.MARKET:
#             _ = execute_market_order(new_order)
#             return jsonify(OrderOut.from_orm(new_order).dict()), 201
#         else:
#             _ = match_limit_order(new_order)
#             return jsonify(OrderOut.from_orm(new_order).dict()), 201
#
#     except RuntimeError as e:
#         db.session.delete(new_order)
#         db.session.commit()
#         return jsonify({"error": str(e)}), 400
#
# # @orders_bp.route("", methods=["POST"])
# # @jwt_required()
# # def place_order():
# #     """
# #     Place a new order (market or limit). The decorator @jwt_required() ensures
# #     a valid JWT is present, and get_jwt_identity() returns the user_id.
# #     """
# #     user_id = get_jwt_identity()  # this will be the integer sub from the JWT
# #
# #     body = request.get_json() or {}
# #     try:
# #         oc = OrderCreate(**body)
# #     except Exception as e:
# #         return jsonify({"error": f"Invalid payload: {e}"}), 400
# #
# #     symbol = oc.symbol.upper().strip()
# #     side = SideEnum(oc.side)
# #     otype = OrderTypeEnum(oc.type)
# #     qty = oc.quantity
# #
# #     limit_price_cents = None
# #     if otype == OrderTypeEnum.LIMIT:
# #         if oc.limit_price is None or oc.limit_price <= 0:
# #             return jsonify({"error": "limit_price must be > 0 for limit orders"}), 400
# #         limit_price_cents = int(round(oc.limit_price * 100))
# #
# #     if side == SideEnum.BUY:
# #         if otype == OrderTypeEnum.MARKET:
# #             if oc.market_price is None or oc.market_price <= 0:
# #                 return jsonify({"error": "market_price is required for market orders"}), 400
# #             market_price_cents = int(round(oc.market_price * 100))
# #             total_cost = market_price_cents * qty
# #         else:
# #             total_cost = limit_price_cents * qty
# #         # TODO: verify user has at least total_cost in cash via your account service
# #     else:  # SELL
# #         pos = Position.query.filter_by(user_id=user_id, symbol=symbol).first()
# #         owned = pos.quantity if pos else 0
# #         if owned < qty:
# #             return jsonify({"error": f"Insufficient shares ({owned}) to sell"}), 400
# #
# #     new_order = Order(
# #         user_id=user_id,
# #         symbol=symbol,
# #         side=side,
# #         type=otype,
# #         quantity=qty,
# #         filled_quantity=0,
# #         limit_price_cents=limit_price_cents,
# #         status=OrderStatusEnum.OPEN
# #     )
# #     db.session.add(new_order)
# #     db.session.commit()
# #     db.session.refresh(new_order)
# #
# #     try:
# #         if otype == OrderTypeEnum.MARKET:
# #             _ = execute_market_order(new_order)
# #             return jsonify(OrderOut.from_orm(new_order).dict()), 201
# #         else:
# #             _ = match_limit_order(new_order)
# #             return jsonify(OrderOut.from_orm(new_order).dict()), 201
# #
# #     except RuntimeError as e:
# #         db.session.delete(new_order)
# #         db.session.commit()
# #         return jsonify({"error": str(e)}), 400
#
#
# @orders_bp.route("", methods=["GET"])
# @jwt_required()
# def list_orders():
#     user_id = get_jwt_identity()
#     orders = Order.query.filter_by(user_id=user_id).order_by(Order.created_at.desc()).all()
#     return jsonify([OrderOut.from_orm(o).dict() for o in orders]), 200
#
#
# @orders_bp.route("/<int:order_id>", methods=["GET"])
# @jwt_required()
# def get_order(order_id):
#     user_id = get_jwt_identity()
#     o = Order.query.filter_by(id=order_id, user_id=user_id).first()
#     if not o:
#         return jsonify({"error": "Order not found"}), 404
#     return jsonify(OrderOut.from_orm(o).dict()), 200
#
#
# @orders_bp.route("/<int:order_id>", methods=["DELETE"])
# @jwt_required()
# def cancel_order(order_id):
#     user_id = get_jwt_identity()
#     o = Order.query.filter_by(id=order_id, user_id=user_id).first()
#     if not o:
#         return jsonify({"error": "Order not found"}), 404
#
#     # Only allow cancellation if it’s still open or partial
#     if o.status not in (OrderStatusEnum.OPEN, OrderStatusEnum.PARTIAL):
#         return jsonify({"error": "Cannot cancel a filled or canceled order"}), 400
#
#     o.status = OrderStatusEnum.CANCELED
#     db.session.commit()
#     return jsonify({"message": f"Order {order_id} canceled"}), 200
