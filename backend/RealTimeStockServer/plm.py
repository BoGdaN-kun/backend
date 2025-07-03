import yfinance as yf
from datetime import datetime, timezone


symbol = "AAPL"  # Replace with your desired stock symbol
now_utc = datetime.now(timezone.utc)
start_of_today_utc = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
stock = yf.Ticker(symbol)
stock_history = stock.history(interval="1m", start=start_of_today_utc, end=now_utc)
print(stock_history)