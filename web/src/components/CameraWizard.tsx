import { useEffect, useState } from "react";
import {
  Device,
  DiscoveredDevice,
  LocalDevice,
  ProbeResult,
  Templates,
  createCamera,
  createPairCode,
  discoverCameras,
  fetchAgentStatus,
  fetchTemplates,
  listDevices,
  listLocalDevices,
  probeStream,
} from "../api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Badge } from "./ui/badge";
import { Separator } from "./ui/separator";
import { Card } from "./ui/card";
import { cn } from "@/lib/utils";
import { Check, Loader2, Plus, Search, Webcam } from "lucide-react";

const VENDORS = ["intelbras", "hikvision", "dahua", "axis", "uniview", "vivotek", "iphone", "generic"] as const;

type Step = "scan" | "stream" | "name";
const STEPS: { id: Step; label: string }[] = [
  { id: "scan", label: "Descobrir" },
  { id: "stream", label: "Testar stream" },
  { id: "name", label: "Salvar" },
];

export function CameraWizard({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
  const [step, setStep] = useState<Step>("scan");

  const [discovered, setDiscovered] = useState<DiscoveredDevice[]>([]);
  const [localDevs, setLocalDevs] = useState<LocalDevice[]>([]);
  const [scanningLocal, setScanningLocal] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [pickedDevice, setPickedDevice] = useState<DiscoveredDevice | null>(null);
  const [manualIp, setManualIp] = useState("");
  const [manualVendor, setManualVendor] = useState<string>("intelbras");

  const [templates, setTemplates] = useState<Templates>({});
  const [vendor, setVendor] = useState<string>("intelbras");
  const [tplIndex, setTplIndex] = useState(0);
  const [user, setUser] = useState("admin");
  const [pwd, setPwd] = useState("");
  const [ip, setIp] = useState("");
  const [probing, setProbing] = useState(false);
  const [probe, setProbe] = useState<ProbeResult | null>(null);
  const [rtspUrl, setRtspUrl] = useState("");

  const [devices, setDevices] = useState<Device[]>([]);
  const [deviceId, setDeviceId] = useState("");
  const [agentOnline, setAgentOnline] = useState<boolean | null>(null);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pairBanner, setPairBanner] = useState<string | null>(null);

  useEffect(() => {
    fetchTemplates().then(setTemplates).catch(console.warn);
    listDevices().then((d) => { setDevices(d); if (d.length > 0) setDeviceId(d[0].id); });
  }, []);

  useEffect(() => {
    if (!deviceId) { setAgentOnline(null); return; }
    let cancelled = false;
    const tick = () => {
      fetchAgentStatus(deviceId)
        .then((s) => { if (!cancelled) setAgentOnline(s.online); })
        .catch(() => { if (!cancelled) setAgentOnline(false); });
    };
    tick();
    const id = setInterval(tick, 5000);
    return () => { cancelled = true; clearInterval(id); };
  }, [deviceId]);

  async function scan() {
    if (!deviceId) { setError("Selecione um PDV/agente primeiro"); return; }
    setScanning(true); setError(null);
    try { setDiscovered(await discoverCameras(deviceId)); }
    catch (e) { setError(String(e)); }
    finally { setScanning(false); }
  }

  async function scanLocal() {
    if (!deviceId) { setError("Selecione um PDV/agente primeiro"); return; }
    setScanningLocal(true); setError(null);
    try { setLocalDevs(await listLocalDevices(deviceId)); }
    catch (e) { setError(String(e)); }
    finally { setScanningLocal(false); }
  }

  async function pickLocal(d: LocalDevice) {
    // Skip vendor/IP/template: source URI is ready (e.g. dshow:video=...)
    setRtspUrl(d.source);
    setName(d.name);
    setError(null);
    setProbing(true); setProbe(null);
    try {
      const r = await probeStream(deviceId, d.source);
      setProbe(r);
      if (r.ok) setStep("name");
      else setError(r.error || "Falha");
    } catch (e) { setError(String(e)); }
    finally { setProbing(false); }
  }

  function pickDiscovered(d: DiscoveredDevice) {
    setPickedDevice(d); setIp(d.ip); setVendor(d.vendor || "generic"); setTplIndex(0);
    if (d.name) setName(d.name);
    setStep("stream");
  }

  function pickManual() {
    if (!manualIp.trim()) { setError("Informe o IP da câmera"); return; }
    setIp(manualIp.trim()); setVendor(manualVendor); setTplIndex(0); setPickedDevice(null);
    setStep("stream");
  }

  function buildUrl(): string {
    const tpls = templates[vendor] || templates["generic"] || [];
    const tpl = tpls[tplIndex];
    if (!tpl) return "";
    return tpl.url
      .replace("{user}", encodeURIComponent(user))
      .replace("{password}", encodeURIComponent(pwd))
      .replace("{ip}", ip);
  }

  async function testStream() {
    setProbing(true); setProbe(null); setError(null);
    const url = buildUrl(); setRtspUrl(url);
    try { const r = await probeStream(deviceId, url); setProbe(r); if (!r.ok) setError(r.error || "Falha"); }
    catch (e) { setError(String(e)); }
    finally { setProbing(false); }
  }

  async function createNewDevice() {
    try {
      const pc = await createPairCode();
      setPairBanner(`Device criado (${pc.device_id.slice(0, 8)}…). Pair code: ${pc.pair_code}.`);
      const fresh = await listDevices(); setDevices(fresh); setDeviceId(pc.device_id);
    } catch (e) { setError(String(e)); }
  }

  async function submit() {
    if (!deviceId) { setError("Selecione um device"); return; }
    if (!name.trim()) { setError("Dê um nome à câmera"); return; }
    setCreating(true); setError(null);
    try { await createCamera({ name: name.trim(), rtsp_url: rtspUrl, device_id: deviceId }); onDone(); }
    catch (e) { setError(String(e)); }
    finally { setCreating(false); }
  }

  const stepIdx = STEPS.findIndex((s) => s.id === step);

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onCancel(); }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader><DialogTitle>Adicionar câmera</DialogTitle></DialogHeader>

        {/* Stepper */}
        <ol className="flex items-center gap-2 text-xs">
          {STEPS.map((s, i) => (
            <li key={s.id} className="flex items-center gap-2">
              <span
                className={cn(
                  "flex h-6 w-6 items-center justify-center rounded-full border text-xs font-medium",
                  i < stepIdx ? "border-primary bg-primary text-primary-foreground" :
                  i === stepIdx ? "border-primary text-primary" : "border-muted text-muted-foreground"
                )}
              >
                {i < stepIdx ? <Check className="h-3 w-3" /> : i + 1}
              </span>
              <span className={cn("font-medium", i === stepIdx ? "text-foreground" : "text-muted-foreground")}>{s.label}</span>
              {i < STEPS.length - 1 && <span className="mx-1 h-px w-6 bg-border" />}
            </li>
          ))}
        </ol>
        <Separator />

        {step === "scan" && (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>PDV/agente (rede local que será escaneada)</Label>
              <div className="flex gap-2">
                <Select value={deviceId} onValueChange={setDeviceId}>
                  <SelectTrigger className="flex-1"><SelectValue placeholder="— selecione —" /></SelectTrigger>
                  <SelectContent>
                    {devices.map((d) => (
                      <SelectItem key={d.id} value={d.id}>{d.name} {d.paired ? "✓" : "(não pareado)"}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button variant="outline" onClick={createNewDevice}><Plus className="h-4 w-4" /> Novo</Button>
              </div>
              {deviceId && (
                <Badge variant={agentOnline ? "success" : "destructive"} className="gap-1">
                  <span className={cn("h-1.5 w-1.5 rounded-full", agentOnline ? "bg-emerald-500" : "bg-rose-500")} />
                  {agentOnline === null ? "verificando…" : agentOnline ? "Agente online" : "Agente offline"}
                </Badge>
              )}
              {pairBanner && <p className="rounded-md bg-secondary p-2 text-xs text-muted-foreground">{pairBanner}</p>}
            </div>

            <div className="grid grid-cols-2 gap-2">
              <Button onClick={scan} disabled={scanning || !deviceId || !agentOnline}>
                {scanning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                {scanning ? "Procurando…" : "Câmeras IP (ONVIF)"}
              </Button>
              <Button variant="outline" onClick={scanLocal} disabled={scanningLocal || !deviceId || !agentOnline}>
                {scanningLocal ? <Loader2 className="h-4 w-4 animate-spin" /> : <Webcam className="h-4 w-4" />}
                {scanningLocal ? "Listando…" : "Câmeras USB locais"}
              </Button>
            </div>

            {localDevs.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-xs font-medium text-muted-foreground">Câmeras conectadas no PDV</p>
                {localDevs.map((d) => (
                  <Card key={d.source} className="cursor-pointer p-3 transition-colors hover:bg-accent" onClick={() => pickLocal(d)}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Webcam className="h-4 w-4 text-muted-foreground" />
                        <div>
                          <p className="text-sm font-medium">{d.name}</p>
                          <p className="text-xs text-muted-foreground">USB / integrada · {d.source}</p>
                        </div>
                      </div>
                      <Badge variant="outline">{probing && rtspUrl === d.source ? "testando…" : "selecionar"}</Badge>
                    </div>
                  </Card>
                ))}
              </div>
            )}

            {discovered.length > 0 && (
              <div className="space-y-1.5">
                {discovered.map((d) => (
                  <Card key={d.ip} className="cursor-pointer p-3 transition-colors hover:bg-accent" onClick={() => pickDiscovered(d)}>
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium">{d.name || d.ip}</p>
                        <p className="text-xs text-muted-foreground">{d.vendor || "desconhecido"} · {d.ip}</p>
                      </div>
                      <Badge variant="outline">selecionar</Badge>
                    </div>
                  </Card>
                ))}
              </div>
            )}

            <Separator />
            <div className="space-y-2">
              <Label>Entrada manual</Label>
              <div className="flex gap-2">
                <Input placeholder="IP local (ex: 192.168.0.42)" value={manualIp} onChange={(e) => setManualIp(e.target.value)} />
                <Select value={manualVendor} onValueChange={setManualVendor}>
                  <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {VENDORS.map((v) => <SelectItem key={v} value={v}>{v}</SelectItem>)}
                  </SelectContent>
                </Select>
                <Button variant="outline" onClick={pickManual}>Continuar</Button>
              </div>
            </div>

            {error && <p className="text-sm text-destructive">{error}</p>}
          </div>
        )}

        {step === "stream" && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">{pickedDevice ? `Configurando ${pickedDevice.name || pickedDevice.ip}` : `IP ${ip} (${vendor})`}</p>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Fabricante</Label>
                <Select value={vendor} onValueChange={(v) => { setVendor(v); setTplIndex(0); }}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{VENDORS.map((v) => <SelectItem key={v} value={v}>{v}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Stream</Label>
                <Select value={String(tplIndex)} onValueChange={(v) => setTplIndex(Number(v))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {(templates[vendor] || []).map((t, i) => <SelectItem key={i} value={String(i)}>{t.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>IP</Label>
                <Input value={ip} onChange={(e) => setIp(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>Usuário</Label>
                <Input value={user} onChange={(e) => setUser(e.target.value)} />
              </div>
              <div className="col-span-2 space-y-1.5">
                <Label>Senha</Label>
                <Input type="password" value={pwd} onChange={(e) => setPwd(e.target.value)} />
              </div>
            </div>
            <code className="block break-all rounded-md bg-secondary px-3 py-2 text-xs text-muted-foreground">
              {buildUrl().replace(/:[^:@]+@/, ":•••••@")}
            </code>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setStep("scan")}>Voltar</Button>
              <Button onClick={testStream} disabled={probing}>
                {probing ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                {probing ? "Testando…" : "Testar stream"}
              </Button>
              <Button variant="outline" onClick={() => setStep("name")} disabled={!probe?.ok} className="ml-auto">
                Avançar →
              </Button>
            </div>
            {probe?.ok && (
              <Card className="overflow-hidden">
                <div className="grid grid-cols-[160px_1fr] gap-3 p-3">
                  <img src={probe.preview_data_url ?? undefined} alt="preview" className="aspect-video w-40 rounded-md object-cover" />
                  <div className="flex flex-col justify-center text-sm">
                    <p>✅ <strong>{probe.codec}</strong> · {probe.width}×{probe.height} @ {probe.fps}fps</p>
                  </div>
                </div>
              </Card>
            )}
            {error && <p className="text-sm text-destructive">{error}</p>}
          </div>
        )}

        {step === "name" && (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label>Nome da câmera</Label>
              <Input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="Ex: Caixa 1" />
            </div>
            <p className="text-xs text-muted-foreground">PDV: {devices.find((d) => d.id === deviceId)?.name ?? "—"}</p>
            <code className="block break-all rounded-md bg-secondary px-3 py-2 text-xs text-muted-foreground">
              {rtspUrl.replace(/:[^:@]+@/, ":•••••@")}
            </code>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setStep("stream")}>Voltar</Button>
              <Button onClick={submit} disabled={creating} className="ml-auto">
                {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                {creating ? "Salvando…" : "Salvar câmera"}
              </Button>
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
