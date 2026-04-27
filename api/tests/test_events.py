import boto3
from httpx import AsyncClient
from moto import mock_aws


async def test_agent_posts_event_and_it_enqueues(
    device_client: AsyncClient, seed_camera, monkeypatch
) -> None:
    with mock_aws():
        sqs = boto3.client("sqs", region_name="sa-east-1")
        queue_url = sqs.create_queue(QueueName="test-events")["QueueUrl"]
        monkeypatch.setenv("CAMS_EVENTS_QUEUE_URL", queue_url)
        from app.config import get_settings

        get_settings.cache_clear()

        payload = {
            "camera_id": str(seed_camera.id),
            "s3_key": "clips/x/y/z.mp4",
            "motion_score": 0.78,
            "started_at": "2026-04-27T12:00:00Z",
            "duration_ms": 10000,
        }
        r = await device_client.post("/events", json=payload)
        assert r.status_code == 201
        assert r.json()["enqueued"] is True

        msgs = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1)
        assert "Messages" in msgs
