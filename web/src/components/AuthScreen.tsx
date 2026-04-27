import { useState } from "react";
import { AuthUser, login, setToken, signup } from "../api";

type Mode = "login" | "signup";

export function AuthScreen({ onAuthed }: { onAuthed: (u: AuthUser) => void }) {
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const fn = mode === "login" ? login : signup;
      const args = mode === "login" ? { email, password } : { email, password, name: name || undefined };
      const r = await fn(args as never);
      setToken(r.access_token);
      onAuthed(r.user);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <form className="auth-card" onSubmit={submit}>
        <h1>cams-erp</h1>
        <div className="auth-tabs">
          <button type="button" className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>
            Entrar
          </button>
          <button type="button" className={mode === "signup" ? "active" : ""} onClick={() => setMode("signup")}>
            Cadastrar
          </button>
        </div>
        {mode === "signup" && (
          <label>
            Nome (opcional)
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Seu nome" />
          </label>
        )}
        <label>
          Email
          <input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label>
          Senha
          <input
            type="password"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            required
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={busy} className="btn-primary">
          {busy ? "Aguarde…" : mode === "login" ? "Entrar" : "Criar conta"}
        </button>
        <small className="muted">
          {mode === "signup"
            ? "Mín. 8 caracteres. Senha hash bcrypt no servidor."
            : "Esqueceu a senha? Use export+delete e cadastre de novo (recovery flow é Phase 3)."}
        </small>
      </form>
    </div>
  );
}
