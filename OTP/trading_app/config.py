import os

basedir = os.path.abspath(os.path.dirname(__file__))

class BaseConfig:
    # Use a secure, random key in production
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "aB3jK0pWcQx8yGzRnL7sT4uVf2hE9iD1mC6o")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(basedir, 'app.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_HEADERS = "Content-Type"
    print("→ SQLALCHEMY_DATABASE_URI is:", SQLALCHEMY_DATABASE_URI)

class DevelopmentConfig(BaseConfig):
    DEBUG = True

class ProductionConfig(BaseConfig):
    DEBUG = False
    # You can override DATABASE_URL or JWT_SECRET_KEY via environment vars
