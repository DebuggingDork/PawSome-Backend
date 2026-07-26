"""Email delivery and the token/OTP lifecycle behind account verification.

Sending goes through Brevo's transactional API. Brevo was chosen over the usual
alternatives for one practical reason: its free tier (300/day, no expiry) lets you
send from a single *verified mailbox* without owning a domain, so verification
works before anyone buys a DNS name. Most competitors restrict domainless accounts
to emailing the account holder, which is useless for a real signup flow.

Delivery is best-effort and never fatal. If Brevo is unconfigured or returns an
error, the code is logged and the request still succeeds: a mail outage must not
turn account creation into a 500.
"""
import logging
import secrets
from typing import Final

import httpx
from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

BREVO_SEND_URL: Final = "https://api.brevo.com/v3/smtp/email"
BREVO_TIMEOUT_S: Final = 10.0

# Link tokens stay long-lived (a link may sit in an inbox for a day); typed codes
# are short-lived because a 6-digit secret is only 10^6 wide and must not sit
# guessable for hours.
VERIFICATION_TOKEN_EXPIRES = 86400
VERIFICATION_TOKEN_PREFIX = "email_verification:"

OTP_EXPIRES = 600  # 10 minutes
OTP_PREFIX = "email_otp:"
OTP_ATTEMPTS_PREFIX = "email_otp_attempts:"
# Caps brute force at 5 guesses per issued code. The counter shares the code's TTL,
# so requesting a fresh code also grants a fresh budget - that is fine, since
# issuing one is itself rate limited below.
OTP_MAX_ATTEMPTS = 5

OTP_RESEND_PREFIX = "email_otp_resend:"
OTP_RESEND_COOLDOWN = 60

PASSWORD_RESET_TOKEN_EXPIRES = 1800
PASSWORD_RESET_TOKEN_PREFIX = "password_reset:"

PASSWORD_RESET_OTP_EXPIRES = 600  # 10 minutes
PASSWORD_RESET_OTP_PREFIX = "password_reset_otp:"
PASSWORD_RESET_OTP_ATTEMPTS_PREFIX = "password_reset_otp_attempts:"
PASSWORD_RESET_OTP_MAX_ATTEMPTS = 5


# ── Delivery ──────────────────────────────────────────────────────────────────

async def _send(to: str, subject: str, html: str, text: str) -> bool:
    """Post one message to Brevo. Returns whether it was accepted.

    Never raises: every caller is in the middle of a user-facing request whose
    success does not actually depend on the mail going out.
    """
    if not settings.email_configured:
        logger.warning(
            "Email not configured (BREVO_API_KEY / BREVO_SENDER_EMAIL unset). "
            "Falling back to console output.\n"
            "--- MAIL TO %s ---\n%s\n%s\n--- END ---",
            to, subject, text,
        )
        return False

    payload = {
        "sender": {"email": settings.brevo_sender_email, "name": settings.brevo_sender_name},
        "to": [{"email": to}],
        "subject": subject,
        "htmlContent": html,
        "textContent": text,
    }

    try:
        async with httpx.AsyncClient(timeout=BREVO_TIMEOUT_S) as client:
            response = await client.post(
                BREVO_SEND_URL,
                json=payload,
                headers={"api-key": settings.brevo_api_key, "accept": "application/json"},
            )
        if response.status_code >= 400:
            # Body carries Brevo's own reason (unverified sender, quota, bad key),
            # which is the only thing that makes these debuggable.
            logger.error("Brevo rejected mail to %s: %s %s", to, response.status_code, response.text)
            return False
        return True
    except httpx.HTTPError:
        logger.exception("Could not reach Brevo while sending to %s", to)
        return False


def _shell(heading: str, body_html: str) -> str:
    """Minimal inline-styled wrapper. Mail clients strip <style> blocks and have no
    flexbox worth relying on, so this stays tables-free and inline."""
    return f"""\
<div style="background:#0a0a0a;padding:32px 16px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <div style="max-width:480px;margin:0 auto;background:#141414;border:1px solid #262626;border-radius:16px;padding:32px;">
    <p style="margin:0 0 24px;font-size:22px;font-weight:700;color:#ff6b35;">PawSome</p>
    <h1 style="margin:0 0 16px;font-size:20px;line-height:1.3;color:#ffffff;">{heading}</h1>
    {body_html}
    <p style="margin:28px 0 0;font-size:12px;line-height:1.6;color:#737373;">
      If you didn't create a PawSome account, you can ignore this email.
    </p>
  </div>
</div>"""


# ── One-time codes ────────────────────────────────────────────────────────────

async def can_send_otp(redis: Redis, user_id: str) -> int:
    """Seconds left on the resend cooldown, or 0 if a code may be sent now."""
    ttl = await redis.ttl(f"{OTP_RESEND_PREFIX}{user_id}")
    return ttl if ttl and ttl > 0 else 0


async def generate_otp(redis: Redis, user_id: str) -> str:
    """Issue a fresh 6-digit code, replacing any outstanding one."""
    # randbelow, not random.randint: this is a credential.
    code = f"{secrets.randbelow(1_000_000):06d}"

    await redis.set(f"{OTP_PREFIX}{user_id}", code, ex=OTP_EXPIRES)
    await redis.delete(f"{OTP_ATTEMPTS_PREFIX}{user_id}")
    await redis.set(f"{OTP_RESEND_PREFIX}{user_id}", "1", ex=OTP_RESEND_COOLDOWN)
    return code


class OtpResult:
    """Outcome of a code check, distinguishing 'wrong' from 'no longer usable' so
    the UI can tell someone to request a new code instead of retrying forever."""

    OK = "ok"
    INVALID = "invalid"
    EXPIRED = "expired"
    TOO_MANY_ATTEMPTS = "too_many_attempts"


async def verify_otp(redis: Redis, user_id: str, submitted: str) -> str:
    key = f"{OTP_PREFIX}{user_id}"
    attempts_key = f"{OTP_ATTEMPTS_PREFIX}{user_id}"

    stored = await redis.get(key)
    if stored is None:
        return OtpResult.EXPIRED

    attempts = await redis.incr(attempts_key)
    if attempts == 1:
        # Match the code's lifetime so the counter can't outlive what it guards.
        await redis.expire(attempts_key, OTP_EXPIRES)
    if attempts > OTP_MAX_ATTEMPTS:
        await redis.delete(key)
        return OtpResult.TOO_MANY_ATTEMPTS

    expected = stored.decode() if isinstance(stored, bytes) else stored
    # Constant-time: a timing oracle on a 6-digit space is worth closing cheaply.
    if not secrets.compare_digest(expected, submitted.strip()):
        return OtpResult.INVALID

    await redis.delete(key)
    await redis.delete(attempts_key)
    return OtpResult.OK


# ── Link tokens ───────────────────────────────────────────────────────────────

async def generate_verification_token(redis: Redis, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    await redis.set(f"{VERIFICATION_TOKEN_PREFIX}{token}", user_id, ex=VERIFICATION_TOKEN_EXPIRES)
    return token


async def verify_token(redis: Redis, token: str) -> str | None:
    key = f"{VERIFICATION_TOKEN_PREFIX}{token}"
    user_id = await redis.get(key)
    if user_id:
        await redis.delete(key)  # single use
        return user_id.decode() if isinstance(user_id, bytes) else user_id
    return None


# ── Messages ──────────────────────────────────────────────────────────────────

async def send_verification_email(email: str, code: str, token: str | None = None) -> bool:
    """The signup verification message: a typed code, plus the link as a fallback
    for anyone who would rather click than retype."""
    link_html = ""
    link_text = ""
    if token:
        url = f"{settings.frontend_url}/verify-email?token={token}"
        link_html = (
            '<p style="margin:24px 0 0;font-size:14px;line-height:1.6;color:#a3a3a3;">'
            f'Or <a href="{url}" style="color:#ff6b35;">verify with one click</a>.</p>'
        )
        link_text = f"\nOr open this link: {url}\n"

    html = _shell(
        "Your verification code",
        f"""
    <p style="margin:0 0 20px;font-size:14px;line-height:1.6;color:#a3a3a3;">
      Enter this code on the PawSome setup screen to confirm this address.
    </p>
    <p style="margin:0;padding:16px 24px;background:#0a0a0a;border:1px solid #262626;border-radius:12px;
              font-size:32px;font-weight:700;letter-spacing:8px;text-align:center;color:#ffffff;">{code}</p>
    <p style="margin:16px 0 0;font-size:13px;color:#737373;">This code expires in 10 minutes.</p>
    {link_html}""",
    )
    text = (
        f"Your PawSome verification code is {code}\n"
        f"It expires in 10 minutes.\n{link_text}"
    )
    return await _send(email, f"{code} is your PawSome verification code", html, text)


async def send_password_reset_email(email: str, token: str) -> bool:
    url = f"{settings.frontend_url}/reset-password?token={token}"
    html = _shell(
        "Reset your password",
        f"""
    <p style="margin:0 0 20px;font-size:14px;line-height:1.6;color:#a3a3a3;">
      Click below to choose a new password. The link works once and expires in
      {PASSWORD_RESET_TOKEN_EXPIRES // 60} minutes.
    </p>
    <a href="{url}" style="display:inline-block;padding:12px 24px;background:#ff6b35;border-radius:999px;
       font-size:14px;font-weight:600;color:#ffffff;text-decoration:none;">Choose a new password</a>""",
    )
    text = f"Reset your PawSome password: {url}\nExpires in {PASSWORD_RESET_TOKEN_EXPIRES // 60} minutes."
    return await _send(email, "Reset your PawSome password", html, text)


async def send_password_reset_otp_email(email: str, code: str) -> bool:
    """Send a 6-digit OTP for password reset"""
    html = _shell(
        "Reset your password",
        f"""
    <p style="margin:0 0 20px;font-size:14px;line-height:1.6;color:#a3a3a3;">
      Enter this code to reset your PawSome password.
    </p>
    <p style="margin:0;padding:16px 24px;background:#0a0a0a;border:1px solid #262626;border-radius:12px;
              font-size:32px;font-weight:700;letter-spacing:8px;text-align:center;color:#ffffff;">{code}</p>
    <p style="margin:16px 0 0;font-size:13px;color:#737373;">This code expires in 10 minutes.</p>""",
    )
    text = (
        f"Your PawSome password reset code is {code}\n"
        f"It expires in 10 minutes.\n"
    )
    return await _send(email, f"{code} is your PawSome password reset code", html, text)


async def generate_password_reset_token(redis: Redis, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    await redis.set(f"{PASSWORD_RESET_TOKEN_PREFIX}{token}", user_id, ex=PASSWORD_RESET_TOKEN_EXPIRES)
    return token


async def verify_password_reset_token(redis: Redis, token: str) -> str | None:
    key = f"{PASSWORD_RESET_TOKEN_PREFIX}{token}"
    user_id = await redis.get(key)
    if user_id:
        await redis.delete(key)
        return user_id.decode() if isinstance(user_id, bytes) else user_id
    return None


async def generate_password_reset_otp(redis: Redis, user_email: str) -> str:
    """Issue a fresh 6-digit code for password reset"""
    code = f"{secrets.randbelow(1_000_000):06d}"
    
    await redis.set(f"{PASSWORD_RESET_OTP_PREFIX}{user_email}", code, ex=PASSWORD_RESET_OTP_EXPIRES)
    await redis.delete(f"{PASSWORD_RESET_OTP_ATTEMPTS_PREFIX}{user_email}")
    return code


async def verify_password_reset_otp(redis: Redis, user_email: str, submitted: str) -> str:
    """Verify OTP for password reset"""
    key = f"{PASSWORD_RESET_OTP_PREFIX}{user_email}"
    attempts_key = f"{PASSWORD_RESET_OTP_ATTEMPTS_PREFIX}{user_email}"

    stored = await redis.get(key)
    if stored is None:
        return OtpResult.EXPIRED

    attempts = await redis.incr(attempts_key)
    if attempts == 1:
        await redis.expire(attempts_key, PASSWORD_RESET_OTP_EXPIRES)
    if attempts > PASSWORD_RESET_OTP_MAX_ATTEMPTS:
        await redis.delete(key)
        return OtpResult.TOO_MANY_ATTEMPTS

    expected = stored.decode() if isinstance(stored, bytes) else stored
    if not secrets.compare_digest(expected, submitted.strip()):
        return OtpResult.INVALID

    # Don't delete the code yet - we'll delete it after password is actually changed
    return OtpResult.OK


async def clear_password_reset_otp(redis: Redis, user_email: str) -> None:
    """Clear the password reset OTP after successful password change"""
    await redis.delete(f"{PASSWORD_RESET_OTP_PREFIX}{user_email}")
    await redis.delete(f"{PASSWORD_RESET_OTP_ATTEMPTS_PREFIX}{user_email}")


async def send_welcome_email(email: str, full_name: str | None) -> bool:
    name = full_name or "there"
    html = _shell(
        f"Welcome, {name}",
        """
    <p style="margin:0 0 20px;font-size:14px;line-height:1.6;color:#a3a3a3;">
      Your email is confirmed. Your pet's card now carries a verified badge, and
      you can start meeting owners nearby.
    </p>""",
    )
    return await _send(email, "Welcome to PawSome", html, f"Hi {name}, welcome to PawSome.")
