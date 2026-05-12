import { useState } from "react";
import { createCheckoutSession } from "../api";
import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";


type Tier = {
  id: "starter" | "pro" | "business";
  name: string;
  basePrice: number;
  extraPrice: number;
  baseCameras: number;
  highlight?: boolean;
  features: string[];
};


const TIERS: Tier[] = [
  {
    id: "starter",
    name: "Starter",
    basePrice: 197,
    extraPrice: 47,
    baseCameras: 2,
    features: [
      "Funciona com o DVR ou câmera IP que você já tem",
      "Regras em português, sem programação",
      "Alertas no WhatsApp + push mobile",
      "Filtro local contra sombra/vento/bicho",
      "Até 2 alertas inteligentes por câmera",
      "Histórico 7 dias",
      "Suporte por e-mail",
    ],
  },
  {
    id: "pro",
    name: "Pro",
    basePrice: 497,
    extraPrice: 87,
    baseCameras: 5,
    highlight: true,
    features: [
      "Tudo do Starter +",
      "IA reforçada em casos duvidosos",
      "Detecta ações rápidas (gaveta em 1s)",
      "Regras ilimitadas, horários personalizados",
      "Câmera ao vivo no celular + download",
      "Histórico 30 dias",
      "Chat com resposta no mesmo dia",
    ],
  },
  {
    id: "business",
    name: "Business",
    basePrice: 1497,
    extraPrice: 67,
    baseCameras: 20,
    features: [
      "Tudo do Pro +",
      "IA top de linha (Claude Sonnet)",
      "Multi-usuário, perfis por equipe",
      "Integração ERP/PDV/Slack/Telegram",
      "Histórico 90 dias para auditoria",
      "Suporte prioritário + gerente",
    ],
  },
];


export function PricingPage() {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const subscribe = async (tier: "starter" | "pro" | "business") => {
    setBusy(tier);
    setError(null);
    try {
      const url = await createCheckoutSession(tier);
      window.location.href = url;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro");
      setBusy(null);
    }
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6 py-4">
      <header className="space-y-2 text-center">
        <h1 className="text-3xl font-bold">
          Câmera comum só grava. cams-erp avisa quando algo importa.
        </h1>
        <p className="text-sm text-muted-foreground">
          Sem fidelidade · Configura em 10 minutos · Cancela quando quiser
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-3">
        {TIERS.map((t) => (
          <Card
            key={t.id}
            className={t.highlight ? "border-2 border-indigo-400 shadow-lg" : ""}
          >
            <CardContent className="space-y-4 p-6">
              {t.highlight && (
                <span className="rounded-full bg-indigo-500 px-3 py-1 text-xs font-semibold text-white">
                  Mais escolhido
                </span>
              )}
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {t.name}
                </p>
                <p className="mt-2 text-3xl font-bold">
                  R$ {t.basePrice}
                  <span className="text-sm font-normal text-muted-foreground">/mês</span>
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {t.baseCameras} câmera{t.baseCameras > 1 ? "s" : ""} incluída{t.baseCameras > 1 ? "s" : ""} ·
                  R$ {t.extraPrice} por câmera extra
                </p>
              </div>
              <Button
                className="w-full"
                variant={t.highlight ? "default" : "outline"}
                disabled={busy !== null}
                onClick={() => subscribe(t.id)}
              >
                {busy === t.id ? "Redirecionando…" : "Assinar"}
              </Button>
              {error && busy === null && (
                <p className="text-xs text-destructive">{error}</p>
              )}
              <ul className="space-y-2 text-sm">
                {t.features.map((f, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="mt-1 h-1.5 w-1.5 flex-none rounded-full bg-indigo-400" />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="rounded-xl border bg-card/50 p-6 text-center">
        <h3 className="text-lg font-semibold">Enterprise</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Mais de 50 câmeras, equipamento dedicado, IA própria sem limite, SLA 99,9%, marca personalizada.
        </p>
        <Button variant="outline" className="mt-3" disabled>
          Falar com vendas
        </Button>
      </div>
    </div>
  );
}
