import { useState } from "react";
import { Camera, Rule, thumbUrl } from "../api";
import { CameraWizard } from "./CameraWizard";

export function CamerasPanel({
  cameras,
  rules,
  onChange,
}: {
  cameras: Camera[];
  rules: Rule[];
  onChange?: () => void;
}) {
  const [showWizard, setShowWizard] = useState(false);
  return (
    <section>
      {!showWizard && (
        <button className="btn-primary" onClick={() => setShowWizard(true)}>
          + Adicionar câmera
        </button>
      )}
      {showWizard && (
        <CameraWizard
          onCancel={() => setShowWizard(false)}
          onDone={() => {
            setShowWizard(false);
            onChange?.();
          }}
        />
      )}
      <div className="cameras">
        {cameras.length === 0 && <p className="empty">Nenhuma câmera cadastrada.</p>}
        {cameras.map((c) => {
          const camRules = rules.filter((r) => r.camera_id === c.id);
          return <CameraCard key={c.id} cam={c} rules={camRules} />;
        })}
      </div>
    </section>
  );
}

function CameraCard({ cam, rules }: { cam: Camera; rules: Rule[] }) {
  const [thumbOk, setThumbOk] = useState(true);
  return (
    <div className="camera-card">
      {thumbOk ? (
        <img src={thumbUrl(cam.id)} alt={cam.name} onError={() => setThumbOk(false)} className="cam-thumb" />
      ) : (
        <div className="cam-thumb cam-thumb-empty">sem capturas ainda</div>
      )}
      <header>
        <strong>{cam.name}</strong>
        <span className={`status-dot ${cam.online ? "online" : "offline"}`} />
      </header>
      <small>id: {cam.id.slice(0, 8)}…</small>
      <ul>
        {rules.length === 0 && <li className="empty">Sem regras</li>}
        {rules.map((r) => (
          <li key={r.id}>
            {r.enabled ? "✓" : "—"} {r.name || r.preset_type}
            {r.custom_prompt && <em title={r.custom_prompt}> [custom]</em>}
          </li>
        ))}
      </ul>
    </div>
  );
}
