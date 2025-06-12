import pyotp

from trading_app.extensions import db, bcrypt


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.LargeBinary(60), nullable=False)
    otp_enabled = db.Column(db.Boolean, default=False)
    otp_secret = db.Column(db.String(32), nullable=True)

    # one‐to‐one relationship with Account
    account = db.relationship(
        "Account", back_populates="user", uselist=False, cascade="all, delete"
    )
    # one‐to‐many relationship with Watchlist
    watchlists = db.relationship(
        "Watchlist", back_populates="user", cascade="all, delete"
    )

    def check_password(self, plaintext_password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash,plaintext_password)

    def set_password(self, plaintext_password: str):
        # bcrypt.gensalt() defaults to 12 rounds. You can increase cost in prod.
        self.password_hash = bcrypt.generate_password_hash(plaintext_password)

    def __repr__(self):
        return f"User {self.email} (id={self.id}, otp_enabled={self.otp_enabled})"

    def generate_otp_secret(self) -> str:
        secret = pyotp.random_base32()
        self.otp_secret = secret
        return secret

    def verify_otp(self, token: str) -> bool:
        if not self.otp_enabled or not self.otp_secret:
            return False
        totp = pyotp.TOTP(self.otp_secret)
        return totp.verify(token)