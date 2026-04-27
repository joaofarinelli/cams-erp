import json

import boto3

from app.config import get_settings


def enqueue_event(payload: dict) -> str:
    settings = get_settings()
    sqs = boto3.client("sqs", region_name=settings.aws_region)
    resp = sqs.send_message(QueueUrl=settings.events_queue_url, MessageBody=json.dumps(payload))
    return resp["MessageId"]
