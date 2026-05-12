# Acordo de Tratamento de Dados — cams-erp × [NOME DO CONTROLADOR]

**Versão:** v1.0
**Data:** [DATA DE ASSINATURA]

Este Acordo de Tratamento de Dados ("DPA" ou "Acordo") é celebrado entre:

**OPERADOR:**
cams-erp, pessoa jurídica de direito privado, com sede em [ENDEREÇO DA SEDE], inscrita no CNPJ sob o nº [CNPJ], representada por seu sócio-administrador João Farinelli ("Operador" ou "cams-erp");

e

**CONTROLADOR:**
[RAZÃO SOCIAL DO CONTROLADOR], pessoa jurídica de direito privado, com sede em [ENDEREÇO], inscrita no CNPJ sob o nº [CNPJ DO CONTROLADOR], representada por [NOME DO REPRESENTANTE LEGAL], [CARGO] ("Controlador");

doravante individualmente denominadas "Parte" e, em conjunto, "Partes".

Este DPA é incorporado por referência ao Contrato de Prestação de Serviços firmado entre as Partes ("Contrato Principal") e prevalece sobre disposições conflitantes do Contrato Principal no que se refere ao tratamento de dados pessoais.

---

## Cláusula 1 — Definições

Para os fins deste Acordo, adotam-se as seguintes definições, conforme a Lei Geral de Proteção de Dados Pessoais (LGPD — Lei nº 13.709/2018):

**1.1 "Controlador":** pessoa natural ou jurídica, de direito público ou privado, a quem competem as decisões referentes ao tratamento de dados pessoais — no presente Acordo, a parte identificada no preâmbulo como Controlador.

**1.2 "Operador":** pessoa natural ou jurídica, de direito público ou privado, que realiza o tratamento de dados pessoais em nome do controlador — no presente Acordo, a cams-erp.

**1.3 "Dado pessoal":** informação relacionada a pessoa natural identificada ou identificável, incluindo dados de identificação, imagens, voz, dados biométricos e dados comportamentais.

**1.4 "Dado pessoal sensível":** dado pessoal sobre origem racial ou étnica, convicção religiosa, opinião política, filiação a sindicato ou a organização de caráter religioso, filosófico ou político, dado referente à saúde ou à vida sexual, dado genético ou biométrico, quando vinculado a uma pessoa natural.

**1.5 "Tratamento":** toda operação realizada com dados pessoais, como coleta, produção, recepção, classificação, utilização, acesso, reprodução, transmissão, distribuição, processamento, arquivamento, armazenamento, eliminação, avaliação ou controle da informação, modificação, comunicação, transferência, difusão ou extração.

**1.6 "Incidente de segurança":** acesso não autorizado ou situação acidental ou ilícita de destruição, perda, alteração, comunicação ou qualquer forma de tratamento inadequado ou ilícito de dados pessoais.

**1.7 "Titular":** pessoa natural a quem se referem os dados pessoais objeto de tratamento — no contexto da plataforma cams-erp, incluindo empregados, clientes e visitantes do estabelecimento do Controlador captados pelas câmeras.

**1.8 "Sub-operador":** pessoa natural ou jurídica, de direito público ou privado, que realiza o tratamento de dados pessoais em nome do Operador, mediante instruções deste.

**1.9 "LGPD":** Lei nº 13.709, de 14 de agosto de 2018, Lei Geral de Proteção de Dados Pessoais, e suas regulamentações posteriores emitidas pela Autoridade Nacional de Proteção de Dados (ANPD).

**1.10 "ANPD":** Autoridade Nacional de Proteção de Dados, órgão da administração pública federal competente para zelar pela proteção de dados pessoais.

---

## Cláusula 2 — Objeto e Finalidade

**2.1** O Operador tratará dados pessoais **exclusivamente** para as finalidades necessárias à prestação dos serviços de monitoramento inteligente por câmeras contratados pelo Controlador, conforme descritos no Contrato Principal, a saber:

- Captura, armazenamento e análise de clipes de vídeo gerados por eventos de detecção de movimento;
- Análise automatizada de ameaças por modelos de visão computacional;
- Envio de notificações de alertas ao Controlador e aos usuários por ele autorizados;
- Reconhecimento de placas veiculares (LPR), quando habilitado pelo Controlador;
- Reconhecimento facial, quando habilitado pelo Controlador com as bases legais adequadas.

**2.2** O Operador não tratará os dados pessoais para qualquer finalidade própria, comercial ou de terceiros, que não esteja expressamente prevista neste Acordo ou autorizada por escrito pelo Controlador.

**2.3** O Operador seguirá as instruções documentadas do Controlador no que diz respeito ao tratamento dos dados pessoais, salvo quando obrigado a agir de outra forma por exigência legal, hipótese em que notificará previamente o Controlador, salvo se a lei proibir tal notificação.

---

## Cláusula 3 — Categorias de Dados e Titulares

**3.1 Categorias de dados pessoais tratados:**

| Categoria | Descrição | Sensível (LGPD art. 11)? |
|---|---|---|
| Imagens de vídeo | Clipes MP4 capturados em eventos de movimento, contendo imagens de empregados, clientes e visitantes do estabelecimento | Não (salvo se revelar dado sensível contextual) |
| Metadados de eventos | Timestamp, câmera de origem, resultado da análise de ameaça, duração do clipe | Não |
| Embeddings faciais | Representações vetoriais extraídas de faces identificadas (opt-in) | **Sim** — dado biométrico |
| Placas veiculares | Leituras de placas de veículos que acessam o estabelecimento (opt-in) | Não |
| Dados de conta do Controlador | Nome, e-mail, telefone, dados da empresa, preferências de configuração | Não |

**3.2 Categorias de titulares:**
- Empregados e colaboradores do Controlador;
- Clientes e visitantes do estabelecimento do Controlador;
- Prestadores de serviço e terceiros que circulem no estabelecimento;
- Usuários da conta do Controlador na plataforma cams-erp.

**3.3** O Controlador declara e garante que possui base legal adequada para cada categoria de dado pessoal listada, incluindo o consentimento individual dos titulares de dados biométricos, e que cumpre com as obrigações de informação e transparência previstas na LGPD.

---

## Cláusula 4 — Sub-operadores

**4.1** O Controlador autoriza o Operador a contratar os sub-operadores listados na página pública de sub-processadores, disponível em [https://cams-erp-web.pages.dev/legal/sub-processadores](https://cams-erp-web.pages.dev/legal/sub-processadores), para fins de prestação do serviço contratado.

**4.2** A lista atual de sub-operadores inclui, entre outros: Amazon Web Services (S3), Fly.io, Cloudflare, Stripe, OpenAI, Google (Gemini), OpenALPR Cloud, Expo Push e Sentry. A lista completa e atualizada está disponível na página mencionada.

**4.3** O Operador notificará o Controlador com **30 (trinta) dias de antecedência** sobre qualquer alteração (adição ou substituição) nos sub-operadores que tratem dados pessoais do Controlador.

**4.4** O Controlador pode, dentro do prazo de 30 dias após a notificação, opor-se por escrito à contratação de novo sub-operador, hipótese em que as Partes negociarão de boa-fé uma solução alternativa. Não havendo acordo, o Controlador poderá resilir o Contrato Principal sem ônus.

**4.5** O Operador é responsável perante o Controlador pelos atos e omissões dos sub-operadores em relação ao tratamento dos dados pessoais cobertos por este Acordo, na mesma medida em que seria responsável se tivesse realizado o tratamento diretamente.

---

## Cláusula 5 — Medidas Técnicas e Organizacionais de Segurança

**5.1** O Operador implementa e mantém as seguintes medidas técnicas e organizacionais para proteção dos dados pessoais tratados:

**Técnicas:**
- **Criptografia em repouso (at rest):** dados armazenados no AWS S3 criptografados com AES-256 via AWS KMS (Key Management Service), com chaves gerenciadas pelo Operador;
- **Criptografia em trânsito (in transit):** todas as comunicações entre componentes da plataforma utilizando TLS 1.2 ou superior;
- **Controle de acesso baseado em papéis (RBAC):** acesso aos dados restrito a usuários com permissão mínima necessária para cada função;
- **Isolamento de dados por tenant:** dados de cada Controlador armazenados com isolamento lógico, impedindo acesso cruzado entre contas;
- **Retenção configurável:** exclusão automática de clipes ao final do período de retenção definido pelo Controlador;
- **Monitoramento de integridade:** logs de acesso a dados pessoais armazenados por 12 meses com alertas de anomalia.

**Organizacionais:**
- **Política de acesso:** acesso interno a dados de produção restrito a engenheiros com necessidade justificada, mediante aprovação e registro de auditoria;
- **Treinamento em privacidade:** equipe treinada anualmente em LGPD e melhores práticas de segurança;
- **Teste de invasão (pen-test):** realizado ao menos **1 (uma) vez por ano** por empresa especializada independente; relatório executivo disponível ao Controlador mediante solicitação;
- **Plano de resposta a incidentes:** procedimento documentado para identificação, contenção, erradicação e notificação de incidentes de segurança;
- **Gestor de privacidade:** DPO designado conforme art. 41 da LGPD, acessível em dpo@cams-erp.com.br.

**5.2** O Operador revisará e atualizará suas medidas de segurança periodicamente, em resposta a novas ameaças ou requisitos regulatórios.

---

## Cláusula 6 — Notificação de Incidentes de Segurança

**6.1** O Operador notificará o Controlador em até **48 (quarenta e oito) horas** após tomar ciência de um incidente de segurança que envolva dados pessoais cobertos por este Acordo.

**6.2** A notificação inicial conterá, no mínimo, as seguintes informações disponíveis no momento:

- Data e hora em que o incidente foi detectado;
- Natureza do incidente (acesso não autorizado, exfiltração, destruição, etc.);
- Categorias e volume estimado de dados pessoais afetados;
- Categorias de titulares afetados;
- Medidas de contenção adotadas até o momento da notificação;
- Contato do ponto focal do Operador para comunicação durante o incidente.

**6.3** O Operador fornecerá atualizações progressivas à medida que novas informações estiverem disponíveis, e um relatório final com análise de causa raiz e medidas corretivas no prazo de **30 (trinta) dias** após a contenção do incidente.

**6.4** O Operador cooperará plenamente com o Controlador para permitir que este cumpra suas obrigações de comunicação à ANPD e aos titulares afetados, conforme art. 48 da LGPD.

**6.5** A notificação de incidente pelo Operador não implica reconhecimento de culpa ou responsabilidade.

---

## Cláusula 7 — Direitos dos Titulares

**7.1** O Operador disponibiliza os seguintes mecanismos para exercício dos direitos dos titulares, nos termos do art. 18 da LGPD:

| Direito | Mecanismo disponível |
|---|---|
| Confirmação e acesso | `GET /me/export` — exportação em formato ZIP (JSON estruturado) |
| Correção | `PATCH /me` — atualização de dados de conta via API ou painel |
| Eliminação | `DELETE /me` — exclusão com grace period de 30 dias |
| Portabilidade | Exportação ZIP via painel ou API |
| Revogação de consentimento | Toggles de opt-in/opt-out no painel > Configurações > Privacidade |
| Revisão de decisão automatizada | Solicitação via dpo@cams-erp.com.br |

**7.2** O Operador atende às solicitações de titulares encaminhadas pelo Controlador em até **15 (quinze) dias úteis** após o recebimento da solicitação devidamente identificada.

**7.3** Quando um titular entrar em contato diretamente com o Operador exercendo seus direitos, o Operador encaminhará a solicitação ao Controlador e informará o titular sobre o procedimento adequado, salvo quando o Operador for o único com acesso técnico para atender a solicitação, hipótese em que atuará em coordenação com o Controlador.

**7.4** O Operador notificará o Controlador sobre qualquer solicitação de titular que não possa ser atendida nos prazos legais, indicando os motivos.

---

## Cláusula 8 — Auditoria e Prestação de Contas

**8.1** O Controlador tem direito a verificar a conformidade do Operador com as obrigações deste Acordo, nos seguintes termos:

**Questionário anual:**
- **1 (uma) vez por ano**, o Controlador pode enviar ao Operador um questionário de avaliação de segurança e privacidade;
- O Operador responderá em até **30 (trinta) dias úteis**;
- O questionário pode abranger: políticas de segurança, resultados de pen-test, incidentes do período, alterações em sub-operadores e conformidade com a LGPD.

**Visita on-site:**
- Visitas de auditoria on-site às instalações do Operador são permitidas mediante:
  - Celebração prévia de Acordo de Confidencialidade (NDA) específico;
  - Aviso prévio de **30 (trinta) dias** ao Operador;
  - Limitação a 1 (uma) visita por período de 12 meses, salvo após incidente de segurança grave;
  - Realização em horário comercial, sem interferência nas operações.

**8.2** Os custos de auditoria são de responsabilidade do Controlador, salvo quando a auditoria revelar descumprimento material deste Acordo pelo Operador.

**8.3** O Operador pode atender a múltiplos Controladores fornecendo relatório de auditoria ou certificação de terceiro (ex.: SOC 2, ISO 27001, relatório de pen-test) em substituição a auditorias individuais, desde que o relatório cubra o período relevante.

---

## Cláusula 9 — Encerramento do Tratamento

**9.1** No encerramento do Contrato Principal, por qualquer motivo, o Operador:

- Cessará todo tratamento dos dados pessoais do Controlador imediatamente após o término do prazo de acesso;
- Excluirá definitivamente todos os dados pessoais do Controlador (incluindo cópias de backup) em até **30 (trinta) dias** após o encerramento;
- Emitirá, mediante solicitação do Controlador, um **certificado de exclusão** confirmando a eliminação dos dados, no prazo de até **15 (quinze) dias úteis** após a conclusão do processo de exclusão.

**9.2** Exceção: o Operador poderá reter dados pessoais além do prazo de 30 dias exclusivamente quando obrigado por lei (ex.: obrigações fiscais, determinação judicial ou administrativa), devendo notificar o Controlador sobre as categorias de dados retidos e o prazo de retenção aplicável.

**9.3** Recomenda-se que o Controlador exporte seus dados antes do encerramento do Contrato, utilizando as ferramentas de exportação disponíveis na plataforma.

---

## Cláusula 10 — Vigência e Rescisão

**10.1** Este Acordo entra em vigor na data de assinatura e permanece vigente enquanto o Contrato Principal estiver em vigor.

**10.2** O encerramento do Contrato Principal, por qualquer motivo, implica automaticamente o encerramento deste Acordo, sem necessidade de manifestação adicional das Partes, observadas as obrigações de encerramento de tratamento previstas na Cláusula 9.

**10.3** As obrigações de confidencialidade, exclusão de dados e notificação de incidentes sobrevivem ao encerramento deste Acordo pelo prazo necessário ao seu cumprimento.

**10.4** Em caso de violação material deste Acordo por qualquer das Partes, a Parte não infratora pode notificar a infratora por escrito, concedendo prazo de **30 (trinta) dias** para cura. Não sanada a violação, a Parte não infratora pode resilir o Contrato Principal com efeito imediato.

---

## Cláusula 11 — Lei Aplicável e Foro

**11.1** Este Acordo é regido exclusivamente pela legislação brasileira, em especial:
- Lei nº 13.709/2018 (LGPD);
- Regulamentações da ANPD;
- Código Civil Brasileiro (Lei nº 10.406/2002).

**11.2** Fica eleito o foro da comarca da sede do Operador para dirimir eventuais litígios decorrentes deste Acordo, com renúncia expressa a qualquer outro, por mais privilegiado que seja.

**11.3** As Partes comprometem-se a tentar solucionar amigavelmente qualquer controvérsia decorrente deste Acordo antes de recorrer ao Poder Judiciário, mediante negociação direta por até **30 (trinta) dias** a partir da notificação da controvérsia.

---

## Bloco de Assinaturas

Local e data: _________________________________, _____ de _______________ de _________.

**OPERADOR:**

cams-erp

_____________________________________________
João Farinelli
Sócio-administrador / DPO
CPF: [CPF DO REPRESENTANTE]
E-mail: jv.farinelli@gmail.com / dpo@cams-erp.com.br

---

**CONTROLADOR:**

[RAZÃO SOCIAL DO CONTROLADOR]

_____________________________________________
[NOME DO REPRESENTANTE LEGAL]
[CARGO]
CPF: [CPF DO REPRESENTANTE]
E-mail: [E-MAIL DO REPRESENTANTE]

---

*Testemunhas (quando exigido):*

1. Nome: _________________________________ CPF: _____________________
2. Nome: _________________________________ CPF: _____________________

---

*Versão: v1.0 — Template Enterprise — 2026-05-12*
*Este template deve ser revisado pelo jurídico do Controlador antes da assinatura.*
