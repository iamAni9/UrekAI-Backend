from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from sqlalchemy import Column, Integer, String

class UserCreate(BaseModel):
    """Request model for creating a new user."""
    name: str = Field(..., description="User's full name.")
    email: EmailStr = Field(..., description="User's email address.")
    password: str = Field(..., min_length=8, description="User's password (min 8 characters).")

class UserLogin(BaseModel):
    """Request model for user login."""
    email: EmailStr = Field(..., description="User's email address.")
    password: str = Field(..., description="User's password.")

class UserResponse(BaseModel):
    """Response model for user details."""
    id: str = Field(..., description="Unique user identifier.")
    name: str = Field(..., description="User's full name.")
    email: EmailStr = Field(..., description="User's email address.")

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    """Response model for authentication tokens."""
    access_token: str
    token_type: str = "bearer"