import { useEffect, useState } from "react";
import {
  FaceEnrollment,
  deleteFaceEnrollment,
  enrollFace,
  listFaceEnrollments,
} from "../api";
import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Badge } from "./ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Plus, Trash2, UserPlus } from "lucide-react";


function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result));
    r.onerror = () => reject(r.error);
    r.readAsDataURL(file);
  });
}


export function FacesPanel() {
  const [list, setList] = useState<FaceEnrollment[]>([]);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [previews, setPreviews] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = () =>
    listFaceEnrollments().then(setList).catch(() => {});

  useEffect(() => {
    refresh();
  }, []);

  async function onFiles(picked: FileList | null) {
    if (!picked) return;
    const arr = Array.from(picked).slice(0, 5);
    const urls = await Promise.all(arr.map(readAsDataUrl));
    setPreviews(urls);
  }

  async function submit() {
    if (!name.trim() || previews.length === 0) {
      setError("Nome e ao menos 1 foto são obrigatórios.");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await enrollFace(name.trim(), previews);
      setOpen(false);
      setName("");
      setPreviews([]);
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro");
    } finally {
      setSubmitting(false);
    }
  }

  async function remove(id: string) {
    if (!confirm("Remover este cadastro?")) return;
    await deleteFaceEnrollment(id);
    refresh();
  }

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Faces conhecidas</h2>
          <p className="text-xs text-muted-foreground">
            Cadastre funcionários ou familiares — quando reconhecidos em uma cena, o alerta é silenciado.
          </p>
        </div>
        <Button onClick={() => setOpen(true)}>
          <Plus className="h-4 w-4" /> Cadastrar pessoa
        </Button>
      </div>

      {list.length === 0 ? (
        <div className="rounded-xl border border-dashed bg-card/50 p-12 text-center">
          <UserPlus className="mx-auto h-6 w-6 text-muted-foreground" />
          <p className="mt-2 text-sm font-medium">Ninguém cadastrado</p>
          <p className="text-xs text-muted-foreground">
            Sem cadastros, todos os alertas chegam. Cadastre seu time pra cortar falso positivo.
          </p>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {list.map((f) => (
            <Card key={f.id} className="overflow-hidden">
              <CardContent className="space-y-2 p-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium">{f.name}</p>
                  <Button variant="ghost" size="sm" onClick={() => remove(f.id)}>
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Badge variant="secondary">{f.embedding_count} embedding{f.embedding_count === 1 ? "" : "s"}</Badge>
                  <Badge variant="outline">{f.photo_count} fotos</Badge>
                </div>
                <p className="text-[10px] text-muted-foreground">
                  cadastrado em {new Date(f.created_at).toLocaleDateString("pt-BR")}
                </p>
                {f.embedding_count === 0 && (
                  <p className="text-[11px] text-amber-600">
                    Aguardando modelo facial no agent — fotos guardadas.
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cadastrar pessoa</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label>Nome</Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Ex: João - Caixa"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Fotos (1-5, rosto visível)</Label>
              <Input
                type="file"
                accept="image/*"
                multiple
                onChange={(e) => onFiles(e.target.files)}
              />
              {previews.length > 0 && (
                <div className="flex gap-2 overflow-x-auto pt-2">
                  {previews.map((p, i) => (
                    <img
                      key={i}
                      src={p}
                      alt={`face ${i}`}
                      className="h-20 w-20 rounded object-cover"
                    />
                  ))}
                </div>
              )}
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setOpen(false)} disabled={submitting}>
                Cancelar
              </Button>
              <Button onClick={submit} disabled={submitting}>
                {submitting ? "Salvando…" : "Salvar"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
