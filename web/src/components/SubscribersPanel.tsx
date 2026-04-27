import { useEffect, useState } from "react";
import { Subscriber, createSubscriber, deleteSubscriber, listSubscribers } from "../api";

export function SubscribersPanel() {
  const [subs, setSubs] = useState<Subscriber[]>([]);
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      setSubs(await listSubscribers());
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (phone.trim().length < 10) {
      setError("Telefone inválido. Use formato com DDI: 5511999991234");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await createSubscriber("whatsapp", phone.trim());
      setPhone("");
      load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    await deleteSubscriber(id);
    load();
  }

  return (
    <section className="rules">
      <form className="rule-form" onSubmit={add}>
        <h2>Inscrever WhatsApp</h2>
        <p className="muted">
          Alertas serão enviados via Evolution API local (não usa Meta API). É preciso parear um
          número WhatsApp na instância antes (ver <code>docker-compose.dev.yml</code>).
        </p>
        <label>
          Número (DDI + DDD + número, só dígitos)
          <input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="5511999991234"
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={busy}>
          {busy ? "Salvando…" : "Adicionar"}
        </button>
      </form>

      <h2>Inscritos ({subs.length})</h2>
      <ul className="rule-list">
        {subs.map((s) => (
          <li key={s.id}>
            <span style={{ marginRight: 8 }}>{s.kind === "whatsapp" ? "📱 WA" : "📲 Push"}</span>
            <code>{s.target}</code>
            <button
              style={{ float: "right", border: 0, background: "transparent", color: "#d33", cursor: "pointer" }}
              onClick={() => remove(s.id)}
            >
              remover
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
