import { useState } from "react";
import { Camera, Rule, createRule } from "../api";

const PRESETS: Rule["preset_type"][] = ["cash_register", "kitchen_consumption", "retail_shelf"];

export function RulesPanel({
  cameras,
  rules,
  onChange,
}: {
  cameras: Camera[];
  rules: Rule[];
  onChange: () => void;
}) {
  const [cameraId, setCameraId] = useState<string>("");
  const [name, setName] = useState("");
  const [preset, setPreset] = useState<Rule["preset_type"]>("cash_register");
  const [customPrompt, setCustomPrompt] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!cameraId) {
      setError("Selecione uma câmera");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await createRule({
        camera_id: cameraId,
        preset_type: preset,
        name: name || undefined,
        custom_prompt: customPrompt || undefined,
      });
      setName("");
      setCustomPrompt("");
      onChange();
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="rules">
      <form onSubmit={submit} className="rule-form">
        <h2>Nova regra</h2>
        <label>
          Câmera
          <select value={cameraId} onChange={(e) => setCameraId(e.target.value)}>
            <option value="">— selecione —</option>
            {cameras.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Nome (opcional)
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Ex: Toque no balcão"
          />
        </label>
        <label>
          Categoria
          <select value={preset} onChange={(e) => setPreset(e.target.value as Rule["preset_type"])}>
            {PRESETS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
        <label>
          Regra customizada (opcional, em pt-BR)
          <textarea
            rows={4}
            value={customPrompt}
            onChange={(e) => setCustomPrompt(e.target.value)}
            placeholder="Ex: Toda vez que alguem bater no balcao com a mao, alertar imediatamente."
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={saving}>
          {saving ? "Salvando…" : "Criar regra"}
        </button>
      </form>

      <h2>Regras existentes ({rules.length})</h2>
      <ul className="rule-list">
        {rules.map((r) => {
          const cam = cameras.find((c) => c.id === r.camera_id);
          return (
            <li key={r.id}>
              <strong>{r.name || r.preset_type}</strong>
              {" — "}
              <span>{cam?.name || r.camera_id.slice(0, 8)}</span>
              {r.custom_prompt && <em title={r.custom_prompt}> [custom]</em>}
              {!r.enabled && <span className="muted"> (desativada)</span>}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
