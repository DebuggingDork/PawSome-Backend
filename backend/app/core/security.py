from passlib.context import CryptContext

from datetime import UTC,datetime,timedelta
from uuid import UUID
from jose import jwt,JWTError
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"],deprecated="auto")

def hash_password(plain:str) -> str:
    return pwd_context.hash(plain)

def verify_password(plain:str,hashed:str)  -> bool:
    return pwd_context.verify(plain,hashed)


## JWT Token Functions

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


def _create_token(*,subject:UUID,token_type:str,expires_delta:timedelta) -> str:
    now = datetime.now(UTC)
    payload={
        "sub":str(subject),
        "type":token_type,
        "iat":now,
        "exp":now+expires_delta,
    }
    return jwt.encode(payload,settings.jwt_secret,algorithm=settings.jwt_algorithm)

def create_access_token(user_id:UUID) -> str:
    return _create_token(
        subject=user_id,
        token_type=TOKEN_TYPE_ACCESS,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes)
    )

def create_refresh_token(user_id:UUID) -> str:
   return _create_token(
    subject=user_id,
    token_type=TOKEN_TYPE_REFRESH,
    expires_delta=timedelta(days=settings.refresh_token_expire_days)
   )

def decode_token(token:str) -> dict:
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )

def verify_token(token:str,expected_type:str) -> UUID:
    try:
        payload = decode_token(token)
    except JWTError as exc:
        raise ValueError("Invalid Token") from exc

    if payload.get("type") != expected_type:
        raise ValueError("Invalid Token Type")

    sub =  payload.get("sub")
    if not sub:
        raise ValueError("Missing subject")
    
    return UUID(sub)