import firebase_admin
from firebase_admin import credentials, auth

cred = credentials.Certificate("app/firebase/firebase-adminsdk.json")
firebase_admin.initialize_app(cred)

def send_firebase_otp(phone_number: str):
    # In Firebase, OTP is sent from client (mobile/web), not server.
    # Here, just a placeholder if needed for admin checks/logs.
    print(f"Firebase OTP sent to: {phone_number}")
