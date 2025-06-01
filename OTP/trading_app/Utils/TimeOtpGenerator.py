import pyotp

def create_totp_uri(email: str, secret: str, issuer_name: str = "MyFlaskApp") -> str:
    """
    Return the provisioning URI that front-end can turn into a QR code.
    """
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=issuer_name)