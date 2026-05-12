import { useState } from "react";
import { Camera, Rule, Schedule, createRule, deleteRule, thumbUrl, updateRule } from "../api";
import { PolygonEditor, Zones } from "./PolygonEditor";
import { ScheduleEditor } from "./ScheduleEditor";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Textarea } from "./ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Switch } from "./ui/switch";
import { Badge } from "./ui/badge";
import { Separator } from "./ui/separator";
import { Pencil, Plus, Trash2, ListChecks } from "lucide-react";
import { cn } from "@/lib/utils";

type FormDraft = {
  cameraId: string;
  name: string;
  customPrompt: string;
  zones: Zones;
  sensitivity: number;
  yoloRequired: boolean;
  schedule: Schedule | null;
};

const empty = (cameras: Camera[]): FormDraft => ({
  cameraId: cameras[0]?.id ?? "",
  name: "",
  customPrompt: "",
  zones: {},
  sensitivity: 50,
  yoloRequired: true,
  schedule: null,
});

export function RulesPanel({ cameras, rules, onChange }: { cameras: Camera[]; rules: Rule[]; onChange: () => void }) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<FormDraft>(empty(cameras));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function openNew() { setDraft(empty(cameras)); setEditingId("new"); setError(null); }
  function openEdit(rule: Rule) {
    setDraft({
      cameraId: rule.camera_id,
      name: rule.name ?? "",
      customPrompt: rule.custom_prompt ?? "",
      zones: rule.zones ?? {},
      sensitivity: rule.sensitivity ?? 50,
      yoloRequired: rule.yolo_required ?? true,
      schedule: rule.schedule ?? null,
    });
    setEditingId(rule.id); setError(null);
  }
  function close() { setEditingId(null); setDraft(empty(cameras)); setError(null); }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!draft.cameraId) { setError("Selecione uma câmera"); return; }
    if (!draft.customPrompt.trim() || draft.customPrompt.trim().length < 10) {
      setError("Descreva a regra (mín. 10 caracteres). É o que o LLM analisa.");
      return;
    }
    const validZones: Zones = {};
    for (const [k, pts] of Object.entries(draft.zones)) if (pts.length >= 3) validZones[k] = pts;
    setSaving(true); setError(null);
    try {
      if (editingId === "new") {
        await createRule({ camera_id: draft.cameraId, name: draft.name || undefined, custom_prompt: draft.customPrompt.trim(), zones: validZones, sensitivity: draft.sensitivity, yolo_required: draft.yoloRequired, schedule: draft.schedule });
      } else if (editingId) {
        await updateRule(editingId, { name: draft.name || null, custom_prompt: draft.customPrompt.trim(), zones: validZones, sensitivity: draft.sensitivity, yolo_required: draft.yoloRequired, schedule: draft.schedule });
      }
      close(); onChange();
    } catch (e) { setError(String(e)); } finally { setSaving(false); }
  }

  async function toggle(rule: Rule) { await updateRule(rule.id, { enabled: !rule.enabled }); onChange(); }
  async function remove(rule: Rule) {
    if (!confirm(`Remover regra "${rule.name || "Sem nome"}"?`)) return;
    await deleteRule(rule.id); onChange();
  }

  const formOpen = editingId !== null;

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">{rules.length} regra{rules.length === 1 ? "" : "s"}</p>
        {!formOpen && <Button onClick={openNew}><Plus className="h-4 w-4" /> Nova regra</Button>}
      </div>

      {formOpen && (
        <Card>
          <CardHeader><CardTitle>{editingId === "new" ? "Nova regra" : "Editar regra"}</CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={submit} className="space-y-4">
              <div className="space-y-1.5">
                <Label>Câmera</Label>
                <Select value={draft.cameraId} onValueChange={(v) => setDraft({ ...draft, cameraId: v, zones: {} })} disabled={editingId !== "new"}>
                  <SelectTrigger><SelectValue placeholder="— selecione —" /></SelectTrigger>
                  <SelectContent>
                    {cameras.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label>Nome</Label>
                <Input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} placeholder="Ex: Toque no balcão" />
              </div>

              <div className="space-y-1.5">
                <Label>Descrição da regra (analisada pelo LLM)</Label>
                <Textarea
                  rows={5}
                  value={draft.customPrompt}
                  onChange={(e) => setDraft({ ...draft, customPrompt: e.target.value })}
                  placeholder="Descreva em pt-BR o que deve disparar alerta. Ex: Toda vez que alguém tocar ou pegar o copo em cima da mesa."
                />
                <p className="text-xs text-muted-foreground">Quanto mais específica, melhor. O modelo analisa frames do vídeo contra esta descrição.</p>
              </div>

              {draft.cameraId && (
                <div className="space-y-1.5">
                  <Label>Zonas (opcional)</Label>
                  <PolygonEditor imgUrl={thumbUrl(draft.cameraId)} value={draft.zones} onChange={(z) => setDraft({ ...draft, zones: z })} />
                </div>
              )}

              <div className="space-y-1.5">
                <Label>Sensibilidade · {draft.sensitivity}</Label>
                <input
                  type="range" min={0} max={100} step={5}
                  value={draft.sensitivity}
                  onChange={(e) => setDraft({ ...draft, sensitivity: Number(e.target.value) })}
                  className="w-full accent-primary"
                />
                <p className="text-xs text-muted-foreground">Mais alto = mais frames passam pelo VLM (mais custo).</p>
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between gap-3">
                  <Label htmlFor="yolo-required">Exigir detecção de pessoa (YOLO)</Label>
                  <Switch
                    id="yolo-required"
                    checked={draft.yoloRequired}
                    onCheckedChange={(v) => setDraft({ ...draft, yoloRequired: v })}
                  />
                </div>
                <p className="text-xs text-muted-foreground">
                  Desative para alertar em todos os clipes — maior custo, menos perdas. Útil quando a câmera está em ângulo que dificulta o detector de pessoa (ex: teto, distante).
                </p>
              </div>

              <div className="space-y-1.5">
                <Label>Horário ativo</Label>
                <ScheduleEditor value={draft.schedule} onChange={(s) => setDraft({ ...draft, schedule: s })} />
              </div>

              {error && <p className="text-sm text-destructive">{error}</p>}
              <Separator />
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={close} disabled={saving}>Cancelar</Button>
                <Button type="submit" disabled={saving}>{saving ? "Salvando…" : editingId === "new" ? "Criar regra" : "Salvar"}</Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {rules.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed bg-card/50 p-12 text-center">
          <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-secondary">
            <ListChecks className="h-5 w-5 text-muted-foreground" />
          </div>
          <p className="text-sm font-medium">Nenhuma regra ainda</p>
          <p className="mt-1 text-xs text-muted-foreground">Crie a primeira regra para começar a monitorar.</p>
        </div>
      ) : (
        <div className="grid gap-3">
          {rules.map((r) => {
            const cam = cameras.find((c) => c.id === r.camera_id);
            const zoneNames = Object.keys(r.zones || {});
            return (
              <Card key={r.id} className={cn(!r.enabled && "opacity-60")}>
                <CardContent className="flex items-start gap-3 p-4">
                  <div className="min-w-0 flex-1 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-semibold">{r.name || "Sem nome"}</p>
                      <Badge variant="outline">{cam?.name || r.camera_id.slice(0, 8)}</Badge>
                      {zoneNames.length > 0 && <Badge variant="secondary">zonas: {zoneNames.join(", ")}</Badge>}
                    </div>
                    {r.custom_prompt && <p className="text-sm text-muted-foreground">{r.custom_prompt}</p>}
                  </div>
                  <div className="flex items-center gap-1">
                    <Switch checked={r.enabled} onCheckedChange={() => toggle(r)} aria-label="Toggle rule" />
                    <Button variant="ghost" size="icon" onClick={() => openEdit(r)}><Pencil className="h-4 w-4" /></Button>
                    <Button variant="ghost" size="icon" onClick={() => remove(r)}><Trash2 className="h-4 w-4 text-destructive" /></Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
