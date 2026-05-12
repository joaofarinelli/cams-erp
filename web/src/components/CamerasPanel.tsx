import { useEffect, useState } from "react";
import { Camera, Device, Rule, listDevices, thumbUrl, updateDevice } from "../api";
import { CameraWizard } from "./CameraWizard";
import { CameraLive } from "./CameraLive";
import { Card, CardContent } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Plus, Play, Camera as CameraIcon, Cpu } from "lucide-react";
import { DeviceHealthPanel } from "./DeviceHealthPanel";
import { cn } from "@/lib/utils";

function DevicesStrip() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const refresh = () => listDevices().then(setDevices).catch(() => {});
  useEffect(() => { refresh(); }, []);
  if (devices.length === 0) return null;
  return (
    <Card>
      <CardContent className="space-y-2 p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">PDVs / agentes</p>
        {devices.map((d) => (
          <div key={d.id} className="flex items-center justify-between gap-3 rounded-md border p-2 text-sm">
            <div className="flex items-center gap-2">
              <Cpu className="h-4 w-4 text-muted-foreground" />
              <span className="font-medium">{d.name}</span>
              {!d.paired && <Badge variant="outline">não pareado</Badge>}
            </div>
            <label className="flex cursor-pointer items-center gap-2 text-xs text-muted-foreground">
              <span>Edge YOLO</span>
              <input
                type="checkbox"
                checked={d.edge_yolo_enabled}
                disabled={!d.paired || busyId === d.id}
                onChange={async (e) => {
                  setBusyId(d.id);
                  try { await updateDevice(d.id, { edge_yolo_enabled: e.target.checked }); }
                  finally { setBusyId(null); refresh(); }
                }}
              />
            </label>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

export function CamerasPanel({ cameras, rules, onChange }: { cameras: Camera[]; rules: Rule[]; onChange?: () => void }) {
  const [showWizard, setShowWizard] = useState(false);
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <DevicesStrip />
      <DeviceHealthPanel />
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">{cameras.length} câmera{cameras.length === 1 ? "" : "s"}</p>
        <Button onClick={() => setShowWizard(true)}><Plus className="h-4 w-4" /> Adicionar câmera</Button>
      </div>

      {cameras.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed bg-card/50 p-12 text-center">
          <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-secondary">
            <CameraIcon className="h-5 w-5 text-muted-foreground" />
          </div>
          <p className="text-sm font-medium">Nenhuma câmera cadastrada</p>
          <p className="mt-1 text-xs text-muted-foreground">Adicione sua primeira câmera ONVIF/RTSP.</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {cameras.map((c) => <CameraCard key={c.id} cam={c} rules={rules.filter((r) => r.camera_id === c.id)} />)}
        </div>
      )}

      {showWizard && (
        <CameraWizard
          onCancel={() => setShowWizard(false)}
          onDone={() => { setShowWizard(false); onChange?.(); }}
        />
      )}
    </div>
  );
}

function CameraCard({ cam, rules }: { cam: Camera; rules: Rule[] }) {
  const [thumbOk, setThumbOk] = useState(true);
  const [showLive, setShowLive] = useState(false);
  return (
    <Card className="overflow-hidden">
      <div className="relative aspect-video w-full bg-secondary">
        {thumbOk ? (
          <img src={thumbUrl(cam.id)} alt={cam.name} onError={() => setThumbOk(false)} className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full items-center justify-center text-xs text-muted-foreground">sem capturas ainda</div>
        )}
        <div className={cn("absolute right-2 top-2 flex items-center gap-1.5 rounded-full bg-background/80 px-2 py-0.5 text-xs backdrop-blur")}>
          <span className={cn("h-1.5 w-1.5 rounded-full", cam.online ? "bg-emerald-500" : "bg-muted-foreground")} />
          {cam.online ? "online" : "offline"}
        </div>
      </div>
      <CardContent className="space-y-3 p-4">
        <div>
          <p className="truncate text-sm font-semibold">{cam.name}</p>
          <p className="text-xs text-muted-foreground">id: {cam.id.slice(0, 8)}…</p>
        </div>
        <div className="flex flex-wrap gap-1">
          {rules.length === 0 ? (
            <span className="text-xs text-muted-foreground">Sem regras</span>
          ) : (
            rules.map((r) => (
              <Badge key={r.id} variant={r.enabled ? "secondary" : "outline"}>
                {r.name || "Sem nome"}
              </Badge>
            ))
          )}
        </div>
        <Button size="sm" className="w-full" onClick={() => setShowLive(true)}>
          <Play className="h-4 w-4" /> Ao vivo
        </Button>
      </CardContent>
      {showLive && <CameraLive cam={cam} onClose={() => setShowLive(false)} />}
    </Card>
  );
}
