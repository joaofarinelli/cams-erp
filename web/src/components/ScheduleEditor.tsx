import { Schedule, ScheduleWindow } from "../api";

const DAYS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];

const PRESETS: { label: string; build: () => Schedule }[] = [
  {
    label: "24/7",
    build: () => ({
      timezone: "America/Sao_Paulo",
      windows: [{ days: [0, 1, 2, 3, 4, 5, 6], start: "00:00", end: "23:59" }],
    }),
  },
  {
    label: "Comércio (8-22)",
    build: () => ({
      timezone: "America/Sao_Paulo",
      windows: [{ days: [0, 1, 2, 3, 4, 5], start: "08:00", end: "22:00" }],
    }),
  },
  {
    label: "Noite (22-06)",
    build: () => ({
      timezone: "America/Sao_Paulo",
      windows: [{ days: [0, 1, 2, 3, 4, 5, 6], start: "22:00", end: "06:00" }],
    }),
  },
];

export function ScheduleEditor({
  value,
  onChange,
}: {
  value: Schedule | null;
  onChange: (v: Schedule | null) => void;
}) {
  function setWindow(idx: number, patch: Partial<ScheduleWindow>) {
    if (!value) return;
    const windows = value.windows.map((w, i) => (i === idx ? { ...w, ...patch } : w));
    onChange({ ...value, windows });
  }
  function addWindow() {
    const wins = value?.windows || [];
    onChange({
      timezone: value?.timezone || "America/Sao_Paulo",
      windows: [...wins, { days: [0, 1, 2, 3, 4, 5, 6], start: "08:00", end: "22:00" }],
    });
  }
  function removeWindow(idx: number) {
    if (!value) return;
    const windows = value.windows.filter((_, i) => i !== idx);
    onChange(windows.length === 0 ? null : { ...value, windows });
  }
  function toggleDay(idx: number, day: number) {
    if (!value) return;
    const w = value.windows[idx];
    const days = w.days.includes(day) ? w.days.filter((d) => d !== day) : [...w.days, day].sort();
    setWindow(idx, { days });
  }

  return (
    <div className="schedule-editor">
      <div className="schedule-presets">
        {PRESETS.map((p) => (
          <button key={p.label} type="button" onClick={() => onChange(p.build())}>
            {p.label}
          </button>
        ))}
        <button type="button" onClick={() => onChange(null)} className="btn-muted">
          Sempre ativa
        </button>
      </div>
      {value && (
        <>
          {value.windows.map((w, idx) => (
            <div className="schedule-window" key={idx}>
              <div className="day-toggles">
                {DAYS.map((label, day) => (
                  <button
                    key={day}
                    type="button"
                    className={w.days.includes(day) ? "active" : ""}
                    onClick={() => toggleDay(idx, day)}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <div className="time-row">
                <input
                  type="time"
                  value={w.start}
                  onChange={(e) => setWindow(idx, { start: e.target.value })}
                />
                <span>até</span>
                <input
                  type="time"
                  value={w.end}
                  onChange={(e) => setWindow(idx, { end: e.target.value })}
                />
                <button type="button" onClick={() => removeWindow(idx)} className="muted">
                  remover
                </button>
              </div>
            </div>
          ))}
          <button type="button" onClick={addWindow} className="btn-muted">
            + Adicionar janela
          </button>
        </>
      )}
      {!value && <p className="muted">Regra ativa 24/7. Selecione um preset acima para limitar o horário.</p>}
    </div>
  );
}
