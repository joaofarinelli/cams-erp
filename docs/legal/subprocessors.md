# Sub-processadores — cams-erp

**Versão:** v1.0
**Atualizado:** 2026-05-12

---

## Política de Sub-processadores

A cams-erp utiliza sub-processadores para prestação dos serviços de monitoramento inteligente por câmeras. Um sub-processador é qualquer terceiro que trata dados pessoais em nome da cams-erp, sob suas instruções, no contexto da prestação do serviço aos contratantes.

**Política de notificação:** Notificaremos os contratantes com **30 (trinta) dias de antecedência** antes de adicionar, substituir ou remover qualquer sub-processador que trate dados pessoais. A notificação será enviada por e-mail ao endereço cadastrado na conta. O contratante pode opor-se à mudança dentro do prazo de 30 dias, conforme previsto no Acordo de Tratamento de Dados (DPA).

Para dúvidas ou objeções relacionadas a sub-processadores, entre em contato com: **dpo@cams-erp.com.br**

---

## Lista de Sub-processadores Ativos

| Sub-processador | País | Finalidade | Política de Privacidade |
|---|---|---|---|
| **Amazon Web Services (AWS S3)** | Brasil (região sa-east-1) | Armazenamento de clipes de vídeo, exportações de dados e backups. Dados criptografados em repouso com AES-256 via AWS KMS. | [aws.amazon.com/privacy](https://aws.amazon.com/privacy/) |
| **Fly.io** | Brasil (região gru — São Paulo) | Hospedagem e execução da API cams-erp (backend FastAPI). Processa requisições da plataforma, análise de eventos e lógica de negócio. | [fly.io/legal/privacy-policy](https://fly.io/legal/privacy-policy/) |
| **Cloudflare Pages** | Global (CDN distribuído) | Hospedagem e entrega do frontend web (React). Processa requisições HTTP de usuários; não armazena dados pessoais de forma persistente além de logs temporários. | [cloudflare.com/privacypolicy](https://www.cloudflare.com/privacypolicy/) |
| **Stripe** | Estados Unidos | Processamento de pagamentos, gestão de assinaturas e faturamento. Armazena dados de cartão de crédito de forma tokenizada, em conformidade com PCI-DSS nível 1. | [stripe.com/br/privacy](https://stripe.com/br/privacy) |
| **Evolution API (self-hosted)** | Brasil (instância própria da cams-erp) | Gateway WhatsApp para envio de notificações de alertas aos contratantes. Instância auto-hospedada pela cams-erp; dados não compartilhados com terceiros adicionais. | N/A — instância proprietária |
| **Expo Push** | Estados Unidos | Envio de notificações push para usuários do aplicativo mobile cams-erp (iOS e Android). Recebe tokens de dispositivo e payload de notificação (sem dados de vídeo). | [expo.dev/privacy](https://expo.dev/privacy) |
| **OpenAI** | Estados Unidos | Inferência de modelos de linguagem visual (VLM) para análise de frames de vídeo e detecção de ameaças. Frames de vídeo são enviados para análise; conforme contrato de API, os dados não são usados para treinamento de modelos. | [openai.com/policies/privacy-policy](https://openai.com/policies/privacy-policy) |
| **Google (Gemini)** | Estados Unidos | Inferência alternativa de VLM para análise de frames de vídeo. Utilizado em rodízio com OpenAI para resiliência. Dados não utilizados para treinamento conforme contrato de API. | [policies.google.com/privacy](https://policies.google.com/privacy) |
| **OpenALPR Cloud** | Estados Unidos | Leitura automatizada de placas veiculares (LPR — License Plate Recognition). Ativado **apenas** quando o contratante habilita explicitamente o recurso. Frames da área de captura de placa são enviados para reconhecimento. | [openalpr.com/privacy.html](https://www.openalpr.com/privacy.html) |
| **Sentry** | Estados Unidos | Monitoramento de erros, rastreamento de exceções e diagnóstico de performance da API e do frontend. Payloads de vídeo nunca são enviados ao Sentry; dados limitados a stack traces, logs de contexto e identificadores de sessão. | [sentry.io/privacy](https://sentry.io/privacy/) |

---

## Transferências Internacionais

Os sub-processadores marcados com "Estados Unidos" ou "Global" implicam transferência internacional de dados pessoais. A cams-erp adota cláusulas contratuais padrão (Standard Contractual Clauses — SCC) compatíveis com o art. 33 da LGPD para todas as transferências internacionais. Cópias dos contratos relevantes estão disponíveis mediante solicitação ao DPO.

---

## Histórico de Alterações

| Data | Versão | Descrição da Alteração |
|---|---|---|
| 2026-05-12 | v1.0 | Versão inicial — lista de 10 sub-processadores ativos |

---

## Contato

Para dúvidas, objeções ou solicitações relacionadas a sub-processadores:

**DPO cams-erp:** dpo@cams-erp.com.br
**Prazo de resposta:** até 15 dias úteis

---

*Próxima revisão programada: 2026-11-12*
