import asyncio
import json
import sys
import threading
import time
from datetime import datetime, timezone  # <-- THIS LINE IS THE FIX

import yfinance as yf
from flask import Flask, jsonify, request
from kafka import KafkaProducer

# --- Service Configuration ---
KAFKA_BOOTSTRAP = "localhost:9092"

# --- Shared State ---
SUBSCRIBED_SYMBOLS = set()
_lock = threading.Lock()

# --- Kafka Producer Setup ---
try:
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        api_version_auto_timeout_ms=10000,
        request_timeout_ms=10000
    )
except Exception as e:
    print(f"FATAL: Could not connect to Kafka at {KAFKA_BOOTSTRAP}. Error: {e}")
    sys.exit(1)


# --- Asynchronous WebSocket Logic ---
async def async_message_handler(msg: dict):
    """Callback function to process messages from the WebSocket and send to Kafka."""
    try:
        symbol = msg.get("id")
        if not symbol: return
        topic = f"ticks.{symbol.lower()}"

        # This line now works correctly because `datetime` refers to the class.
        ts = datetime.fromtimestamp(int(msg.get("time")) / 1000, tz=timezone.utc).isoformat()

        tick = {
            "symbol": symbol,
            "ts": ts,
            "price": msg.get("price"),
        }
        producer.send(topic, tick)
        print(f"Published to {topic}: {tick}")
    except Exception as e:
        print(f"Could not parse or publish message: {msg}. Error: {e}")


async def run_websocket_client():
    """The core async function that runs the yfinance WebSocket client."""
    current_symbols = []
    while True:
        with _lock:
            if set(current_symbols) != SUBSCRIBED_SYMBOLS:
                print(f"Symbol list changed. Restarting WebSocket.")
                current_symbols = list(SUBSCRIBED_SYMBOLS)

        if not current_symbols:
            await asyncio.sleep(5)
            continue

        try:
            print(f"Connecting to WebSocket for symbols: {current_symbols}")
            async with yf.AsyncWebSocket() as ws:
                await ws.subscribe(current_symbols)
                await ws.listen(async_message_handler)
        except Exception as e:
            print(f"WebSocket connection error: {e}. Reconnecting in 15 seconds...")
            await asyncio.sleep(15)


def run_producer_in_thread():
    """Helper to run the async WebSocket client in its own thread."""
    asyncio.run(run_websocket_client())


# --- Flask Application ---
app = Flask(__name__)


@app.route('/subscribe', methods=['POST'])
def subscribe():
    """API endpoint to add a new symbol to the producer's watchlist."""
    data = request.get_json()
    if not data or 'symbol' not in data:
        return jsonify({"error": "Invalid request body. 'symbol' is required."}), 400

    symbol = data['symbol'].upper()

    with _lock:
        if symbol in SUBSCRIBED_SYMBOLS:
            return jsonify({"message": f"Already subscribed to {symbol}."}), 200
        SUBSCRIBED_SYMBOLS.add(symbol)

    print(f"API: Received request to subscribe to {symbol}")
    return jsonify({"message": f"Subscribed to {symbol}. The producer will connect shortly."})


if __name__ == '__main__':
    producer_thread = threading.Thread(target=run_producer_in_thread, daemon=True)
    producer_thread.start()

    print("Producer service running on http://localhost:8001")
    app.run(host='0.0.0.0', port=8001)