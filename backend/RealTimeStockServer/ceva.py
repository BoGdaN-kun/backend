import requests

# ─── Configuration ─────────────────────────────────────────────────────────
USER_URL     = "http://localhost:5000"
EXCHANGE_URL = "http://localhost:9000"

# 1) Log in (or register and then log in). If you already have a JWT, paste it here.
email = "alice@example.com"
password = "SecurePassword123"

# Log in and grab JWT
resp = requests.post(f"{USER_URL}/auth/login", json={
    "email": email, "password": password
})
resp.raise_for_status()
token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# ─── Deposit $1,000 ─────────────────────────────────────────────────────────
# (If you want to start fresh every time, you can comment out this line
# after the first run, so you don't keep adding funds endlessly.)
resp = requests.post(
    f"{USER_URL}/account/deposit",
    json={"amount": 1000.0},
    headers=headers
)
resp.raise_for_status()
print("After deposit:", resp.json())


# Helper to wrap requests and show server-side error if 500 occurs
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


# ─── Step 1: Check how many AAPL you already own ────────────────────────────
portfolio = call_exchange("/portfolio")
existing_aapl = 0
for pos in portfolio:
    if pos["symbol"] == "AAPL":
        existing_aapl = pos["quantity"]
        break
print(f"\nYou currently own {existing_aapl} AAPL shares.")

# We want to end up with at least 5 AAPL (so we can safely sell 2 and then match 2).
target_total = 22
to_buy = max(0, target_total - existing_aapl)
print(f"We need to buy {to_buy} more AAPL shares to reach {target_total} total.\n")

# ─── Step 2: Market‐Buy however many are needed to reach 5 AAPL ─────────────
if to_buy > 0:
    print(f"--- Market Buy {to_buy} AAPL @ $130.25 ---")
    buy_resp = call_exchange("/orders", method="POST", payload={
        "symbol": "AAPL",
        "side": "buy",
        "type": "market",
        "quantity": to_buy,
        "market_price": 130.25
    })
    print("Market buy response:", buy_resp)
else:
    print("No market buy needed; you already have ≥5 AAPL.")


# ─── At this point, you have ≥5 AAPL. ──────────────────────────────────────────
# ─── Step 3: Limit‐Sell 2 AAPL @ $132.00 ────────────────────────────────────
print("\n--- Limit Sell 2 AAPL @ $132.00 ---")
sell_resp = call_exchange("/orders", method="POST", payload={
    "symbol": "AAPL",
    "side": "sell",
    "type": "limit",
    "quantity": 2,
    "limit_price": 132.00
})
print("Limit‐sell response:", sell_resp)


# ─── Step 4: Limit‐Buy 2 AAPL @ $133.00 (should match your own sell) ─────────
print("\n--- Limit Buy 2 AAPL @ $133.00 (match) ---")
match_resp = call_exchange("/orders", method="POST", payload={
    "symbol": "AAPL",
    "side": "buy",
    "type": "limit",
    "quantity": 2,
    "limit_price": 133.00
})
print("Limit‐buy (matching) response:", match_resp)


# ─── Final Checks ─────────────────────────────────────────────────────────────
print("\n--- Final Portfolio ---")
final_portfolio = call_exchange("/portfolio")
print(final_portfolio)

print("\n--- All Trades ---")
print(call_exchange("/trades"))

print("\n--- All Orders ---")
print(call_exchange("/orders"))
