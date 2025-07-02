import os
from INIT.main import create_app  # Assuming INIT.main is where create_app is located

config_name = os.getenv("EXCHANGE_ENV", "DevelopmentConfig")
app = create_app(config_name)

if __name__ == "__main__":
    # Get debug status from config
    debug_mode = app.config.get("DEBUG", False)

    app.run(
        host="0.0.0.0",
        port=9000,
        debug=debug_mode,
        threaded=False,
        use_reloader=False
    )
# # run.py
#
# import os
# from INIT.main import create_app
#
# # Choose config class via EXCHANGE_ENV (defaults to DevelopmentConfig)
# config_name = os.getenv("EXCHANGE_ENV", "DevelopmentConfig")
# app = create_app(config_name)
#
# if __name__ == "__main__":
#     # This uses Flask’s built-in server; in production you’d switch to gunicorn or similar.
#     app.run(host="0.0.0.0", port=9000, debug=app.config.get("DEBUG", False))
