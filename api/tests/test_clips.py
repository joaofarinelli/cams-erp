from httpx import AsyncClient
from moto import mock_aws


async def test_agent_requests_upload_url(device_client: AsyncClient, seed_camera) -> None:
    import boto3

    with mock_aws():
        boto3.client("s3", region_name="sa-east-1").create_bucket(
            Bucket="cams-erp-staging-clips",
            CreateBucketConfiguration={"LocationConstraint": "sa-east-1"},
        )

        payload = {
            "camera_id": str(seed_camera.id),
            "started_at": "2026-04-27T12:00:00Z",
            "duration_ms": 10000,
        }
        r = await device_client.post("/clips/upload-url", json=payload)
        assert r.status_code == 200
        body = r.json()
        assert "upload_url" in body
        assert body["s3_key"].endswith(".mp4")
