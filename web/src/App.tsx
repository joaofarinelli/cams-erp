import { useEffect, useState } from "react";
import { Alert, AlertFilters, Camera, Rule, listAlerts, listCameras, listRules, openAlertStream } from "./api";
import { AlertCard } from "./components/AlertCard";
import { AlertsFilters, ClientFilters, filterAlertsClient } from "./components/AlertsFilters";
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
  const [serverFilters, setServerFilters] = useState<AlertFilters>({});
  const [clientFilters, setClientFilters] = useState<ClientFilters>({ status: "all", search: "" });

  async function refreshAlerts(filters: AlertFilters = serverFilters) {
    try {
      setAlerts(await listAlerts(filters));
    } catch (e) {
      console.error("listAlerts failed", e);
    }
  }

  async function refreshAll(filters: AlertFilters = serverFilters) {
    try {
      const [a, c, r] = await Promise.all([listAlerts(filters), listCameras(), listRules()]);
      setAlerts(a);
      setCameras(c);
      setRules(r);
    } catch (e) {
      console.error("refresh failed", e);
    }
  }

  useEffect(() => {
    refreshAll();
    const close = openAlertStream((wsAlert) => {
      setWsConnected(true);
      refreshAlerts();
      flashTitle(wsAlert.rule_name || wsAlert.preset_type);
    });
    return close;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-fetch when server filters change
  useEffect(() => {
    refreshAlerts(serverFilters);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(serverFilters)]);

  function flashTitle(rule: string) {
    const orig = document.title;
    document.title = `🔔 ${rule}`;
    setTimeout(() => {
      document.title = orig;
    }, 4000);
  }

  const visible = filterAlertsClient(alerts, clientFilters);

  return (
    <div className="app">
      <header>
        <h1>cams-erp</h1>
        <nav>
          <button className={tab === "alerts" ? "active" : ""} onClick={() => setTab("alerts")}>
            Alertas {visible.length > 0 && <span className="badge">{visible.length}</span>}
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
        <span
          className={`ws-dot ${wsConnected ? "ok" : "off"}`}
          title={wsConnected ? "WS conectado" : "aguardando"}
        />
      </header>

      <main>
        {tab === "alerts" && (
          <>
            <AlertsFilters
              serverFilters={serverFilters}
              clientFilters={clientFilters}
              cameras={cameras}
              onServerChange={setServerFilters}
              onClientChange={setClientFilters}
            />
            <section className="alerts">
              {visible.length === 0 && <p className="empty">Nenhum alerta para os filtros atuais.</p>}
              {visible.map((a) => (
                <AlertCard key={a.id} alert={a} onUpdate={() => refreshAlerts()} />
              ))}
            </section>
          </>
        )}
        {tab === "cameras" && <CamerasPanel cameras={cameras} rules={rules} />}
        {tab === "rules" && <RulesPanel cameras={cameras} rules={rules} onChange={() => refreshAll()} />}
        {tab === "subscribers" && <SubscribersPanel />}
      </main>
    </div>
  );
}
