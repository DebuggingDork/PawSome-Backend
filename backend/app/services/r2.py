"""Cloudflare R2 storage (S3-compatible API via boto3).

Upload flow:
1. Client asks for a presigned PUT URL (we never proxy image bytes).
2. Client PUTs the file directly to R2.
3. Client confirms; we verify the object exists, then save the DB row.

boto3 is sync — network calls (head/delete) must be wrapped in
run_in_threadpool by the caller's route. Presigning is pure local
computation (no network), so it's safe to call directly.
"""
import uuid
from functools import lru_cache

import boto3
from botocore.client import Config

from app.core.config import settings

PRESIGNED_URL_EXPIRES_SECONDS = 600
MAX_PHOTO_BYTES = 10 * 1024 * 1024  # 10 MB

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


@lru_cache(maxsize=1)
def _client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


def build_object_key(pet_id: uuid.UUID, content_type: str) -> str:
    ext = ALLOWED_CONTENT_TYPES[content_type]
    return f"pets/{pet_id}/{uuid.uuid4().hex}.{ext}"


def build_user_photo_key(user_id: uuid.UUID, content_type: str) -> str:
    """Build object key for user profile photo"""
    ext = ALLOWED_CONTENT_TYPES[content_type]
    return f"users/{user_id}/profile.{ext}"


def public_url(object_key: str) -> str:
    return f"{settings.r2_public_base_url.rstrip('/')}/{object_key}"


def create_presigned_upload(object_key: str, content_type: str) -> str:
    """Presigned PUT URL. ContentType is part of the signature, so the
    client must upload with the exact same Content-Type header."""
    return _client().generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.r2_bucket_name,
            "Key": object_key,
            "ContentType": content_type,
        },
        ExpiresIn=PRESIGNED_URL_EXPIRES_SECONDS,
    )


def get_object_size(object_key: str) -> int | None:
    """Object size in bytes, or None if the object doesn't exist.
    Blocking — call via run_in_threadpool."""
    try:
        head = _client().head_object(Bucket=settings.r2_bucket_name, Key=object_key)
    except _client().exceptions.ClientError:
        return None
    return head["ContentLength"]


def delete_object(object_key: str) -> None:
    """Blocking — call via run_in_threadpool. Idempotent (S3 delete
    succeeds even if the key is already gone)."""
    _client().delete_object(Bucket=settings.r2_bucket_name, Key=object_key)
