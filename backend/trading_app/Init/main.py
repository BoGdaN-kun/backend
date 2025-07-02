from flask import Flask
from trading_app.extensions import db, jwt, bcrypt, cors

# Import the Blueprints
from trading_app.Services.AuthentificationService import auth_bp
from trading_app.Services.AccountService import account_bp
from trading_app.Services.WatchlistService import watchlists_bp



def create_app(config_object="config.DevelopmentConfig"):

    app = Flask(__name__)
    app.config.from_object(config_object)

    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    bcrypt.init_app(app)
    cors.init_app(app)

    # Create tables (in dev mode). In production, you might run migrations separately
    with app.app_context():
        db.create_all()

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(watchlists_bp)

    return app
