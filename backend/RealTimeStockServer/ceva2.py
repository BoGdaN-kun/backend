from time import sleep
import requests

# ─── Configuration ─────────────────────────────────────────────────────────
USER_URL = "http://localhost:5000"
EXCHANGE_URL = "http://localhost:9000"

email = "alice@example.com"
password = "SecurePassword123"

# 1) Log in and grab a JWT
resp = requests.post(f"{USER_URL}/auth/login", json={
    "email": email,
    "password": password
})
resp.raise_for_status()
token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}


def call_exchange(path: str, method: str = "GET", payload: dict = None):
    url = f"{EXCHANGE_URL}{path}"
    try:
        if method == "POST":
            r = requests.post(url, json=payload, headers=headers)
        else:
            r = requests.get(url, headers=headers, params=payload)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError:
        print(f"\n>>> HTTP {r.status_code} on {method} {url}")
        try:
            print("Response JSON:", r.json())
        except:
            print("Response text:", r.text)
        raise


# ─── INITIAL CLEANUP: Cancel ALL historical AAPL‐sell limit orders ─────────
print("\n— Initial cleanup: canceling any open/partial AAPL‐sell orders… —")
all_orders = call_exchange("/orders")
for o in all_orders:
    if (
            o["symbol"] == "AAPL"
            and o["side"] == "sell"
            and o["status"] in ("open", "partial")
    ):
        cancel_resp = requests.delete(
            f"{EXCHANGE_URL}/orders/{o['id']}",
            headers=headers
        )
        cancel_resp.raise_for_status()
        print(f"Canceled order #{o['id']} (sell {o['quantity']} @ {o['limit_price']}).")

# ─── TOP‐UP CHECK: Ensure at least 4 AAPL free before entering cycles ────────
# We need 4 free shares to do one sell(2)+match(2) cycle.
portfolio = call_exchange("/portfolio")
current_aapl = next((p["quantity"] for p in portfolio if p["symbol"] == "AAPL"), 0)
print(f"\nYou currently hold a total of {current_aapl} AAPL shares.")

required_free = 4
if current_aapl < required_free:
    to_buy_initial = required_free - current_aapl
    print(f"Not enough total AAPL. Market‐buy {to_buy_initial} to reach {required_free} shares.")
    buy_resp = call_exchange("/orders", method="POST", payload={
        "symbol": "AAPL",
        "side": "buy",
        "type": "market",
        "quantity": to_buy_initial,
        "market_price": 130.25
    })
    print("Initial market‐buy response:", buy_resp)
    # After this order fills, you'll have ≥4 AAPL.  (We'll re‐fetch per‐cycle if needed.)

# ─────────────────────────────────────────────────────────────────────────────
# Run two sell→match cycles (each needs 4 free shares at the moment of sell)
# ─────────────────────────────────────────────────────────────────────────────

for cycle in (1, 2):
    print(f"\n========== Cycle {cycle} ==========")

    # Step 1: Fetch total AAPL from /portfolio
    portfolio = call_exchange("/portfolio")
    total_aapl = next((p["quantity"] for p in portfolio if p["symbol"] == "AAPL"), 0)
    print(f"You currently hold a total of {total_aapl} AAPL shares.")

    # Step 2: Sum up how many are already committed to open/partial sells
    orders = call_exchange("/orders")
    old_committed = sum(
        (o["quantity"] - o["filled_quantity"])
        for o in orders
        if o["symbol"] == "AAPL"
        and o["side"] == "sell"
        and o["status"] in ("open", "partial")
    )
    print(f"You already have {old_committed} AAPL shares committed to open/partial sells.")

    available_aapl = total_aapl - old_committed
    print(f"That leaves {available_aapl} AAPL freely available to sell.")

    # Step 3: Reserve for this cycle: sell 2 + match 2 ⇒ need 4
    sell_qty = 2
    match_qty = 2
    total_needed = sell_qty + match_qty  # We need 4 total for the cycle

    if available_aapl < total_needed:
        to_buy = total_needed - available_aapl
        print(f"\nNot enough free shares for cycle {cycle}. Market‐buy {to_buy} AAPL to top up.")
        buy_resp = call_exchange("/orders", method="POST", payload={
            "symbol": "AAPL",
            "side": "buy",
            "type": "market",
            "quantity": to_buy,
            "market_price": 130.25
        })
        print("Market‐buy response:", buy_resp)
        # After this market‐buy fills, re‐fetch portfolio before placing the sell
        sleep(1)  # Give time for the market order to process
        portfolio = call_exchange("/portfolio")
        total_aapl = next((p["quantity"] for p in portfolio if p["symbol"] == "AAPL"), 0)
        print(f"After top‐up, you hold {total_aapl} AAPL shares.")

    # Step 4: Place limit‐sell for this cycle
    print(f"\n--- Cycle {cycle}: Limit Sell {sell_qty} AAPL @ $135.00 ---")
    sell_resp = call_exchange("/orders", method="POST", payload={
        "symbol": "AAPL",
        "side": "sell",
        "type": "limit",
        "quantity": sell_qty,
        "limit_price": 135.00  # Higher price so it won't match immediately
    })
    print("Limit‐sell response:", sell_resp)

    # Brief pause to ensure orders settle before matching
    sleep(1)

    # Step 5: Place separate limit‐buy (won't match with our sell)
    print(f"\n--- Cycle {cycle}: Limit Buy {match_qty} AAPL @ $130.00 (separate) ---")
    match_resp = call_exchange("/orders", method="POST", payload={
        "symbol": "AAPL",
        "side": "buy",
        "type": "limit",
        "quantity": match_qty,
        "limit_price": 130.00  # Lower price so it won't match with our sell
    })
    print("Limit‐buy response:", match_resp)

    # Give time for the orders to potentially match
    sleep(1)

# ─── Final Checks ─────────────────────────────────────────────────────────────
print("\n--- Final Portfolio ---")
print(call_exchange("/portfolio"))

print("\n--- All Trades ---")
print(call_exchange("/trades"))

print("\n--- All Orders ---")
print(call_exchange("/orders"))