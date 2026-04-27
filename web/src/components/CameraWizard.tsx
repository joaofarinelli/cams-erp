import { useEffect, useState } from "react";
import {
  Device,
  DiscoveredDevice,
  ProbeResult,
  Templates,
  createCamera,
  createPairCode,
  discoverCameras,
  fetchTemplates,
  listDevices,
  probeStream,
} from "../api";

const VENDORS = ["intelbras", "hikvision", "dahua", "axis", "uniview", "vivotek", "generic"] as const;

type Step = "scan" | "stream" | "name";

export function CameraWizard({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
  const [step, setStep] = useState<Step>("scan");

  // Scan state
  const [discovered, setDiscovered] = useState<DiscoveredDevice[]>([]);
  const [scanning, setScanning] = useState(false);
  const [pickedDevice, setPickedDevice] = useState<DiscoveredDevice | null>(null);
  const [manualIp, setManualIp] = useState("");
  const [manualVendor, setManualVendor] = useState<string>("intelbras");

  // Stream state
  const [templates, setTemplates] = useState<Templates>({});
  const [vendor, setVendor] = useState<string>("intelbras");
  const [tplIndex, setTplIndex] = useState(0);
  const [user, setUser] = useState("admin");
  const [pwd, setPwd] = useState("");
  const [ip, setIp] = useState("");
  const [probing, setProbing] = useState(false);
  const [probe, setProbe] = useState<ProbeResult | null>(null);
  const [rtspUrl, setRtspUrl] = useState("");

  // Name + create state
  const [devices, setDevices] = useState<Device[]>([]);
  const [deviceId, setDeviceId] = useState("");
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pairBanner, setPairBanner] = useState<string | null>(null);

  useEffect(() => {
    fetchTemplates().then(setTemplates).catch(console.warn);
    listDevices().then((d) => {
      setDevices(d);
      if (d.length > 0) setDeviceId(d[0].id);
    });
  }, []);

  async function scan() {
    setScanning(true);
    setError(null);
    try {
      const r = await discoverCameras();
      setDiscovered(r);
    } catch (e) {
      setError(String(e));
    } finally {
      setScanning(false);
    }
  }

  function pickDiscovered(d: DiscoveredDevice) {
    setPickedDevice(d);
    setIp(d.ip);
    setVendor(d.vendor || "generic");
    setTplIndex(0);
    if (d.name) setName(d.name);
    setStep("stream");
  }

  function pickManual() {
    if (!manualIp.trim()) {
      setError("Informe o IP da câmera");
      return;
    }
    setIp(manualIp.trim());
    setVendor(manualVendor);
    setTplIndex(0);
    setPickedDevice(null);
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
    setProbing(true);
    setProbe(null);
    setError(null);
    const url = buildUrl();
    setRtspUrl(url);
    try {
      const r = await probeStream(url);
      setProbe(r);
      if (!r.ok) setError(r.error || "Falha ao conectar");
    } catch (e) {
      setError(String(e));
    } finally {
      setProbing(false);
    }
  }

  async function createNewDevice() {
    try {
      const pc = await createPairCode();
      setPairBanner(
        `Device criado (id ${pc.device_id.slice(0, 8)}…). Para vinculá-lo a um agente real, use o pair_code ${pc.pair_code}. Pra cadastrar a câmera neste device basta selecioná-lo abaixo.`
      );
      const fresh = await listDevices();
      setDevices(fresh);
      setDeviceId(pc.device_id);
    } catch (e) {
      setError(String(e));
    }
  }

  async function submit() {
    if (!deviceId) {
      setError("Crie ou selecione um device");
      return;
    }
    if (!name.trim()) {
      setError("Dê um nome à câmera");
      return;
    }
    setCreating(true);
    setError(null);
    try {
      await createCamera({ name: name.trim(), rtsp_url: rtspUrl, device_id: deviceId });
      onDone();
    } catch (e) {
      setError(String(e));
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="wizard">
      <header>
        <h2>Adicionar câmera</h2>
        <button type="button" onClick={onCancel} className="btn-muted">Fechar</button>
      </header>

      <ol className="wizard-steps">
        <li className={step === "scan" ? "active" : ""}>1 · Descobrir</li>
        <li className={step === "stream" ? "active" : ""}>2 · Testar stream</li>
        <li className={step === "name" ? "active" : ""}>3 · Salvar</li>
      </ol>

      {step === "scan" && (
        <div className="wizard-step">
          <p>Descubra câmeras ONVIF na rede local ou informe um IP manualmente.</p>
          <button type="button" onClick={scan} disabled={scanning} className="btn-primary">
            {scanning ? "Procurando…" : "Procurar agora"}
          </button>
          <ul className="discovered-list">
            {discovered.length === 0 && !scanning && (
              <li className="muted">Nenhum dispositivo respondeu. Use entrada manual.</li>
            )}
            {discovered.map((d) => (
              <li key={d.ip}>
                <button onClick={() => pickDiscovered(d)} className="link-btn">
                  <strong>{d.name || d.ip}</strong>
                  <span className="muted"> · {d.vendor || "desconhecido"} · {d.ip}</span>
                </button>
              </li>
            ))}
          </ul>

          <div className="manual-add">
            <h3>Manual</h3>
            <div className="row">
              <input
                placeholder="IP local (ex: 192.168.0.42)"
                value={manualIp}
                onChange={(e) => setManualIp(e.target.value)}
              />
              <select value={manualVendor} onChange={(e) => setManualVendor(e.target.value)}>
                {VENDORS.map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>
              <button onClick={pickManual}>Continuar</button>
            </div>
          </div>
          {error && <p className="error">{error}</p>}
        </div>
      )}

      {step === "stream" && (
        <div className="wizard-step">
          <p className="muted">
            {pickedDevice ? `Configurando ${pickedDevice.name || pickedDevice.ip}` : `IP ${ip} (${vendor})`}
          </p>
          <div className="grid-2">
            <label>
              Fabricante
              <select value={vendor} onChange={(e) => { setVendor(e.target.value); setTplIndex(0); }}>
                {VENDORS.map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            </label>
            <label>
              Stream
              <select value={tplIndex} onChange={(e) => setTplIndex(Number(e.target.value))}>
                {(templates[vendor] || []).map((t, i) => (
                  <option key={i} value={i}>{t.label}</option>
                ))}
              </select>
            </label>
            <label>
              IP
              <input value={ip} onChange={(e) => setIp(e.target.value)} />
            </label>
            <label>
              Usuário
              <input value={user} onChange={(e) => setUser(e.target.value)} />
            </label>
            <label className="span-2">
              Senha
              <input type="password" value={pwd} onChange={(e) => setPwd(e.target.value)} />
            </label>
          </div>
          <code className="rtsp-preview">{buildUrl().replace(/:[^:@]+@/, ":•••••@")}</code>
          <div className="form-actions">
            <button onClick={testStream} disabled={probing} className="btn-primary">
              {probing ? "Testando…" : "Testar stream"}
            </button>
            <button onClick={() => setStep("scan")} className="btn-muted">Voltar</button>
            <button onClick={() => setStep("name")} disabled={!probe?.ok} className="btn-muted">
              Avançar →
            </button>
          </div>
          {probe?.ok && (
            <div className="probe-result">
              <img src={probe.preview_data_url ?? undefined} alt="preview" />
              <div>
                <p>
                  ✅ <strong>{probe.codec}</strong> · {probe.width}×{probe.height} @ {probe.fps}fps
                </p>
              </div>
            </div>
          )}
          {error && <p className="error">{error}</p>}
        </div>
      )}

      {step === "name" && (
        <div className="wizard-step">
          <label>
            Nome da câmera
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ex: Caixa 1"
            />
          </label>
          <label>
            Device (PDV/agente)
            <select value={deviceId} onChange={(e) => setDeviceId(e.target.value)}>
              <option value="">— selecione —</option>
              {devices.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} {d.paired ? "✓" : "(não pareado)"}
                </option>
              ))}
            </select>
          </label>
          <button type="button" onClick={createNewDevice} className="btn-muted">
            + Criar novo device
          </button>
          {pairBanner && <p className="muted">{pairBanner}</p>}
          <code className="rtsp-preview">{rtspUrl.replace(/:[^:@]+@/, ":•••••@")}</code>
          <div className="form-actions">
            <button onClick={() => setStep("stream")} className="btn-muted">Voltar</button>
            <button onClick={submit} disabled={creating} className="btn-primary">
              {creating ? "Salvando…" : "Salvar câmera"}
            </button>
          </div>
          {error && <p className="error">{error}</p>}
        </div>
      )}
    </div>
  );
}
