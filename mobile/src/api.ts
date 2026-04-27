import Constants from "expo-constants";

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

const cfg = (Constants.expoConfig?.extra ?? {}) as { apiBase?: string };
export const API_BASE = cfg.apiBase ?? "http://localhost:8000";

export async function listAlerts(): Promise<Alert[]> {
  const r = await fetch(`${API_BASE}/alerts`);
  if (!r.ok) throw new Error(`alerts GET ${r.status}`);
  return r.json();
}

export async function postFeedback(alertId: string, isFalsePositive: boolean): Promise<Alert> {
  const r = await fetch(
    `${API_BASE}/alerts/${alertId}/feedback?is_false_positive=${isFalsePositive}`,
    { method: "POST" }
  );
  if (!r.ok) throw new Error(`feedback POST ${r.status}`);
  return r.json();
}

export function clipUrl(s3_key: string): string {
  return `${API_BASE}/dev/s3/${s3_key}`;
}

export function openAlertStream(onMessage: (alert: WSAlert) => void): () => void {
  const url = API_BASE.replace(/^http/, "ws") + "/alerts/stream";
  const ws = new WebSocket(url);
  ws.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data);
      if (data.type === "alert") onMessage(data as WSAlert);
    } catch {
      // ignore
    }
  };
  ws.onerror = (e) => console.warn("ws error", e);
  return () => ws.close();
}
