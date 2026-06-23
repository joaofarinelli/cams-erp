# cams-erp — LGPD Compliance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reach LGPD (Lei Geral de Proteção de Dados, Lei 13.709/2018) compliance before onboarding the first paying customer. Surveillance video of employees + cloud storage of clips makes cams-erp a "controlador" for the owner's account-level PII and a "operador" for the employees' images. ANPD fines reach R$50M or 2% of revenue.

**Scope:** Legal artifacts (privacy policy, ToS, DPA, employee consent), product changes (consent UI, retention enforcement, audit log, data export/erasure hardening, sub-processor disclosure, breach process), and ops (ANPD registration, DPO appointment, incident runbook).

**Reference law:** LGPD art. 7º (bases legais), art. 9º (transparência), art. 15º (término do tratamento), art. 18º (direitos do titular), art. 48º (comunicação de incidente em prazo razoável — ANPD entende ~72h).

**Current state (commit aca10a4):**
- `api/app/routers/privacy.py` already exposes `GET /me/export` (JSON dump) and `DELETE /me` (cascade).
- Clip retention env var `CAMS_RETENTION_DAYS_CLIPS` referenced but no scheduler enforces it.
- No employee consent, audit log, breach process, or public legal pages.
- `web/` and `mobile/` have zero LGPD UX.
- `agent/` 24h ring buffer stores clips locally — also in LGPD scope.

**Conventions:**
- Conventional Commits (`feat(privacy):`, `feat(legal):`, `chore(lgpd):`).
- Branch: `feat/lgpd-compliance` → squash-merge to `main`.
- Legal copy: Portuguese (BR). Code/commits/comments: English.
- Sub-processor changes require updating `docs/legal/subprocessors.md` + bumping `privacy_policy_version` in DB.

**Out of scope (deferred):**
- ISO 27001 / SOC 2 (post-Series A).
- Full DPIA template (do on-demand per Enterprise customer).
- Employee biometric consent for face-rec — face feature already gated; gate it harder until separate biometric consent UI ships (Task 7).

---

# PHASE A — Legal Artifacts

## Task A.1: Draft Privacy Policy (Política de Privacidade)

**Files:**
- Create: `docs/legal/privacy-policy.md` (canonical source, Portuguese)
- Create: `docs/legal/privacy-policy.en.md` (English copy for international ops)

- [ ] **Step 1: List data categories collected**
  - User account: nome, email, telefone, CNPJ/CPF, endereço de cobrança, IP de acesso, user-agent.
  - Câmera config: RTSP URL (KMS-encrypted), localização do estabelecimento, nome da câmera.
  - Conteúdo de vídeo: clipes de 8-30s motion-triggered, frames extraídos para inferência, miniaturas.
  - Biométricos (opt-in): embeddings faciais (insightface), placas via LPR.
  - Áudio (opt-in): YAMNet event labels — NÃO armazena waveform.
  - Pagamento: tokenizado via Stripe (cams-erp não toca PAN).
  - Telemetria: agent_errors, heartbeat, alert feedback.

- [ ] **Step 2: List finalidades + bases legais**
  - Execução de contrato (art. 7º V): provisionar serviço, faturamento.
  - Legítimo interesse (art. 7º IX): detecção de fraude, segurança operacional do estabelecimento.
  - Consentimento (art. 7º I): face-rec, áudio, retenção > 30 dias.

- [ ] **Step 3: List sub-processadores (CRITICAL)**
  - AWS S3 (sa-east-1) — armazenamento de clipes
  - Fly.io (gru) — hosting API
  - Cloudflare Pages (global) — frontend
  - Stripe — pagamento
  - Evolution API self-hosted — WhatsApp gateway
  - Expo Push — notificações mobile
  - OpenAI / Google Gemini — VLM cascade (frames enviados; sem PII textual)
  - OpenALPR Cloud — leitura de placas (opt-in)
  - Sentry — error monitoring (sem payloads de vídeo)

- [ ] **Step 4: Direitos do titular (art. 18º)**
  - Confirmação + acesso → `GET /me/export`
  - Correção → `PATCH /me`
  - Anonimização / eliminação → `DELETE /me` (com grace period)
  - Portabilidade → mesmo export em JSON estruturado
  - Revogação de consentimento → toggles em `/me/settings`

- [ ] **Step 5: Contato do encarregado (DPO)**
  - Email dedicado: `dpo@cams-erp.com.br`
  - Endereço físico do controlador
  - Prazo de resposta: 15 dias úteis (art. 19º §2º)

- [ ] **Step 6: Versionamento**
  - Header `Vigente desde: YYYY-MM-DD` + `Versão: vX.Y`.
  - Histórico de mudanças no rodapé.

**Verification:**
- [ ] Reviewer jurídico assina (placeholder: usar Tarcísio/Doc9 ou advogado próprio).
- [ ] Documento renderiza em `https://cams-erp-web.pages.dev/legal/privacidade`.

## Task A.2: Draft Terms of Service (Termos de Uso)

**Files:**
- Create: `docs/legal/terms.md`

- [ ] **Step 1: Cláusulas obrigatórias**
  - Objeto, preços (linkar tabela Starter/Pro/Business), trial 14 dias.
  - SLA: best-effort 99.5%, sem indenização monetária no Starter.
  - Vedações: uso em vias públicas sem autorização, biometria sem consentimento.
  - Responsabilidade do contratante: obter consentimento dos empregados, afixar aviso "ambiente monitorado".
  - Limitação de responsabilidade: cap mensalidade × 3.
  - Foro: comarca da sede do controlador.

## Task A.3: Draft DPA (Acordo de Tratamento de Dados)

**Files:**
- Create: `docs/legal/dpa-template.md`

- [ ] **Step 1: DPA enxuto p/ Enterprise**
  - Identifica controlador (cliente) e operador (cams-erp).
  - Lista categorias e finalidades.
  - Sub-processadores (referência à página pública).
  - Medidas técnicas: KMS, TLS 1.2+, RBAC, audit log, retenção configurável.
  - Notificação de incidente: até 48h após ciência.
  - Auditoria: 1×/ano via questionário; on-site mediante NDA.

## Task A.4: Aviso de Monitoramento (cartaz cliente)

**Files:**
- Create: `docs/legal/aviso-monitoramento.pdf` (template imprimível A4)

- [ ] **Step 1: Texto obrigatório**
  - "AMBIENTE MONITORADO POR CÂMERAS COM ANÁLISE AUTOMATIZADA — Lei 13.709/2018. Controlador: [nome cliente]. Encarregado: [contato]. Imagens armazenadas por até XX dias para fins de segurança e gestão. Direitos do titular: [link]."
  - Download disponível no painel web em `/legal/aviso`.

---

# PHASE B — Data Subject Rights (Hardening)

## Task B.1: Soft-delete com grace period

Hoje `DELETE /me` é cascade-hard. LGPD permite, mas usuários reclamam de exclusão acidental + Stripe webhook chega depois e falha. Adicionar 30-day soft-delete.

**Files:**
- Create: `api/alembic/versions/e2f4g6h8i0j2_user_soft_delete.py`
- Modify: `api/app/db/models.py` — `User.deleted_at: datetime | None`, `User.deletion_reason: str | None`
- Modify: `api/app/routers/privacy.py` — `DELETE /me` marks `deleted_at`, schedules purge
- Create: `api/app/services/account_purge.py` — daily cron deletes users where `deleted_at < now() - 30d`
- Modify: `api/app/security/cognito.py` — block requests when `user.deleted_at is not None`

- [ ] **Step 1: Migration**
  ```python
  op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
  op.add_column("users", sa.Column("deletion_reason", sa.String(500), nullable=True))
  op.create_index("ix_users_deleted_at", "users", ["deleted_at"])
  ```

- [ ] **Step 2: Endpoint behavior**
  - `DELETE /me` → 202 Accepted, `{"deleted_at": "...", "purge_at": "...+30d"}`.
  - `POST /me/restore` (autenticado, dentro da janela) → desfaz.
  - Login via Cognito bloqueado quando `deleted_at` set (raise 410 Gone com link de restore).

- [ ] **Step 3: Cron job**
  - Adicionar a `api/app/services/account_purge.py::run()` ao scheduler ao lado de `trial_expiry`.
  - Purge: deletar `User` (cascade já cuida do resto) + emitir Stripe `subscription.cancel`.

- [ ] **Step 4: Tests**
  - `tests/test_privacy_soft_delete.py`: delete → restore → login → ok.
  - delete → wait (mock now+31d) → run purge → user gone, stripe cancel called.

## Task B.2: Export rate limit + assinatura

`GET /me/export` hoje sem rate-limit. Abusável p/ esgotar DB. Também devolve JSON cru — LGPD pede formato estruturado mas idealmente assinado.

**Files:**
- Modify: `api/app/routers/privacy.py`
- Create: `api/app/services/data_export.py`

- [ ] **Step 1: Rate-limit 1× por hora por user**
  - Tabela `data_export_requests(user_id, requested_at, status, url, expires_at)`.
  - Migration.
  - 429 quando `requested_at > now() - 1h`.

- [ ] **Step 2: Background job gera ZIP**
  - JSON estruturado + manifest.json com hash sha256.
  - Upload p/ S3 com presigned URL 24h.
  - Email com link.

- [ ] **Step 3: Tests**
  - 2 calls em sequência → 2º retorna 429.
  - ZIP gerado contém manifest.json + hash bate.

## Task B.3: Audit log de acesso a clipes

Hoje qualquer query a `GET /clips/{id}` é silenciosa. Para defesa em caso de denúncia ANPD (e auditoria Enterprise), gravar quem viu qual clipe quando.

**Files:**
- Create: `api/alembic/versions/k3l5m7n9o1p3_audit_log.py`
- Create: `api/app/db/models.py` — `AuditLog` (id, user_id, action, target_type, target_id, ip, user_agent, created_at)
- Create: `api/app/services/audit.py` — `record(db, user, action, target)`
- Modify: `api/app/routers/clips.py`, `alerts.py`, `cameras.py` — chamar `audit.record` em GET/DELETE
- Modify: `api/app/routers/privacy.py` — inclui audit log no export

- [ ] **Step 1: Modelo + migration** — particionar mensal (`PARTITION BY RANGE (created_at)`); retenção 12 meses via cron.

- [ ] **Step 2: Middleware FastAPI** captura IP + UA, anexa a `request.state.audit_ctx`.

- [ ] **Step 3: Tests** — `GET /alerts/{id}` deixa 1 linha; `GET /clips/{id}` idem.

---

# PHASE C — Consent Management

## Task C.1: Termos no signup + versionamento

**Files:**
- Create: `api/alembic/versions/q5r7s9t1u3v5_consent_log.py`
- Modify: `api/app/db/models.py` — `ConsentLog(id, user_id, policy_version, terms_version, ip, ua, accepted_at)`
- Modify: `api/app/routers/auth.py` — signup recusa sem `terms_accepted=true` + `policy_version` válido.
- Modify: `web/src/pages/Signup.tsx` — checkbox obrigatório linkando `/legal/privacidade` e `/legal/termos`.

- [ ] **Step 1: Tabela `policy_versions(version, doc_type, effective_at, body_md, sha256)`** — admin atualiza, força re-aceite.

- [ ] **Step 2: Endpoint `POST /me/accept-terms`** quando aparecer banner de nova versão.

- [ ] **Step 3: Tests** — signup sem aceite → 400; aceite grava ConsentLog com IP.

## Task C.2: Consentimento por câmera (employee acknowledgment)

LGPD não exige consentimento de cada empregado para câmera de segurança (legítimo interesse), MAS exige transparência. O cliente atesta no painel que afixou o cartaz e notificou empregados.

**Files:**
- Modify: `api/app/db/models.py` — `Camera.consent_attested_at`, `Camera.consent_attested_by_user_id`
- Modify: `api/app/routers/cameras.py` — bloqueia ativação sem atestado
- Modify: `web/src/pages/CameraSetup.tsx` — checkbox "Confirmo afixação do aviso de monitoramento conforme LGPD" + link p/ baixar PDF.

- [ ] **Step 1: Migration** adiciona colunas + backfill `consent_attested_at = created_at` para câmeras existentes (legado).
- [ ] **Step 2: API gate** — POST/PATCH camera com `enabled=true` exige `consent_attested=true`.
- [ ] **Step 3: Mobile screen** mostra status de atestado por câmera.

## Task C.3: Toggle de biometria + áudio + retenção

Face-rec e áudio só com opt-in explícito por câmera.

**Files:**
- Modify: `api/app/db/models.py` — `Camera.face_recognition_enabled` (default False), `Camera.audio_enabled` (default False), `Camera.retention_days` (default 7, max varia por tier)
- Modify: `api/app/routers/cameras.py` — PATCH só aceita com ConsentLog `feature='face'` válido.
- Modify: `web/src/pages/CameraSettings.tsx` — toggle exibe modal de consentimento; gravar ConsentLog ao confirmar.

- [ ] **Step 1: Schema + migration**
- [ ] **Step 2: Inference gate** — `inference/pipeline.py` lê flag; pula face stage quando false.
- [ ] **Step 3: Agent gate** — `agent/face.py` e `agent/audio.py` checam config recebido em `/agent/config`.
- [ ] **Step 4: Tests** — toggle on sem ConsentLog → 403; toggle on com consent → inference roda.

---

# PHASE D — Retention Enforcement

## Task D.1: Cron de purga de clipes S3

`CAMS_RETENTION_DAYS_CLIPS` existe na config mas nada apaga. Risco LGPD: reter "por padrão para sempre".

**Files:**
- Create: `api/app/services/clip_retention.py`
- Modify: `api/app/main.py` — agendar diário 03:00 BRT

- [ ] **Step 1: Query** clips com `created_at < now() - camera.retention_days`.
- [ ] **Step 2: Delete S3** em batch (`delete_objects` 1000-key chunks).
- [ ] **Step 3: Audit log** action=`retention_purge`, target=clip_id.
- [ ] **Step 4: Soft-fail** se S3 retorna erro — marca `clips.purge_failed_at`, alerta Sentry.
- [ ] **Step 5: Tests** com moto.

## Task D.2: Ring-buffer enforcement no agent

24h ring buffer já gira por tempo. Adicionar:
- Comando remoto "purge_now" via control WS p/ DELETE /me trigger.
- Verificar que clip files são `chmod 600` e dir `chmod 700`.

**Files:**
- Modify: `agent/dev/ring_buffer.py`
- Modify: `agent/dev/control_ws.py`
- Modify: `api/app/routers/agent.py` — `POST /agent/{device_id}/purge` (admin/owner only)

- [ ] **Step 1: Comando WS** `{"action": "purge_clips"}` → agent rm -rf ring dir.
- [ ] **Step 2: API trigger** — quando `DELETE /me` purge roda, manda comando p/ todos devices do owner.
- [ ] **Step 3: Tests** — agent test suite simula control msg, valida dir vazio.

## Task D.3: Inferência não persiste frames

Verificar que `inference/` nunca grava frame em disco fora do scope do alerta. Frames mandados a OpenAI/Gemini: documentar em privacy-policy que sub-processador recebe imagem; reter <30s sem cache.

**Files:**
- Modify: `inference/db_worker.py` — auditar; comentar paths de frame
- Create: `docs/privacy/data-flow.md` — diagrama de quem toca pixel quando

- [ ] **Step 1: Code audit** — grep `cv2.imwrite`, `PIL.save`, ensure só temp + unlink.
- [ ] **Step 2: Doc data-flow** com sequência: agent → S3 → inference fetch → VLM POST → discard.

---

# PHASE E — Breach Process

## Task E.1: Detection + comunicação

**Files:**
- Create: `docs/runbooks/lgpd-breach-response.md`
- Create: `api/app/services/incident.py`
- Modify: Sentry alert rules (config in `infra/sentry/`)

- [ ] **Step 1: Runbook** — quem decide é incidente; classificação (acesso indevido, vazamento, indisponibilidade); template comunicação titular + ANPD.
- [ ] **Step 2: Endpoint admin `POST /admin/incident`** registra; dispara emails p/ titulares afetados.
- [ ] **Step 3: Métricas** — Sentry: anomalia de 4xx em `/clips`, multiple-IP login em 1 user em <5min.

## Task E.2: ANPD registration

- [ ] **Step 1: Registrar controlador** em [anpd.gov.br](https://www.gov.br/anpd) — formulário simples, gratuito.
- [ ] **Step 2: Nomear DPO** (pessoa física + email + endereço). Pode ser o próprio fundador no início.
- [ ] **Step 3: Documento de RIPD (Relatório de Impacto)** para o caso de uso "monitoramento de empregados em PME" — template em docs/legal/ripd-template.md.

---

# PHASE F — Web + Mobile UX

## Task F.1: Cookie banner + preferences

**Files:**
- Create: `web/src/components/CookieBanner.tsx`
- Modify: `web/src/main.tsx`

- [ ] **Step 1: Cookies usados** — sessão (essencial), tema (preferência), Sentry (analytics). Banner pergunta opcionais.
- [ ] **Step 2: Persiste escolha** em `localStorage.cookie_consent_v1`.
- [ ] **Step 3: Re-prompt** quando policy_version bumpa.

## Task F.2: Páginas legais + footer

**Files:**
- Create: `web/src/pages/legal/Privacy.tsx`
- Create: `web/src/pages/legal/Terms.tsx`
- Create: `web/src/pages/legal/Subprocessors.tsx`
- Modify: `web/src/components/Footer.tsx` — links

- [ ] **Step 1: Renderiza markdown** de `docs/legal/*.md` via `react-markdown`.
- [ ] **Step 2: Versão visível** no rodapé da página.

## Task F.3: Mobile — privacy screen + delete account

**Files:**
- Create: `mobile/app/privacy.tsx`
- Modify: `mobile/app/settings.tsx` — adiciona "Privacidade & Dados"

- [ ] **Step 1: Tela mostra** consents ativos, link export, botão "excluir conta" (com confirmação dupla).
- [ ] **Step 2: Deep link** p/ web view de privacy-policy (não duplicar markdown no bundle).

## Task F.4: Re-aceite de termos quando versão sobe

**Files:**
- Modify: `web/src/lib/api.ts` — interceptor 412 Precondition Failed
- Modify: `mobile/src/api.ts` — idem
- Modify: `api/app/main.py` — middleware compara `user.policy_version` × atual; 412 + body `{required_version}`

- [ ] **Step 1: Banner modal** força aceite antes de qualquer ação.

---

# PHASE G — Ops + Verification

## Task G.1: Sub-processor changelog

**Files:**
- Create: `docs/legal/subprocessors.md` + `CHANGELOG`

- [ ] **Step 1: Política** — toda mudança em sub-processador notifica titulares por email 30 dias antes (LGPD não obriga prazo, mas é boa prática).

## Task G.2: End-to-end LGPD test suite

**Files:**
- Create: `api/tests/test_lgpd_e2e.py`

- [ ] **Step 1: Cenário 1** — signup sem aceite → 400.
- [ ] **Step 2: Cenário 2** — toggle face-rec sem consent → 403.
- [ ] **Step 3: Cenário 3** — DELETE /me → soft-delete → access blocked → after 30d purge → user gone + clips deletados.
- [ ] **Step 4: Cenário 4** — GET /me/export retorna JSON com user, devices, cameras, alerts, audit_log, consent_log.
- [ ] **Step 5: Cenário 5** — clip > retention_days → cron apaga + audit log.

## Task G.3: Legal review

- [ ] **Step 1:** Advogado especializado em LGPD revisa privacy-policy, terms, DPA, RIPD. Iterar até aprovação.
- [ ] **Step 2:** Validar com 1 cliente piloto antes de cobrar.

## Task G.4: Release

- [ ] **Step 1:** Bump versão `v1.1.0`, tag git, deploy.
- [ ] **Step 2:** Email blast: "Atualizamos nossa política de privacidade. Vigência YYYY-MM-DD."
- [ ] **Step 3:** Update memory `deferred_decisions.md` removendo bullet LGPD; adicionar `lgpd_compliance.md` memory.

---

# Definition of Done

- [ ] Páginas `/legal/privacidade`, `/legal/termos`, `/legal/sub-processadores` no ar.
- [ ] Signup exige aceite + grava ConsentLog.
- [ ] `DELETE /me` soft-delete + cron purga 30d + apaga clipes S3 + comanda agent purge.
- [ ] `GET /me/export` rate-limited, gera ZIP assinado.
- [ ] Audit log preenchido em GET/DELETE de clipes/alertas; visível em export.
- [ ] Retention cron rodando diariamente; clipes além de `camera.retention_days` apagados.
- [ ] Face-rec + áudio gated por ConsentLog; toggle UI funcional.
- [ ] Cookie banner web + cookie preferences.
- [ ] Mobile privacy screen + delete account.
- [ ] Runbook de breach + endpoint admin de incidente.
- [ ] DPO nomeado, registrado ANPD, email `dpo@cams-erp.com.br` recebendo.
- [ ] Suite e2e LGPD passa em CI.
- [ ] Advogado assinou peças legais.
- [ ] Memory `deferred_decisions.md` atualizada.
