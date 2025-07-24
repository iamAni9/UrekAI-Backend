import time
import json
import jwt  # PyJWT
from app.config.settings import settings

firebase_credentials = json.loads(settings.FIREBASE_CREDENTIALS_JSON)

def generate_firebase_custom_token(uid: str, additional_claims: dict = None) -> str:
    now = int(time.time())

    payload = {
        "iss": firebase_credentials["client_email"],
        "sub": firebase_credentials["client_email"],
        "aud": "https://identitytoolkit.googleapis.com/google.identity.identitytoolkit.v1.IdentityToolkit",
        "iat": now,
        "exp": now + 3600,  # 1 hour expiration
        "uid": uid
    }

    if additional_claims:
        payload["claims"] = additional_claims

    private_key = firebase_credentials["private_key"]

    token = jwt.encode(payload, private_key, algorithm="RS256")
    
    return token if isinstance(token, str) else token.decode("utf-8")