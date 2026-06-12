"""Email service for sending verification and notification emails"""
import secrets
from datetime import datetime, timedelta

from redis.asyncio import Redis

from app.core.config import settings

# Token expires in 24 hours
VERIFICATION_TOKEN_EXPIRES = 86400
VERIFICATION_TOKEN_PREFIX = "email_verification:"


async def generate_verification_token(redis: Redis, user_id: str) -> str:
    """Generate a unique verification token for email verification"""
    token = secrets.token_urlsafe(32)
    key = f"{VERIFICATION_TOKEN_PREFIX}{token}"
    
    # Store user_id in Redis with expiration
    await redis.set(key, user_id, ex=VERIFICATION_TOKEN_EXPIRES)
    
    return token


async def verify_token(redis: Redis, token: str) -> str | None:
    """Verify token and return user_id if valid, None otherwise"""
    key = f"{VERIFICATION_TOKEN_PREFIX}{token}"
    user_id = await redis.get(key)
    
    if user_id:
        # Delete token after use (single-use)
        await redis.delete(key)
        return user_id.decode() if isinstance(user_id, bytes) else user_id
    
    return None


def send_verification_email(email: str, token: str) -> None:
    """Send verification email to user
    
    In production, this would use a service like SendGrid, AWS SES, or similar.
    For now, we just log the verification link.
    """
    verification_url = f"{settings.frontend_url}/verify-email?token={token}"
    
    # TODO: Integrate with email service
    # For development, just log the URL
    print(f"\n{'='*60}")
    print(f"📧 EMAIL VERIFICATION")
    print(f"{'='*60}")
    print(f"To: {email}")
    print(f"Verification Link: {verification_url}")
    print(f"{'='*60}\n")
    
    # In production:
    # email_client.send(
    #     to=email,
    #     subject="Verify your PawSome account",
    #     html=render_template("verification_email.html", url=verification_url)
    # )


def send_welcome_email(email: str, full_name: str | None) -> None:
    """Send welcome email after successful verification"""
    name = full_name or "there"
    
    print(f"\n{'='*60}")
    print(f"📧 WELCOME EMAIL")
    print(f"{'='*60}")
    print(f"To: {email}")
    print(f"Hi {name}! Welcome to PawSome 🐾")
    print(f"{'='*60}\n")
