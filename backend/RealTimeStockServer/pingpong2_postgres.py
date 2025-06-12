import asyncio
import aiohttp
import random
import time

USER_URL = "http://localhost:5000"
EXCHANGE_URL = "http://localhost:9000"

# User credentials
email1 = "alice@example.com"
password1 = "SecurePassword123"

email2 = "bob@example.com"
password2 = "SecurePassword123"

# Simulation parameters
TOTAL_CYCLES = 100
MAX_SHARES_PER_CYCLE = 10
PRELOAD_CASH = 1_000_000  # Cash for each user
PRELOAD_SHARES = 1000  # Shares for each user to start with


async def login(session, email, password):
    """Logs in a user and returns their auth token."""
    async with session.post(f"{USER_URL}/auth/login", json={"email": email, "password": password}) as resp:
        resp.raise_for_status()
        data = await resp.json()
        return data["access_token"]


async def place_order(session, headers, symbol, side, type_, quantity, price):
    """Places a market or limit order."""
    payload = {
        "symbol": symbol,
        "side": side,
        "type": type_,
        "quantity": quantity,
    }
    if type_ == "limit":
        payload["limit_price"] = price
    # For HFT simulation, using limit orders is more realistic for matching
    # elif type_ == "market":
    #     payload["market_price"] = price

    async with session.post(f"{EXCHANGE_URL}/orders", json=payload, headers=headers) as resp:
        if resp.status != 201:
            try:
                error = await resp.json()
                raise Exception(f"HTTP {resp.status} Error placing {side} order: {error}")
            except Exception:
                text = await resp.text()
                raise Exception(f"HTTP {resp.status} Error placing {side} order: {text}")
        return await resp.json()


async def get_portfolio(session, headers):
    """Fetches the user's portfolio."""
    async with session.get(f"{EXCHANGE_URL}/portfolio", headers=headers) as resp:
        resp.raise_for_status()
        return await resp.json()


async def ensure_enough_shares(session, headers, required_shares, user_name):
    """Checks if a user has enough shares, buying more if needed."""
    portfolio = await get_portfolio(session, headers)
    aapl_position = next((p for p in portfolio if p["symbol"] == "AAPL"), None)
    current_shares = aapl_position["quantity"] if aapl_position else 0

    print(f"User '{user_name}' has {current_shares} shares.")
    if current_shares < required_shares:
        to_buy = required_shares - current_shares
        print(f"Buying {to_buy} more AAPL shares for '{user_name}'.")
        # Using a market order for setup simplicity
        await place_order(session, headers, "AAPL", "buy", "market", to_buy,
                          170.00)  # Assuming a high enough market price


async def ensure_enough_cash(session, headers, amount, user_name):
    """Deposits a set amount of cash for a user."""
    print(f"Depositing ${amount} cash for '{user_name}'.")
    payload = {"amount": amount}
    async with session.post(f"{USER_URL}/account/deposit", json=payload, headers=headers) as resp:
        resp.raise_for_status()


async def simulate_trade_cycle(session, cycle_id, alice, bob, quantity, latencies, semaphore):
    """A single HFT cycle where roles of buyer and seller are randomized."""
    symbol = "AAPL"
    # Simulate a tight bid-ask spread
    base_price = 170 + random.uniform(-0.5, 0.5)

    # Randomly assign who is buying and who is selling for this cycle
    seller, buyer = random.sample([alice, bob], 2)
    seller_headers, seller_name = seller
    buyer_headers, buyer_name = buyer

    async with semaphore:
        try:
            start_time = time.perf_counter()

            # Seller places a limit-sell order
            await place_order(session, seller_headers, symbol, "sell", "limit", quantity, base_price)

            # Buyer places a matching limit-buy order almost instantly
            await place_order(session, buyer_headers, symbol, "buy", "limit", quantity, base_price)

            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)

            print(
                f"[Cycle {cycle_id:03d}] {seller_name} sold {quantity} to {buyer_name} @ ${base_price:.2f}  |  Latency: {latency_ms:.2f} ms")
        except Exception as e:
            print(f"[Cycle {cycle_id:03d}] Error: {e}")


async def main():
    async with aiohttp.ClientSession() as session:
        # --- 1. Login and Setup ---
        token1 = await login(session, email1, password1)
        token2 = await login(session, email2, password2)

        headers1 = {"Authorization": f"Bearer {token1}"}
        headers2 = {"Authorization": f"Bearer {token2}"}

        alice = (headers1, "Alice")
        bob = (headers2, "Bob")

        # --- 2. Pre-load BOTH accounts with cash and shares ---
        print("--- Pre-loading accounts ---")
        await ensure_enough_cash(session, headers1, PRELOAD_CASH, "Alice")
        await ensure_enough_cash(session, headers2, PRELOAD_CASH, "Bob")
        await ensure_enough_shares(session, headers1, PRELOAD_SHARES, "Alice")
        await ensure_enough_shares(session, headers2, PRELOAD_SHARES, "Bob")
        print("--- Pre-loading complete ---\n")

        latencies = []
        quantities = [random.randint(1, MAX_SHARES_PER_CYCLE) for _ in range(TOTAL_CYCLES)]

        # A semaphore limits the number of concurrent trades to avoid overwhelming the server
        semaphore = asyncio.Semaphore(15)

        # --- 3. Run HFT Simulation ---
        print(f"--- Starting {TOTAL_CYCLES} HFT cycles ---")
        tasks = [
            simulate_trade_cycle(session, i + 1, alice, bob, quantities[i], latencies, semaphore)
            for i in range(TOTAL_CYCLES)
        ]

        start_time = time.perf_counter()
        await asyncio.gather(*tasks)
        end_time = time.perf_counter()

        # --- 4. Print Results ---
        print("\n--- Simulation Finished ---")
        print(f"Total time for {TOTAL_CYCLES} trade cycles: {end_time - start_time:.2f} seconds")
        if latencies:
            print(f"Avg latency: {sum(latencies) / len(latencies):.2f} ms")
            print(f"Min latency: {min(latencies):.2f} ms")
            print(f"Max latency: {max(latencies):.2f} ms")


if __name__ == "__main__":
    asyncio.run(main())