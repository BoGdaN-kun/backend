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

TOTAL_CYCLES = 50
MAX_SHARES_PER_CYCLE = 10
PRELOAD_CASH = 1_000_000  # Bob's cash

async def login(session, email, password):
    async with session.post(f"{USER_URL}/auth/login", json={"email": email, "password": password}) as resp:
        resp.raise_for_status()
        data = await resp.json()
        return data["access_token"]

async def place_order(session, headers, symbol, side, type_, quantity, price):
    payload = {
        "symbol": symbol,
        "side": side,
        "type": type_,
        "quantity": quantity,
    }
    if type_ == "limit":
        payload["limit_price"] = price
    elif type_ == "market":
        payload["market_price"] = price

    async with session.post(f"{EXCHANGE_URL}/orders", json=payload, headers=headers) as resp:
        if resp.status != 201:
            try:
                error = await resp.json()
                raise Exception(f"HTTP {resp.status} Error: {error}")
            except Exception as e: # Fallback if response is not JSON
                text = await resp.text()
                raise Exception(f"HTTP {resp.status} Error: {text} (Original exception: {e})")
        return await resp.json()

async def get_portfolio(session, headers):
    async with session.get(f"{EXCHANGE_URL}/portfolio", headers=headers) as resp:
        resp.raise_for_status()
        return await resp.json()

async def ensure_enough_shares(session, headers, required_shares):
    portfolio = await get_portfolio(session, headers)
    aapl_position = next((p for p in portfolio if p["symbol"] == "AAPL"), None)
    current_shares = aapl_position["quantity"] if aapl_position else 0

    print(f"Alice already has {current_shares} shares.")
    if current_shares < required_shares:
        to_buy = required_shares - current_shares
        print(f"Buying {to_buy} more AAPL shares for Alice.")
        # Assuming price for market order is just an estimate/placeholder here
        await place_order(session, headers, "AAPL", "buy", "market", to_buy, 130.00)

async def ensure_enough_cash(session, headers, amount):
    print(f"Depositing cash for Bob.")
    payload = {"amount": amount}
    async with session.post(f"{USER_URL}/account/deposit", json=payload, headers=headers) as resp:
        resp.raise_for_status()

async def simulate_trade_cycle(session, cycle_id, headers1, headers2, quantity, latencies):
    symbol = "AAPL"
    base_price = 130 + random.random() * 5  # 130 - 135 USD

    try:
        start_time = time.perf_counter()

        # Alice places limit-sell
        await place_order(session, headers1, symbol, "sell", "limit", quantity, base_price)

        await asyncio.sleep(0.5)  # Short delay to let sell order be processed

        # Bob places limit-buy
        await place_order(session, headers2, symbol, "buy", "limit", quantity, base_price)

        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000
        latencies.append(latency_ms)

        print(f"[Cycle {cycle_id}] SELL/BUY {quantity} @ {base_price:.2f} | {latency_ms:.2f} ms")
    except Exception as e:
        print(f"[Cycle {cycle_id}] Error: {e}")

async def main():
    # You can configure connector limits for aiohttp.ClientSession if needed
    # For example, to increase the number of connections to a single host:
    # conn = aiohttp.TCPConnector(limit_per_host=50) # Default is 0 (unlimited within session limit)
    # async with aiohttp.ClientSession(connector=conn) as session:
    async with aiohttp.ClientSession() as session:
        token1 = await login(session, email1, password1)
        token2 = await login(session, email2, password2)

        headers1 = {"Authorization": f"Bearer {token1}"}
        headers2 = {"Authorization": f"Bearer {token2}"}

        quantities = [random.randint(1, MAX_SHARES_PER_CYCLE) for _ in range(TOTAL_CYCLES)]
        total_shares_needed = sum(quantities)

        print(f"Total shares needed: {total_shares_needed}")
        await ensure_enough_shares(session, headers1, total_shares_needed)
        await ensure_enough_cash(session, headers2, PRELOAD_CASH)

        latencies = []
        tasks = [
            simulate_trade_cycle(session, i, headers1, headers2, quantities[i], latencies)
            for i in range(TOTAL_CYCLES)
        ]

        start_time_all_trades = time.perf_counter()
        await asyncio.gather(*tasks)
        end_time_all_trades = time.perf_counter()

        total_time_seconds = end_time_all_trades - start_time_all_trades
        print(f"\nTotal time for {TOTAL_CYCLES} trades: {total_time_seconds:.2f} seconds")
        if latencies: # Ensure latencies list is not empty
            print(f"Avg latency: {sum(latencies)/len(latencies):.2f} ms")
            print(f"Min latency: {min(latencies):.2f} ms")
            print(f"Max latency: {max(latencies):.2f} ms")
        else:
            print("No successful trades to calculate latency.")


if __name__ == "__main__":
    asyncio.run(main())