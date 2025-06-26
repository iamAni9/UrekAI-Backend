from starlette.middleware.sessions import SessionMiddleware

SESSION_SECRET = "your-session-secret"  

def setup_session(app):
    app.add_middleware(
        SessionMiddleware,
        secret_key=SESSION_SECRET,
        session_cookie="session",
        max_age=86400,  # 1 day in seconds
        same_site="lax",
        https_only=False,  # set to True in production
    )