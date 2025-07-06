import firebase_admin
from firebase_admin import auth, credentials
import os

# Load your Firebase credentials (adjust path as needed)
cred = credentials.Certificate("app/firebase/firebase-adminsdk.json")  # rename your downloaded JSON to this
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

def send_firebase_otp(phone_number: str):
    # In production, Firebase Admin SDK doesn’t support sending OTP directly via Python.
    # You’d do that from frontend (JS/Android) via Firebase Auth SDK.

    # This is just a stub — in practice you'd trigger the frontend or a callable cloud function
    print(f"Triggering OTP to: {phone_number}")
    return True

def verify_firebase_token(token: str):
    try:
        decoded_token = auth.verify_id_token(token)
        return True
    except Exception as e:
        print(f"Token verification failed: {e}")
        return False
