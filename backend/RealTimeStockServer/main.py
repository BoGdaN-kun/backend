# import asyncio
# import json
# from datetime import datetime, timezone
#
# import yfinance as yf
# from kafka import KafkaProducer
#
# BOOTSTRAP_SERVERS = ["localhost:9092"]
# SYMBOLS = ["AAPL"]
# TOPIC = "ticks.aapl"
#
#
# producer = KafkaProducer(
#     bootstrap_servers=BOOTSTRAP_SERVERS,
#     value_serializer=lambda v: json.dumps(v).encode("utf-8"),
# )
#
# async def async_message_handler(msg: dict) -> None:
#
#     print(f"Received message: {msg}")
#     try:
#         ts_ms = int(msg.get("time"))
#         ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
#
#         tick = {
#             "symbol":   msg.get("id"),
#             "ts":       ts,
#             "price":    msg.get("price"),
#         }
#         producer.send(TOPIC, tick)
#         print(f"Sent to Kafka: {tick}") # Optional: for debugging
#     except (ValueError, TypeError) as e:
#         print(f"Could not parse message: {msg}. Error: {e}")
#
# async def main() -> None:
#     print("Connecting to Yahoo Finance WebSocket…")
#     async with yf.AsyncWebSocket() as ws:
#         await ws.subscribe(SYMBOLS)
#         print(f"Subscribed to {', '.join(SYMBOLS)}; streaming ticks to Kafka.")
#         await ws.listen(async_message_handler)
#
# if __name__ == "__main__":
#     try:
#         asyncio.run(main())
#     finally:
#         print("Flushing final messages and closing producer...")
#         producer.flush()
#         producer.close()

# # tick_producer.py
import json, time, yfinance as yf
import random

from kafka import KafkaProducer
from datetime import datetime, timezone

TICKER = "AAPL"
TOPIC = "ticks.aapl"

producer = KafkaProducer(
    bootstrap_servers="localhost:9092",
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
)

apple = yf.Ticker(TICKER)

while True:
    fi = apple.fast_info
    tick = {
        "symbol": TICKER,
        "ts":     datetime.now().isoformat(timespec="seconds") + "Z",
        "price":  fi["last_price"],
    }
    producer.send(TOPIC, tick)
    producer.flush()
    print(tick)
    time.sleep(1)
