from pydantic import BaseModel, Field
from typing import Optional

# Generic Error Model
class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str

# Shopify Auth Models
class ShopifyAuthRedirectQueries(BaseModel):
    """Query parameters for the Shopify auth redirect endpoint."""
    shop: str = Field(..., description="The name of the user's shop.")
    host: str = Field(..., description="The host of the user's shop.")
    embedded: Optional[str] = Field("0", description="Indicates if the app is embedded in Shopify admin.")

class ShopifyAuthCallbackQueries(BaseModel):
    """Query parameters for the Shopify auth callback endpoint."""
    code: str = Field(..., description="The authorization code from Shopify.")
    hmac: str = Field(..., description="The HMAC signature to verify the request.")
    host: str = Field(..., description="The host of the user's shop, decoded from Base64.")
    shop: str = Field(..., description="The name of the user's shop.")
    state: str = Field(..., description="The state parameter provided in the initial auth request.")
    timestamp: str = Field(..., description="The timestamp of the request.")