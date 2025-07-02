# run.py

from Init.main import create_app

app = create_app("config.DevelopmentConfig")

if __name__ == "__main__":
    app.run(debug=True)