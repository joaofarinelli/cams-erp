import { useEffect, useState } from "react";
import { Subscriber, createSubscriber, deleteSubscriber, listSubscribers, runDigestNow } from "../api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Badge } from "./ui/badge";
import { MessageCircle, Send, Smartphone, Trash2 } from "lucide-react";

export function SubscribersPanel() {
  const [subs, setSubs] = useState<Subscriber[]>([]);
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try { setSubs(await listSubscribers()); } catch (e) { setError(String(e)); }
  }

  useEffect(() => { load(); }, []);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (phone.trim().length < 10) { setError("Telefone inválido. Use formato com DDI: 5511999991234"); return; }
    setBusy(true); setError(null);
    try { await createSubscriber("whatsapp", phone.trim()); setPhone(""); load(); }
    catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }

  async function remove(id: string) { await deleteSubscriber(id); load(); }

  async function digest() {
    try {
      const r = await runDigestNow();
      alert(r.sent ? "Resumo enviado." : "Sem inscritos.");
    } catch (e) { alert(String(e)); }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><MessageCircle className="h-4 w-4" /> WhatsApp</CardTitle>
          <CardDescription>Alertas via Evolution API local. Pareie um número WhatsApp na instância antes.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={add} className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="phone">Número (DDI + DDD + número, só dígitos)</Label>
              <Input id="phone" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="5511999991234" />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" disabled={busy}>{busy ? "Salvando…" : "Adicionar"}</Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Send className="h-4 w-4" /> Resumo diário</CardTitle>
          <CardDescription>Enviado automaticamente todo dia às 08:00 (America/Sao_Paulo).</CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant="outline" onClick={digest}><Send className="h-4 w-4" /> Enviar agora</Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Inscritos ({subs.length})</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {subs.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nenhum inscrito ainda.</p>
          ) : (
            subs.map((s) => (
              <div key={s.id} className="flex items-center justify-between rounded-md border bg-card p-2">
                <div className="flex items-center gap-2">
                  <Badge variant="secondary" className="gap-1">
                    {s.kind === "whatsapp" ? <MessageCircle className="h-3 w-3" /> : <Smartphone className="h-3 w-3" />}
                    {s.kind}
                  </Badge>
                  <code className="text-sm">{s.target}</code>
                </div>
                <Button variant="ghost" size="icon" onClick={() => remove(s.id)}>
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
