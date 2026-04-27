import { Alert, AlertFilters, Camera, Rule } from "../api";

const PRESETS: Rule["preset_type"][] = ["cash_register", "kitchen_consumption", "retail_shelf"];
const STATUSES: (Alert["status"] | "all")[] = ["all", "pending", "seen", "false_positive"];
const SINCE_OPTIONS: { label: string; minutes: number | null }[] = [
  { label: "Tudo", minutes: null },
  { label: "1h", minutes: 60 },
  { label: "Hoje", minutes: 60 * 24 },
  { label: "7d", minutes: 60 * 24 * 7 },
];

export type ClientFilters = {
  status: Alert["status"] | "all";
  search: string;
};

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
      const dt = new Date(Date.now() - minutes * 60_000).toISOString();
      onServerChange({ ...serverFilters, since: dt });
    }
  }

  const activeSinceMinutes =
    serverFilters.since
      ? Math.round((Date.now() - new Date(serverFilters.since).getTime()) / 60_000)
      : null;

  return (
    <div className="alerts-filters">
      <input
        type="search"
        placeholder="Buscar mensagem ou regra…"
        value={clientFilters.search}
        onChange={(e) => onClientChange({ ...clientFilters, search: e.target.value })}
      />

      <select
        value={serverFilters.camera_id ?? ""}
        onChange={(e) =>
          onServerChange({ ...serverFilters, camera_id: e.target.value || undefined })
        }
      >
        <option value="">Todas câmeras</option>
        {cameras.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>

      <select
        value={serverFilters.preset_type ?? ""}
        onChange={(e) =>
          onServerChange({
            ...serverFilters,
            preset_type: (e.target.value as Rule["preset_type"]) || undefined,
          })
        }
      >
        <option value="">Todos presets</option>
        {PRESETS.map((p) => (
          <option key={p} value={p}>
            {p}
          </option>
        ))}
      </select>

      <select
        value={clientFilters.status}
        onChange={(e) =>
          onClientChange({ ...clientFilters, status: e.target.value as ClientFilters["status"] })
        }
      >
        {STATUSES.map((s) => (
          <option key={s} value={s}>
            {s === "all" ? "Todos status" : s}
          </option>
        ))}
      </select>

      <div className="since-group" role="group" aria-label="Período">
        {SINCE_OPTIONS.map((o) => {
          const active =
            (o.minutes == null && activeSinceMinutes == null) ||
            (o.minutes != null && activeSinceMinutes != null && Math.abs(activeSinceMinutes - o.minutes) < 2);
          return (
            <button
              key={o.label}
              type="button"
              className={active ? "active" : ""}
              onClick={() => setSince(o.minutes)}
            >
              {o.label}
            </button>
          );
        })}
      </div>

      <button
        type="button"
        className="btn-muted"
        onClick={() => {
          onServerChange({});
          onClientChange({ status: "all", search: "" });
        }}
      >
        Limpar
      </button>
    </div>
  );
}

export function filterAlertsClient(alerts: Alert[], cf: ClientFilters): Alert[] {
  const s = cf.search.trim().toLowerCase();
  return alerts.filter((a) => {
    if (cf.status !== "all" && a.status !== cf.status) return false;
    if (!s) return true;
    return (
      a.message.toLowerCase().includes(s) ||
      (a.rule_name ?? "").toLowerCase().includes(s) ||
      a.preset_type.toLowerCase().includes(s)
    );
  });
}
