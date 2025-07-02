import asyncio
import json
import os
import requests
import sys
import atexit
import threading
import time
from collections import deque, defaultdict
from datetime import datetime, timezone, timedelta

import yfinance as yf
from aiokafka import AIOKafkaConsumer
from flask import Flask, jsonify, request, abort
from pydantic import BaseModel

# --- Configuration ---
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
PRODUCER_API_URL = "http://localhost:8001/subscribe"
MAX_CANDLES = 500


# --- Pydantic Models for Data Validation and Serialization ---
class Candle(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float


class SparklineData(BaseModel):
    time: int
    close: float


# --- In-Memory State Management ---
CANDLE_CACHE = defaultdict(lambda: deque(maxlen=MAX_CANDLES))
CANDLE_INDEX = defaultdict(dict)
CONSUMER_THREADS = {}
ACTIVE_SYMBOLS = set()
_lock = threading.Lock()


# --- Candle Aggregation Logic ---
def _floor_time(ts: datetime) -> datetime:
    return ts.replace(microsecond=0, tzinfo=timezone.utc)


def _update_candle(symbol: str, price: float, bucket_time: datetime):
    with _lock:
        epoch = int(bucket_time.timestamp())
        symbol_cache = CANDLE_CACHE[symbol]
        symbol_index = CANDLE_INDEX[symbol]
        candle = symbol_index.get(epoch)

        if candle is None:
            candle = Candle(time=epoch, open=price, high=price, low=price, close=price)
            symbol_cache.append(candle)
            symbol_index[epoch] = candle
        else:
            candle.high = max(candle.high, price)
            candle.low = min(candle.low, price)
            candle.close = price


# --- Kafka Consumer Logic (runs in a background thread) ---
async def consume_symbol(symbol: str):
    """A long-running async task that consumes and processes messages for one symbol."""
    topic = f"ticks.{symbol.lower()}"
    print(f"Starting consumer for topic: {topic}")

    consumer = None
    retries = 5
    for attempt in range(retries):
        try:
            consumer = AIOKafkaConsumer(
                topic,
                bootstrap_servers=KAFKA_BOOTSTRAP,
                auto_offset_reset="latest",
                request_timeout_ms=15000,
                # --- THIS IS THE FIX ---
                # Tells the consumer how to convert the raw bytes from Kafka
                # back into a Python dictionary.
                value_deserializer=lambda v: json.loads(v.decode("utf-8"))
            )
            await consumer.start()
            print(f"Consumer for {topic} started successfully on attempt {attempt + 1}.")
            break
        except Exception as e:
            print(
                f"Warning: Attempt {attempt + 1}/{retries} to start consumer for {topic} failed. Retrying in 5 seconds... Error: {e}")
            if consumer:
                await consumer.stop()
            if attempt + 1 == retries:
                print(
                    f"FATAL: Could not start consumer for {topic} after {retries} attempts. Aborting task for this symbol.")
                return
            await asyncio.sleep(5)

    try:
        async for msg in consumer:
            # 'data' will now be a dictionary, not bytes.
            data = msg.value
            if data.get("symbol") != symbol:
                continue
            try:
                ts = datetime.fromisoformat(data["ts"].replace("Z", "+00:00"))
                price = float(data["price"])
                _update_candle(symbol, price, _floor_time(ts))
            except (KeyError, ValueError) as e:
                print(f"Error processing tick for {symbol}: {e} - Data: {data}")
    except Exception as e:
        print(f"Consumer for {symbol} encountered a fatal error during message consumption: {e}")
    finally:
        if consumer:
            print(f"Stopping consumer for {symbol}.")
            await consumer.stop()


def run_consumer_in_thread(symbol: str):
    """Helper to run the async consumer in a separate thread."""
    asyncio.run(consume_symbol(symbol))


# --- Core subscription logic, separated from the web route ---
def subscribe_to_symbol_logic(symbol: str):
    """The core logic for subscribing to a symbol. Can be called from anywhere."""
    upper_symbol = symbol.upper()
    with _lock:
        if upper_symbol in ACTIVE_SYMBOLS:
            print(f"Attempted to subscribe to {upper_symbol}, but it is already active.")
            return False

        try:
            print(f"Signaling Producer Service to subscribe to {upper_symbol}...")
            response = requests.post(PRODUCER_API_URL, json={"symbol": upper_symbol}, timeout=5)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"ERROR: Could not signal producer for {upper_symbol}. Is it running? {e}")
            return False

        thread = threading.Thread(target=run_consumer_in_thread, args=(upper_symbol,), daemon=True)
        thread.start()
        CONSUMER_THREADS[upper_symbol] = thread
        ACTIVE_SYMBOLS.add(upper_symbol)
        print(f"Successfully subscribed to {upper_symbol}.")
        return True


# --- Flask Application ---
app = Flask(__name__)


# --- API Endpoints ---
@app.route('/subscribe/<symbol>', methods=['POST'])
def subscribe_route(symbol: str):
    success = subscribe_to_symbol_logic(symbol)
    if success:
        return jsonify({"message": f"Successfully subscribed to symbol: {symbol}"})
    else:
        return jsonify({"error": f"Failed to subscribe to {symbol}. Check service logs."}), 500


@app.route('/candles/<symbol>', methods=['GET'])
def get_candles(symbol: str):
    upper_symbol = symbol.upper()
    if upper_symbol not in ACTIVE_SYMBOLS:
        abort(404, description=f"Not subscribed. Use POST /subscribe/{symbol} first.")
    try:
        limit = int(request.args.get('limit', 200))
        if limit <= 0:
            abort(400, description="Limit must be > 0")
    except ValueError:
        abort(400, description="Invalid limit parameter.")
    with _lock:
        candles_data = [candle.model_dump() for candle in CANDLE_CACHE[upper_symbol]]
    return jsonify(candles_data[-limit:])


@app.route('/news/<symbol>', methods=['GET'])
def get_news(symbol: str):
    try:
        ticker = yf.Ticker(symbol)
        news = ticker.news
        if not news:
            abort(404, description=f"No news found for {symbol}")
        return jsonify(news)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/sparkline/<symbol>', methods=['GET'])
def get_sparkline(symbol: str):
    try:
        days = int(request.args.get('days', 7))
    except ValueError:
        abort(400, description="Invalid days parameter.")
    stock = yf.Ticker(symbol)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    df = stock.history(interval="1d", start=start, end=end).tz_convert("UTC").dropna(subset=["Close"])
    if df.empty:
        abort(404, f"No sparkline data found for {symbol} in the last {days} days")
    sparkline_data = [SparklineData(time=int(idx.timestamp()), close=float(row["Close"])).model_dump() for idx, row in
                      df.iterrows()]
    return jsonify(sparkline_data)


# --- Main Execution Block ---
if __name__ == '__main__':
    DEFAULT_SYMBOLS = ["AAPL", "GOOGL"]


    def startup_subscriptions():
        """A function to run in a background thread that subscribes to default symbols."""
        print("Waiting for producer service to start...")
        time.sleep(3)
        for symbol in DEFAULT_SYMBOLS:
            subscribe_to_symbol_logic(symbol)


    startup_thread = threading.Thread(target=startup_subscriptions, daemon=True)
    startup_thread.start()

    app.run(host='0.0.0.0', port=8000, debug=False)