import firebase_admin
from firebase_admin import credentials

cred = credentials.Certificate("app/firebase/firebase-adminsdk.json")
firebase_admin.initialize_app(cred)
