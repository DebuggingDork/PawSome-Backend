"""Validation shared by the proxied photo-upload routes.

These back up the presigned-PUT flow (see services/r2.py). When the browser
uploads straight to R2, R2 itself enforces the content type baked into the
signature and the route checks the size afterwards with a HEAD. When the bytes
come through this API instead, nothing has vetted them yet — so both checks
happen here, before anything reaches storage.
"""
from fastapi import HTTPException, UploadFile, status

from app.services import r2

# Enough to read the file's magic number and no more.
_CHUNK_BYTES = 64 * 1024


def validated_upload_content_type(file: UploadFile) -> str:
    """The declared content type, or a 400 naming what is accepted.

    Trusts the browser's declaration in the same way the presigned flow does:
    there, the client picks the content type and it is signed into the URL.
    The object key's extension is derived from this either way.
    """
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in r2.ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image must be a JPEG, PNG, or WebP.",
        )
    return content_type


async def read_upload_within_limit(file: UploadFile) -> bytes:
    """Read the whole upload, refusing anything over the photo size limit.

    Streamed rather than a single `await file.read()`: the limit has to be
    enforced *while* reading, otherwise a client claiming to send a photo can
    make this server allocate however many gigabytes it feels like first and
    only then be told it was too big.
    """
    limit = r2.MAX_PHOTO_BYTES
    chunks: list[bytes] = []
    total = 0

    while chunk := await file.read(_CHUNK_BYTES):
        total += len(chunk)
        if total > limit:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Image exceeds {limit // (1024 * 1024)} MB limit",
            )
        chunks.append(chunk)

    if total == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That file was empty.",
        )

    return b"".join(chunks)
