import { useEffect, useState } from "react";
import { Alert, clipUrl, postAlertFeedback, seekBack } from "../api";
import { Card, CardContent } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Check, Rewind, ThumbsDown } from "lucide-react";
import { cn } from "@/lib/utils";

export function AlertCard({ alert, onUpdate }: { alert: Alert; onUpdate: () => void }) {
  const [busy, setBusy] = useState(false);
  const [src, setSrc] = useState<string | null>(null);
  const [seeking, setSeeking] = useState(false);
  const [seekSrc, setSeekSrc] = useState<string | null>(null);
  const [seekError, setSeekError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    clipUrl(alert.s3_key).then((u) => { if (!cancelled) setSrc(u); }).catch(() => {});
    return () => { cancelled = true; };
  }, [alert.s3_key]);

  async function loadSeekBack() {
    setSeeking(true);
    setSeekError(null);
    try {
      const resp = await seekBack(alert.id, 30, 5);
      setSeekSrc(resp.view_url);
    } catch (e) {
      setSeekError(e instanceof Error ? e.message : "Erro ao buscar contexto");
    } finally {
      setSeeking(false);
    }
  }

  async function feedback(isFalsePositive: boolean) {
    setBusy(true);
    try {
      await postAlertFeedback(alert.id, isFalsePositive);
      onUpdate();
    } finally {
      setBusy(false);
    }
  }

  const created = new Date(alert.created_at);
  const scoreVariant = alert.score >= 0.8 ? "destructive" : alert.score >= 0.5 ? "warning" : "secondary";
  const statusVariant: "default" | "success" | "destructive" | "secondary" =
    alert.status === "pending" ? "default" : alert.status === "seen" ? "success" : "destructive";

  return (
    <Card className="overflow-hidden">
      <div className="grid grid-cols-1 md:grid-cols-[280px_1fr]">
        <div className="aspect-video w-full bg-black md:aspect-auto md:min-h-full">
          {src && <video controls preload="metadata" src={src} className="h-full w-full object-cover" />}
        </div>
        <CardContent className="flex flex-col gap-3 p-4">
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold">{alert.rule_name || "Sem nome"}</p>
              <p className="text-xs text-muted-foreground">{created.toLocaleString("pt-BR")}</p>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={scoreVariant as never}>score {alert.score.toFixed(2)}</Badge>
              <Badge variant={statusVariant as never}>{alert.status}</Badge>
            </div>
          </div>
          <p className={cn("text-sm leading-relaxed text-muted-foreground")}>{alert.message}</p>
          <div className="flex items-center gap-2">
            <Button size="sm" variant="ghost" disabled={seeking} onClick={loadSeekBack}>
              <Rewind className="h-4 w-4" /> {seeking ? "Carregando…" : "Ver 30s antes"}
            </Button>
            {seekError && <span className="text-xs text-destructive">{seekError}</span>}
          </div>
          {seekSrc && (
            <video
              controls
              autoPlay
              src={seekSrc}
              className="w-full rounded-md bg-black"
            />
          )}
          {alert.status === "pending" && (
            <div className="mt-auto flex gap-2 pt-2">
              <Button size="sm" variant="default" disabled={busy} onClick={() => feedback(false)}>
                <Check className="h-4 w-4" /> Confirmar
              </Button>
              <Button size="sm" variant="outline" disabled={busy} onClick={() => feedback(true)}>
                <ThumbsDown className="h-4 w-4" /> Falso positivo
              </Button>
            </div>
          )}
        </CardContent>
      </div>
    </Card>
  );
}
