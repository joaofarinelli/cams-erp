# Política de Privacidade — cams-erp

**Versão:** v1.0
**Vigente desde:** 2026-05-12

---

## 1. Quem somos

**Controlador dos dados:**
cams-erp (denominada neste documento "cams-erp", "nós" ou "nossa empresa") é a pessoa jurídica responsável pelo tratamento dos dados pessoais coletados por meio da plataforma de monitoramento inteligente por câmeras.

**Encarregado pelo Tratamento de Dados Pessoais (DPO):**
João Farinelli
E-mail: dpo@cams-erp.com.br
Para exercício de direitos, dúvidas sobre privacidade e incidentes de segurança.

Esta Política de Privacidade descreve como coletamos, utilizamos, armazenamos, compartilhamos e protegemos os dados pessoais de nossos clientes (contratantes), usuários da plataforma e terceiros cujas imagens ou dados são capturados pelos dispositivos de câmera configurados na plataforma cams-erp, em conformidade com a Lei Geral de Proteção de Dados Pessoais (LGPD — Lei nº 13.709/2018).

---

## 2. Dados que coletamos

### 2.1 Dados de conta
Informações fornecidas no momento do cadastro e durante o uso da plataforma:
- Nome completo e endereço de e-mail do titular da conta;
- Dados da empresa (razão social, CNPJ, endereço do estabelecimento);
- Número de telefone (para notificações via WhatsApp);
- Senha (armazenada com hash bcrypt, nunca em texto claro);
- Preferências da plataforma e configurações de notificação.

### 2.2 Configuração de câmeras
- URLs RTSP dos dispositivos de câmera (tratadas como informação confidencial);
- Nome e descrição de cada câmera;
- Parâmetros de detecção de movimento (zonas, sensibilidade, horários);
- Configurações de retenção de vídeo por câmera.

### 2.3 Conteúdo de vídeo
- Clipes de vídeo curtos capturados em eventos de detecção de movimento (formato MP4, armazenados em AWS S3, região sa-east-1);
- Frames extraídos dos clipes para análise por modelos de visão computacional (enviados a sub-processadores de inferência — ver Seção 4);
- Metadados associados (timestamp, câmera de origem, duração, resultado da análise de ameaça).

### 2.4 Dados biométricos (opt-in)
Quando o contratante habilita o reconhecimento facial (recurso opcional):
- Embeddings faciais extraídos de frames de vídeo para identificação de pessoas cadastradas na lista de acesso do estabelecimento;
- **Base legal:** consentimento do titular (art. 7º, I, LGPD) — exigido individualmente para cada pessoa identificada.

### 2.5 Dados de áudio (opt-in)
Quando o contratante habilita a captura de áudio via câmeras com microfone:
- Clipes de áudio associados aos eventos de vídeo;
- **Base legal:** consentimento do titular (art. 7º, I, LGPD).

### 2.6 Dados de pagamento
- Processados exclusivamente pelo Stripe (sub-processador);
- A cams-erp não armazena números de cartão de crédito, CVV ou dados bancários completos;
- Armazenamos apenas o identificador do cliente no Stripe (customer_id), últimos 4 dígitos do cartão e histórico de faturas.

### 2.7 Telemetria e logs
- Endereço IP e user-agent das sessões de acesso à plataforma web e API;
- Logs de auditoria de ações (login, exportação de dados, exclusão de clipes, alterações de configuração);
- Dados de erro e diagnóstico coletados pelo Sentry (sem payloads de vídeo).

---

## 3. Finalidades e bases legais

| Finalidade | Base legal (LGPD) | Detalhes |
|---|---|---|
| Prestação do serviço de monitoramento contratado | Art. 7º, V — execução de contrato | Análise de clipes, armazenamento, notificações de alertas |
| Gestão de conta e autenticação | Art. 7º, V — execução de contrato | Criação e manutenção do acesso à plataforma |
| Cobrança e gestão de assinatura | Art. 7º, V — execução de contrato | Processamento de pagamentos via Stripe |
| Segurança da plataforma e prevenção de fraudes | Art. 7º, IX — legítimo interesse | Logs de acesso, detecção de abusos, integridade do serviço |
| Melhoria dos modelos de detecção | Art. 7º, IX — legítimo interesse | Dados anonimizados e agregados; vídeos identificáveis apenas com consentimento |
| Suporte técnico e atendimento | Art. 7º, V — execução de contrato | Acesso controlado a logs para diagnóstico de problemas |
| Reconhecimento facial | Art. 7º, I — consentimento | Opt-in explícito; exige consentimento individual dos titulares identificados |
| Captura de áudio | Art. 7º, I — consentimento | Opt-in explícito por câmera |
| Retenção de vídeo superior a 30 dias | Art. 7º, I — consentimento | Configurável por câmera; acima de 30 dias exige justificativa e consentimento registrado |
| Comunicações de marketing | Art. 7º, I — consentimento | Opt-in na criação da conta; revogável a qualquer tempo |

---

## 4. Sub-processadores

A cams-erp compartilha dados com os seguintes sub-processadores para prestação do serviço. Mantemos contratos de proteção de dados com cada um deles.

| Sub-processador | País | Finalidade | Política de Privacidade |
|---|---|---|---|
| Amazon Web Services (S3) | Brasil (sa-east-1) | Armazenamento de clipes de vídeo e exports | [aws.amazon.com/privacy](https://aws.amazon.com/privacy/) |
| Fly.io | Brasil (gru) | Hospedagem da API e processamento | [fly.io/legal/privacy-policy](https://fly.io/legal/privacy-policy/) |
| Cloudflare Pages | Global (CDN) | Hospedagem do frontend web | [cloudflare.com/privacypolicy](https://www.cloudflare.com/privacypolicy/) |
| Stripe | Estados Unidos | Processamento de pagamentos e assinaturas | [stripe.com/br/privacy](https://stripe.com/br/privacy) |
| Evolution API (self-hosted) | Brasil | Gateway WhatsApp para notificações | N/A (instância própria) |
| Expo Push | Estados Unidos | Notificações push para app mobile | [expo.dev/privacy](https://expo.dev/privacy) |
| OpenAI | Estados Unidos | Inferência VLM — análise de frames de vídeo | [openai.com/policies/privacy-policy](https://openai.com/policies/privacy-policy) |
| Google (Gemini) | Estados Unidos | Inferência VLM — análise de frames de vídeo | [policies.google.com/privacy](https://policies.google.com/privacy) |
| OpenALPR Cloud | Estados Unidos | Leitura de placas veiculares (opt-in) | [openalpr.com/privacy.html](https://www.openalpr.com/privacy.html) |
| Sentry | Estados Unidos | Monitoramento de erros e diagnóstico | [sentry.io/privacy](https://sentry.io/privacy/) |

A lista completa e atualizada de sub-processadores está disponível em [https://cams-erp-web.pages.dev/legal/sub-processadores](https://cams-erp-web.pages.dev/legal/sub-processadores).

Notificaremos os contratantes com **30 dias de antecedência** antes de adicionar ou substituir qualquer sub-processador.

---

## 5. Transferência internacional de dados

Alguns sub-processadores operam fora do Brasil, o que implica transferência internacional de dados pessoais. A cams-erp adota as seguintes salvaguardas, conforme art. 33 da LGPD:

- **OpenAI e Google (Gemini):** frames de vídeo (sem texto pessoal identificável) são enviados para inferência. Transferência baseada em cláusulas contratuais padrão (Standard Contractual Clauses — SCC) compatíveis com a LGPD. Os dados não são utilizados para treinamento dos modelos conforme contratos de API.
- **Cloudflare:** hospedagem de assets estáticos; dados em trânsito protegidos por TLS 1.3; sem armazenamento persistente de dados pessoais além de logs temporários.
- **Stripe:** processamento de pagamentos sujeito à regulamentação PCI-DSS; transferência coberta por cláusulas contratuais e adequação regulatória.
- **OpenALPR Cloud:** ativado apenas com opt-in explícito do contratante; placas de veículos enviadas sem contexto pessoal adicional; cláusulas contratuais padrão aplicáveis.
- **Expo Push e Sentry:** tokens de dispositivo e dados de erro transferidos; sem dados de vídeo; cláusulas contratuais padrão aplicáveis.

---

## 6. Retenção de dados

| Categoria de dado | Prazo de retenção | Critério |
|---|---|---|
| Clipes de vídeo | 7 dias (padrão) / configurável por câmera | Excluídos automaticamente ao final do período; extensão acima de 30 dias exige consentimento |
| Dados de conta | Enquanto o contrato estiver ativo + 5 anos | Prazo para cumprimento de obrigações legais e fiscais |
| Logs de auditoria | 12 meses | Segurança e conformidade |
| Dados de pagamento | Conforme regulação Stripe e PCI-DSS | Cams-erp retém apenas identificadores; dados completos com Stripe |
| Embeddings faciais | Enquanto o recurso estiver ativo | Excluídos imediatamente ao desabilitar o reconhecimento facial |
| Dados de áudio | Mesmo prazo dos clipes de vídeo associados | Excluídos junto com o clipe |

Após o cancelamento da conta, todos os dados pessoais são excluídos em até **30 dias**, salvo obrigação legal de retenção.

---

## 7. Direitos do titular

Nos termos do art. 18 da LGPD, o titular dos dados tem os seguintes direitos, exercíveis diretamente na plataforma ou via e-mail ao DPO:

| Direito | Como exercer |
|---|---|
| Confirmação de existência e acesso aos dados | `GET /me/export` via API ou botão "Exportar meus dados" no painel |
| Correção de dados incompletos ou incorretos | `PATCH /me` via API ou formulário de perfil no painel |
| Anonimização, bloqueio ou eliminação | `DELETE /me` via painel; grace period de 30 dias (dados ficam inacessíveis e são excluídos definitivamente ao final do prazo) |
| Portabilidade | Export em formato ZIP via `GET /me/export` (JSON estruturado + metadados) |
| Eliminação de dados tratados com consentimento | Toggles de opt-in/opt-out no painel; revogação imediata |
| Informação sobre compartilhamento | Esta política e a página de sub-processadores |
| Revogação do consentimento | Toggles no painel > Configurações > Privacidade |
| Oposição ao tratamento | Solicitação via e-mail ao DPO: dpo@cams-erp.com.br |
| Revisão de decisões automatizadas | Solicitação via DPO; análise humana disponível para qualquer alerta gerado pela IA |

Atendemos as solicitações em até **15 dias úteis**. Poderemos solicitar confirmação de identidade antes de processar a solicitação.

---

## 8. Cookies

A plataforma web cams-erp utiliza os seguintes cookies:

| Cookie | Tipo | Finalidade | Duração |
|---|---|---|---|
| `session_token` | Essencial | Autenticação e manutenção da sessão | Sessão / 30 dias (se "lembrar-me") |
| `theme_preference` | Preferência | Armazenar preferência de tema claro/escuro | 1 ano |
| `sentry_session` | Analytics | Diagnóstico de erros de interface | Sessão |

Cookies essenciais não requerem consentimento. Cookies opcionais (analytics) são ativados somente após aceitação no banner de cookies exibido no primeiro acesso.

O contratante pode gerenciar cookies nas configurações do navegador. A desativação de cookies essenciais impede o funcionamento da plataforma.

---

## 9. Contato do Encarregado (DPO)

Para exercício de direitos, dúvidas, reclamações ou notificação de incidentes relacionados à privacidade:

**Encarregado:** João Farinelli
**E-mail:** dpo@cams-erp.com.br
**Prazo de resposta:** até 15 dias úteis após o recebimento da solicitação

Em casos de incidentes de segurança graves, notificaremos proativamente os titulares afetados e a Autoridade Nacional de Proteção de Dados (ANPD) conforme exigido pelo art. 48 da LGPD.

---

## 10. Alterações a esta política

A cams-erp pode atualizar esta Política de Privacidade periodicamente. Quando alterações relevantes forem realizadas:

- Publicaremos a nova versão com data de vigência atualizada;
- Notificaremos os contratantes por e-mail com **30 dias de antecedência**;
- Exigiremos novo aceite explícito no próximo login após a entrada em vigor da nova versão.

O histórico de versões anteriores será mantido disponível mediante solicitação ao DPO.

---

## 11. Foro e lei aplicável

Esta Política de Privacidade é regida pela legislação brasileira, em especial pela Lei nº 13.709/2018 (LGPD) e pelo Código de Defesa do Consumidor (Lei nº 8.078/1990).

Fica eleito o foro da comarca da sede do controlador para dirimir eventuais litígios decorrentes desta política, com renúncia a qualquer outro, por mais privilegiado que seja.

---

*Última atualização: 2026-05-12 — v1.0 inicial*
