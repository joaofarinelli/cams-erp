// Thin API client for the dev API. Goes through the Vite proxy at /api.

export type Camera = {
  id: string;
  device_id: string;
  name: string;
  online: boolean;
  last_frame_at: string | null;
  created_at: string;
};

export type Rule = {
  id: string;
  camera_id: string;
  name: string | null;
  enabled: boolean;
  zones: Record<string, [number, number][]>;
  sensitivity: number;
  cooldown_seconds: number;
  custom_prompt: string;
  schedule: Schedule | null;
  created_at: string;
};

export type ScheduleWindow = { days: number[]; start: string; end: string };
export type Schedule = { timezone: string; windows: ScheduleWindow[] };

export type Alert = {
  id: string;
  rule_id: string;
  rule_name: string | null;
  event_id: string;
  camera_id: string;
  status: "pending" | "seen" | "false_positive";
  score: number;
  message: string;
  s3_key: string;
  created_at: string;
};

export type WSAlert = {
  type: "alert";
  id: string;
  rule_id: string;
  rule_name: string | null;
  camera_id: string;
  score: number;
  message: string;
  created_at: string;
};

const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "/api";

// ---- Auth ----
const TOKEN_KEY = "cams.auth.token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const t = getToken();
  return t ? { ...extra, Authorization: `Bearer ${t}` } : extra;
}

export type AuthUser = { id: string; email: string; name: string | null; email_verified: boolean };

export async function signup(input: { email: string; password: string; name?: string }): Promise<{
  access_token: string;
  user: AuthUser;
}> {
  const r = await fetch(`${BASE}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!r.ok) throw new Error(`signup ${r.status}: ${await r.text()}`);
  return r.json();
}

export async function login(input: { email: string; password: string }): Promise<{
  access_token: string;
  user: AuthUser;
}> {
  const r = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!r.ok) throw new Error(`login ${r.status}: ${await r.text()}`);
  return r.json();
}

export async function fetchMe(): Promise<AuthUser | null> {
  if (!getToken()) return null;
  const r = await fetch(`${BASE}/auth/me`, { headers: authHeaders() });
  if (r.status === 401) {
    setToken(null);
    return null;
  }
  if (!r.ok) throw new Error(`me ${r.status}`);
  return r.json();
}

export async function deleteMyAccount(): Promise<void> {
  const r = await fetch(`${BASE}/me`, { method: "DELETE", headers: authHeaders() });
  if (!r.ok) throw new Error(`delete-me ${r.status}`);
  setToken(null);
}

export async function exportMyData(): Promise<unknown> {
  const r = await fetch(`${BASE}/me/export`, { headers: authHeaders() });
  if (!r.ok) throw new Error(`export ${r.status}`);
  return r.json();
}

// Wrap fetch so every API call carries the bearer when present. Same-origin
// thanks to the Vite proxy.
const _origFetch = window.fetch.bind(window);
window.fetch = function (input: RequestInfo | URL, init: RequestInit = {}) {
  const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
  if (url.startsWith(BASE) || url.startsWith(window.location.origin + BASE)) {
    const headers = new Headers(init.headers || {});
    if (!headers.has("Authorization")) {
      const t = getToken();
      if (t) headers.set("Authorization", `Bearer ${t}`);
    }
    init = { ...init, headers };
  }
  return _origFetch(input, init);
} as typeof fetch;

export async function listCameras(): Promise<Camera[]> {
  const r = await fetch(`${BASE}/cameras`);
  if (!r.ok) throw new Error(`cameras GET ${r.status}`);
  return r.json();
}

export async function listRules(): Promise<Rule[]> {
  const r = await fetch(`${BASE}/rules`);
  if (!r.ok) throw new Error(`rules GET ${r.status}`);
  return r.json();
}

export type AlertFilters = {
  camera_id?: string;
  since?: string; // ISO datetime
  limit?: number;
};

export async function listAlerts(filters: AlertFilters = {}): Promise<Alert[]> {
  const params = new URLSearchParams();
  if (filters.camera_id) params.set("camera_id", filters.camera_id);
  if (filters.since) params.set("since", filters.since);
  if (filters.limit) params.set("limit", String(filters.limit));
  const qs = params.toString();
  const r = await fetch(`${BASE}/alerts${qs ? `?${qs}` : ""}`);
  if (!r.ok) throw new Error(`alerts GET ${r.status}`);
  return r.json();
}

export async function createRule(input: {
  camera_id: string;
  name?: string;
  custom_prompt: string;
  zones?: Rule["zones"];
  sensitivity?: number;
  schedule?: Schedule | null;
}): Promise<Rule> {
  const r = await fetch(`${BASE}/rules`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ zones: {}, ...input }),
  });
  if (!r.ok) throw new Error(`rules POST ${r.status}: ${await r.text()}`);
  return r.json();
}

export async function updateRule(
  ruleId: string,
  patch: Partial<Pick<Rule, "name" | "enabled" | "zones" | "sensitivity" | "cooldown_seconds" | "custom_prompt" | "schedule">>
): Promise<Rule> {
  const r = await fetch(`${BASE}/rules/${ruleId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!r.ok) throw new Error(`rules PUT ${r.status}: ${await r.text()}`);
  return r.json();
}

export async function deleteRule(ruleId: string): Promise<void> {
  const r = await fetch(`${BASE}/rules/${ruleId}`, { method: "DELETE" });
  if (!r.ok) throw new Error(`rules DELETE ${r.status}`);
}

export async function postAlertFeedback(alertId: string, isFalsePositive: boolean): Promise<Alert> {
  const r = await fetch(`${BASE}/alerts/${alertId}/feedback?is_false_positive=${isFalsePositive}`, {
    method: "POST",
  });
  if (!r.ok) throw new Error(`feedback POST ${r.status}`);
  return r.json();
}

export type Device = {
  id: string;
  name: string;
  paired: boolean;
  edge_yolo_enabled: boolean;
};

export async function listDevices(): Promise<Device[]> {
  const r = await fetch(`${BASE}/devices`);
  if (!r.ok) throw new Error(`devices GET ${r.status}`);
  return r.json();
}

export async function updateDevice(
  id: string,
  patch: { edge_yolo_enabled?: boolean; name?: string },
): Promise<Device> {
  const r = await fetch(`${BASE}/devices/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!r.ok) throw new Error(`devices PATCH ${r.status}`);
  return r.json();
}

export async function createPairCode(): Promise<{
  pair_code: string;
  expires_at: string;
  device_id: string;
}> {
  const r = await fetch(`${BASE}/pair/code`, { method: "POST" });
  if (!r.ok) throw new Error(`pair/code ${r.status}`);
  return r.json();
}

export type DiscoveredDevice = {
  ip: string;
  name: string | null;
  vendor: string | null;
  xaddrs: string[];
  url_templates: { label: string; url: string }[];
};

export async function discoverCameras(deviceId: string): Promise<DiscoveredDevice[]> {
  const r = await fetch(`${BASE}/onboarding/cameras/discover`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ device_id: deviceId }),
  });
  if (!r.ok) throw new Error(`discover ${r.status}: ${await r.text()}`);
  return (await r.json()).devices;
}

export type LocalDevice = { name: string; kind: string; source: string };

export async function listLocalDevices(deviceId: string): Promise<LocalDevice[]> {
  const r = await fetch(`${BASE}/onboarding/cameras/local-devices`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ device_id: deviceId }),
  });
  if (!r.ok) throw new Error(`local-devices ${r.status}: ${await r.text()}`);
  return (await r.json()).local_devices;
}

export function liveStreamUrl(cameraId: string): string {
  const t = encodeURIComponent(getToken() ?? "");
  if (BASE.startsWith("http")) {
    return BASE.replace(/^http/, "ws") + `/cameras/${cameraId}/live?token=${t}`;
  }
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}${BASE}/cameras/${cameraId}/live?token=${t}`;
}

export type BulkProbeMatch = {
  ip: string;
  name?: string | null;
  vendor?: string | null;
  ok: boolean;
  label?: string | null;
  url?: string | null;
  user?: string | null;
};

export async function bulkProbeCameras(
  deviceId: string,
  ips: { ip: string; vendor?: string | null; name?: string | null }[],
  credentials: [string, string][],
): Promise<BulkProbeMatch[]> {
  const r = await fetch(`${BASE}/onboarding/cameras/bulk-probe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ device_id: deviceId, ips, credentials }),
  });
  if (!r.ok) throw new Error(`bulk-probe ${r.status}: ${await r.text()}`);
  return (await r.json()).matches;
}

export async function createCamerasBulk(
  deviceId: string,
  cameras: { name: string; rtsp_url: string }[],
): Promise<Camera[]> {
  const r = await fetch(`${BASE}/cameras/bulk`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ device_id: deviceId, cameras }),
  });
  if (!r.ok) throw new Error(`cameras/bulk ${r.status}: ${await r.text()}`);
  return r.json();
}

export async function fetchAgentStatus(deviceId: string): Promise<{ online: boolean }> {
  const r = await fetch(`${BASE}/onboarding/cameras/agent-status?device_id=${deviceId}`);
  if (!r.ok) throw new Error(`agent-status ${r.status}`);
  return r.json();
}

export type Templates = Record<string, { label: string; url: string }[]>;

export async function fetchTemplates(): Promise<Templates> {
  const r = await fetch(`${BASE}/onboarding/cameras/templates`);
  if (!r.ok) throw new Error(`templates ${r.status}`);
  return (await r.json()).vendors;
}

export type ProbeResult = {
  ok: boolean;
  codec: string | null;
  width: number | null;
  height: number | null;
  fps: number | null;
  error: string | null;
  preview_data_url: string | null;
};

export async function probeStream(deviceId: string, rtsp_url: string): Promise<ProbeResult> {
  const r = await fetch(`${BASE}/onboarding/cameras/probe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ device_id: deviceId, rtsp_url, include_frame: true }),
  });
  if (!r.ok) throw new Error(`probe ${r.status}: ${await r.text()}`);
  return r.json();
}

export async function createCamera(input: {
  name: string;
  rtsp_url: string;
  device_id: string;
}): Promise<Camera> {
  const r = await fetch(`${BASE}/cameras`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!r.ok) throw new Error(`cameras POST ${r.status}: ${await r.text()}`);
  return r.json();
}

export type Subscriber = {
  id: string;
  kind: "whatsapp" | "expo_push";
  target: string;
  enabled: boolean;
  created_at: string;
};

export async function listSubscribers(): Promise<Subscriber[]> {
  const r = await fetch(`${BASE}/me/subscribers`);
  if (!r.ok) throw new Error(`subscribers GET ${r.status}`);
  return r.json();
}

export async function createSubscriber(kind: Subscriber["kind"], target: string): Promise<Subscriber> {
  const r = await fetch(`${BASE}/me/subscribers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind, target }),
  });
  if (!r.ok) throw new Error(`subscribers POST ${r.status}: ${await r.text()}`);
  return r.json();
}

export async function deleteSubscriber(id: string): Promise<void> {
  const r = await fetch(`${BASE}/me/subscribers/${id}`, { method: "DELETE" });
  if (!r.ok) throw new Error(`subscribers DELETE ${r.status}`);
}

export async function runDigestNow(): Promise<{ sent: boolean }> {
  const r = await fetch(`${BASE}/digest/run-now`, { method: "POST" });
  if (!r.ok) throw new Error(`digest POST ${r.status}: ${await r.text()}`);
  return r.json();
}

export async function clipUrl(s3_key: string): Promise<string> {
  const r = await fetch(`${BASE}/clips/signed-url?key=${encodeURIComponent(s3_key)}`);
  if (!r.ok) throw new Error(`clip URL ${r.status}`);
  const j = await r.json();
  return j.url as string;
}

export function thumbUrl(cameraId: string, bust = 0): string {
  const t = encodeURIComponent(getToken() ?? "");
  const ts = bust ? `&ts=${bust}` : "";
  return `${BASE}/cameras/${cameraId}/thumb.jpg?token=${t}${ts}`;
}

export function openAlertStream(onMessage: (alert: WSAlert) => void): () => void {
  // Vite proxy forwards /api/alerts/stream over WS. Same-origin URL so no
  // CORS / cookies pain.
  const wsUrl = BASE.startsWith("http")
    ? BASE.replace(/^http/, "ws") + "/alerts/stream"
    : `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}${BASE}/alerts/stream`;
  const ws = new WebSocket(wsUrl);
  ws.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data);
      if (data.type === "alert") onMessage(data as WSAlert);
    } catch {
      // ignore
    }
  };
  return () => ws.close();
}
