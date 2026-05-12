import { useEffect, useRef, useState } from "react";
import { Camera, liveStreamUrl } from "../api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Badge } from "./ui/badge";
import { cn } from "@/lib/utils";

const CLOSE_REASONS: Record<number, string> = {
  4401: "Sessão expirada",
  4404: "Câmera não encontrada",
  4409: "Agente offline",
};

export function CameraLive({ cam, onClose }: { cam: Camera; onClose: () => void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [status, setStatus] = useState("conectando…");
  const [live, setLive] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const ws = new WebSocket(liveStreamUrl(cam.id));
    ws.binaryType = "arraybuffer";
    ws.onopen = () => { if (!cancelled) setStatus("aguardando frame…"); };
    ws.onerror = () => { if (!cancelled) setStatus("erro"); };
    ws.onclose = (e) => { if (!cancelled) setStatus(CLOSE_REASONS[e.code] || `desconectado`); setLive(false); };
    ws.onmessage = async (ev) => {
      if (cancelled || !(ev.data instanceof ArrayBuffer)) return;
      try {
        const blob = new Blob([ev.data], { type: "image/jpeg" });
        const bmp = await createImageBitmap(blob);
        const c = canvasRef.current;
        if (!c) return;
        if (c.width !== bmp.width || c.height !== bmp.height) {
          c.width = bmp.width;
          c.height = bmp.height;
        }
        const ctx = c.getContext("2d");
        ctx?.drawImage(bmp, 0, 0);
        bmp.close?.();
        setLive(true);
        setStatus("ao vivo");
      } catch { /* ignore */ }
    };
    return () => { cancelled = true; try { ws.close(); } catch { /* noop */ } };
  }, [cam.id]);

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <div className="flex items-center justify-between gap-2 pr-6">
            <DialogTitle>{cam.name}</DialogTitle>
            <Badge variant={live ? "success" : "secondary"} className="gap-1">
              <span className={cn("h-1.5 w-1.5 rounded-full", live ? "bg-emerald-500" : "bg-muted-foreground")} />
              {status}
            </Badge>
          </div>
        </DialogHeader>
        <div className="overflow-hidden rounded-md bg-black">
          <canvas ref={canvasRef} className="h-auto w-full" />
        </div>
      </DialogContent>
    </Dialog>
  );
}
