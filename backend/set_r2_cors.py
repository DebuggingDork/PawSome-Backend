"""Apply CORS policy to the R2 bucket so browsers can PUT directly to presigned URLs.

R2 bucket CORS is separate from the FastAPI app's CORS_ORIGINS setting - it must be
set on the bucket itself via the S3-compatible API. Without it, the browser's PUT to
the presigned URL is blocked before it ever reaches R2 (shows as a failed request with
no status code in devtools, and the frontend reports "Upload failed. Try again.").
"""
from app.core.config import settings
from app.services.r2 import _client

ALLOWED_ORIGINS = [
    "http://localhost:5174",
    "http://localhost:5173",
]

CORS_CONFIGURATION = {
    "CORSRules": [
        {
            "AllowedOrigins": ALLOWED_ORIGINS,
            "AllowedMethods": ["PUT", "GET", "HEAD"],
            "AllowedHeaders": ["content-type"],
            "MaxAgeSeconds": 3600,
        }
    ]
}


def main() -> None:
    client = _client()
    client.put_bucket_cors(Bucket=settings.r2_bucket_name, CORSConfiguration=CORS_CONFIGURATION)
    print(f"CORS policy applied to bucket '{settings.r2_bucket_name}':")
    result = client.get_bucket_cors(Bucket=settings.r2_bucket_name)
    for rule in result["CORSRules"]:
        print(f"  origins={rule['AllowedOrigins']} methods={rule['AllowedMethods']}")


if __name__ == "__main__":
    main()
