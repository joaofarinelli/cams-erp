type LegalPage = "privacy" | "terms" | "subprocessors";

const LEGAL_TITLES: Record<LegalPage, string> = {
  privacy: "Política de Privacidade",
  terms: "Termos de Uso",
  subprocessors: "Sub-processadores",
};

// Condensed legal content (plain text — full docs at docs/legal/)
const LEGAL_CONTENT: Record<LegalPage, string> = {
  privacy: `Política de Privacidade — cams-erp
Versão v1.0 | Vigente desde: 2026-05-12

1. QUEM SOMOS
Controlador: cams-erp (João Farinelli). Encarregado (DPO): dpo@cams-erp.com.br

2. DADOS COLETADOS
• Conta: nome, e-mail, CPF/CNPJ, telefone, IP, user-agent
• Câmeras: URL RTSP (criptografada), localização do estabelecimento
• Vídeo: clipes de 8-30s (motion-triggered), frames para inferência
• Biométricos (opt-in): embeddings faciais, placas via LPR
• Áudio (opt-in): eventos de áudio (sem armazenamento de waveform)
• Pagamento: tokenizado via Stripe (não tocamos dados do cartão)
• Telemetria: heartbeat, erros do agente, feedback de alertas

3. FINALIDADES E BASES LEGAIS
• Execução de contrato (art. 7º V): provisionar serviço e faturamento
• Legítimo interesse (art. 7º IX): segurança do estabelecimento
• Consentimento (art. 7º I): face, áudio, retenção > 30 dias

4. RETENÇÃO
• Clipes: padrão 7 dias (configurável por câmera, máx. 90 dias)
• Dados de conta: enquanto contrato ativo + 5 anos
• Logs de auditoria: 12 meses

5. SEUS DIREITOS (art. 18 LGPD)
Acesse Configurações > Privacidade para exportar ou excluir seus dados.
Resposta em até 15 dias úteis.

6. CONTATO
DPO: dpo@cams-erp.com.br`,

  terms: `Termos de Uso — cams-erp
Versão v1.0 | Vigente desde: 2026-05-12

PLANOS E PREÇOS
• Starter: R$ 197/mês | 2 câmeras | câmera extra R$ 47
• Pro: R$ 497/mês | 5 câmeras | câmera extra R$ 87
• Business: R$ 1.497/mês | 20 câmeras | câmera extra R$ 67
• Enterprise: sob consulta
Trial: 14 dias grátis. Sem fidelidade. Pagamento: cartão, Pix, boleto.

SLA
Melhor esforço 99,5%. Crédito de 1 dia por incidente > 4h confirmado (Business/Enterprise).

RESPONSABILIDADES DO CONTRATANTE
• Obter consentimento dos empregados monitorados
• Afixar aviso de monitoramento visível (download em Privacidade)
• Não usar em vias públicas sem autorização legal
• Não usar para fins de discriminação

LIMITAÇÃO DE RESPONSABILIDADE
Cap: 3× última mensalidade. Sem responsabilidade por danos indiretos.

CANCELAMENTO
Cancele a qualquer momento. Dados excluídos em 30 dias após cancelamento.

Foro: comarca da sede do controlador. Lei brasileira aplicável.`,

  subprocessors: `Sub-processadores — cams-erp
Versão v1.0 | Atualizado: 2026-05-12

Política: notificamos por e-mail com 30 dias de antecedência sobre mudanças.

SUB-PROCESSADORES

AWS S3 (Brasil)
Finalidade: armazenamento de clipes de vídeo
Política: aws.amazon.com/privacy

Fly.io (Brasil/EUA)
Finalidade: hospedagem da API
Política: fly.io/legal/privacy-policy

Cloudflare Pages (Global)
Finalidade: frontend web
Política: cloudflare.com/privacypolicy

Stripe (EUA)
Finalidade: processamento de pagamentos
Política: stripe.com/privacy

Evolution API (auto-hospedado)
Finalidade: gateway WhatsApp
Política: WhatsApp Business API Terms

Expo Push (EUA)
Finalidade: notificações push mobile
Política: expo.dev/privacy

OpenAI (EUA)
Finalidade: inferência VLM (frames de vídeo)
Política: openai.com/policies/privacy-policy

Google Gemini (EUA)
Finalidade: inferência VLM (fallback)
Política: policies.google.com/privacy

OpenALPR Cloud (EUA, opt-in)
Finalidade: leitura de placas veiculares
Política: openalpr.com/privacy.html

Sentry (EUA)
Finalidade: monitoramento de erros
Política: sentry.io/privacy

Objeções: dpo@cams-erp.com.br`,
};

interface LegalModalProps {
  page: LegalPage | null;
  onClose: () => void;
}

export function LegalModal({ page, onClose }: LegalModalProps) {
  if (!page) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-card border border-border rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <h2 className="text-lg font-semibold">{LEGAL_TITLES[page]}</h2>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground text-xl leading-none"
          >
            ✕
          </button>
        </div>
        <div className="overflow-y-auto p-4 flex-1">
          <pre className="text-sm text-foreground whitespace-pre-wrap font-sans leading-relaxed">
            {LEGAL_CONTENT[page]}
          </pre>
        </div>
        <div className="p-3 border-t border-border text-center text-xs text-muted-foreground">
          Versão v1.0 — vigente desde 2026-05-12
        </div>
      </div>
    </div>
  );
}

export type { LegalPage };
