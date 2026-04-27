import { useState } from "react";
import { Camera, Rule, Schedule, createRule, deleteRule, thumbUrl, updateRule } from "../api";
import { PolygonEditor, Zones } from "./PolygonEditor";
import { ScheduleEditor } from "./ScheduleEditor";

const PRESETS: Rule["preset_type"][] = ["cash_register", "kitchen_consumption", "retail_shelf"];

type FormDraft = {
  cameraId: string;
  name: string;
  preset: Rule["preset_type"];
  customPrompt: string;
  zones: Zones;
  sensitivity: number;
  schedule: Schedule | null;
};

const empty = (cameras: Camera[]): FormDraft => ({
  cameraId: cameras[0]?.id ?? "",
  name: "",
  preset: "cash_register",
  customPrompt: "",
  zones: {},
  sensitivity: 50,
  schedule: null,
});

export function RulesPanel({
  cameras,
  rules,
  onChange,
}: {
  cameras: Camera[];
  rules: Rule[];
  onChange: () => void;
}) {
  const [editingId, setEditingId] = useState<string | null>(null); // null = no form, "new" = new, else rule id
  const [draft, setDraft] = useState<FormDraft>(empty(cameras));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function openNew() {
    setDraft(empty(cameras));
    setEditingId("new");
    setError(null);
  }

  function openEdit(rule: Rule) {
    setDraft({
      cameraId: rule.camera_id,
      name: rule.name ?? "",
      preset: rule.preset_type,
      customPrompt: rule.custom_prompt ?? "",
      zones: rule.zones ?? {},
      sensitivity: rule.sensitivity ?? 50,
      schedule: rule.schedule ?? null,
    });
    setEditingId(rule.id);
    setError(null);
  }

  function close() {
    setEditingId(null);
    setDraft(empty(cameras));
    setError(null);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!draft.cameraId) {
      setError("Selecione uma câmera");
      return;
    }
    const validZones: Zones = {};
    for (const [k, pts] of Object.entries(draft.zones)) {
      if (pts.length >= 3) validZones[k] = pts;
    }
    setSaving(true);
    setError(null);
    try {
      if (editingId === "new") {
        await createRule({
          camera_id: draft.cameraId,
          preset_type: draft.preset,
          name: draft.name || undefined,
          custom_prompt: draft.customPrompt || undefined,
          zones: validZones,
          sensitivity: draft.sensitivity,
          schedule: draft.schedule,
        });
      } else if (editingId) {
        await updateRule(editingId, {
          name: draft.name || null,
          custom_prompt: draft.customPrompt || null,
          zones: validZones,
          sensitivity: draft.sensitivity,
          schedule: draft.schedule,
        });
      }
      close();
      onChange();
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  async function toggle(rule: Rule) {
    await updateRule(rule.id, { enabled: !rule.enabled });
    onChange();
  }

  async function remove(rule: Rule) {
    if (!confirm(`Remover regra "${rule.name || rule.preset_type}"?`)) return;
    await deleteRule(rule.id);
    onChange();
  }

  const formOpen = editingId !== null;

  return (
    <section className="rules">
      {!formOpen && (
        <button onClick={openNew} className="btn-primary">
          + Nova regra
        </button>
      )}

      {formOpen && (
        <form onSubmit={submit} className="rule-form">
          <h2>{editingId === "new" ? "Nova regra" : "Editar regra"}</h2>
          <label>
            Câmera
            <select
              value={draft.cameraId}
              onChange={(e) => setDraft({ ...draft, cameraId: e.target.value, zones: {} })}
              disabled={editingId !== "new"}
            >
              <option value="">— selecione —</option>
              {cameras.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Nome
            <input
              value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              placeholder="Ex: Toque no balcão"
            />
          </label>
          <label>
            Categoria
            <select
              value={draft.preset}
              onChange={(e) =>
                setDraft({ ...draft, preset: e.target.value as Rule["preset_type"] })
              }
              disabled={editingId !== "new"}
            >
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
              value={draft.customPrompt}
              onChange={(e) => setDraft({ ...draft, customPrompt: e.target.value })}
              placeholder="Ex: Toda vez que alguem bater no balcao com a mao."
            />
          </label>
          {draft.cameraId && (
            <div>
              <label className="zones-label">Zonas (opcional)</label>
              <PolygonEditor
                imgUrl={thumbUrl(draft.cameraId)}
                value={draft.zones}
                onChange={(z) => setDraft({ ...draft, zones: z })}
              />
            </div>
          )}
          <label>
            Sensibilidade ({draft.sensitivity})
            <input
              type="range"
              min={0}
              max={100}
              step={5}
              value={draft.sensitivity}
              onChange={(e) => setDraft({ ...draft, sensitivity: Number(e.target.value) })}
            />
            <small className="muted">
              Quanto maior, mais frames passam pelo VLM (mais sensível, mais custo). Padrão 50.
            </small>
          </label>
          <div>
            <label className="zones-label">Horário ativo</label>
            <ScheduleEditor
              value={draft.schedule}
              onChange={(s) => setDraft({ ...draft, schedule: s })}
            />
          </div>
          {error && <p className="error">{error}</p>}
          <div className="form-actions">
            <button type="submit" disabled={saving}>
              {saving ? "Salvando…" : editingId === "new" ? "Criar regra" : "Salvar"}
            </button>
            <button type="button" onClick={close} className="btn-muted" disabled={saving}>
              Cancelar
            </button>
          </div>
        </form>
      )}

      <h2>Regras existentes ({rules.length})</h2>
      {rules.length === 0 && <p className="empty">Nenhuma regra ainda. Crie a primeira acima.</p>}
      <ul className="rule-cards">
        {rules.map((r) => {
          const cam = cameras.find((c) => c.id === r.camera_id);
          const zoneNames = Object.keys(r.zones || {});
          return (
            <li key={r.id} className={`rule-card ${r.enabled ? "" : "disabled"}`}>
              <div className="rule-card-body">
                <header>
                  <strong>{r.name || r.preset_type}</strong>
                  <span className="muted">{cam?.name || r.camera_id.slice(0, 8)}</span>
                </header>
                {r.custom_prompt && <p className="custom-prompt">{r.custom_prompt}</p>}
                <small>
                  {r.preset_type}
                  {zoneNames.length > 0 && ` · zonas: ${zoneNames.join(", ")}`}
                  {!r.enabled && " · desativada"}
                </small>
              </div>
              <div className="rule-card-actions">
                <button onClick={() => toggle(r)} title={r.enabled ? "Desativar" : "Ativar"}>
                  {r.enabled ? "✓" : "○"}
                </button>
                <button onClick={() => openEdit(r)}>Editar</button>
                <button onClick={() => remove(r)} className="danger">
                  ✕
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
