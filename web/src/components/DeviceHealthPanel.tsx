import { useEffect, useState } from "react";
import {
  AgentError,
  Device,
  DeviceDetail,
  fetchDevice,
  fetchDeviceErrors,
  listDevices,
} from "../api";
import { Card, CardContent } from "./ui/card";
import { Badge } from "./ui/badge";
import { AlertTriangle, CheckCircle2, Cpu, XCircle } from "lucide-react";


function timeAgo(iso: string | null): string {
  if (!iso) return "nunca";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return `há ${Math.round(s)}s`;
  if (s < 3600) return `há ${Math.round(s / 60)}min`;
  if (s < 86400) return `há ${Math.round(s / 3600)}h`;
  return `há ${Math.round(s / 86400)}d`;
}


function DeviceRow({ device }: { device: Device }) {
  const [detail, setDetail] = useState<DeviceDetail | null>(null);
  const [errors, setErrors] = useState<AgentError[]>([]);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [d, e] = await Promise.all([
          fetchDevice(device.id),
          fetchDeviceErrors(device.id, 10),
        ]);
        if (!cancelled) {
          setDetail(d);
          setErrors(e);
        }
      } catch {
        // ignore — keep last state
      }
    };
    load();
    const id = setInterval(load, 15000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [device.id]);

  const tests = detail?.last_self_test_json?.results || [];
  const ok = tests.filter((t) => t.ok).length;
  const tail = detail?.last_self_test_json?.tailscale;
  const heartbeatStale =
    detail?.last_heartbeat_at &&
    Date.now() - new Date(detail.last_heartbeat_at).getTime() > 90000;

  return (
    <div className="rounded-md border p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Cpu className="h-4 w-4 text-muted-foreground" />
          <div>
            <p className="text-sm font-medium">{device.name}</p>
            <p className="text-xs text-muted-foreground">
              último heartbeat: {timeAgo(detail?.last_heartbeat_at ?? null)}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs">
          {heartbeatStale && <Badge variant="destructive">offline</Badge>}
          {device.edge_yolo_enabled && <Badge variant="secondary">Edge YOLO</Badge>}
          {tests.length > 0 && (
            <Badge variant={ok === tests.length ? "default" : "destructive"}>
              {ok}/{tests.length} câmeras
            </Badge>
          )}
          {errors.length > 0 && (
            <Badge variant="destructive">
              <AlertTriangle className="mr-1 h-3 w-3" />
              {errors.length} erro{errors.length === 1 ? "" : "s"}
            </Badge>
          )}
        </div>
      </div>

      {tail && (
        <p className="mt-2 text-xs text-muted-foreground">
          Tailscale: {tail.ip} {tail.online ? "(online)" : "(offline)"}
        </p>
      )}

      {(tests.length > 0 || errors.length > 0) && (
        <button
          className="mt-2 text-xs text-muted-foreground underline"
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? "Esconder detalhes" : "Ver detalhes"}
        </button>
      )}

      {expanded && (
        <div className="mt-2 space-y-2">
          {tests.length > 0 && (
            <div className="space-y-1 text-xs">
              <p className="font-medium text-muted-foreground">Diagnóstico câmeras:</p>
              {tests.map((t) => (
                <div key={t.camera_id} className="flex items-center gap-2">
                  {t.ok ? (
                    <CheckCircle2 className="h-3 w-3 text-emerald-500" />
                  ) : (
                    <XCircle className="h-3 w-3 text-destructive" />
                  )}
                  <span className="font-medium">{t.name}:</span>
                  <span className="text-muted-foreground">{t.message}</span>
                </div>
              ))}
            </div>
          )}
          {errors.length > 0 && (
            <div className="space-y-1 text-xs">
              <p className="font-medium text-muted-foreground">Erros recentes:</p>
              {errors.slice(0, 5).map((e) => (
                <div key={e.id} className="rounded border bg-secondary/40 p-2">
                  <p className="font-medium">{e.kind}</p>
                  <p className="text-muted-foreground">{e.message}</p>
                  <p className="text-[10px] text-muted-foreground">
                    {timeAgo(e.occurred_at)} · {e.agent_version || "?"}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}


export function DeviceHealthPanel() {
  const [devices, setDevices] = useState<Device[]>([]);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      listDevices()
        .then((d) => {
          if (!cancelled) setDevices(d);
        })
        .catch(() => {});
    };
    load();
    const id = setInterval(load, 30000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  if (devices.length === 0) return null;
  return (
    <Card>
      <CardContent className="space-y-2 p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Saúde dos PDVs
        </p>
        {devices.map((d) => (
          <DeviceRow key={d.id} device={d} />
        ))}
      </CardContent>
    </Card>
  );
}
