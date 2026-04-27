# cams-erp

AI camera surveillance platform for Brazilian SMB retail (restaurants, mini-markets).
Detects suspicious behavior at cash registers, kitchens, and shelves via heuristic
inference on motion-triggered video clips uploaded by a Windows agent running on
the customer's PDV PC.

## Workspaces
- `agent/` — Windows agent (Go) running on the customer's PDV PC
- `api/` — Cloud API (Python + FastAPI) on AWS ECS Fargate
- `inference/` — GPU worker (Python + PyTorch + Ultralytics) on AWS ECS GPU
- `mobile/` — Owner app (React Native + Expo)
- `infra/` — Terraform (AWS, sa-east-1)
- `docs/` — Specs and plans

## Status
Phase 0 (infra) + Phase 1 (Cloud API). See
`docs/superpowers/plans/2026-04-27-phase0-infra-and-phase1-cloud-api.md`.
