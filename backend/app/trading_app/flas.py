from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import pyotp

app = Flask(__name__)
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)  # Use hashing in production
    otp_enabled = db.Column(db.Boolean, default=False)
    otp_secret = db.Column(db.String(32), nullable=True)



@app.route('/register', methods=['POST'])
def register():
    data = request.json
    email = data['email']
    password = data['password']
    enable_2fa = data.get('enable_2fa', False)

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'User already exists'}), 400

    otp_secret = pyotp.random_base32() if enable_2fa else None

    user = User(email=email, password=password, otp_enabled=enable_2fa, otp_secret=otp_secret)
    db.session.add(user)
    db.session.commit()

    if enable_2fa:
        uri = pyotp.totp.TOTP(otp_secret).provisioning_uri(name=email, issuer_name="MyReactApp")
        return jsonify({'qr_uri': uri, 'secret': otp_secret}), 201

    return jsonify({'message': 'User registered'}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data['email']
    password = data['password']
    user = User.query.filter_by(email=email, password=password).first()

    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401

    if user.otp_enabled:
        return jsonify({'message': 'OTP required', 'otp_required': True}), 200

    return jsonify({'message': 'Login successful'}), 200

@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    data = request.json
    email = data['email']
    code = data['otp']

    user = User.query.filter_by(email=email).first()
    if not user or not user.otp_secret:
        return jsonify({'error': 'User not found or 2FA not enabled'}), 400

    totp = pyotp.TOTP(user.otp_secret)
    if totp.verify(code):
        return jsonify({'message': 'OTP verified, login success'}), 200

    return jsonify({'error': 'Invalid OTP'}), 401

if __name__ == '__main__':

    with app.app_context():
        db.create_all()
    app.run(debug=True)