import { useEffect, useState } from "react";
import { CookieBanner } from "./components/CookieBanner";
import { LegalModal } from "./components/LegalModal";
import type { LegalPage } from "./components/LegalModal";
import {
  Alert,
  AlertFilters,
  AuthUser,
  Camera,
  Rule,
  acceptTerms,
  fetchMe,
  listAlerts,
  listCameras,
  listRules,
  openAlertStream,
  setToken,
} from "./api";
import { AlertCard } from "./components/AlertCard";
import { AlertsFilters, ClientFilters, filterAlertsClient } from "./components/AlertsFilters";
import { AuthScreen } from "./components/AuthScreen";
import { BillingPage } from "./components/BillingPage";
import { CamerasPanel } from "./components/CamerasPanel";
import { FacesPanel } from "./components/FacesPanel";
import { PricingPage } from "./components/PricingPage";
import { RulesPanel } from "./components/RulesPanel";
import { SubscribersPanel } from "./components/SubscribersPanel";
import { ThemeProvider } from "./components/ui/theme-provider";
import { ThemeToggle } from "./components/ThemeToggle";
import { Badge } from "./components/ui/badge";
import { Separator } from "./components/ui/separator";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./components/ui/dropdown-menu";
import { Bell, Camera as CameraIcon, ChevronDown, CreditCard, ListChecks, LogOut, Receipt, Send, ShieldAlert, UserCircle2 } from "lucide-react";
import { cn } from "./lib/utils";

type Tab = "alerts" | "cameras" | "rules" | "subscribers" | "faces" | "pricing" | "billing";

const NAV: { id: Tab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: "alerts", label: "Alertas", icon: Bell },
  { id: "cameras", label: "Câmeras", icon: CameraIcon },
  { id: "rules", label: "Regras", icon: ListChecks },
  { id: "subscribers", label: "Notificações", icon: Send },
  { id: "faces", label: "Faces conhecidas", icon: UserCircle2 },
  { id: "pricing", label: "Planos", icon: CreditCard },
  { id: "billing", label: "Cobrança", icon: Receipt },
];

export function App() {
  const [user, setUser] = useState<AuthUser | null | undefined>(undefined);
  const [termsUpdateRequired, setTermsUpdateRequired] = useState(false);

  useEffect(() => {
    fetchMe().then((u) => setUser(u)).catch(() => setUser(null));
  }, []);

  useEffect(() => {
    const handler = () => setTermsUpdateRequired(true);
    window.addEventListener("terms-update-required", handler);
    return () => window.removeEventListener("terms-update-required", handler);
  }, []);

  return (
    <ThemeProvider defaultTheme="system">
      {user === undefined ? (
        <div className="flex h-screen items-center justify-center text-sm text-muted-foreground">Carregando…</div>
      ) : user === null ? (
        <AuthScreen onAuthed={setUser} />
      ) : (
        <Authenticated user={user} onLogout={() => { setToken(null); setUser(null); }} />
      )}
      {termsUpdateRequired && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60">
          <div className="bg-card border border-border rounded-lg p-6 max-w-md w-full mx-4 shadow-xl">
            <h2 className="text-lg font-semibold mb-2">Termos atualizados</h2>
            <p className="text-sm text-muted-foreground mb-4">
              Nossa política de privacidade foi atualizada. Você precisa aceitar os novos termos para continuar.
            </p>
            <button
              onClick={async () => {
                await acceptTerms("v1.0");
                setTermsUpdateRequired(false);
              }}
              className="w-full py-2 px-4 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
            >
              Aceitar e continuar
            </button>
          </div>
        </div>
      )}
    </ThemeProvider>
  );
}

function Authenticated({ user, onLogout }: { user: AuthUser; onLogout: () => void }) {
  const [tab, setTab] = useState<Tab>("alerts");
  const [legalPage, setLegalPage] = useState<LegalPage | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [serverFilters, setServerFilters] = useState<AlertFilters>({});
  const [clientFilters, setClientFilters] = useState<ClientFilters>({ status: "all", search: "" });

  async function refreshAlerts(filters: AlertFilters = serverFilters) {
    try { setAlerts(await listAlerts(filters)); } catch (e) { console.error(e); }
  }
  async function refreshAll(filters: AlertFilters = serverFilters) {
    try {
      const [a, c, r] = await Promise.all([listAlerts(filters), listCameras(), listRules()]);
      setAlerts(a); setCameras(c); setRules(r);
    } catch (e) { console.error(e); }
  }

  useEffect(() => {
    refreshAll();
    const close = openAlertStream((wsAlert) => {
      setWsConnected(true);
      refreshAlerts();
      flashTitle(wsAlert.rule_name || "Sem nome");
    });
    return close;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    refreshAlerts(serverFilters);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(serverFilters)]);

  function flashTitle(rule: string) {
    const orig = document.title;
    document.title = `🔔 ${rule}`;
    setTimeout(() => { document.title = orig; }, 4000);
  }

  const visible = filterAlertsClient(alerts, clientFilters);
  const pending = visible.filter((a) => a.status === "pending").length;

  const pageTitle = NAV.find((n) => n.id === tab)?.label ?? "";

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      {/* Sidebar */}
      <aside className="flex w-60 flex-col border-r bg-card">
        <div className="flex h-14 items-center gap-2 px-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <ShieldAlert className="h-4 w-4" />
          </div>
          <span className="text-sm font-semibold tracking-tight">cams-erp</span>
        </div>
        <Separator />
        <nav className="flex-1 space-y-1 p-2">
          {NAV.map((item) => {
            const Icon = item.icon;
            const active = tab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setTab(item.id)}
                className={cn(
                  "flex w-full items-center justify-between rounded-md px-3 py-2 text-sm transition-colors",
                  active ? "bg-secondary text-foreground" : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground"
                )}
              >
                <span className="flex items-center gap-2"><Icon className="h-4 w-4" /> {item.label}</span>
                {item.id === "alerts" && pending > 0 && <Badge variant="default" className="h-5 px-1.5">{pending}</Badge>}
              </button>
            );
          })}
        </nav>
        <Separator />
        <div className="p-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="flex w-full items-center justify-between rounded-md px-2 py-2 text-left text-sm hover:bg-secondary/60">
                <span className="flex min-w-0 items-center gap-2">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-secondary text-xs font-medium uppercase">
                    {(user.name || user.email).slice(0, 1)}
                  </span>
                  <span className="min-w-0 truncate">{user.name || user.email}</span>
                </span>
                <ChevronDown className="h-4 w-4 opacity-50" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-56">
              <DropdownMenuLabel className="truncate">{user.email}</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={onLogout}><LogOut className="h-4 w-4" /> Sair</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </aside>

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-between border-b bg-background/80 px-6 backdrop-blur">
          <div className="flex items-center gap-3">
            <h1 className="text-base font-semibold tracking-tight">{pageTitle}</h1>
            {tab === "alerts" && (
              <Badge variant={wsConnected ? "success" : "secondary"} className="gap-1">
                <span className={cn("h-1.5 w-1.5 rounded-full", wsConnected ? "bg-emerald-500" : "bg-muted-foreground")} />
                {wsConnected ? "ao vivo" : "aguardando"}
              </Badge>
            )}
          </div>
          <ThemeToggle />
        </header>

        <main className="min-h-0 flex-1 overflow-y-auto p-6 flex flex-col">
          {tab === "alerts" && (
            <div className="mx-auto max-w-5xl space-y-4">
              <AlertsFilters
                serverFilters={serverFilters}
                clientFilters={clientFilters}
                cameras={cameras}
                onServerChange={setServerFilters}
                onClientChange={setClientFilters}
              />
              {visible.length === 0 ? (
                <EmptyState icon={Bell} title="Nenhum alerta" hint="Os alertas vão aparecer aqui em tempo real." />
              ) : (
                <div className="grid gap-4">
                  {visible.map((a) => <AlertCard key={a.id} alert={a} onUpdate={() => refreshAlerts()} />)}
                </div>
              )}
            </div>
          )}
          {tab === "cameras" && <CamerasPanel cameras={cameras} rules={rules} onChange={() => refreshAll()} />}
          {tab === "rules" && <RulesPanel cameras={cameras} rules={rules} onChange={() => refreshAll()} />}
          {tab === "subscribers" && <SubscribersPanel />}
          {tab === "faces" && <FacesPanel />}
          {tab === "pricing" && <PricingPage />}
          {tab === "billing" && <BillingPage />}
          <footer className="border-t border-border mt-8 py-4 text-center text-xs text-muted-foreground space-x-4">
            <button onClick={() => setLegalPage("privacy")} className="hover:underline">Privacidade</button>
            <button onClick={() => setLegalPage("terms")} className="hover:underline">Termos</button>
            <button onClick={() => setLegalPage("subprocessors")} className="hover:underline">Sub-processadores</button>
            <span>© 2026 cams-erp · v1.0</span>
          </footer>
        </main>
      </div>
      <CookieBanner onOpenPrivacy={() => setLegalPage("privacy")} />
      <LegalModal page={legalPage} onClose={() => setLegalPage(null)} />
    </div>
  );
}

function EmptyState({ icon: Icon, title, hint }: { icon: React.ComponentType<{ className?: string }>; title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed bg-card/50 p-12 text-center">
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-secondary">
        <Icon className="h-5 w-5 text-muted-foreground" />
      </div>
      <p className="text-sm font-medium">{title}</p>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
