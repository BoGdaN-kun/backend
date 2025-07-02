import requests
from datetime import datetime

from StockExchangeSimualtor.database import db
from StockExchangeSimualtor.Models.Order import Order, OrderTypeEnum, OrderStatusEnum, SideEnum
from StockExchangeSimualtor.Models.Trade import Trade
from StockExchangeSimualtor.Models.Positions import Position
from flask import current_app, request as flask_request

USER_SERVICE_URL = "http://localhost:5000"


def _update_cash_balance(user_id: int, amount_cents: int, action: str):
    """
    Calls the user service to update a user's cash balance.
    :param user_id: The ID of the user whose balance will change.
    :param amount_cents: The amount in cents to deposit or withdraw. Must be positive.
    :param action: Either 'deposit' or 'withdraw'.
    """
    if action not in ['deposit', 'withdraw']:
        raise ValueError("Invalid action for cash update.")

    auth_header = flask_request.headers.get('Authorization')
    if not auth_header:
        current_app.logger.error(
            f"Cannot update cash for user {user_id}: Authorization header is missing in the original request.")
        raise RuntimeError("Missing Authorization for inter-service communication.")

    headers = {
        "Authorization": auth_header,
        "Content-Type": "application/json"
    }
    payload = {"amount": amount_cents / 100.0}
    endpoint = f"{USER_SERVICE_URL}/account/{action}"

    try:
        response = requests.post(endpoint, json=payload, headers=headers)
        response.raise_for_status()
        current_app.logger.info(f"Successfully posted {action} of ${payload['amount']:.2f} for user_id {user_id}")
    except requests.exceptions.RequestException as e:

        current_app.logger.critical(
            f"FAILED to {action} cash for user_id {user_id}. Amount: {payload['amount']}. Error: {e}. "
            f"Response: {e.response.text if e.response else 'N/A'}. "
            "SYSTEM IS IN AN INCONSISTENT STATE!"
        )

        raise RuntimeError("Failed to update user cash balance.")


def fetch_latest_price(symbol: str) -> int:
    url = current_app.config["MARKET_FEED_URL"]
    resp = requests.get(url)
    if resp.status_code != 200:
        current_app.logger.error(f"Market-feed returned {resp.status_code} for {symbol}: {resp.text}")
        raise RuntimeError(f"Market-feed returned {resp.status_code}")
    data = resp.json()
    if not data:
        current_app.logger.error(f"No candles returned from market-feed for {symbol}")
        raise RuntimeError("No candles returned from market-feed")
    latest = data[-1]
    return int(round(latest["close"] * 100))


def execute_market_order(order: Order):
    price_cents = fetch_latest_price(order.symbol)
    fill_qty = order.quantity  # Market orders are typically filled completely if possible

    # Create Trade record first
    trade = Trade(
        buy_order_id=(order.id if order.side == SideEnum.BUY else None),
        sell_order_id=(order.id if order.side == SideEnum.SELL else None),
        symbol=order.symbol,
        executed_qty=fill_qty,
        executed_price_cents=price_cents,
        timestamp=datetime.utcnow()
    )
    db.session.add(trade)

    # Update Order status
    order.filled_quantity = fill_qty
    order.status = OrderStatusEnum.FILLED

    # Update Position (with row-level lock)
    try:
        # Lock the position row for update
        pos = db.session.query(Position).filter_by(user_id=order.user_id, symbol=order.symbol).with_for_update().first()

        if order.side == SideEnum.BUY:
            if not pos:
                pos = Position(user_id=order.user_id, symbol=order.symbol, quantity=0, total_cost_cents=0)
                db.session.add(pos)
            pos.quantity += fill_qty
            pos.total_cost_cents += fill_qty * price_cents
            # TODO: Debit actual cash from user's account (lock account, update balance) - done
            #_update_cash_balance(order.user_id, fill_qty * price_cents, 'withdraw')
        else:  # SELL
            if not pos or pos.quantity < fill_qty:
                # This check should ideally not fail if place_order was correct,
                # but as a safeguard for market orders.
                db.session.rollback()  # Rollback before raising
                current_app.logger.error(
                    f"Market SELL order {order.id}: Insufficient shares ({pos.quantity if pos else 0}) for {fill_qty} of {order.symbol}")
                raise RuntimeError(f"Insufficient shares for market SELL of {order.symbol}")
            if pos.quantity > 0:  # Ensure no division by zero if quantity is already 0 (should be caught by earlier check)
                average_cost_at_sale_cents = pos.total_cost_cents / pos.quantity
                cost_of_goods_sold_cents = fill_qty * average_cost_at_sale_cents
                pos.total_cost_cents -= int(round(cost_of_goods_sold_cents))
            else:  # Should ideally not happen if pos.quantity < fill_qty check is robust
                pos.total_cost_cents = 0
            pos.quantity -= fill_qty
            if pos.quantity == 0:
                pos.total_cost_cents = 0  # Reset cost if all shares sold
            # TODO: Credit cash to user's account (lock account, update balance) - DONE
            #_update_cash_balance(order.user_id, fill_qty * price_cents, 'deposit')

        db.session.commit()  # Commit all changes (Trade, Order status, Position)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error processing market order {order.id} position update: {str(e)}", exc_info=True)
        raise  # Re-raise the exception to be caught by the caller in orders_bp

    return {  # Not explicitly used by place_order but good to return info
        "trade_id": trade.id,
        "executed_price_cents": price_cents,
        "filled_qty": fill_qty
    }


def match_limit_order(incoming: Order):
    trades_executed = []

    while incoming.remaining_qty > 0:

        if incoming.side == SideEnum.BUY:
            best_opposite_query = db.session.query(Order).filter(
                Order.symbol == incoming.symbol,
                Order.side == SideEnum.SELL,
                Order.type == OrderTypeEnum.LIMIT,
                Order.status.in_([OrderStatusEnum.OPEN, OrderStatusEnum.PARTIAL]),
                Order.limit_price_cents <= incoming.limit_price_cents  # Buyer wants price <= seller's ask
            ).order_by(Order.limit_price_cents.asc(), Order.created_at.asc())
        else:  # incoming.side == SideEnum.SELL
            best_opposite_query = db.session.query(Order).filter(
                Order.symbol == incoming.symbol,
                Order.side == SideEnum.BUY,
                Order.type == OrderTypeEnum.LIMIT,
                Order.status.in_([OrderStatusEnum.OPEN, OrderStatusEnum.PARTIAL]),
                Order.limit_price_cents >= incoming.limit_price_cents
            ).order_by(Order.limit_price_cents.desc(), Order.created_at.asc())

        best_opposite = best_opposite_query.with_for_update().first()

        if not best_opposite:
            break

        fill_qty = min(incoming.remaining_qty, best_opposite.remaining_qty)

        executed_price_cents = best_opposite.limit_price_cents

        # Determine buyer and seller
        buy_order = incoming if incoming.side == SideEnum.BUY else best_opposite
        sell_order = incoming if incoming.side == SideEnum.SELL else best_opposite

        try:
            # Lock positions for both buyer and seller
            buyer_pos = db.session.query(Position).filter_by(user_id=buy_order.user_id,
                                                             symbol=incoming.symbol).with_for_update().first()
            seller_pos = db.session.query(Position).filter_by(user_id=sell_order.user_id,
                                                              symbol=incoming.symbol).with_for_update().first()

            if not seller_pos or seller_pos.quantity < fill_qty:
                db.session.rollback()  # Release locks

                current_app.logger.warning(
                    f"Match attempt for {incoming.id} with {best_opposite.id}: Seller {sell_order.user_id} has insufficient shares ({seller_pos.quantity if seller_pos else 0} < {fill_qty}) for {incoming.symbol}. Skipping this match.")

                raise RuntimeError(
                    f"Seller {sell_order.user_id} (order {sell_order.id}) has insufficient shares for fill quantity {fill_qty}")

            trade_value_cents = fill_qty * executed_price_cents
            if not buyer_pos:
                buyer_pos = Position(user_id=buy_order.user_id, symbol=incoming.symbol, quantity=0, total_cost_cents=0)
                db.session.add(buyer_pos)
            buyer_pos.quantity += fill_qty
            buyer_pos.total_cost_cents += fill_qty * executed_price_cents
            #_update_cash_balance(buyer_pos.user_id, trade_value_cents, 'withdraw')

            if seller_pos.quantity > 0:
                average_cost_at_sale_cents = seller_pos.total_cost_cents / seller_pos.quantity
                cost_of_goods_sold_cents = fill_qty * average_cost_at_sale_cents
                seller_pos.total_cost_cents -= int(round(cost_of_goods_sold_cents))
            else:
                seller_pos.total_cost_cents = 0
            seller_pos.quantity -= fill_qty
            if seller_pos.quantity == 0:
                seller_pos.total_cost_cents = 0  # Reset cost if all shares sold
            #_update_cash_balance(seller_pos.user_id, trade_value_cents, 'deposit')
            buy_order.filled_quantity += fill_qty
            sell_order.filled_quantity += fill_qty

            buy_order.status = OrderStatusEnum.FILLED if buy_order.remaining_qty == 0 else OrderStatusEnum.PARTIAL
            sell_order.status = OrderStatusEnum.FILLED if sell_order.remaining_qty == 0 else OrderStatusEnum.PARTIAL

            trade = Trade(
                buy_order_id=buy_order.id,
                sell_order_id=sell_order.id,
                symbol=incoming.symbol,
                executed_qty=fill_qty,
                executed_price_cents=executed_price_cents,
                timestamp=datetime.utcnow()
            )
            db.session.add(trade)

            db.session.commit()

            trades_executed.append({
                "trade_id": trade.id,
                "price_cents": executed_price_cents,
                "quantity": fill_qty,
                "buy_order_id": buy_order.id,
                "sell_order_id": sell_order.id
            })

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"Error during limit order matching fill (incoming: {incoming.id}, opposite: {best_opposite.id if best_opposite else 'N/A'}): {str(e)}",
                exc_info=True)
            raise

    return trades_executed
# # app/services/matching.py
#
# import requests
# from datetime import datetime
# import os
# from flask import current_app
# from sqlalchemy import or_
#
# from StockExchangeSimualtor.database import db
# from StockExchangeSimualtor.Models.Order import Order, OrderTypeEnum, OrderStatusEnum, SideEnum
# from StockExchangeSimualtor.Models.Trade import Trade
# from StockExchangeSimualtor.Models.Positions import Position
#
# def fetch_latest_price(symbol: str) -> int:
#     """
#     GET the latest candle from the Market‐Feed (configured in current_app.config["MARKET_FEED_URL"])
#     and return the close in integer cents.
#     """
#     url = current_app.config["MARKET_FEED_URL"]
#     resp = requests.get(url)
#     if resp.status_code != 200:
#         raise RuntimeError(f"Market‐feed returned {resp.status_code}: {resp.text}")
#     data = resp.json()
#     if not data:
#         raise RuntimeError("No candles returned from market‐feed")
#     latest = data[-1]
#     return int(round(latest["close"] * 100))
#
#
# def execute_market_order(order: Order):
#     """
#     Instantly fill a market order at the latest price. Updates DB.
#     """
#     price_cents = fetch_latest_price(order.symbol)
#     fill_qty = order.quantity
#
#     trade = Trade(
#         buy_order_id=(order.id if order.side == SideEnum.BUY else None),
#         sell_order_id=(order.id if order.side == SideEnum.SELL else None),
#         symbol=order.symbol,
#         executed_qty=fill_qty,
#         executed_price_cents=price_cents,
#         timestamp=datetime.utcnow()
#     )
#     db.session.add(trade)
#
#     order.filled_quantity = fill_qty
#     order.status = OrderStatusEnum.FILLED
#
#     user = order.user_id
#     pos = Position.query.filter_by(user_id=user, symbol=order.symbol).first()
#     if order.side == SideEnum.BUY:
#         if not pos:
#             pos = Position(user_id=user, symbol=order.symbol, quantity=0)
#             db.session.add(pos)
#         pos.quantity += fill_qty
#     else:  # SELL
#         if not pos or pos.quantity < fill_qty:
#             raise RuntimeError("Insufficient shares for market SELL")
#         pos.quantity -= fill_qty
#
#     db.session.commit()
#     return {
#         "trade_id": trade.id,
#         "executed_price_cents": price_cents,
#         "filled_qty": fill_qty
#     }
#
#
# def match_limit_order(incoming: Order):
#     """
#     Repeatedly match an incoming limit order against existing opposite‐side limit orders.
#     """
#     trades_executed = []
#
#     while incoming.remaining_qty > 0:
#         if incoming.side == SideEnum.BUY:
#             best_opposite = Order.query.filter(
#                 Order.symbol == incoming.symbol,
#                 Order.side == SideEnum.SELL,
#                 Order.type == OrderTypeEnum.LIMIT,
#                 Order.status.in_([OrderStatusEnum.OPEN, OrderStatusEnum.PARTIAL]),
#                 Order.limit_price_cents <= incoming.limit_price_cents
#             ).order_by(Order.limit_price_cents.asc(), Order.created_at.asc()).first()
#         else:  # incoming.side == SELL
#             best_opposite = Order.query.filter(
#                 Order.symbol == incoming.symbol,
#                 Order.side == SideEnum.BUY,
#                 Order.type == OrderTypeEnum.LIMIT,
#                 Order.status.in_([OrderStatusEnum.OPEN, OrderStatusEnum.PARTIAL]),
#                 Order.limit_price_cents >= incoming.limit_price_cents
#             ).order_by(Order.limit_price_cents.desc(), Order.created_at.asc()).first()
#
#         if not best_opposite:
#             break  # no compatible order
#
#         fill_qty = min(incoming.remaining_qty, best_opposite.remaining_qty)
#         executed_price_cents = best_opposite.limit_price_cents
#
#         buy_id  = incoming.id if incoming.side == SideEnum.BUY else best_opposite.id
#         sell_id = best_opposite.id if incoming.side == SideEnum.BUY else incoming.id
#
#         trade = Trade(
#             buy_order_id=buy_id,
#             sell_order_id=sell_id,
#             symbol=incoming.symbol,
#             executed_qty=fill_qty,
#             executed_price_cents=executed_price_cents,
#             timestamp=datetime.utcnow()
#         )
#         db.session.add(trade)
#
#         incoming.filled_quantity += fill_qty
#         best_opposite.filled_quantity += fill_qty
#
#         best_opposite.status = (OrderStatusEnum.FILLED
#                                 if best_opposite.remaining_qty == 0
#                                 else OrderStatusEnum.PARTIAL)
#         incoming.status = (OrderStatusEnum.FILLED
#                           if incoming.remaining_qty == 0
#                           else OrderStatusEnum.PARTIAL)
#
#         buyer_id  = buy_id
#         seller_id = sell_id
#
#         buyer_pos = Position.query.filter_by(user_id=buyer_id, symbol=incoming.symbol).first()
#         if not buyer_pos:
#             buyer_pos = Position(user_id=buyer_id, symbol=incoming.symbol, quantity=0)
#             db.session.add(buyer_pos)
#         buyer_pos.quantity += fill_qty
#
#         seller_pos = Position.query.filter_by(user_id=seller_id, symbol=incoming.symbol).first()
#         if not seller_pos or seller_pos.quantity < fill_qty:
#             raise RuntimeError("Seller has insufficient shares")
#         seller_pos.quantity -= fill_qty
#
#         db.session.commit()
#         trades_executed.append({
#             "trade_id": trade.id,
#             "price_cents": executed_price_cents,
#             "quantity": fill_qty
#         })
#
#     return trades_executed
