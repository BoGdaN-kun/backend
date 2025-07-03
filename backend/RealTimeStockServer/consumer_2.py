import asyncio
import json
import os
from collections import deque
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
import yfinance as yf
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from starlette.middleware.cors import CORSMiddleware

# Assuming 'news.py' is in the same directory or accessible via PYTHONPATH
# If news.py is not available, you might need to mock or remove this import
try:
    from news import extractNewsInfo
except ImportError:
    print("Warning: news.py not found. News endpoints might not function.")
    def extractNewsInfo(data):
        return [] # Mock function if news.py is missing

# Kafka configuration
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")

# Topic for real-time stock ticks (all symbols will go here)
TICKS_TOPIC = "realtime_ticks"
# Topic for sending subscription requests to the producer
SUBSCRIPTION_REQUEST_TOPIC = "ticker_subscription_requests"

# Declare subscription_producer globally, but initialize it within lifespan
subscription_producer = None

TIMEFRAME = timedelta(seconds=1)
MAX_CANDLES = 500

class Candle(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float

# Dictionary to store candles for multiple symbols
# Structure: { "SYMBOL": { epoch_timestamp: Candle_object, ... } }
_all_candles: dict[str, dict[int, Candle]] = {}
# Dictionary to store deques for limiting number of candles per symbol
# Structure: { "SYMBOL": deque[Candle, ...] }
_all_candle_deques: dict[str, deque[Candle]] = {}

def _floor(ts: datetime) -> datetime:
    """Floors a datetime object to the nearest second (for 1-second candles)."""
    return ts.replace(microsecond=0, tzinfo=timezone.utc)

def _update_candle(symbol: str, price: float, bucket: datetime):
    """
    Updates or creates a candle for a given symbol at a specific time bucket.
    """
    # Ensure the symbol's data structures exist
    if symbol not in _all_candles:
        _all_candles[symbol] = {}
        _all_candle_deques[symbol] = deque(maxlen=MAX_CANDLES)

    epoch = int(bucket.timestamp())
    c = _all_candles[symbol].get(epoch)

    if c is None:
        # Create a new candle if it doesn't exist for this bucket
        c = Candle(time=epoch, open=price, high=price, low=price, close=price)
        _all_candles[symbol][epoch] = c
        _all_candle_deques[symbol].append(c) # Add to deque for max length management
    else:
        # Update existing candle
        c.high = max(c.high, price)
        c.low = min(c.low, price)
        c.close = price

async def _consume():
    """
    Consumes real-time stock ticks from Kafka and updates candle data.
    """
    consumer = AIOKafkaConsumer(
        TICKS_TOPIC, # Consume from the generic ticks topic
        bootstrap_servers=KAFKA_BOOTSTRAP,
        auto_offset_reset="latest",
        enable_auto_commit=True,
        group_id="realtime-candle-consumer-group", # Consumer group for this consumer
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    await consumer.start()
    print(f"Listening for real-time ticks on {TICKS_TOPIC}...")
    try:
        async for msg in consumer:
            data = msg.value
            symbol = data.get("symbol")
            ts_str = data.get("ts")
            price = data.get("price")

            if not all([symbol, ts_str, price]):
                print(f"Skipping incomplete tick message: {data}")
                continue

            # Convert timestamp from ISO format to datetime object
            # Removed .replace("Z", "+00:00") as datetime.fromisoformat handles 'Z' directly
            ts = datetime.fromisoformat(ts_str)
            price = float(price)

            # Print the raw tick coming off Kafka
            print(f"Tick ⤵︎ [{symbol}] price: {price}")

            # Update the candle for the specific symbol
            _update_candle(symbol, price, _floor(ts))

            # Optional: print the candle that was just updated/created
            bucket_epoch = int(_floor(ts).timestamp())
            if symbol in _all_candles and bucket_epoch in _all_candles[symbol]:
                print(f"Candle ⤴︎ [{symbol}]", _all_candles[symbol][bucket_epoch].model_dump())
    except asyncio.CancelledError:
        print("Consumer task cancelled.")
    except Exception as e:
        print(f"Error in consumer: {e}")
    finally:
        await consumer.stop()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the lifecycle of the FastAPI application, including Kafka consumer and producer.
    """
    global subscription_producer # Access the global producer instance

    # Initialize Kafka producer for subscription requests within the async context
    subscription_producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    # Start Kafka producer for subscription requests
    await subscription_producer.start()
    print("Subscription Kafka Producer started.")

    # Start Kafka consumer for real-time ticks in a background task
    consumer_task = asyncio.create_task(_consume())
    try:
        yield
    finally:
        consumer_task.cancel() # Cancel the consumer task
        await consumer_task # Await its completion
        if subscription_producer: # Ensure producer is initialized before stopping
            await subscription_producer.stop() # Stop the subscription producer
        print("Consumer and subscription producer stopped.")

app = FastAPI(title="Real-Time Stock Data Consumer", lifespan=lifespan)

# CORS middleware to allow cross-origin requests from your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Adjust this to your frontend's origin in production
    allow_methods=["GET", "POST"], # Allow POST for subscription requests
    allow_headers=["*"],
)

# -------------------------- API Endpoints ------------------------------------ #

@app.get("/")
async def root():
    """Returns basic status and number of symbols being tracked."""
    return {"status": "ok", "tracked_symbols": list(_all_candles.keys())}

@app.get("/candles", response_model=list[Candle])
async def get_candles(symbol: str, limit: int = 200):
    """
    Returns the latest real-time candles for a specific stock symbol.
    """
    symbol = symbol.upper()
    if limit <= 0:
        raise HTTPException(400, "limit must be > 0")

    if symbol not in _all_candle_deques or not _all_candle_deques[symbol]:
        await subscribe_ticker(symbol)
        raise HTTPException(404, f"No real-time candle data found for {symbol}. "
                                 "It might not be subscribed or data hasn't arrived yet.")
    return list(_all_candle_deques[symbol])[-limit:]

@app.post("/subscribe/{symbol}")
async def subscribe_ticker(symbol: str):
    """
    Sends a request to the producer to start streaming data for the given symbol.
    """
    symbol = symbol.upper()
    request_payload = {"symbol": symbol, "action": "subscribe"}
    try:
        if subscription_producer: # Ensure producer is initialized before sending
            await subscription_producer.send(SUBSCRIPTION_REQUEST_TOPIC, request_payload)
            print(f"Sent subscription request for {symbol} to Kafka.")
            return {"message": f"Subscription request for {symbol} sent. Data should start streaming soon."}
        else:
            raise HTTPException(500, "Subscription producer not initialized.")
    except Exception as e:
        raise HTTPException(500, f"Failed to send subscription request: {e}")

@app.post("/unsubscribe/{symbol}")
async def unsubscribe_ticker(symbol: str):
    """
    Sends a request to the producer to stop streaming data for the given symbol.
    """
    symbol = symbol.upper()
    request_payload = {"symbol": symbol, "action": "unsubscribe"}
    try:
        if subscription_producer: # Ensure producer is initialized before sending
            await subscription_producer.send(SUBSCRIPTION_REQUEST_TOPIC, request_payload)
            print(f"Sent unsubscription request for {symbol} to Kafka.")
            return {"message": f"Unsubscription request for {symbol} sent. Data should stop streaming soon."}
        else:
            raise HTTPException(500, "Subscription producer not initialized.")
    except Exception as e:
        raise HTTPException(500, f"Failed to send unsubscription request: {e}")

# get news about specific news symbol
@app.get("/news/{symbol}")
async def get_news(symbol: str):
    """Fetches news for a given stock symbol."""
    stock = yf.Ticker(symbol)
    news = extractNewsInfo(stock.news)
    if not news:
        raise HTTPException(404, f"No news found for {symbol}")
    return news

# get stock history price for a specific symbol and timeframe from parameters route
@app.get("/history/{symbol}/{startDate}/{endDate}/{granularity}")
async def get_history(symbol: str, startDate: str, endDate: str, granularity: str = "1d"):
    """
    Retrieves historical stock data for a given symbol, date range, and granularity.
    """
    stock = yf.Ticker(symbol)
    start = datetime.fromisoformat(startDate).astimezone(timezone.utc)
    end = datetime.fromisoformat(endDate).astimezone(timezone.utc)
    print(f"Fetching history for {symbol} from {start} to {end} with {granularity} interval.")

    granularity = granularity.lower()
    df = (
        stock.history(interval=granularity, start=start, end=end)
             .tz_convert("UTC")
             .dropna(subset=["Open"])
    )

    if df.empty:
        raise HTTPException(404, f"No history data found for {symbol} between {startDate} and {endDate}")

    return [
        Candle(
            time=int(idx.timestamp()),
            open=float(row["Open"]),
            high=float(row["High"]),
            low=float(row["Low"]),
            close=float(row["Close"]),
        ).model_dump()
        for idx, row in df.iterrows()
    ]

class SparklineData(BaseModel):
    time: int
    close: float

@app.get("/sparkline/{symbol}")
async def get_sparkline(symbol: str, days: int = 7):
    """
    Retrieves sparkline data (daily close prices) for a given symbol over a specified number of days.
    """
    stock = yf.Ticker(symbol)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    df = (
        stock.history(interval="1d", start=start, end=end)
             .tz_convert("UTC")
             .dropna(subset=["Open"])
    )

    if df.empty:
        raise HTTPException(404, f"No sparkline data found for {symbol} in the last {days} days")

    return [
        SparklineData(
            time=int(idx.timestamp()),
            close=float(row["Close"]),
        ).model_dump()
        for idx, row in df.iterrows()
    ]

@app.get("/today/{symbol}", response_model=list[Candle])
async def get_today_realtime_candles(symbol: str):
    """
    Retrieves all real-time candles collected for the given symbol for today.
    If no data is found, it attempts to subscribe to the symbol.
    """
    symbol = symbol.upper()

    # Get the start of today in UTC
    now_utc = datetime.now(timezone.utc)
    start_of_today_utc = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_today_epoch = int(start_of_today_utc.timestamp())
    request_payload = {"symbol": symbol, "action": "subscribe"}
    if symbol not in _all_candles or not _all_candles[symbol]:
        # If no data for the symbol at all, send a subscription request

        await subscription_producer.send(SUBSCRIPTION_REQUEST_TOPIC, request_payload)
        raise HTTPException(
            404,
            detail=f"No real-time candle data found for {symbol} yet. "
                   f"A subscription request has been sent. Please try again in a moment."
        )

    # Filter candles to only include those from today
    stock = yf.Ticker(symbol)
    # start date to be yesterday to ensure we get today's data
    #start_of_today_utc = start_of_today_utc - timedelta(days=1)  # Ensure we cover today's data
    stock_history = stock.history(interval="1m", start=start_of_today_utc, end=now_utc)

    today_candles = [
        Candle(
            time=int(idx.timestamp()),
            open=float(row["Open"]),
            high=float(row["High"]),
            low=float(row["Low"]),
            close=float(row["Close"]),
        ).model_dump()
        for idx, row in stock_history.iterrows()
    ]

    if not today_candles:
        # If no candles for today (but maybe some for past days are present),
        # still suggest subscription or indicate no recent data.
        await subscription_producer.send(SUBSCRIPTION_REQUEST_TOPIC, request_payload)
        raise HTTPException(
            status_code=400,
            detail=f"No real-time candle data for {symbol} found for today yet. "
                   f"A subscription request has been sent. Please try again in a moment."
        )

    # Sort candles by time to ensure chronological order
    #today_candles.sort(key=lambda c: c.time)
    return today_candles

# @app.get("/today", response_model=list[Candle])
# async def get_today():
#     candles = _fetch_today_1m()
#     if not candles:
#         raise HTTPException(404, "No data found for today")
#     return candles


if __name__ == "__main__":
    import uvicorn
    # IMPORTANT: Ensure the module name matches the filename (e.g., "consumer_2:app" for consumer_2.py)
    uvicorn.run("consumer_2:app", host="0.0.0.0", port=8000, reload=True)