import { useEffect, useMemo, useRef, useState } from "react";

type Point = [number, number]; // normalized 0..1
export type Zones = Record<string, Point[]>;

const ZONE_COLORS = ["#06a", "#a06", "#0a6", "#a60", "#60a", "#6a0"];

export function PolygonEditor({
  imgUrl,
  value,
  onChange,
}: {
  imgUrl: string;
  value: Zones;
  onChange: (zones: Zones) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [imgOk, setImgOk] = useState(true);
  const [activeZone, setActiveZone] = useState<string>(() => Object.keys(value)[0] ?? "");
  const [drafting, setDrafting] = useState<Point[]>([]);
  const [renamingFrom, setRenamingFrom] = useState<string | null>(null);

  useEffect(() => {
    setImgOk(true);
  }, [imgUrl]);

  const zoneNames = useMemo(() => Object.keys(value), [value]);

  function addPointFromEvent(e: React.MouseEvent<SVGSVGElement>) {
    if (!activeZone) return;
    const rect = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    setDrafting((d) => [...d, [Math.min(1, Math.max(0, x)), Math.min(1, Math.max(0, y))]]);
  }

  function commitDraft() {
    if (!activeZone || drafting.length < 3) {
      setDrafting([]);
      return;
    }
    onChange({ ...value, [activeZone]: drafting });
    setDrafting([]);
  }

  function startNewZone() {
    const name = window.prompt("Nome da zona (ex: gaveta, balcao):", `zona_${zoneNames.length + 1}`);
    if (!name) return;
    if (value[name]) {
      window.alert("Já existe uma zona com esse nome.");
      return;
    }
    setActiveZone(name);
    setDrafting([]);
    onChange({ ...value, [name]: [] });
  }

  function deleteZone(name: string) {
    const { [name]: _, ...rest } = value;
    onChange(rest);
    if (activeZone === name) {
      setActiveZone(Object.keys(rest)[0] ?? "");
      setDrafting([]);
    }
  }

  function renameZone(oldName: string, newName: string) {
    if (!newName || newName === oldName || value[newName]) {
      setRenamingFrom(null);
      return;
    }
    const next: Zones = {};
    for (const [k, v] of Object.entries(value)) next[k === oldName ? newName : k] = v;
    onChange(next);
    if (activeZone === oldName) setActiveZone(newName);
    setRenamingFrom(null);
  }

  function clearActive() {
    if (!activeZone) return;
    onChange({ ...value, [activeZone]: [] });
    setDrafting([]);
  }

  return (
    <div className="polygon-editor">
      <div className="polygon-canvas" ref={containerRef}>
        {imgOk ? (
          <img
            src={imgUrl}
            alt="thumbnail"
            onError={() => setImgOk(false)}
            draggable={false}
          />
        ) : (
          <div className="polygon-placeholder">
            Sem thumbnail ainda. Aguarde um evento de movimento ser capturado nesta câmera.
          </div>
        )}
        <svg
          viewBox="0 0 1 1"
          preserveAspectRatio="none"
          onClick={addPointFromEvent}
          onDoubleClick={commitDraft}
        >
          {zoneNames.map((name, i) => {
            const pts = value[name];
            if (!pts || pts.length === 0) return null;
            const color = ZONE_COLORS[i % ZONE_COLORS.length];
            const closed = pts.map((p) => p.join(",")).join(" ");
            return (
              <g key={name} pointerEvents="none">
                <polygon points={closed} fill={color} fillOpacity={0.18} stroke={color} strokeWidth={0.005} />
                {pts.map((p, idx) => (
                  <circle key={idx} cx={p[0]} cy={p[1]} r={0.01} fill={color} />
                ))}
              </g>
            );
          })}
          {drafting.length > 0 && (
            <g pointerEvents="none">
              <polyline
                points={drafting.map((p) => p.join(",")).join(" ")}
                fill="none"
                stroke="#d33"
                strokeWidth={0.005}
                strokeDasharray="0.01,0.005"
              />
              {drafting.map((p, idx) => (
                <circle key={idx} cx={p[0]} cy={p[1]} r={0.012} fill="#d33" />
              ))}
            </g>
          )}
        </svg>
      </div>

      <div className="polygon-controls">
        <div className="zone-list">
          {zoneNames.map((name, i) => {
            const color = ZONE_COLORS[i % ZONE_COLORS.length];
            const isActive = name === activeZone;
            return (
              <div key={name} className={`zone-row ${isActive ? "active" : ""}`}>
                <span className="zone-color" style={{ background: color }} />
                {renamingFrom === name ? (
                  <input
                    autoFocus
                    defaultValue={name}
                    onBlur={(e) => renameZone(name, e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") renameZone(name, (e.target as HTMLInputElement).value);
                      if (e.key === "Escape") setRenamingFrom(null);
                    }}
                  />
                ) : (
                  <button
                    type="button"
                    className="zone-name"
                    onClick={() => {
                      setActiveZone(name);
                      setDrafting([]);
                    }}
                    onDoubleClick={() => setRenamingFrom(name)}
                    title="Duplo clique pra renomear"
                  >
                    {name} ({value[name].length})
                  </button>
                )}
                <button type="button" className="muted" onClick={() => deleteZone(name)} title="Remover zona">
                  ✕
                </button>
              </div>
            );
          })}
        </div>
        <div className="polygon-actions">
          <button type="button" onClick={startNewZone}>+ Nova zona</button>
          <button type="button" disabled={!activeZone || drafting.length < 3} onClick={commitDraft}>
            Fechar zona ({drafting.length} pontos)
          </button>
          <button type="button" disabled={!activeZone} onClick={clearActive} className="muted">
            Limpar zona ativa
          </button>
        </div>
        <p className="polygon-help">
          Clique no thumbnail para adicionar pontos à zona ativa. Mín. 3 pontos. Duplo clique pra fechar.
          Coordenadas normalizadas (0..1) — funcionam mesmo se a câmera mudar de resolução.
        </p>
      </div>
    </div>
  );
}
