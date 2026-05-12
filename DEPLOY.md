# cams-erp — Deployment & operação

Guia rápido pra instalar o agent no PDV do cliente, operar o painel web,
e plugar features opcionais (Tailscale, code signing, modelos premium).

Stack: Supabase (Postgres) + Cloudflare R2 (clips) + Fly.io (API + worker)
+ Cloudflare Pages (web) + Expo EAS (mobile). JWT self-issued (sem
Supabase Auth).

---

## 1. Pré-requisitos

- DVR Hikvision-compatible OU câmera IP com RTSP/HTTP snapshot
- PC Windows 10/11 dedicado (i3 8th gen ou superior, 8GB RAM)
- Internet estável no PDV
- Conta cams-erp criada em https://cams-erp-web.pages.dev

---

## 2. Quick start — instalar o agent

1. **Cria um PDV** no painel web → Câmeras → "+ Novo" → copia o **pair code**
   de 6 dígitos.
2. **Baixa o release** mais recente:
   https://github.com/joaofarinelli/cams-erp/releases/latest
3. Extrai o zip pra `C:\cams-agent\`.
4. Duplo-clique em `run-agent.bat` → janela Tkinter pede o pair code.
5. Cola o código → "Parear" → tray icon aparece na bandeja.
6. No painel web, o PDV vira **paired**. Adiciona câmeras pelo wizard.

**Autostart**: o agent registra `HKCU\Software\Microsoft\Windows\
CurrentVersion\Run\cams-agent` no primeiro boot (sem admin). Próximas
reinicializações do Windows abrem o tray sozinho.

---

## 3. Aviso "Windows protegeu seu PC" (SmartScreen)

O .exe ainda não tem **code signing certificate** (R$ 800–1800/ano,
deferido para um próximo ciclo). No primeiro launch, o Windows mostra:

> Windows protegeu seu PC. SmartScreen impediu a inicialização…

Clique em **Mais informações → Executar mesmo assim**. Acontece **uma
vez por release**. Após o primeiro launch, autostart roda silencioso.

---

## 4. Auto-update

Agent verifica `https://api.github.com/repos/joaofarinelli/cams-erp/
releases/latest` toda hora. Quando uma tag nova é publicada (ex.
`v1.1.0`), o agent:

1. Baixa o zip pra `cams-agent-v1.1.0/` ao lado do install atual
2. Aponta o `cams-agent-current` (junction) para a nova pasta
3. Relança via `run-agent.bat`
4. Versão antiga fica em disco para rollback manual

Tray menu → "Verificar atualização" força o check fora do agendamento.

---

## 5. Cadastro de câmeras

**Câmera IP (ONVIF)**
- Câmeras → "+ Novo" → "Câmeras IP (ONVIF)"
- Marca várias na lista → "Cadastrar todas"
- Informa user/senha mestre (1x) → agent testa templates por fabricante
- Adiciona todas em lote

**DVR Hikvision (HTTP snapshot ISAPI)**
- Entrada manual → IP do DVR → vendor `hikvision`
- Stream dropdown → escolhe `ISAPI snapshot ch1` (até ch16)
- user/senha do DVR
- Testar → Salvar

**Câmera RTSP genérica**
- Entrada manual → IP + vendor → escolhe template Main/Sub
- Testar → Salvar

---

## 6. Edge YOLO local

Filtra uploads no PC antes de enviar pra cloud. Corta 70–90% de bandwidth
+ VLM cost em cenas vazias. Habilitado **por PDV** no painel web (card
"PDVs / agentes" no topo de Câmeras).

**Quando ligar**: PDV com câmera de área pouco movimentada (estoque,
escritório, portão de entrega) — filtra ruído mecânico/luz/sombra.

**Quando desligar**: multi-PDV onde o PC do agent já roda perto do limite
de CPU; processamento adicional pode travar o PDV.

**Verificar funcionando**: tray → "Open logs" → procurar `[edge]
person in zone -> upload` (passou filtro) ou `[edge] no person in zone
-> skip` (cortado). Cliente típico vê 70-90% skip ratio.

---

## 7. Diagnóstico no tray

- **Status** — mostra API, device_name, contagem de câmeras, Edge YOLO ON/OFF
- **Diagnóstico** — roda self-test contra cada câmera. Notification mostra
  `✓ caixa principal | ✗ entregas (timeout)`. Útil pra confirmar setup.
- **Verificar atualização** — força check de release
- **Open logs** — abre `%LOCALAPPDATA%\cams-agent\agent.log` no editor
- **Run at startup** — toggle autostart HKCU
- **Reset pairing** — apaga `config.json`; próximo launch volta pra GUI
- **Exit** — encerra agent

---

## 8. Tailscale (acesso remoto direto, opcional)

Por padrão, toda comunicação passa pela cloud. Pra clientes que querem
acessar câmera **direto** sem cloud-roundtrip (menor latência, sem custo
de bandwidth):

1. Instale Tailscale no PC do agent
   (https://tailscale.com/download/windows)
2. Inicie e autentique na sua tailnet
3. Agent detecta `tailscaled` automaticamente e reporta IP tailnet no
   heartbeat
4. Painel web (DeviceHealthPanel) mostra `Tailscale 100.x.y.z`
5. Outros membros da tailnet acessam a câmera direto via IP local
   do DVR (ex. `192.168.2.200`)

Tailscale **não substitui** o agent — pipeline de motion + Edge YOLO +
upload pra cloud continua igual. É só uma rota alternativa pra live view.

---

## 9. Troca de PC

Token cifrado no `config.json` é derivado do **BIOS UUID do PC**. Se você
trocar o PC, o token velho fica inutilizável:

1. PC novo → instala zip → roda `run-agent.bat`
2. Painel web → gera novo pair code → cola no GUI
3. PC velho pode ser descartado — token criptografado não funciona em
   outra máquina

---

## 10. Modelos premium (LPR / Face / Audio)

Infra está pronta na codebase mas ONNX/datasets ficam opcional:

- **LPR (placas)**: setar `CAMS_OPENALPR_KEY` no environment do agent
  ativa o backend OpenALPR Cloud (~$0.001/lookup, sem bundle pesado).
  ONNX próprio treinado em placas BR é alternativa futura.
- **Face whitelist**: precisa `insightface>=0.7` instalado no Python do
  agent e modelo `buffalo_l` baixado uma vez (~50MB). Fluxo de
  enrollment já roda — embeddings ficam vazios até insightface estar
  disponível, depois nova foto já é matchable.
- **Audio detect**: precisa `yamnet.onnx` (~17MB) bundlado em
  `agent/dev/`. Sem o arquivo, `AudioWatcher.is_available()` retorna
  False e regras audio são no-op.

---

## 11. Custos do operador (referência rápida)

| Item | Custo aprox |
|------|-------------|
| Fly.io API + Inference | $17/mês |
| Cloudflare R2 storage | $2/mês baseline |
| Evolution WhatsApp VPS | $12/mês |
| LLM Gemini Flash Lite | ~$0.001 por análise VLM |
| LLM Cascade Gemini Pro | ~$0.025 por análise |
| **Total custo fixo** | **~R$ 160/mês** |

Edge YOLO + dedup + zone YOLO + intensity profiles cortam tipicamente
75-90% do custo VLM real vs pipeline cru.

---

## 12. Pricing comercial

| Plano | Base/mês | Câmeras incluídas | Câmera extra |
|-------|----------|-------------------|--------------|
| Starter | R$ 197 | 2 | R$ 47 |
| Pro (recomendado) | R$ 497 | 5 | R$ 87 |
| Business | R$ 1.497 | 20 | R$ 67 |
| Enterprise | sob consulta | — | — |

Quotas, billing Stripe e trial de 14 dias geridos automaticamente após
deploy do bloco F3 (presente em `main`).

---

## 13. Troubleshooting

| Sintoma | Causa provável | Fix |
|---------|----------------|-----|
| Tray não aparece | Agent crashou na 1ª execução | `%LOCALAPPDATA%\cams-agent\agent.log` → procura `Traceback` |
| Câmera "offline" no painel | Heartbeat parou (>90s sem post) | `tasklist | findstr cams-agent` no PC; mate processo duplicado se houver |
| 0 events sendo gerados | Motion threshold alto ou Edge YOLO matando tudo | Tray → Open logs → procura `[edge] ... skip`. Reduza `CAMS_EDGE_YOLO_CONF` |
| 401 ao parear | Pair code expirado (10 min TTL) | Gera novo no painel |
| Live view "desconectado" | Control WS dropou ou device diferente do dono da câmera | Confirme só 1 agent rodando; reset pairing se 2 devices acumularam |
| Alerts em duplicata | Cooldown muito baixo | Edite regra → cooldown_seconds (default 300s) |
| Webhook Stripe não chega | Endpoint não cadastrado | Stripe dashboard → Webhooks → `https://cams-erp-api.fly.dev/webhooks/stripe` |

---

## 14. Links

- Painel web: https://cams-erp-web.pages.dev
- API: https://cams-erp-api.fly.dev
- Releases: https://github.com/joaofarinelli/cams-erp/releases
- Issues: https://github.com/joaofarinelli/cams-erp/issues
