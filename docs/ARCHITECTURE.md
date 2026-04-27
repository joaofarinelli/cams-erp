# Architecture

cams-erp = camera-surveillance + AI for Brazilian SMB retail (restaurants, mini-markets). MVP detects 3 cases: cash-register theft, kitchen consumption, retail-shelf theft.

## Components

- **Cloud API** (`api/`): Python 3.12 + FastAPI + SQLAlchemy 2 (async) + Postgres. Owns owner-facing endpoints (cameras, rules, alerts, pairing) and agent endpoints (heartbeat, config, events, clips upload-url). Deployed on AWS ECS Fargate behind ALB. Region `sa-east-1`.
- **Agent** (`agent/`): Go binary on customer's PDV PC (Windows). Reads RTSP from local NVR, runs motion detection, uploads clips to S3 via signed URL, posts events to API. Authenticates with `X-Device-Token` minted via pairing.
- **Inference worker** (`inference/`): Pulls SQS jobs, runs YOLOv8 + MediaPipe Pose heuristics, writes alerts. Phase 2.
- **Mobile app** (`mobile/`): React Native + Expo. Owners receive push, browse alerts, give feedback (false positive). WS subscription to `/alerts/stream` for real-time.

## Data flow

1. Owner signs up (Cognito) → registers agent via 6-digit pair code → agent obtains `device_token`.
2. Owner adds cameras (RTSP URL encrypted at rest with KMS) and rules (preset + zone polygons).
3. Agent pulls `/agent/config` (decrypted RTSP, rules per camera).
4. Motion → agent uploads clip to S3 (signed PUT, 10min TTL) → POSTs `/events` (persisted + enqueued in SQS).
5. Inference worker dequeues, scores clip vs. rule, writes `Alert`, publishes via in-process broker (Phase 1) / Redis (Phase 2).
6. Mobile WS receives alert. Owner posts feedback → status flipped to `seen` or `false_positive`.

## Security

- **Owner auth**: AWS Cognito (User Pool, JWT). API verifies via JWKS.
- **Agent auth**: device-token (32 bytes, urlsafe base64) — only SHA-256 hash stored. Sent via `X-Device-Token` header.
- **RTSP credentials**: encrypted at rest via AWS KMS (`alias/cams-erp-<env>-app`). Decrypted only for `/agent/config`.
- **DB**: row-level scoping on `Device.owner_id` — no shared tables; queries always join through `Device → owner_id`.
- **Network**: ECS in private subnets, ALB in public. RDS no public endpoint. Secrets via AWS Secrets Manager.

## Deployment

- Infra: Terraform. Bootstrap (S3 tf-state + DynamoDB lock) provisioned. Main stack (VPC, RDS, ECS, ALB, Cognito, ECR, SQS, S3) deferred until API is feature-complete.
- CI: GitHub Actions runs `pytest` + `ruff` + `mypy` on PR. Build & push to ECR on `main` push.
- DB migrations: Alembic, applied via one-off ECS task or SSM tunnel.
