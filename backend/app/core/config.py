from typing import Any
from urllib.parse import parse_qs, urlparse, urlunparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_database_url(url: str) -> tuple[str, dict[str, Any]]:
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    connect_args: dict[str, Any] = {}

    sslmode = query.pop("sslmode", [None])[0]
    if sslmode in ("require", "verify-full", "verify-ca"):
        connect_args["ssl"] = True

    # asyncpg doesn't accept channel_binding (libpq-only param in Neon URLs)
    query.pop("channel_binding", None)

    clean_query = "&".join(f"{k}={v[0]}" for k, v in query.items())
    clean_url = urlunparse(parsed._replace(query=clean_query))
    return clean_url, connect_args


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    database_url: str
    redis_url: str = Field(..., description="Redis URL")

    jwt_secret: str = Field(..., description="JWT Secret")
    jwt_algorithm: str = Field("HS256", description="JWT Algorithm")
    access_token_expire_minutes: int = Field(30, description="Access token expire minutes")
    refresh_token_expire_days: int = Field(7, description="Refresh token expire days")

    cors_origins: str = Field("http://localhost:5173", description="CORS Origins")
    frontend_url: str = Field("http://localhost:5173", description="Frontend base URL for email links")

    # Cloudflare R2 (S3-compatible). Empty defaults let the app boot without
    # photo support; photo endpoints return 503 until these are set.
    r2_account_id: str = Field("", description="Cloudflare account ID")
    r2_access_key_id: str = Field("", description="R2 API token access key ID")
    r2_secret_access_key: str = Field("", description="R2 API token secret")
    r2_bucket_name: str = Field("", description="R2 bucket name")
    r2_public_base_url: str = Field(
        "", description="Public base URL for the bucket (r2.dev or custom domain)"
    )

    # Brevo (transactional email). Empty API key keeps the app bootable without
    # mail: send_* falls back to logging the code to the console, which is how
    # local development worked before any provider existed.
    brevo_api_key: str = Field("", description="Brevo v3 API key")
    brevo_sender_email: str = Field(
        "", description="Verified sender address in Brevo (a single verified mailbox is enough)"
    )
    brevo_sender_name: str = Field("PawSome", description="Display name on outgoing mail")

    # Ola Maps (routed distance + drive time, tuned for India; 500K calls/month
    # free). Entirely optional: without a key /travel/eta answers with
    # straight-line distance instead, so the feature degrades rather than
    # disappearing. Weather, air quality, and nearby places need no key at all.
    ola_maps_api_key: str = Field("", description="Ola Maps API key")
    ola_maps_base_url: str = Field("https://api.olamaps.io", description="Ola Maps API base URL")

    # Whether an unverified account is blocked from swiping and matching. Kept as a
    # switch rather than hard-coded so a provider outage can be downgraded to a
    # nag without a redeploy: mail delivery is outside our control, and locking
    # every user out of the core feature is worse than a few unverified accounts.
    require_email_verification: bool = Field(
        True, description="Block swiping/matching until the email is verified"
    )

    @property
    def email_configured(self) -> bool:
        return bool(self.brevo_api_key and self.brevo_sender_email)

    @property
    def ola_maps_configured(self) -> bool:
        return bool(self.ola_maps_api_key)

    @property
    def r2_configured(self) -> bool:
        return all([
            self.r2_account_id,
            self.r2_access_key_id,
            self.r2_secret_access_key,
            self.r2_bucket_name,
            self.r2_public_base_url,
        ])

    database_connect_args: dict[str, Any] = Field(default_factory=dict, exclude=True)

    @model_validator(mode="before")
    @classmethod
    def normalize_database_url(cls, data: Any) -> Any:
        if not isinstance(data, dict) or "database_url" not in data:
            return data

        clean_url, connect_args = _normalize_database_url(data["database_url"])
        data["database_url"] = clean_url
        data["database_connect_args"] = connect_args
        return data


settings = Settings()
