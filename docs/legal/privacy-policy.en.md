# Privacy Policy — cams-erp

**Version:** v1.0
**Effective:** 2026-05-12

---

## 1. Who We Are

**Data Controller:**
cams-erp (referred to in this document as "cams-erp", "we", or "our company") is the legal entity responsible for processing personal data collected through the intelligent camera monitoring platform.

**Data Protection Officer (DPO):**
João Farinelli
E-mail: dpo@cams-erp.com.br
For rights requests, privacy questions, and security incidents.

This Privacy Policy describes how we collect, use, store, share, and protect the personal data of our customers (subscribers), platform users, and third parties whose images or data are captured by camera devices configured on the cams-erp platform, in compliance with Brazil's General Data Protection Law (Lei Geral de Proteção de Dados Pessoais — LGPD, Law No. 13,709/2018).

---

## 2. Data We Collect

### 2.1 Account Data
Information provided at registration and during platform use:
- Full name and email address of the account holder;
- Company information (legal name, CNPJ tax ID, establishment address);
- Phone number (for WhatsApp notifications);
- Password (stored as bcrypt hash, never in plain text);
- Platform preferences and notification settings.

### 2.2 Camera Configuration
- RTSP URLs of camera devices (treated as confidential information);
- Name and description of each camera;
- Motion detection parameters (zones, sensitivity, schedules);
- Per-camera video retention settings.

### 2.3 Video Content
- Short video clips captured on motion detection events (MP4 format, stored on AWS S3, sa-east-1 region);
- Frames extracted from clips for analysis by computer vision models (sent to inference sub-processors — see Section 4);
- Associated metadata (timestamp, source camera, duration, threat analysis result).

### 2.4 Biometric Data (opt-in)
When the subscriber enables facial recognition (optional feature):
- Facial embeddings extracted from video frames for identification of persons enrolled in the establishment's access list;
- **Legal basis:** data subject's consent (art. 7, I, LGPD) — required individually for each identified person.

### 2.5 Audio Data (opt-in)
When the subscriber enables audio capture via cameras with microphones:
- Audio clips associated with video events;
- **Legal basis:** data subject's consent (art. 7, I, LGPD).

### 2.6 Payment Data
- Processed exclusively by Stripe (sub-processor);
- cams-erp does not store credit card numbers, CVV, or full banking details;
- We store only the Stripe customer identifier (customer_id), last 4 card digits, and invoice history.

### 2.7 Telemetry and Logs
- IP address and user-agent from web platform and API access sessions;
- Audit logs of actions (login, data export, clip deletion, configuration changes);
- Error and diagnostic data collected by Sentry (no video payloads).

---

## 3. Purposes and Legal Bases

| Purpose | Legal basis (LGPD) | Details |
|---|---|---|
| Provision of the contracted monitoring service | Art. 7, V — contract performance | Clip analysis, storage, alert notifications |
| Account management and authentication | Art. 7, V — contract performance | Account creation and platform access |
| Billing and subscription management | Art. 7, V — contract performance | Payment processing via Stripe |
| Platform security and fraud prevention | Art. 7, IX — legitimate interest | Access logs, abuse detection, service integrity |
| Improvement of detection models | Art. 7, IX — legitimate interest | Anonymized and aggregated data; identifiable videos only with consent |
| Technical support and customer service | Art. 7, V — contract performance | Controlled access to logs for troubleshooting |
| Facial recognition | Art. 7, I — consent | Explicit opt-in; requires individual consent from each identified data subject |
| Audio capture | Art. 7, I — consent | Explicit opt-in per camera |
| Video retention beyond 30 days | Art. 7, I — consent | Configurable per camera; beyond 30 days requires justification and recorded consent |
| Marketing communications | Art. 7, I — consent | Opt-in at account creation; revocable at any time |

---

## 4. Sub-Processors

cams-erp shares data with the following sub-processors to provide the service. We maintain data protection agreements with each of them.

| Sub-processor | Country | Purpose | Privacy Policy |
|---|---|---|---|
| Amazon Web Services (S3) | Brazil (sa-east-1) | Video clip and export storage | [aws.amazon.com/privacy](https://aws.amazon.com/privacy/) |
| Fly.io | Brazil (gru) | API hosting and processing | [fly.io/legal/privacy-policy](https://fly.io/legal/privacy-policy/) |
| Cloudflare Pages | Global (CDN) | Web frontend hosting | [cloudflare.com/privacypolicy](https://www.cloudflare.com/privacypolicy/) |
| Stripe | United States | Payment and subscription processing | [stripe.com/br/privacy](https://stripe.com/br/privacy) |
| Evolution API (self-hosted) | Brazil | WhatsApp gateway for notifications | N/A (proprietary instance) |
| Expo Push | United States | Mobile app push notifications | [expo.dev/privacy](https://expo.dev/privacy) |
| OpenAI | United States | VLM inference — video frame analysis | [openai.com/policies/privacy-policy](https://openai.com/policies/privacy-policy) |
| Google (Gemini) | United States | VLM inference — video frame analysis | [policies.google.com/privacy](https://policies.google.com/privacy) |
| OpenALPR Cloud | United States | License plate reading (opt-in) | [openalpr.com/privacy.html](https://www.openalpr.com/privacy.html) |
| Sentry | United States | Error monitoring and diagnostics | [sentry.io/privacy](https://sentry.io/privacy/) |

The complete and up-to-date list of sub-processors is available at [https://cams-erp-web.pages.dev/legal/sub-processadores](https://cams-erp-web.pages.dev/legal/sub-processadores).

We will notify subscribers **30 days in advance** before adding or replacing any sub-processor.

---

## 5. International Data Transfers

Some sub-processors operate outside Brazil, which involves international transfers of personal data. cams-erp adopts the following safeguards pursuant to art. 33 of the LGPD:

- **OpenAI and Google (Gemini):** video frames (without personally identifiable text) are sent for inference. Transfer based on Standard Contractual Clauses (SCC) compatible with LGPD. Data is not used for model training per API contracts.
- **Cloudflare:** static asset hosting; data in transit protected by TLS 1.3; no persistent storage of personal data beyond temporary logs.
- **Stripe:** payment processing subject to PCI-DSS regulation; transfer covered by contractual clauses and regulatory adequacy.
- **OpenALPR Cloud:** activated only with explicit subscriber opt-in; license plates sent without additional personal context; standard contractual clauses applicable.
- **Expo Push and Sentry:** device tokens and error data transferred; no video data; standard contractual clauses applicable.

---

## 6. Data Retention

| Data Category | Retention Period | Criterion |
|---|---|---|
| Video clips | 7 days (default) / configurable per camera | Auto-deleted at end of period; extension beyond 30 days requires consent |
| Account data | While contract is active + 5 years | Period for compliance with legal and fiscal obligations |
| Audit logs | 12 months | Security and compliance |
| Payment data | Per Stripe and PCI-DSS regulation | cams-erp retains only identifiers; full data with Stripe |
| Facial embeddings | While the feature is active | Immediately deleted upon disabling facial recognition |
| Audio data | Same period as associated video clips | Deleted together with the clip |

After account cancellation, all personal data is deleted within **30 days**, unless a legal retention obligation applies.

---

## 7. Data Subject Rights

Under art. 18 of the LGPD, the data subject has the following rights, exercisable directly on the platform or via email to the DPO:

| Right | How to Exercise |
|---|---|
| Confirmation of existence and access to data | `GET /me/export` via API or "Export my data" button in the dashboard |
| Correction of incomplete or incorrect data | `PATCH /me` via API or profile form in the dashboard |
| Anonymization, blocking, or deletion | `DELETE /me` via dashboard; 30-day grace period (data becomes inaccessible and is permanently deleted at end of period) |
| Data portability | ZIP export via `GET /me/export` (structured JSON + metadata) |
| Deletion of data processed under consent | Opt-in/opt-out toggles in the dashboard; immediate revocation |
| Information on sharing | This policy and the sub-processors page |
| Consent revocation | Toggles in Dashboard > Settings > Privacy |
| Objection to processing | Request via email to DPO: dpo@cams-erp.com.br |
| Review of automated decisions | Request via DPO; human review available for any AI-generated alert |

We respond to requests within **15 business days**. We may request identity confirmation before processing the request.

---

## 8. Cookies

The cams-erp web platform uses the following cookies:

| Cookie | Type | Purpose | Duration |
|---|---|---|---|
| `session_token` | Essential | Authentication and session management | Session / 30 days (if "remember me") |
| `theme_preference` | Preference | Store light/dark theme preference | 1 year |
| `sentry_session` | Analytics | Interface error diagnostics | Session |

Essential cookies do not require consent. Optional cookies (analytics) are activated only after acceptance via the cookie banner displayed on first access.

The subscriber can manage cookies in browser settings. Disabling essential cookies prevents the platform from functioning.

---

## 9. Data Protection Officer (DPO) Contact

For rights requests, questions, complaints, or privacy incident reports:

**DPO:** João Farinelli
**Email:** dpo@cams-erp.com.br
**Response time:** up to 15 business days after receipt of the request

In cases of serious security incidents, we will proactively notify affected data subjects and the National Data Protection Authority (Autoridade Nacional de Proteção de Dados — ANPD) as required by art. 48 of the LGPD.

---

## 10. Changes to This Policy

cams-erp may update this Privacy Policy periodically. When material changes are made:

- We will publish the new version with an updated effective date;
- We will notify subscribers by email **30 days in advance**;
- We will require a new explicit acceptance at the next login after the new version takes effect.

The history of previous versions will be kept available upon request to the DPO.

---

## 11. Jurisdiction and Applicable Law

This Privacy Policy is governed by Brazilian law, in particular Law No. 13,709/2018 (LGPD) and the Consumer Defense Code (Law No. 8,078/1990).

The courts of the jurisdiction of the controller's registered office are hereby elected as the exclusive forum for any disputes arising from this policy, to the exclusion of any other, however privileged it may be.

---

*Last updated: 2026-05-12 — v1.0 initial*
