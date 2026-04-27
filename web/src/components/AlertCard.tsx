import { useState } from "react";
import { Alert, clipUrl, postAlertFeedback } from "../api";

export function AlertCard({ alert, onUpdate }: { alert: Alert; onUpdate: () => void }) {
  const [busy, setBusy] = useState(false);

  async function feedback(isFalsePositive: boolean) {
    setBusy(true);
    try {
      await postAlertFeedback(alert.id, isFalsePositive);
      onUpdate();
    } finally {
      setBusy(false);
    }
  }

  const created = new Date(alert.created_at);
  const scoreColor = alert.score >= 0.8 ? "#d33" : alert.score >= 0.5 ? "#d80" : "#888";

  return (
    <div className="alert-card">
      <video controls preload="metadata" src={clipUrl(alert.s3_key)} />
      <div className="alert-body">
        <header>
          <strong>{alert.rule_name || alert.preset_type}</strong>
          <span className="score" style={{ color: scoreColor }}>
            score {alert.score.toFixed(2)}
          </span>
          <span className={`status ${alert.status}`}>{alert.status}</span>
        </header>
        <p>{alert.message}</p>
        <footer>
          <small>{created.toLocaleString("pt-BR")}</small>
          {alert.status === "pending" && (
            <span>
              <button disabled={busy} onClick={() => feedback(false)}>
                Confirmar
              </button>
              <button disabled={busy} onClick={() => feedback(true)}>
                Falso positivo
              </button>
            </span>
          )}
        </footer>
      </div>
    </div>
  );
}
