import os


basedir = os.path.abspath(os.path.dirname(__file__))
class BaseConfig:
    # Use a secure, random key in production
    JWT_SECRET_KEY = os.environ.get(
        "JWT_SECRET_KEY",
        "aB3jK0pWcQx8yGzRnL7sT4uVf2hE9iD1mC6o"
    )
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(basedir, 'exchange.db')}"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_HEADERS = "Content-Type"

    # URL to your Market-Feed service (returns latest 1s candle)
    MARKET_FEED_URL = os.environ.get(
        "MARKET_FEED_URL",
        "http://localhost:8000/candles?limit=1"
    )
    print("→ SQLALCHEMY_DATABASE_URI is:", SQLALCHEMY_DATABASE_URI)


class DevelopmentConfig(BaseConfig):
    DEBUG = True

class ProductionConfig(BaseConfig):
    DEBUG = False
    # Override via env vars if desired
