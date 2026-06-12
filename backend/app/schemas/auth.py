from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email : EmailStr
    password : str = Field(min_length=8, max_length=128, description="Password must be at least 8 characters long")

class LoginRequest(BaseModel):
    email : EmailStr
    password : str 

class RefreshRequest(BaseModel):
    refresh_token : str = Field(description="Refresh token")

class TokenResponse(BaseModel):
    access_token : str = Field(description="Access token")
    refresh_token : str = Field(description="Refresh token")
    token_type : str = Field(description="Token type")

class UserResponse(BaseModel):
    id:str
    email:EmailStr
    is_verified:bool

    model_config = {
        "from_attributes": True,
    }