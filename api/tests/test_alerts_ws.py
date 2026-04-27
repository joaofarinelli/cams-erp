from fastapi.testclient import TestClient

from app.main import create_app
from app.security.cognito import get_current_user
from app.services.pubsub import broker


def test_ws_receives_published_alert(seed_user) -> None:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: seed_user
    client = TestClient(app)
    with client.websocket_connect("/alerts/stream") as ws:
        ws.portal.call(broker.publish, seed_user.id, {"type": "alert", "id": "abc"})
        msg = ws.receive_json()
        assert msg == {"type": "alert", "id": "abc"}
