import boto3

from app.config import get_settings


def signed_put_url(key: str, expires_in: int = 600) -> str:
    settings = get_settings()
    if settings.auth_bypass:
        # Dev mode: use the API's own /dev/s3/ stub so we don't need moto/localstack.
        base = settings.aws_endpoint_url or "http://localhost:8000"
        return f"{base}/dev/s3/{key}"
    kwargs: dict = {"region_name": settings.aws_region}
    if settings.aws_endpoint_url:
        kwargs["endpoint_url"] = settings.aws_endpoint_url
    s3 = boto3.client("s3", **kwargs)
    return s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={"Bucket": settings.clips_bucket, "Key": key, "ContentType": "video/mp4"},
        ExpiresIn=expires_in,
        HttpMethod="PUT",
    )
