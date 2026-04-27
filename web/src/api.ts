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
  preset_type: "cash_register" | "kitchen_consumption" | "retail_shelf";
  name: string | null;
  enabled: boolean;
  zones: Record<string, [number, number][]>;
  sensitivity: number;
  cooldown_seconds: number;
  custom_prompt: string | null;
  created_at: string;
};

export type Alert = {
  id: string;
  rule_id: string;
  rule_name: string | null;
  event_id: string;
  camera_id: string;
  preset_type: string;
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
  preset_type: string;
  score: number;
  message: string;
  created_at: string;
};

const BASE = "/api";

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
  preset_type?: Rule["preset_type"];
  since?: string; // ISO datetime
  limit?: number;
};

export async function listAlerts(filters: AlertFilters = {}): Promise<Alert[]> {
  const params = new URLSearchParams();
  if (filters.camera_id) params.set("camera_id", filters.camera_id);
  if (filters.preset_type) params.set("preset_type", filters.preset_type);
  if (filters.since) params.set("since", filters.since);
  if (filters.limit) params.set("limit", String(filters.limit));
  const qs = params.toString();
  const r = await fetch(`${BASE}/alerts${qs ? `?${qs}` : ""}`);
  if (!r.ok) throw new Error(`alerts GET ${r.status}`);
  return r.json();
}

export async function createRule(input: {
  camera_id: string;
  preset_type: Rule["preset_type"];
  name?: string;
  custom_prompt?: string;
  zones?: Rule["zones"];
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
  patch: Partial<Pick<Rule, "name" | "enabled" | "zones" | "sensitivity" | "cooldown_seconds" | "custom_prompt">>
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

export function clipUrl(s3_key: string): string {
  return `${BASE}/dev/s3/${s3_key}`;
}

export function thumbUrl(cameraId: string, bust = 0): string {
  // bust is appended as a query param so the browser refetches when we want
  // a fresh thumbnail (e.g. after a new event has come in).
  return `${BASE}/cameras/${cameraId}/thumb.jpg${bust ? `?t=${bust}` : ""}`;
}

export function openAlertStream(onMessage: (alert: WSAlert) => void): () => void {
  // Vite proxy forwards /api/alerts/stream over WS. Same-origin URL so no
  // CORS / cookies pain.
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}${BASE}/alerts/stream`);
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
