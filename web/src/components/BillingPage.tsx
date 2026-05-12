import { useEffect, useState } from "react";
import { UsageMe, fetchUsageMe, getBillingPortal } from "../api";
import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";


function pct(n: number, max: number | null): number {
  if (!max || max <= 0) return 0;
  return Math.min(100, Math.round((n / max) * 100));
}


export function BillingPage() {
  const [usage, setUsage] = useState<UsageMe | null>(null);
  const [portalBusy, setPortalBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchUsageMe()
      .then(setUsage)
      .catch((e) => setError(e instanceof Error ? e.message : "Erro"));
  }, []);

  const openPortal = async () => {
    setPortalBusy(true);
    setError(null);
    try {
      const url = await getBillingPortal();
      window.location.href = url;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro");
      setPortalBusy(false);
    }
  };

  if (!usage)
    return (
      <div className="mx-auto max-w-3xl py-12 text-center text-sm text-muted-foreground">
        {error || "Carregando uso…"}
      </div>
    );

  const eventsPct = pct(usage.events_count, usage.events_limit);

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <header>
        <h2 className="text-xl font-semibold">Plano e cobrança</h2>
        <p className="text-sm text-muted-foreground">
          Plano atual: <strong>{usage.tier}</strong>
          {usage.trial_ends_at &&
            ` · trial até ${new Date(usage.trial_ends_at).toLocaleDateString("pt-BR")}`}
        </p>
      </header>

      <Card>
        <CardContent className="space-y-4 p-6">
          <div>
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Análises este mês
              </p>
              <p className="text-xs text-muted-foreground">
                {usage.events_count}
                {usage.events_limit !== null && ` / ${usage.events_limit}`}
              </p>
            </div>
            <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-indigo-500"
                style={{ width: `${eventsPct}%` }}
              />
            </div>
            <p className="mt-1 text-[11px] text-muted-foreground">
              {eventsPct}% usado · cascade {usage.cascade_allowed ? "permitido" : "bloqueado"} ·
              câmeras: {usage.cameras_limit ?? "ilimitado"}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <p className="font-medium text-muted-foreground">VLM stage 1</p>
              <p>{usage.vlm_calls} calls</p>
            </div>
            <div>
              <p className="font-medium text-muted-foreground">Cascade</p>
              <p>{usage.vlm_cascade_calls} calls</p>
            </div>
            <div>
              <p className="font-medium text-muted-foreground">Alertas disparados</p>
              <p>{usage.alerts_count}</p>
            </div>
            <div>
              <p className="font-medium text-muted-foreground">Storage</p>
              <p>{usage.storage_gb_hours.toFixed(2)} GB-h</p>
            </div>
          </div>

          <div className="flex gap-2 pt-2">
            <Button onClick={openPortal} disabled={portalBusy}>
              {portalBusy ? "Abrindo…" : "Gerenciar pagamento"}
            </Button>
          </div>
          {error && <p className="text-xs text-destructive">{error}</p>}
        </CardContent>
      </Card>
    </div>
  );
}
