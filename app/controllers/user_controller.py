# controllers/user_controller.py
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from fastapi.concurrency import run_in_threadpool
from datetime import datetime, timezone
import bcrypt
import httpx
from app.config.database_config.postgres import database as db
from app.config.logger import get_logger
from app.utils.uniqueId import generate_unique_id
from app.config.database_config.firebase import generate_firebase_custom_token

logger = get_logger("API Logger")

async def sign_in_user(request: Request, response: Response):
    data = await request.json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    user = await db.fetch_one("SELECT * FROM users WHERE email = :email", {"email": email})

    if not user or not bcrypt.checkpw(password.encode(), user["password"].encode()):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    response = JSONResponse({"success": True, "message": "User login successfully"})
    request.session["user"] = {
        "id": str(user["id"]),
        "name": user["name"],
        "email": user["email"],
    }

    return response

async def sign_up_user(request: Request, response: Response):
    data = await request.json()
    if not data:
        raise HTTPException(status_code=400, detail="Request body is empty")
    
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")
    
    if not name or not email or not password:
        raise HTTPException(status_code=400, detail="Name, email, and password are required")
   
    existing_user = await db.fetch_one("SELECT * FROM users WHERE email = :email", {"email": email})

    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")

    user_id = generate_unique_id()
    now = datetime.now(timezone.utc) 
    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    await db.execute(
        """
        INSERT INTO users (id, name, email, password, created_at, updated_at)
        VALUES (:id, :name, :email, :password, :created_at, :updated_at)
        """,
        {
            "id": user_id,
            "name": name,
            "email": email,
            "password": hashed_password,
            "created_at": now,
            "updated_at": now
        }
    )

    response = JSONResponse({"success": True, "message": "User created successfully"})
    request.session["user"] = { 
        "id": str(user_id), 
        "name": name, 
        "email": email 
    }

    return response

async def google_auth(request: Request):
    data = await request.json()
    access_token = data.get("access_token")

    if not access_token:
        raise HTTPException(status_code=400, detail="Access token is required")

    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            res.raise_for_status()
            user_info = res.json()
            name = user_info.get("name")
            email = user_info.get("email")
        except Exception as e:
            logger.error(f"Failed Google token exchange: {e}")
            raise HTTPException(status_code=401, detail="Invalid Google access token")

    # async with db.acquire() as conn:
        user = await db.fetch_one("SELECT * FROM users WHERE email = :email", {"email" : email})

        if not user:
            logger.info("Creating new user for Google login")
            user_id = generate_unique_id()
            now = datetime.now(timezone.utc)
            await db.execute(
                """
                INSERT INTO users (id, name, email, password, created_at, updated_at)
                VALUES (:id, :name, :email, :password, :created_at, :updated_at)
                """,
                {
                    "id": user_id,
                    "name": name,
                    "email": email,
                    "password": "null_null",
                    "created_at": now,
                    "updated_at": now
                }
            )
            user = {"id": user_id, "name": name, "email": email}

        response = JSONResponse({"success": True, "message": "Google authentication successful"})
        request.session["user"] = {
            "id": str(user["id"]),
            "name": user["name"],
            "email": user["email"]
        }

        return response


async def check_user(request: Request):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Not logged in")
    
    # firebase_token = await get_or_create_firebase_token(user["email"], user["name"])
    firebase_token = await run_in_threadpool(generate_firebase_custom_token, user["email"])
    
    return JSONResponse({
        "success": True,
        "message": "User already logged in",
        "name": user["name"],
        "email": user["email"],
        "firebase_token": firebase_token,
    })


async def sign_out_user(request: Request):
    if request.session.get("user"):
        request.session.clear()
        return JSONResponse({"success": True, "message": "User logged out successfully"})
    return JSONResponse({"success": False, "message": "No active session to log out"}, status_code=400)

