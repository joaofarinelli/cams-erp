import json

import boto3

from app.config import get_settings


def enqueue_event(payload: dict) -> str:
    settings = get_settings()
    if settings.auth_bypass:
        from app.routers.dev_storage import append_event

        append_event(payload)
        return "dev-stub"
    if not settings.events_queue_url:
        # Production worker polls the events table directly. No queue needed.
        return "db-poll"
    kwargs: dict = {"region_name": settings.aws_region}
    if settings.aws_endpoint_url:
        kwargs["endpoint_url"] = settings.aws_endpoint_url
    sqs = boto3.client("sqs", **kwargs)
    resp = sqs.send_message(QueueUrl=settings.events_queue_url, MessageBody=json.dumps(payload))
    return resp["MessageId"]
