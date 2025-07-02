from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from StockExchangeSimualtor.database import db
from StockExchangeSimualtor.Services.OrderService import orders_bp
from StockExchangeSimualtor.Services.PortofolioService import portfolio_bp
from StockExchangeSimualtor.Services.TradeService import trades_bp

def create_app(config_name: str = "DevelopmentConfig") -> Flask:

    config_module = __import__("config", fromlist=[config_name])
    config_class = getattr(config_module, config_name)

    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    JWTManager(app)
    CORS(app)


    with app.app_context():
        db.create_all()


    app.register_blueprint(orders_bp)
    app.register_blueprint(portfolio_bp)
    app.register_blueprint(trades_bp)

    return app
