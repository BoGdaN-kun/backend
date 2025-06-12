import asyncio, json, os
from collections import deque
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
import yfinance as yf
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from aiokafka import AIOKafkaConsumer
from starlette.middleware.cors import CORSMiddleware

from news import extractNewsInfo

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
TOPIC           = os.getenv("KAFKA_TOPIC",     "ticks.aapl")
SYMBOL          = os.getenv("SYMBOL",          "AAPL")
TIMEFRAME       = timedelta(seconds=1)
MAX_CANDLES     = 500

class Candle(BaseModel):
    time: int
    open: float
    high: float
    low:  float
    close: float

_candles: "deque[Candle]" = deque(maxlen=MAX_CANDLES)
_candle_index: dict[int, Candle] = {}

def _floor(ts: datetime) -> datetime:
    return ts.replace(microsecond=0, tzinfo=timezone.utc)
def _update(price: float, bucket: datetime):
    epoch = int(bucket.timestamp())
    c = _candle_index.get(epoch)
    if c is None:
        c = Candle(time=epoch, open=price, high=price, low=price, close=price)
        _candles.append(c)
        _candle_index[epoch] = c
    else:
        c.high = max(c.high, price)
        c.low  = min(c.low,  price)
        c.close = price


async def _consume():
    consumer = AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        auto_offset_reset="latest",
        enable_auto_commit=True,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    await consumer.start()
    try:
        async for msg in consumer:
            data  = msg.value
            if data.get("symbol") != SYMBOL:
                continue

            # ◆ print the raw tick coming off Kafka
            print("Tick ⤵︎", data)

            ts = datetime.fromisoformat(data["ts"].replace("Z", "+00:00"))
            price = float(data["price"])
            _update(price, _floor(ts))

            # ◆ print the candle that was just updated/created
            bucket_epoch = int(_floor(ts).timestamp())
            print("Candle ⤴︎", _candle_index[bucket_epoch].model_dump())
    finally:
        await consumer.stop()


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_consume())
    try:
        yield
    finally:
        task.cancel()

app = FastAPI(title=f"{SYMBOL} Live Candles", lifespan=lifespan)

@app.get("/candles", response_model=list[Candle])
async def get_candles(limit: int = 200):
    if limit <= 0:
        raise HTTPException(400, "limit must be > 0")
    return list(_candles)[-limit:]

@app.get("/")
async def root():
    return {"status": "ok", "candles": len(_candles)}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

def _fetch_today_1m() -> list[Candle]:
    """
    Return today's 1-minute candles as a list of Candle-dicts
    (same shape your /candles route emits).
    """
    apple = yf.Ticker(SYMBOL)

    # intraday granularity – Yahoo allows 1m for the last ~30 days
    # start = datetime.now(timezone.utc).replace(hour=0, minute=0,
    #                                            second=0, microsecond=0)
    start = "2025-05-22 00:00:00"
    start = datetime.fromisoformat(start).astimezone(timezone.utc)
    end = start + timedelta(days=1)

    df = (
        apple.history(interval="1m", start=start, end=end)
             .tz_convert("UTC")
             .dropna(subset=["Open"])
    )

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

# -------------------------- routes ------------------------------------ #
@app.get("/today", response_model=list[Candle])
async def get_today():
    candles = _fetch_today_1m()
    if not candles:
        raise HTTPException(404, "No data found for today")
    return candles

# get news about spewcific news symbol
@app.get("/news/{symbol}")
async def get_news(symbol: str):
    symbol = yf.Ticker(symbol)
    news = extractNewsInfo(symbol.news)
    if not news:
        raise HTTPException(404, f"No news found for {symbol}")
    return news

# get stock history price for a specific symbol and timeframe from parameters route
@app.get("/history/{symbol}/{startDate}/{endDate}/{granularity}")
async def get_history(symbol: str, startDate: str, endDate: str, granularity: str = "1d"):
    """
     TODO:
     data = yf.download(symbol, start=start, end=end, interval="1d")
     Download the stock from max perios, and if it doesnt exist to download it all, and when i request a stock with a higher granularity to use the downloaded file
     instead of the api call???

    :param symbol:
    :param startDate:
    :param endDate:
    :param granularity:
    :return:
    """
    apple = yf.Ticker(symbol)
    start = datetime.fromisoformat(startDate).astimezone(timezone.utc)
    end = datetime.fromisoformat(endDate).astimezone(timezone.utc)
    print(start, end)
    granularity = granularity.lower()
    df = (
        apple.history(interval=granularity, start=start, end=end)
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

# GET /sparkline/{symbol}?days=7
@app.get("/sparkline/{symbol}")
async def get_sparkline(symbol: str, days: int = 7):
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("consumer:app", host="0.0.0.0", port=8000, reload=True)
