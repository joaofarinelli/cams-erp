"""Detect a running tailscaled and report the agent's tailnet IP.

When Tailscale is installed on the PDV PC, the customer can grant the
operator access to the LAN cameras directly (no cloud roundtrip for live
view, which saves bandwidth and latency). We just *report* the tailnet
status here; the actual VPN install is the customer's responsibility,
documented in the onboarding guide.

The agent's heartbeat picks up `status()` and forwards the value, which
the web panel uses to surface "Acesso remoto direto disponível" + the
machine's MagicDNS name.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any


def status() -> dict[str, Any] | None:
    """Returns {ip, hostname, online} when tailscaled is running, else None."""
    try:
        out = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    try:
        data = json.loads(out.stdout)
    except json.JSONDecodeError:
        return None
    self_node = data.get("Self") or {}
    ip_list = self_node.get("TailscaleIPs") or []
    if not ip_list:
        return None
    return {
        "ip": ip_list[0],
        "hostname": self_node.get("HostName"),
        "magic_dns": self_node.get("DNSName"),
        "online": bool(self_node.get("Online")),
    }
