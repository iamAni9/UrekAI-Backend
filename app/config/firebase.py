import firebase_admin
from firebase_admin import credentials, auth
from app.config.settings import settings
import json

firebase_credentials = json.loads(settings.FIREBASE_CREDENTIALS_JSON)
cred = credentials.Certificate(firebase_credentials)
firebase_admin.initialize_app(cred)

async def get_or_create_firebase_token(email: str, display_name: str):
    try:
        user = auth.get_user_by_email(email)
    except auth.UserNotFoundError:
        user = auth.create_user(email=email, display_name=display_name)

    custom_token = auth.create_custom_token(user.uid)
    return custom_token.decode("utf-8")