import { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { cn } from "@/lib/utils";
import { Pencil, Plus, Trash2, X } from "lucide-react";

type Point = [number, number]; // normalized 0..1
export type Zones = Record<string, Point[]>;

const ZONE_COLORS = [
  "#3b82f6", // blue
  "#ef4444", // red
  "#10b981", // emerald
  "#f59e0b", // amber
  "#a855f7", // purple
  "#06b6d4", // cyan
];

type DragState = { zone: string; idx: number } | null;

export function PolygonEditor({
  imgUrl,
  value,
  onChange,
}: {
  imgUrl: string;
  value: Zones;
  onChange: (zones: Zones) => void;
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [imgOk, setImgOk] = useState(true);
  const [activeZone, setActiveZone] = useState<string>(() => Object.keys(value)[0] ?? "");
  const [renamingFrom, setRenamingFrom] = useState<string | null>(null);
  const [drag, setDrag] = useState<DragState>(null);

  useEffect(() => { setImgOk(true); }, [imgUrl]);

  const zoneNames = useMemo(() => Object.keys(value), [value]);
  const activePoints = activeZone ? value[activeZone] ?? [] : [];

  function clientToNormalized(clientX: number, clientY: number): Point {
    const svg = svgRef.current;
    if (!svg) return [0, 0];
    const rect = svg.getBoundingClientRect();
    const x = (clientX - rect.left) / rect.width;
    const y = (clientY - rect.top) / rect.height;
    return [Math.min(1, Math.max(0, x)), Math.min(1, Math.max(0, y))];
  }

  function addPoint(e: React.MouseEvent<SVGSVGElement>) {
    if (!activeZone || drag) return;
    if ((e.target as Element).getAttribute("data-handle") === "1") return; // ignore click on handle
    const p = clientToNormalized(e.clientX, e.clientY);
    onChange({ ...value, [activeZone]: [...activePoints, p] });
  }

  function startDrag(zone: string, idx: number, e: React.MouseEvent) {
    e.stopPropagation();
    e.preventDefault();
    setActiveZone(zone);
    setDrag({ zone, idx });
  }

  useEffect(() => {
    if (!drag) return;
    function onMove(e: MouseEvent) {
      const p = clientToNormalized(e.clientX, e.clientY);
      const pts = value[drag!.zone];
      if (!pts) return;
      const next = pts.slice();
      next[drag!.idx] = p;
      onChange({ ...value, [drag!.zone]: next });
    }
    function onUp() { setDrag(null); }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [drag]);

  function removePoint(zone: string, idx: number) {
    const pts = value[zone];
    if (!pts) return;
    onChange({ ...value, [zone]: pts.filter((_, i) => i !== idx) });
  }

  function startNewZone() {
    const base = `zona_${zoneNames.length + 1}`;
    let name = base;
    let n = zoneNames.length + 1;
    while (value[name]) { n += 1; name = `zona_${n}`; }
    setActiveZone(name);
    onChange({ ...value, [name]: [] });
    setRenamingFrom(name);
  }

  function deleteZone(name: string) {
    const { [name]: _, ...rest } = value;
    onChange(rest);
    if (activeZone === name) setActiveZone(Object.keys(rest)[0] ?? "");
  }

  function renameZone(oldName: string, newName: string) {
    const target = newName.trim();
    if (!target || target === oldName || value[target]) {
      setRenamingFrom(null);
      return;
    }
    const next: Zones = {};
    for (const [k, v] of Object.entries(value)) next[k === oldName ? target : k] = v;
    onChange(next);
    if (activeZone === oldName) setActiveZone(target);
    setRenamingFrom(null);
  }

  function clearActive() {
    if (!activeZone) return;
    onChange({ ...value, [activeZone]: [] });
  }

  return (
    <div className="space-y-3">
      <div className="relative mx-auto w-full max-w-md select-none overflow-hidden rounded-md border bg-black">
        {imgOk ? (
          <img
            src={imgUrl}
            alt="snapshot"
            onError={() => setImgOk(false)}
            draggable={false}
            className="block h-auto w-full"
          />
        ) : (
          <div className="aspect-video flex items-center justify-center p-6 text-center text-sm text-muted-foreground">
            Não foi possível obter um frame da câmera. Verifique se o agente do PDV está online.
          </div>
        )}
        {imgOk && (
          <svg
            ref={svgRef}
            viewBox="0 0 1 1"
            preserveAspectRatio="none"
            className={cn("absolute inset-0 h-full w-full", activeZone ? "cursor-crosshair" : "cursor-not-allowed")}
            onClick={addPoint}
          >
            {zoneNames.map((name, i) => {
              const pts = value[name];
              if (!pts || pts.length === 0) return null;
              const color = ZONE_COLORS[i % ZONE_COLORS.length];
              const isActive = name === activeZone;
              return (
                <g key={name}>
                  {pts.length >= 3 && (
                    <polygon
                      points={pts.map((p) => p.join(",")).join(" ")}
                      fill={color}
                      fillOpacity={isActive ? 0.25 : 0.15}
                      stroke={color}
                      strokeWidth={0.004}
                      pointerEvents="none"
                    />
                  )}
                  {pts.length === 2 && (
                    <line
                      x1={pts[0][0]} y1={pts[0][1]} x2={pts[1][0]} y2={pts[1][1]}
                      stroke={color} strokeWidth={0.004} strokeDasharray="0.01,0.005"
                      pointerEvents="none"
                    />
                  )}
                  {pts.map((p, idx) => (
                    <circle
                      key={idx}
                      data-handle="1"
                      cx={p[0]}
                      cy={p[1]}
                      r={isActive ? 0.014 : 0.01}
                      fill={color}
                      stroke="#fff"
                      strokeWidth={0.004}
                      vectorEffect="non-scaling-stroke"
                      onMouseDown={(e) => startDrag(name, idx, e)}
                      onContextMenu={(e) => { e.preventDefault(); removePoint(name, idx); }}
                      style={{ cursor: "grab" }}
                    />
                  ))}
                </g>
              );
            })}
          </svg>
        )}
      </div>

      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          {zoneNames.length === 0 && (
            <span className="text-sm text-muted-foreground">Nenhuma zona — opcional, regra sem zonas analisa o frame inteiro.</span>
          )}
          {zoneNames.map((name, i) => {
            const color = ZONE_COLORS[i % ZONE_COLORS.length];
            const isActive = name === activeZone;
            const pts = value[name] ?? [];
            if (renamingFrom === name) {
              return (
                <Input
                  key={name}
                  autoFocus
                  defaultValue={name}
                  onBlur={(e) => renameZone(name, e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") renameZone(name, (e.target as HTMLInputElement).value);
                    if (e.key === "Escape") setRenamingFrom(null);
                  }}
                  className="h-8 w-32"
                />
              );
            }
            return (
              <div
                key={name}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs transition-colors",
                  isActive ? "border-primary bg-secondary" : "border-border hover:bg-secondary/50"
                )}
              >
                <button type="button" onClick={() => setActiveZone(name)} className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full" style={{ background: color }} />
                  <span className="font-medium">{name}</span>
                  <span className="text-muted-foreground">({pts.length})</span>
                </button>
                <button type="button" onClick={() => setRenamingFrom(name)} className="text-muted-foreground hover:text-foreground" title="Renomear">
                  <Pencil className="h-3 w-3" />
                </button>
                <button type="button" onClick={() => deleteZone(name)} className="text-muted-foreground hover:text-destructive" title="Remover">
                  <X className="h-3 w-3" />
                </button>
              </div>
            );
          })}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" size="sm" variant="outline" onClick={startNewZone}>
            <Plus className="h-4 w-4" /> Nova zona
          </Button>
          <Button type="button" size="sm" variant="ghost" onClick={clearActive} disabled={!activeZone || activePoints.length === 0}>
            <Trash2 className="h-4 w-4" /> Limpar pontos
          </Button>
          <span className="text-xs text-muted-foreground">
            Clique no frame pra adicionar ponto · arraste pra mover · clique-direito apaga ponto · 3+ pontos formam polígono
          </span>
        </div>
      </div>
    </div>
  );
}
