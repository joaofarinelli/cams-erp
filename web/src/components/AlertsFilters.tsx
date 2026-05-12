import { Alert, AlertFilters, Camera } from "../api";
import { Input } from "./ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Button } from "./ui/button";
import { cn } from "@/lib/utils";
import { Search, X } from "lucide-react";

const STATUSES: (Alert["status"] | "all")[] = ["all", "pending", "seen", "false_positive"];
const SINCE_OPTIONS: { label: string; minutes: number | null }[] = [
  { label: "Tudo", minutes: null },
  { label: "1h", minutes: 60 },
  { label: "Hoje", minutes: 60 * 24 },
  { label: "7d", minutes: 60 * 24 * 7 },
];

export type ClientFilters = { status: Alert["status"] | "all"; search: string };

export function AlertsFilters({
  serverFilters,
  clientFilters,
  cameras,
  onServerChange,
  onClientChange,
}: {
  serverFilters: AlertFilters;
  clientFilters: ClientFilters;
  cameras: Camera[];
  onServerChange: (next: AlertFilters) => void;
  onClientChange: (next: ClientFilters) => void;
}) {
  function setSince(minutes: number | null) {
    if (minutes == null) {
      const { since: _omit, ...rest } = serverFilters;
      onServerChange(rest);
    } else {
      onServerChange({ ...serverFilters, since: new Date(Date.now() - minutes * 60_000).toISOString() });
    }
  }
  const activeSinceMinutes = serverFilters.since
    ? Math.round((Date.now() - new Date(serverFilters.since).getTime()) / 60_000)
    : null;

  const hasFilters = !!(serverFilters.camera_id || serverFilters.since || clientFilters.status !== "all" || clientFilters.search);

  return (
    <div className="rounded-xl border bg-card p-3">
      <div className="grid grid-cols-1 gap-2 md:grid-cols-[1fr_220px_180px]">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Buscar mensagem ou regra…"
            value={clientFilters.search}
            onChange={(e) => onClientChange({ ...clientFilters, search: e.target.value })}
            className="pl-9"
          />
        </div>
        <Select value={serverFilters.camera_id ?? "all"} onValueChange={(v) => onServerChange({ ...serverFilters, camera_id: v === "all" ? undefined : v })}>
          <SelectTrigger><SelectValue placeholder="Câmeras" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todas câmeras</SelectItem>
            {cameras.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={clientFilters.status} onValueChange={(v) => onClientChange({ ...clientFilters, status: v as ClientFilters["status"] })}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            {STATUSES.map((s) => <SelectItem key={s} value={s}>{s === "all" ? "Todos status" : s}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <div className="inline-flex rounded-md border p-0.5">
          {SINCE_OPTIONS.map((o) => {
            const active =
              (o.minutes == null && activeSinceMinutes == null) ||
              (o.minutes != null && activeSinceMinutes != null && Math.abs(activeSinceMinutes - o.minutes) < 2);
            return (
              <button
                key={o.label}
                type="button"
                onClick={() => setSince(o.minutes)}
                className={cn(
                  "rounded px-2.5 py-1 text-xs font-medium transition-colors",
                  active ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground"
                )}
              >
                {o.label}
              </button>
            );
          })}
        </div>
        {hasFilters && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => { onServerChange({}); onClientChange({ status: "all", search: "" }); }}
            className="ml-auto"
          >
            <X className="h-4 w-4" /> Limpar
          </Button>
        )}
      </div>
    </div>
  );
}

export function filterAlertsClient(alerts: Alert[], cf: ClientFilters): Alert[] {
  const s = cf.search.trim().toLowerCase();
  return alerts.filter((a) => {
    if (cf.status !== "all" && a.status !== cf.status) return false;
    if (!s) return true;
    return a.message.toLowerCase().includes(s) || (a.rule_name ?? "").toLowerCase().includes(s);
  });
}
