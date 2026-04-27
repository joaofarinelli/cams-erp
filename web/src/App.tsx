import { useEffect, useState } from "react";
import { Alert, Camera, Rule, listAlerts, listCameras, listRules, openAlertStream } from "./api";
import { AlertCard } from "./components/AlertCard";
import { CamerasPanel } from "./components/CamerasPanel";
import { RulesPanel } from "./components/RulesPanel";
import { SubscribersPanel } from "./components/SubscribersPanel";

type Tab = "alerts" | "cameras" | "rules" | "subscribers";

export function App() {
  const [tab, setTab] = useState<Tab>("alerts");
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [wsConnected, setWsConnected] = useState(false);

  async function refresh() {
    try {
      const [a, c, r] = await Promise.all([listAlerts(), listCameras(), listRules()]);
      setAlerts(a);
      setCameras(c);
      setRules(r);
    } catch (e) {
      console.error("refresh failed", e);
    }
  }

  useEffect(() => {
    refresh();
    const close = openAlertStream((wsAlert) => {
      setWsConnected(true);
      // The WS payload is a slim subset; refetch the full list to get s3_key
      // and the canonical AlertOut shape. Cheap (< 100ms locally).
      refresh();
      flashTitle(wsAlert.rule_name || wsAlert.preset_type);
    });
    return close;
  }, []);

  function flashTitle(rule: string) {
    const orig = document.title;
    document.title = `🔔 ${rule}`;
    setTimeout(() => {
      document.title = orig;
    }, 4000);
  }

  return (
    <div className="app">
      <header>
        <h1>cams-erp</h1>
        <nav>
          <button className={tab === "alerts" ? "active" : ""} onClick={() => setTab("alerts")}>
            Alertas {alerts.length > 0 && <span className="badge">{alerts.length}</span>}
          </button>
          <button className={tab === "cameras" ? "active" : ""} onClick={() => setTab("cameras")}>
            Câmeras
          </button>
          <button className={tab === "rules" ? "active" : ""} onClick={() => setTab("rules")}>
            Regras
          </button>
          <button className={tab === "subscribers" ? "active" : ""} onClick={() => setTab("subscribers")}>
            Notificações
          </button>
        </nav>
        <span className={`ws-dot ${wsConnected ? "ok" : "off"}`} title={wsConnected ? "WS conectado" : "aguardando"} />
      </header>

      <main>
        {tab === "alerts" && (
          <section className="alerts">
            {alerts.length === 0 && <p className="empty">Nenhum alerta ainda.</p>}
            {alerts.map((a) => (
              <AlertCard key={a.id} alert={a} onUpdate={refresh} />
            ))}
          </section>
        )}
        {tab === "cameras" && <CamerasPanel cameras={cameras} rules={rules} />}
        {tab === "rules" && <RulesPanel cameras={cameras} rules={rules} onChange={refresh} />}
        {tab === "subscribers" && <SubscribersPanel />}
      </main>
    </div>
  );
}
