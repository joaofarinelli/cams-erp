# Runbook: Resposta a Incidente de Privacidade (LGPD)

**Versão:** v1.0  
**Vigente desde:** 2026-05-12  
**Responsável:** DPO (dpo@cams-erp.com.br)

## 1. Detecção e Triagem

### Exemplos de incidentes de privacidade:
- Acesso não autorizado a clips de vídeo (S3, API, agent)
- Exposição de credenciais de banco de dados
- Vazamento de dados de usuários (e-mail, nome, CNPJ)
- Acesso indevido à API sem autenticação
- Extração massiva de dados via endpoint

### Classificação de severidade:
| Severidade | Critério | Prazo notif. ANPD |
|-----------|----------|-------------------|
| Crítico | >100 titulares afetados OU dado biométrico | Imediato (< 24h) |
| Alto | 10-100 titulares, dado sensível | < 48h |
| Médio | < 10 titulares, dado não-sensível | < 72h |
| Baixo | Sem exposição real (tentativa bloqueada) | Avaliar; geralmente não notificar |

## 2. Contenção (primeiras 2h)

1. **Isolar** — se comprometimento de credenciais: revogar chaves AWS/Fly/DB imediatamente
2. **Preservar evidências** — exportar logs CloudWatch/Fly.io antes de rotacionar
3. **Bloquear vetor** — force-invalidar sessões afetadas, revogar tokens
4. **Acionar** — notificar João Farinelli (fundador) e DPO

## 3. Avaliação de impacto

Responder:
- Quais dados foram expostos? (categorias LGPD)
- Quantos titulares afetados?
- Por quanto tempo houve exposição?
- O incidente continua ativo?

## 4. Notificação aos titulares

Template de e-mail:

```
Assunto: Aviso de incidente de segurança — cams-erp

Prezado(a) [Nome],

Identificamos um incidente de segurança que pode ter afetado seus dados em nosso serviço.

O que aconteceu: [DESCRIÇÃO]
Dados possivelmente afetados: [CATEGORIAS]
Período: [DATA INÍCIO] a [DATA FIM]
Medidas tomadas: [AÇÕES]

Para proteger sua conta, recomendamos: [AÇÕES USUÁRIO]

Seu encarregado (DPO): dpo@cams-erp.com.br
ANPD: https://www.gov.br/anpd
```

## 5. Notificação à ANPD (art. 48 LGPD)

Prazo: conforme tabela acima. Prazo máximo ANPD aceita: 72h para incidentes de risco relevante.

Portal de notificação: https://www.gov.br/anpd/pt-br/assuntos/noticias/anpd-lanca-formulario

Campos obrigatórios:
- Natureza dos dados afetados
- Informações sobre os titulares
- Medidas técnicas e de segurança
- Riscos relacionados
- Medidas adotadas

## 6. Remediação e pós-incidente

1. Patch / correção do vetor
2. Rotação de todas as credenciais potencialmente expostas
3. Atualizar política de segurança
4. Post-mortem interno (72h após contenção)
5. Registro no sistema de incidentes (`POST /admin/incident`)

## 7. Contatos de emergência

| Papel | Contato |
|-------|---------|
| DPO | dpo@cams-erp.com.br |
| Fundador | jv.farinelli@gmail.com |
| AWS Support | console.aws.amazon.com/support |
| Fly.io Support | fly.io/docs/support |
| ANPD | https://www.gov.br/anpd |
