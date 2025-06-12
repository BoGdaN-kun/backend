from datetime import datetime, timezone

import yfinance as yf

symbol = "AAPL"
startDate = "2025-05-05"
endDate = "2025-06-09"

apple = yf.Ticker(symbol)
start = datetime.fromisoformat(startDate).astimezone(timezone.utc)
end = datetime.fromisoformat(endDate).astimezone(timezone.utc)
print(start, end)

df = (
    apple.history(interval="5d", start=start, end=end)
    .tz_convert("UTC")
    .dropna(subset=["Open"])
)



# donwload the data to a csv file
data = yf.download(symbol, start=start, end=end, interval="1d")

print(data)

# get sector and industry for a given stock symbol
def get_sector_and_industry(symbol: str):
    stock = yf.Ticker(symbol)
    info = stock.info
    sector = info.get("sector")
    industry = info.get("industry")

    if not sector or not industry:
        raise ValueError(f"Sector or industry information not available for {symbol}")

    return {
        "sector": sector,
    }

print(get_sector_and_industry("AAPL"))  # Example usage



# from datetime import datetime, timezone, timedelta
# from http.client import HTTPException
#
# import yfinance as yf
# from pydantic import BaseModel
#
# symbol = "AAPL"
# stock = yf.Ticker(symbol)
# end = datetime.now(timezone.utc)
# days = 7  # Default to the last 7 days
# start = end - timedelta(days=days)
#
#
#
#
# df = (
#     stock.history(interval="1d", start=start, end=end)
#     .tz_convert("UTC")
#     .dropna(subset=["Open"])
# )
#
# if df.empty:
#     raise HTTPException(404, f"No sparkline data found for {symbol} in the last {days} days")
#
# # i need to get only the time and close price
# class SparklineData(BaseModel):
#     time: int
#     close: float
# output = [
#     SparklineData(
#         time=int(idx.timestamp()),
#         close=float(row["Close"]),
#     ).model_dump()
#     for idx, row in df.iterrows()
# ]
#
# # save to json file
#
# with open(f'{symbol}_sparkline.json', 'w') as f:
#     import json
#     json.dump(output, f, indent=4)
#
# #
# #
# # import yfinance as yf
# # from datetime import datetime, timezone, timedelta
# # from pydantic import BaseModel
# #
# #
# # symbol = 'AAPL'
# # apple = yf.Ticker(symbol)
# #
# # startDate = '2025-05-30'
# # endDate = '2025-06-01'
# # start = datetime.fromisoformat(startDate).astimezone(timezone.utc)
# # end = datetime.fromisoformat(endDate).astimezone(timezone.utc)
# #
# # df = (
# #         apple.history(interval="1m", start=start, end=end)
# #              .tz_convert("UTC")
# #              .dropna(subset=["Open"])
# #     )
# # class Candle(BaseModel):
# #     time: int
# #     open: float
# #     high: float
# #     low:  float
# #     close: float
# #
# #
# # dx = [
# #         Candle(
# #             time=int(idx.timestamp()),
# #             open=float(row["Open"]),
# #             high=float(row["High"]),
# #             low=float(row["Low"]),
# #             close=float(row["Close"]),
# #         ).model_dump()
# #         for idx, row in df.iterrows()
# #     ]
# #
# # # save into file
# # with open(f'{symbol}_history.json', 'w') as f:
# #     import json
# #     json.dump(dx, f, indent=4)
