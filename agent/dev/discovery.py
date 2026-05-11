"""ONVIF WS-Discovery over UDP multicast.

Sends a single Probe packet to 239.255.255.250:3702 and collects responses
for ~3s. No per-host scan, no nmap. Devices that don't speak ONVIF (or are
on a different subnet / blocked by router) won't show up — fall back to
manual IP entry in the UI."""

from __future__ import annotations

import asyncio
import logging
import re
import socket
import uuid
from typing import Any
from xml.etree import ElementTree as ET

log = logging.getLogger("discovery")

WS_DISCOVERY_GROUP = "239.255.255.250"
WS_DISCOVERY_PORT = 3702

PROBE_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing"
            xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"
            xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
  <s:Header>
    <a:Action s:mustUnderstand="1">http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</a:Action>
    <a:MessageID>uuid:{uuid}</a:MessageID>
    <a:To s:mustUnderstand="1">urn:schemas-xmlsoap-org:ws:2005:04:discovery</a:To>
  </s:Header>
  <s:Body>
    <d:Probe>
      <d:Types>dn:NetworkVideoTransmitter</d:Types>
    </d:Probe>
  </s:Body>
</s:Envelope>"""

NS = {
    "s": "http://www.w3.org/2003/05/soap-envelope",
    "d": "http://schemas.xmlsoap.org/ws/2005/04/discovery",
    "a": "http://schemas.xmlsoap.org/ws/2004/08/addressing",
}

VENDOR_HINTS = [
    ("hikvision", "hikvision"),
    ("intelbras", "intelbras"),
    ("dahua", "dahua"),
    ("axis", "axis"),
    ("amcrest", "dahua"),
    ("uniview", "uniview"),
    ("vivotek", "vivotek"),
]


def _parse_probe_match(xml_bytes: bytes) -> dict[str, Any] | None:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None
    addrs_el = root.find(".//d:XAddrs", NS)
    scopes_el = root.find(".//d:Scopes", NS)
    types_el = root.find(".//d:Types", NS)
    if addrs_el is None:
        return None
    xaddrs = (addrs_el.text or "").split()
    scopes = (scopes_el.text or "").split() if scopes_el is not None else []
    types = (types_el.text or "") if types_el is not None else ""

    # First IP from the first xaddr URL
    ip = None
    for x in xaddrs:
        m = re.search(r"https?://([^:/]+)", x)
        if m:
            ip = m.group(1)
            break

    vendor = None
    name = None
    scope_blob = " ".join(scopes).lower()
    for needle, label in VENDOR_HINTS:
        if needle in scope_blob:
            vendor = label
            break
    for s in scopes:
        if s.startswith("onvif://www.onvif.org/name/"):
            name = s.rsplit("/", 1)[-1].replace("%20", " ")
        elif s.startswith("onvif://www.onvif.org/hardware/"):
            name = name or s.rsplit("/", 1)[-1].replace("%20", " ")
    return {
        "ip": ip,
        "xaddrs": xaddrs,
        "scopes": scopes,
        "types": types,
        "vendor": vendor,
        "name": name,
    }


class _DiscoveryProtocol(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.devices: list[dict] = []
        self._seen: set[str] = set()

    def datagram_received(self, data: bytes, addr) -> None:
        parsed = _parse_probe_match(data)
        if parsed is None or not parsed.get("ip"):
            return
        key = parsed["ip"]
        if key in self._seen:
            return
        self._seen.add(key)
        self.devices.append(parsed)


async def ws_discover(timeout: float = 3.0) -> list[dict]:
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        _DiscoveryProtocol,
        local_addr=("0.0.0.0", 0),
        family=socket.AF_INET,
        allow_broadcast=True,
    )
    try:
        sock: socket.socket = transport.get_extra_info("socket")
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        msg = PROBE_TEMPLATE.format(uuid=uuid.uuid4()).encode()
        transport.sendto(msg, (WS_DISCOVERY_GROUP, WS_DISCOVERY_PORT))
        await asyncio.sleep(timeout)
        return list(protocol.devices)
    finally:
        transport.close()


# RTSP URL templates per vendor. {user},{pass},{ip} placeholders. Listed
# main + sub stream where the brand has a documented split.
URL_TEMPLATES: dict[str, list[dict]] = {
    "hikvision": [
        {"label": "Main (HD)", "url": "rtsp://{user}:{password}@{ip}:554/Streaming/Channels/101"},
        {"label": "Sub (SD)", "url": "rtsp://{user}:{password}@{ip}:554/Streaming/Channels/102"},
        {"label": "ISAPI snapshot ch1", "url": "http://{user}:{password}@{ip}/ISAPI/Streaming/channels/101/picture"},
    ],
    "intelbras": [
        {"label": "Main", "url": "rtsp://{user}:{password}@{ip}:554/cam/realmonitor?channel=1&subtype=0"},
        {"label": "Sub", "url": "rtsp://{user}:{password}@{ip}:554/cam/realmonitor?channel=1&subtype=1"},
    ],
    "dahua": [
        {"label": "Main", "url": "rtsp://{user}:{password}@{ip}:554/cam/realmonitor?channel=1&subtype=0"},
        {"label": "Sub", "url": "rtsp://{user}:{password}@{ip}:554/cam/realmonitor?channel=1&subtype=1"},
    ],
    "axis": [
        {"label": "Main", "url": "rtsp://{user}:{password}@{ip}:554/axis-media/media.amp"},
    ],
    "uniview": [
        {"label": "Main", "url": "rtsp://{user}:{password}@{ip}:554/media/video1"},
        {"label": "Sub", "url": "rtsp://{user}:{password}@{ip}:554/media/video2"},
    ],
    "vivotek": [
        {"label": "Main", "url": "rtsp://{user}:{password}@{ip}:554/live.sdp"},
    ],
    "generic": [
        {"label": "ONVIF stream 1", "url": "rtsp://{user}:{password}@{ip}:554/onvif1"},
        {"label": "ONVIF stream 2", "url": "rtsp://{user}:{password}@{ip}:554/onvif2"},
        {"label": "Generic /live", "url": "rtsp://{user}:{password}@{ip}:554/live"},
    ],
    "iphone": [
        {"label": "IP Camera Lite", "url": "rtsp://{user}:{password}@{ip}:8554/live"},
    ],
}


def url_templates_for(vendor: str | None) -> list[dict]:
    if vendor and vendor in URL_TEMPLATES:
        return URL_TEMPLATES[vendor] + URL_TEMPLATES["generic"]
    return URL_TEMPLATES["generic"]
