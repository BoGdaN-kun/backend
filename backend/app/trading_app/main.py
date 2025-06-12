import base64
import time
import pyotp
import qrcode
import requests

# # Generate a base32 secret key
# key = "BoGdaNelSecretKey"
# raw_key = "BoGdaNelSecretKey"
#
# key_bytes = key.encode()
# base32_key = base64.b32encode(key_bytes).decode()
#
# time_OTP = pyotp.TOTP(base32_key)
#
# print(time_OTP.now())
#
#
# keyToVerify = input("Enter the OTP: ")
#
# print(time_OTP.verify(keyToVerify))

# uri  = pyotp.totp.TOTP(base32_key).provisioning_uri(name="Bogdan",
#                                                     issuer_name="BoGdaNel")

#print(uri)

#qrcode.make(uri).save("qrcode.png")

BASE_URL = "http://localhost:5000"
def test_register():
    """Test the register endpoint"""
    data = {
        "email": "test@example.com",
        "password": "password123",
        "enable_2fa": False
    }
    response = requests.post(f"{BASE_URL}/register", json=data)
    print(f"Status code: {response.status_code}")
    print(f"Response: {response.text}")

def test_login():
    """Test the login endpoint"""
    data = {
        "email": "test@example.com",
        "password": "password123"
    }
    response = requests.post(f"{BASE_URL}/login", json=data)
    print(f"Status code: {response.status_code}")
    print(f"Response: {response.text}")


test_login()
test_register()
test_login()