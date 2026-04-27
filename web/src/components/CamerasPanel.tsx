import { Camera, Rule } from "../api";

export function CamerasPanel({ cameras, rules }: { cameras: Camera[]; rules: Rule[] }) {
  return (
    <section className="cameras">
      {cameras.length === 0 && <p className="empty">Nenhuma câmera cadastrada.</p>}
      {cameras.map((c) => {
        const camRules = rules.filter((r) => r.camera_id === c.id);
        return (
          <div className="camera-card" key={c.id}>
            <header>
              <strong>{c.name}</strong>
              <span className={`status-dot ${c.online ? "online" : "offline"}`} />
            </header>
            <small>id: {c.id.slice(0, 8)}…</small>
            <ul>
              {camRules.length === 0 && <li className="empty">Sem regras</li>}
              {camRules.map((r) => (
                <li key={r.id}>
                  {r.enabled ? "✓" : "—"} {r.name || r.preset_type}
                  {r.custom_prompt && <em title={r.custom_prompt}> [custom]</em>}
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </section>
  );
}
