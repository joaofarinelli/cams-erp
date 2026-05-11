from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class HeartbeatIn(BaseModel):
    cameras_status: dict[str, bool]
    cpu_pct: float
    ram_mb: int
    disk_free_mb: int
    agent_version: str


class HeartbeatOut(BaseModel):
    server_time: datetime
    config_etag: str


class CameraConfigItem(BaseModel):
    camera_id: UUID
    name: str
    rtsp_url: str
    rules: list[dict]


class AgentConfigOut(BaseModel):
    etag: str
    cameras: list[CameraConfigItem]
    edge_yolo_enabled: bool = False
    device_name: str | None = None
