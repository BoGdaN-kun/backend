# app/services/matching.py

import requests
from datetime import datetime
# import os # os was unused
from flask import current_app
# from sqlalchemy import or_ # or_ was unused

from StockExchangeSimualtor.database import db
from StockExchangeSimualtor.Models.Order import Order, OrderTypeEnum, OrderStatusEnum, SideEnum
from StockExchangeSimualtor.Models.Trade import Trade
from StockExchangeSimualtor.Models.Positions import Position


def fetch_latest_price(symbol: str) -> int:
    # ... (no changes needed here)
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
                pos = Position(user_id=order.user_id, symbol=order.symbol, quantity=0)
                db.session.add(pos)
            pos.quantity += fill_qty
            # TODO: Debit actual cash from user's account (lock account, update balance)
        else:  # SELL
            if not pos or pos.quantity < fill_qty:
                # This check should ideally not fail if place_order was correct,
                # but as a safeguard for market orders.
                db.session.rollback()  # Rollback before raising
                current_app.logger.error(
                    f"Market SELL order {order.id}: Insufficient shares ({pos.quantity if pos else 0}) for {fill_qty} of {order.symbol}")
                raise RuntimeError(f"Insufficient shares for market SELL of {order.symbol}")
            pos.quantity -= fill_qty
            # TODO: Credit cash to user's account (lock account, update balance)

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
        # Determine matching criteria based on incoming order side
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
                Order.limit_price_cents >= incoming.limit_price_cents  # Seller wants price >= buyer's bid
            ).order_by(Order.limit_price_cents.desc(), Order.created_at.asc())

        # Lock the best opposite order to prevent other matchers from using it simultaneously
        best_opposite = best_opposite_query.with_for_update().first()

        if not best_opposite:
            break  # No compatible order found, incoming order remains on book (or part of it)

        # Determine fill quantity and price
        fill_qty = min(incoming.remaining_qty, best_opposite.remaining_qty)

        # Price is determined by the resting order (best_opposite) in a typical limit order book
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

            # Validate seller has enough shares (final check under lock)
            # This check is particularly for `best_opposite` if it's a sell order.
            # `incoming` (if it's a sell) should have passed rigorous checks in `place_order`.
            if not seller_pos or seller_pos.quantity < fill_qty:
                db.session.rollback()  # Release locks
                # This order (best_opposite) is problematic, maybe mark it or log.
                # For now, we can't fill against it. Try next opposite or break.
                current_app.logger.warning(
                    f"Match attempt for {incoming.id} with {best_opposite.id}: Seller {sell_order.user_id} has insufficient shares ({seller_pos.quantity if seller_pos else 0} < {fill_qty}) for {incoming.symbol}. Skipping this match.")
                # To prevent an infinite loop if this problematic order is always chosen,
                # one might need to temporarily ignore it or change its status.
                # For simplicity now, we just break this matching attempt and the outer loop might continue if incoming still has qty.
                # A better approach might be to invalidate/cancel `best_opposite` if it's consistently problematic.
                # If we `continue` here, it might find another best_opposite. If `break`, it stops for `incoming`.
                # Let's assume we should try to find another match if this one fails due to opponent's lack of shares.
                # This means we need to somehow exclude this `best_opposite` from the next query in this loop, which is hard.
                # So, if this happens, it means an inconsistent state. Raising an error might be better.
                raise RuntimeError(
                    f"Seller {sell_order.user_id} (order {sell_order.id}) has insufficient shares for fill quantity {fill_qty}")

            # Update Buyer's Position
            if not buyer_pos:
                buyer_pos = Position(user_id=buy_order.user_id, symbol=incoming.symbol, quantity=0)
                db.session.add(buyer_pos)
            buyer_pos.quantity += fill_qty
            # TODO: Debit/reserve cash for buyer

            # Update Seller's Position
            # (seller_pos is already fetched and validated above)
            seller_pos.quantity -= fill_qty
            # TODO: Credit cash to seller

            # Update orders
            buy_order.filled_quantity += fill_qty
            sell_order.filled_quantity += fill_qty

            buy_order.status = OrderStatusEnum.FILLED if buy_order.remaining_qty == 0 else OrderStatusEnum.PARTIAL
            sell_order.status = OrderStatusEnum.FILLED if sell_order.remaining_qty == 0 else OrderStatusEnum.PARTIAL

            # Create Trade record
            trade = Trade(
                buy_order_id=buy_order.id,
                sell_order_id=sell_order.id,
                symbol=incoming.symbol,
                executed_qty=fill_qty,
                executed_price_cents=executed_price_cents,
                timestamp=datetime.utcnow()
            )
            db.session.add(trade)

            db.session.commit()  # Commit all changes for this fill (positions, orders, trade)

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
            # Re-raise to be caught by the top-level try-except in place_order or propagate if called elsewhere
            raise
            # If we break here, the incoming order matching stops for this attempt.
            # break

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
