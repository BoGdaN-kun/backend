import requests
import time
import threading
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Dict, Optional
import statistics

# ─── Configuration ─────────────────────────────────────────────────────────
USER_URL = "http://localhost:5000"
EXCHANGE_URL = "http://localhost:9000"

email = "alice@example.com"
password = "SecurePassword123"


# Login and get token
def get_auth_token():
    resp = requests.post(f"{USER_URL}/auth/login", json={
        "email": email,
        "password": password
    })
    resp.raise_for_status()
    return resp.json()["access_token"]


token = get_auth_token()
headers = {"Authorization": f"Bearer {token}"}


@dataclass
class OrderBook:
    bids: List[Dict]  # [{"price": 100.0, "quantity": 10}, ...]
    asks: List[Dict]  # [{"price": 101.0, "quantity": 5}, ...]

    @property
    def best_bid(self) -> Optional[float]:
        return max([b["price"] for b in self.bids]) if self.bids else None

    @property
    def best_ask(self) -> Optional[float]:
        return min([a["price"] for a in self.asks]) if self.asks else None

    @property
    def spread(self) -> Optional[float]:
        if self.best_bid and self.best_ask:
            return self.best_ask - self.best_bid
        return None


class HFTBot:
    def __init__(self, symbol: str = "AAPL"):
        self.symbol = symbol
        self.active = False
        self.order_history = []
        self.positions = {}
        self.latency_stats = []

    def api_call(self, path: str, method: str = "GET", payload: dict = None) -> dict:
        """Low-latency API call with timing"""
        start_time = time.perf_counter()
        url = f"{EXCHANGE_URL}{path}"

        try:
            if method == "POST":
                r = requests.post(url, json=payload, headers=headers, timeout=0.1)
            elif method == "DELETE":
                r = requests.delete(url, headers=headers, timeout=0.1)
            else:
                r = requests.get(url, headers=headers, params=payload, timeout=0.1)

            latency = (time.perf_counter() - start_time) * 1000  # ms
            self.latency_stats.append(latency)

            # Check for HTTP errors
            r.raise_for_status() # This will raise an exception for 4xx/5xx responses

            return r.json()
        except requests.exceptions.HTTPError as e:
            # This is where we catch 400, 404, 500 errors etc.
            try:
                error_json = r.json() # Try to parse the error response as JSON
                print(f"API Error: {e} - Server Response: {error_json}")
            except ValueError: # If it's not JSON
                print(f"API Error: {e} - Server Response (not JSON): {r.text}")
            return {}
        except Exception as e:
            print(f"API Error: {e}")
            return {}

    def get_orderbook(self) -> OrderBook:
        """Mock orderbook - replace with real orderbook endpoint if available"""
        # Simulate realistic orderbook data
        base_price = 130.0
        bids = [
            {"price": base_price - 0.01 * i, "quantity": random.randint(10, 100)}
            for i in range(1, 6)
        ]
        asks = [
            {"price": base_price + 0.01 * i, "quantity": random.randint(10, 100)}
            for i in range(1, 6)
        ]
        return OrderBook(bids=bids, asks=asks)

    def get_portfolio(self) -> Dict:
        """Get current positions"""
        portfolio = self.api_call("/portfolio")
        positions = {p["symbol"]: p["quantity"] for p in portfolio}
        return positions

    def place_order_fast(self, side: str, quantity: int, price: float, order_type: str = "limit") -> Optional[Dict]:
        """Ultra-fast order placement"""
        payload = {
            "symbol": self.symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }

        if order_type == "limit":
            payload["limit_price"] = price
        elif order_type == "market" and side == "buy":  # Only for BUY market orders
            payload["market_price"] = price  # Use the provided price as market_price

        # For SELL market orders, your server code does *not* explicitly check for market_price,
        # so it should not be included in the payload. The 'price' argument for SELL market orders
        # might be a dummy value in the HFT bot, as it's not used by the server's execute_market_order.

        return self.api_call("/orders", method="POST", payload=payload)

    def cancel_order_fast(self, order_id: int) -> bool:
        """Ultra-fast order cancellation"""
        result = self.api_call(f"/orders/{order_id}", method="DELETE")
        return bool(result)

    # ═══════════════════════════════════════════════════════════════════════════
    # HFT STRATEGY 1: MARKET MAKING
    # ═══════════════════════════════════════════════════════════════════════════
    def market_making_strategy(self, duration_seconds: int = 30):
        """
        Classic market making: continuously quote bid/ask to capture spread
        """
        print("🎯 Starting Market Making Strategy...")
        self.active = True
        start_time = time.time()
        active_orders = []

        try:
            while self.active and (time.time() - start_time) < duration_seconds:
                orderbook = self.get_orderbook()
                current_portfolio = self.get_portfolio()  # Fetch current portfolio
                current_aapl_shares = current_portfolio.get(self.symbol, 0)  # Get AAPL quantity

                if orderbook.best_bid and orderbook.best_ask:
                    # Cancel existing orders
                    for order_id in active_orders:
                        self.cancel_order_fast(order_id)
                    active_orders.clear()

                    mid_price = (orderbook.best_bid + orderbook.best_ask) / 2
                    our_bid = mid_price - 0.005
                    our_ask = mid_price + 0.005

                    # Place buy order
                    bid_order = self.place_order_fast("buy", 10, our_bid)
                    if bid_order and bid_order.get("id"):
                        active_orders.append(bid_order["id"])

                    # Place sell order only if we have shares to sell
                    if current_aapl_shares >= 10:  # Assuming selling 10 shares
                        ask_order = self.place_order_fast("sell", 10, our_ask)
                        if ask_order and ask_order.get("id"):
                            active_orders.append(ask_order["id"])
                    else:
                        print(
                            f"📊 Market Making: Skipping SELL order due to insufficient shares ({current_aapl_shares})")

                    print(f"📊 Market Making: Bid ${our_bid:.3f} | Ask ${our_ask:.3f} | Spread: ${orderbook.spread:.3f}")

                time.sleep(0.01)

        finally:
            # Cleanup
            for order_id in active_orders:
                self.cancel_order_fast(order_id)
            self.active = False

    # ═══════════════════════════════════════════════════════════════════════════
    # HFT STRATEGY 2: SCALPING
    # ═══════════════════════════════════════════════════════════════════════════
    def scalping_strategy(self, duration_seconds: int = 30):
        """
        Ultra-fast scalping: buy/sell quickly for small profits
        """
        print("⚡ Starting Scalping Strategy...")
        self.active = True
        start_time = time.time()
        trades = 0

        try:
            while self.active and (time.time() - start_time) < duration_seconds:
                orderbook = self.get_orderbook()

                if orderbook.spread and orderbook.spread > 0.01:  # Only trade if spread > 1 cent
                    # Quick buy at bid, immediate sell at ask
                    buy_order = self.place_order_fast("buy", 5, orderbook.best_bid + 0.001)

                    if buy_order and buy_order.get("status") == "filled":
                        # Immediately try to sell
                        sell_order = self.place_order_fast("sell", 5, orderbook.best_ask - 0.001)
                        trades += 1
                        print(f"⚡ Scalp #{trades}: Buy ${orderbook.best_bid:.3f} → Sell ${orderbook.best_ask:.3f}")

                time.sleep(0.005)  # 5ms between trades

        finally:
            self.active = False
            print(f"✅ Scalping completed: {trades} trades executed")

    # ═══════════════════════════════════════════════════════════════════════════
    # HFT STRATEGY 3: MOMENTUM TRADING
    # ═══════════════════════════════════════════════════════════════════════════
    def momentum_strategy(self, duration_seconds: int = 30):
        """
        Momentum-based HFT: detect price movements and trade in direction
        """
        print("🚀 Starting Momentum Strategy...")
        self.active = True
        start_time = time.time()
        price_history = []

        try:
            while self.active and (time.time() - start_time) < duration_seconds:
                orderbook = self.get_orderbook()
                current_mid = (
                                          orderbook.best_bid + orderbook.best_ask) / 2 if orderbook.best_bid and orderbook.best_ask else None

                if current_mid:
                    price_history.append(current_mid)

                    # Keep only recent prices (last 10 ticks)
                    if len(price_history) > 10:
                        price_history.pop(0)

                    # Detect momentum (simple moving average crossover)
                    if len(price_history) >= 5:
                        recent_avg = statistics.mean(price_history[-3:])
                        older_avg = statistics.mean(price_history[-6:-3])

                        momentum = recent_avg - older_avg

                        if abs(momentum) > 0.005:  # Significant momentum
                            direction = "buy" if momentum > 0 else "sell"
                            quantity = min(20, max(5, int(abs(momentum) * 1000)))  # Size based on momentum

                            price = orderbook.best_ask if direction == "buy" else orderbook.best_bid
                            order = self.place_order_fast(direction, quantity, price, "market")

                            if order:
                                print(
                                    f"🚀 Momentum {direction.upper()}: {quantity} @ ${price:.3f} (momentum: {momentum:.4f})")

                time.sleep(0.002)  # 2ms refresh rate

        finally:
            self.active = False

    # ═══════════════════════════════════════════════════════════════════════════
    # HFT STRATEGY 4: STATISTICAL ARBITRAGE
    # ═══════════════════════════════════════════════════════════════════════════
    def statistical_arbitrage(self, duration_seconds: int = 30):
        """
        Mean reversion based on price deviations
        """
        print("📈 Starting Statistical Arbitrage...")
        self.active = True
        start_time = time.time()
        price_history = []

        try:
            while self.active and (time.time() - start_time) < duration_seconds:
                orderbook = self.get_orderbook()
                current_mid = (
                                          orderbook.best_bid + orderbook.best_ask) / 2 if orderbook.best_bid and orderbook.best_ask else None

                if current_mid:
                    price_history.append(current_mid)

                    if len(price_history) > 50:
                        price_history.pop(0)

                    # Calculate statistical measures
                    if len(price_history) >= 20:
                        mean_price = statistics.mean(price_history)
                        stdev = statistics.stdev(price_history)
                        z_score = (current_mid - mean_price) / stdev if stdev > 0 else 0

                        # Trade on mean reversion signals
                        if z_score > 2:  # Price too high, expect reversion down
                            order = self.place_order_fast("sell", 15, orderbook.best_bid)
                            print(f"📉 StatArb SELL: Z-score {z_score:.2f} @ ${orderbook.best_bid:.3f}")
                        elif z_score < -2:  # Price too low, expect reversion up
                            order = self.place_order_fast("buy", 15, orderbook.best_ask)
                            print(f"📈 StatArb BUY: Z-score {z_score:.2f} @ ${orderbook.best_ask:.3f}")

                time.sleep(0.001)  # 1ms refresh rate

        finally:
            self.active = False

    # ═══════════════════════════════════════════════════════════════════════════
    # HFT STRATEGY 5: ORDER FLOW IMBALANCE
    # ═══════════════════════════════════════════════════════════════════════════
    def order_flow_strategy(self, duration_seconds: int = 30):
        """
        Trade based on order book imbalances
        """
        print("🌊 Starting Order Flow Strategy...")
        self.active = True
        start_time = time.time()

        try:
            while self.active and (time.time() - start_time) < duration_seconds:
                orderbook = self.get_orderbook()

                if orderbook.bids and orderbook.asks:
                    # Calculate order book imbalance
                    total_bid_volume = sum(b["quantity"] for b in orderbook.bids[:5])  # Top 5 levels
                    total_ask_volume = sum(a["quantity"] for a in orderbook.asks[:5])

                    imbalance = (total_bid_volume - total_ask_volume) / (total_bid_volume + total_ask_volume)

                    # Trade on significant imbalances
                    if imbalance > 0.3:  # More bids than asks - price likely to go up
                        order = self.place_order_fast("buy", 8, orderbook.best_ask)
                        print(f"🟢 Flow BUY: Imbalance {imbalance:.2f} @ ${orderbook.best_ask:.3f}")
                    elif imbalance < -0.3:  # More asks than bids - price likely to go down
                        order = self.place_order_fast("sell", 8, orderbook.best_bid)
                        print(f"🔴 Flow SELL: Imbalance {imbalance:.2f} @ ${orderbook.best_bid:.3f}")

                time.sleep(0.001)  # 1ms refresh rate

        finally:
            self.active = False

    def get_performance_stats(self):
        """Display performance statistics"""
        if self.latency_stats:
            avg_latency = statistics.mean(self.latency_stats)
            min_latency = min(self.latency_stats)
            max_latency = max(self.latency_stats)

            print(f"\n📊 Performance Stats:")
            print(f"   Average Latency: {avg_latency:.2f}ms")
            print(f"   Min Latency: {min_latency:.2f}ms")
            print(f"   Max Latency: {max_latency:.2f}ms")
            print(f"   Total API Calls: {len(self.latency_stats)}")


# ═══════════════════════════════════════════════════════════════════════════════
# MULTI-STRATEGY HFT RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

def run_hft_simulation():
    """Run multiple HFT strategies simultaneously"""
    bot = HFTBot("AAPL")

    print("🚀 Starting HFT Simulation...")
    print("=" * 60)

    # Strategy selection
    strategies = {
        "1": ("Market Making", bot.market_making_strategy),
        "2": ("Scalping", bot.scalping_strategy),
        "3": ("Momentum", bot.momentum_strategy),
        "4": ("Statistical Arbitrage", bot.statistical_arbitrage),
        "5": ("Order Flow", bot.order_flow_strategy),
    }

    print("Available HFT Strategies:")
    for key, (name, _) in strategies.items():
        print(f"  {key}. {name}")
    print("  6. Run All Strategies (Multi-threaded)")

    choice = input("\nSelect strategy (1-6): ").strip()
    duration = int(input("Duration in seconds (default 30): ") or 30)

    if choice in strategies:
        name, strategy_func = strategies[choice]
        print(f"\n🎯 Running {name} for {duration} seconds...")
        strategy_func(duration)
        bot.get_performance_stats()

    elif choice == "6":
        print(f"\n🎯 Running ALL strategies simultaneously for {duration} seconds...")

        # Run all strategies in parallel
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for name, strategy_func in strategies.values():
                future = executor.submit(strategy_func, duration // 5)  # Shorter duration for each
                futures.append((name, future))

            # Wait for all to complete
            for name, future in futures:
                try:
                    future.result()
                    print(f"✅ {name} completed")
                except Exception as e:
                    print(f"❌ {name} failed: {e}")

        bot.get_performance_stats()

    else:
        print("Invalid choice!")


if __name__ == "__main__":
    run_hft_simulation()