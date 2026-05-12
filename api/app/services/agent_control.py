"""Agent control plane: maps device_id -> active WebSocket and provides
request/response RPC over that socket.

Limitation: this registry is in-memory per process. Works as long as the API
runs on a single machine. To scale horizontally, replace with a pub/sub
fan-out (Redis Streams, NATS) or pin agent connections via consistent
hashing. For now we keep `fly scale count 1` for the API.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import WebSocket


class AgentOfflineError(Exception):
    pass


class AgentControlRegistry:
    def __init__(self) -> None:
        self._sockets: dict[str, WebSocket] = {}
        self._pending: dict[str, asyncio.Future] = {}
        # camera_id -> set of viewer browser WebSockets
        self._viewers: dict[str, set[WebSocket]] = {}
        # camera_id -> device_id for cleanup
        self._stream_devices: dict[str, str] = {}

    def register(self, device_id: str, ws: WebSocket) -> None:
        self._sockets[device_id] = ws

    def unregister(self, device_id: str, ws: WebSocket) -> None:
        if self._sockets.get(device_id) is ws:
            self._sockets.pop(device_id, None)
        # tear down any active streams owned by this device
        for cam_id, dev in list(self._stream_devices.items()):
            if dev == device_id:
                self._stream_devices.pop(cam_id, None)
                self._viewers.pop(cam_id, None)

    def is_online(self, device_id: str) -> bool:
        return device_id in self._sockets

    async def add_viewer(
        self,
        camera_id: str,
        device_id: str,
        rtsp_url: str,
        viewer: WebSocket,
    ) -> None:
        first = camera_id not in self._viewers
        self._viewers.setdefault(camera_id, set()).add(viewer)
        self._stream_devices[camera_id] = device_id
        if first:
            agent_ws = self._sockets.get(device_id)
            if agent_ws is not None:
                await agent_ws.send_json(
                    {"type": "live_start", "camera_id": camera_id, "rtsp_url": rtsp_url}
                )

    async def remove_viewer(self, camera_id: str, viewer: WebSocket) -> None:
        viewers = self._viewers.get(camera_id)
        if viewers is None:
            return
        viewers.discard(viewer)
        if viewers:
            return
        self._viewers.pop(camera_id, None)
        device_id = self._stream_devices.pop(camera_id, None)
        if device_id is None:
            return
        agent_ws = self._sockets.get(device_id)
        if agent_ws is not None:
            try:
                await agent_ws.send_json({"type": "live_stop", "camera_id": camera_id})
            except Exception:  # noqa: BLE001
                pass

    async def broadcast_frame(self, camera_id: str, jpeg: bytes) -> None:
        viewers = self._viewers.get(camera_id)
        if not viewers:
            return
        dead: list[WebSocket] = []
        for ws in list(viewers):
            try:
                await ws.send_bytes(jpeg)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            viewers.discard(ws)

    async def call(
        self,
        device_id: str,
        type_: str,
        params: dict[str, Any],
        timeout: float = 15.0,
    ) -> dict[str, Any]:
        ws = self._sockets.get(device_id)
        if ws is None:
            raise AgentOfflineError(device_id)
        job_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        self._pending[job_id] = fut
        try:
            await ws.send_json({"job_id": job_id, "type": type_, "params": params})
            return await asyncio.wait_for(fut, timeout=timeout)
        finally:
            self._pending.pop(job_id, None)

    def resolve(self, job_id: str, result: dict[str, Any]) -> None:
        fut = self._pending.get(job_id)
        if fut and not fut.done():
            fut.set_result(result)


registry = AgentControlRegistry()
