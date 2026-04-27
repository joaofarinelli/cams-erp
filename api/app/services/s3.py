import boto3

from app.config import get_settings


def signed_put_url(key: str, expires_in: int = 600) -> str:
    settings = get_settings()
    s3 = boto3.client("s3", region_name=settings.aws_region)
    return s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={"Bucket": settings.clips_bucket, "Key": key, "ContentType": "video/mp4"},
        ExpiresIn=expires_in,
        HttpMethod="PUT",
    )
