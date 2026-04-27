import base64

import boto3

from app.config import get_settings


def encrypt(plaintext: str) -> str:
    settings = get_settings()
    if settings.env in ("test", "dev"):
        return base64.b64encode(plaintext.encode()).decode()
    kms = boto3.client("kms", region_name=settings.aws_region)
    resp = kms.encrypt(KeyId=f"alias/cams-erp-{settings.env}-app", Plaintext=plaintext.encode())
    return base64.b64encode(resp["CiphertextBlob"]).decode()


def decrypt(ciphertext_b64: str) -> str:
    settings = get_settings()
    if settings.env in ("test", "dev"):
        return base64.b64decode(ciphertext_b64).decode()
    kms = boto3.client("kms", region_name=settings.aws_region)
    resp = kms.decrypt(CiphertextBlob=base64.b64decode(ciphertext_b64))
    return resp["Plaintext"].decode()
