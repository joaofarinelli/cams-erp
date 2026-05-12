import boto3
from botocore.config import Config

from app.config import get_settings


def _client():
    settings = get_settings()
    kwargs: dict = {
        "region_name": settings.aws_region,
        "config": Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
    }
    if settings.aws_endpoint_url:
        kwargs["endpoint_url"] = settings.aws_endpoint_url
    return boto3.client("s3", **kwargs)


def signed_put_url(key: str, expires_in: int = 600) -> str:
    settings = get_settings()
    if settings.auth_bypass:
        base = settings.aws_endpoint_url or "http://localhost:8000"
        return f"{base}/dev/s3/{key}"
    return _client().generate_presigned_url(
        ClientMethod="put_object",
        Params={"Bucket": settings.clips_bucket, "Key": key, "ContentType": "video/mp4"},
        ExpiresIn=expires_in,
        HttpMethod="PUT",
    )


def signed_get_url(key: str, expires_in: int = 600) -> str:
    settings = get_settings()
    if settings.auth_bypass:
        base = settings.aws_endpoint_url or "http://localhost:8000"
        return f"{base}/dev/s3/{key}"
    return _client().generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": settings.clips_bucket, "Key": key},
        ExpiresIn=expires_in,
        HttpMethod="GET",
    )
