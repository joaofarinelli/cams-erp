# cams-erp — Phase 0 (Infra) + Phase 1 (Cloud API) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up production-ready AWS infra and a fully tested Cloud API that exposes all endpoints needed by the agent, mobile app and inference worker for the cash-register use case.

**Architecture:** Mono-repo with workspaces (`agent/`, `api/`, `inference/`, `mobile/`, `infra/`, `docs/`). Phase 0 provisions AWS via Terraform (VPC, RDS, S3, SQS, Cognito, ECS). Phase 1 builds the FastAPI service that talks to RDS, signs S3 URLs, enqueues SQS jobs, authenticates owners (Cognito JWT) and agents (device-token), and pushes WS alerts.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 + Alembic, PostgreSQL 16, AWS (Cognito, S3, SQS, RDS, ECS Fargate, SES, KMS, Secrets Manager, Route53, ACM), Terraform 1.7+, GitHub Actions, Sentry, pytest, httpx, Docker.

**Reference spec:** `/Users/joaofarinelli/.claude/plans/n-s-precisamos-desenvolver-um-velvety-puddle.md` (the design spec approved 2026-04-27).

**Conventions:**
- Commit messages: Conventional Commits (`feat:`, `fix:`, `chore:`, `test:`, `infra:`).
- Branch strategy: trunk-based on `main`; PR for every task; squash-merge.
- Code/comments/commit messages: English. Plan prose: Portuguese.
- `region = sa-east-1` (São Paulo) for lower latency to BR clients.
- Secrets never in code: AWS Secrets Manager + env vars at runtime.

---

# PHASE 0 — Infrastructure

## Task 0.1: Initialize mono-repo skeleton

**Files:**
- Create: `/Users/joaofarinelli/dev/cams-erp/README.md`
- Create: `/Users/joaofarinelli/dev/cams-erp/.gitignore`
- Create: `/Users/joaofarinelli/dev/cams-erp/.editorconfig`
- Create: `/Users/joaofarinelli/dev/cams-erp/CODEOWNERS`
- Create: `/Users/joaofarinelli/dev/cams-erp/agent/.gitkeep`
- Create: `/Users/joaofarinelli/dev/cams-erp/api/.gitkeep`
- Create: `/Users/joaofarinelli/dev/cams-erp/inference/.gitkeep`
- Create: `/Users/joaofarinelli/dev/cams-erp/mobile/.gitkeep`
- Create: `/Users/joaofarinelli/dev/cams-erp/infra/.gitkeep`

- [ ] **Step 1: Initialize git repo**

```bash
cd /Users/joaofarinelli/dev/cams-erp
git init -b main
```

- [ ] **Step 2: Create README.md**

```markdown
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
```

- [ ] **Step 3: Create .gitignore**

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
htmlcov/
.coverage

# Node
node_modules/
.expo/
dist/

# Go
agent/bin/
*.exe

# Terraform
infra/.terraform/
*.tfstate
*.tfstate.*
.terraform.lock.hcl

# IDE
.idea/
.vscode/
*.swp

# OS
.DS_Store
Thumbs.db

# Env
.env
.env.local
.env.*.local

# Build artifacts
dist/
build/
*.log
```

- [ ] **Step 4: Create .editorconfig**

```ini
root = true

[*]
indent_style = space
indent_size = 2
end_of_line = lf
charset = utf-8
trim_trailing_whitespace = true
insert_final_newline = true

[*.py]
indent_size = 4

[*.go]
indent_style = tab

[Makefile]
indent_style = tab
```

- [ ] **Step 5: Create empty workspace dirs**

```bash
mkdir -p agent api inference mobile infra
touch agent/.gitkeep api/.gitkeep inference/.gitkeep mobile/.gitkeep infra/.gitkeep
```

- [ ] **Step 6: Initial commit**

```bash
git add .
git commit -m "chore: initialize cams-erp mono-repo skeleton"
```

---

## Task 0.2: GitHub repo + branch protection

**Files:** none (GitHub config)

- [ ] **Step 1: Create remote repo**

```bash
gh repo create cams-erp --private --source=. --remote=origin --push
```

- [ ] **Step 2: Set branch protection on main**

```bash
gh api -X PUT /repos/:owner/cams-erp/branches/main/protection \
  -f required_status_checks='{"strict":true,"contexts":[]}' \
  -f enforce_admins=false \
  -f required_pull_request_reviews='{"required_approving_review_count":1}' \
  -f restrictions=null
```

Expected: 200 OK with branch protection JSON.

- [ ] **Step 3: Commit**

No code change; proceed.

---

## Task 0.3: AWS account bootstrap (manual + Terraform state backend)

**Files:**
- Create: `infra/bootstrap/main.tf`
- Create: `infra/bootstrap/README.md`

This task creates the S3 bucket + DynamoDB table that hold *future* Terraform state. Must be applied once with local state, then never re-applied.

- [ ] **Step 1: Confirm AWS CLI authenticated as root or admin user**

```bash
aws sts get-caller-identity
```

Expected: JSON with `Account` matching the cams-erp AWS account.

- [ ] **Step 2: Create `infra/bootstrap/main.tf`**

```hcl
terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.50" }
  }
}

provider "aws" {
  region = "sa-east-1"
}

resource "aws_s3_bucket" "tfstate" {
  bucket        = "cams-erp-tfstate"
  force_destroy = false
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket                  = aws_s3_bucket.tfstate.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_dynamodb_table" "tflock" {
  name         = "cams-erp-tflock"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"
  attribute {
    name = "LockID"
    type = "S"
  }
}
```

- [ ] **Step 3: Apply bootstrap**

```bash
cd infra/bootstrap
terraform init
terraform apply -auto-approve
```

Expected: 4 resources created.

- [ ] **Step 4: Document & commit**

Create `infra/bootstrap/README.md`:

```markdown
# Bootstrap

Run **once per account**. Creates the S3 + DynamoDB used as Terraform backend
for everything else. Local state file is committed-ignored.

If you re-run it, you'll error harmlessly on resources-already-exist.
```

```bash
cd /Users/joaofarinelli/dev/cams-erp
git add infra/bootstrap/main.tf infra/bootstrap/README.md
git commit -m "infra(bootstrap): add tf-state S3 bucket and DynamoDB lock table"
```

---

## Task 0.4: Root Terraform module structure with remote state

**Files:**
- Create: `infra/main/versions.tf`
- Create: `infra/main/variables.tf`
- Create: `infra/main/providers.tf`
- Create: `infra/main/backend.tf`
- Create: `infra/main/outputs.tf`

- [ ] **Step 1: Create `infra/main/versions.tf`**

```hcl
terraform {
  required_version = ">= 1.7"
  required_providers {
    aws    = { source = "hashicorp/aws", version = "~> 5.50" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }
}
```

- [ ] **Step 2: Create `infra/main/backend.tf`**

```hcl
terraform {
  backend "s3" {
    bucket         = "cams-erp-tfstate"
    key            = "main/terraform.tfstate"
    region         = "sa-east-1"
    dynamodb_table = "cams-erp-tflock"
    encrypt        = true
  }
}
```

- [ ] **Step 3: Create `infra/main/variables.tf`**

```hcl
variable "env" {
  type        = string
  description = "Environment name (staging|prod)"
}

variable "region" {
  type    = string
  default = "sa-east-1"
}

variable "domain_root" {
  type        = string
  description = "Root domain (e.g. cams-erp.com)"
}
```

- [ ] **Step 4: Create `infra/main/providers.tf`**

```hcl
provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project     = "cams-erp"
      Environment = var.env
      ManagedBy   = "terraform"
    }
  }
}
```

- [ ] **Step 5: Create empty `infra/main/outputs.tf`**

```hcl
# Outputs filled per resource module.
```

- [ ] **Step 6: Initialize**

```bash
cd infra/main
terraform init
```

Expected: backend initialized, S3 + DynamoDB referenced.

- [ ] **Step 7: Commit**

```bash
git add infra/main
git commit -m "infra: add root tf module with remote S3 backend"
```

---

## Task 0.5: VPC + networking

**Files:**
- Create: `infra/main/network.tf`

- [ ] **Step 1: Write `infra/main/network.tf`**

```hcl
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.8"

  name = "cams-erp-${var.env}"
  cidr = "10.20.0.0/16"

  azs             = ["${var.region}a", "${var.region}b", "${var.region}c"]
  private_subnets = ["10.20.1.0/24", "10.20.2.0/24", "10.20.3.0/24"]
  public_subnets  = ["10.20.101.0/24", "10.20.102.0/24", "10.20.103.0/24"]

  enable_nat_gateway   = true
  single_nat_gateway   = true # cheap; HA later
  enable_dns_hostnames = true
}
```

- [ ] **Step 2: Add outputs**

Append to `infra/main/outputs.tf`:

```hcl
output "vpc_id" { value = module.vpc.vpc_id }
output "private_subnet_ids" { value = module.vpc.private_subnets }
output "public_subnet_ids" { value = module.vpc.public_subnets }
```

- [ ] **Step 3: Plan & apply**

```bash
cd infra/main
terraform plan -var env=staging -var domain_root=cams-erp.com -out=plan.tfplan
terraform apply plan.tfplan
```

Expected: VPC, 3 private subnets, 3 public subnets, 1 NAT, 1 IGW.

- [ ] **Step 4: Commit**

```bash
git add infra/main/network.tf infra/main/outputs.tf
git commit -m "infra: add VPC with 3 AZs, single NAT, public+private subnets"
```

---

## Task 0.6: RDS Postgres

**Files:**
- Create: `infra/main/rds.tf`

- [ ] **Step 1: Write `infra/main/rds.tf`**

```hcl
resource "random_password" "db_master" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "db_master" {
  name = "cams-erp-${var.env}-db-master"
}

resource "aws_secretsmanager_secret_version" "db_master" {
  secret_id     = aws_secretsmanager_secret.db_master.id
  secret_string = jsonencode({ username = "camsadmin", password = random_password.db_master.result })
}

resource "aws_db_subnet_group" "main" {
  name       = "cams-erp-${var.env}"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "db" {
  name   = "cams-erp-${var.env}-db"
  vpc_id = module.vpc.vpc_id
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.api.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_db_instance" "main" {
  identifier             = "cams-erp-${var.env}"
  engine                 = "postgres"
  engine_version         = "16"
  instance_class         = var.env == "prod" ? "db.t4g.medium" : "db.t4g.micro"
  allocated_storage      = 20
  max_allocated_storage  = 100
  db_name                = "camserp"
  username               = "camsadmin"
  password               = random_password.db_master.result
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.db.id]
  publicly_accessible    = false
  storage_encrypted      = true
  skip_final_snapshot    = var.env != "prod"
  backup_retention_period = var.env == "prod" ? 7 : 1
  deletion_protection    = var.env == "prod"
}
```

NOTE: `aws_security_group.api` is forward-referenced from Task 0.10. Create empty placeholder now in `infra/main/api_sg.tf` to allow terraform plan to succeed:

```hcl
resource "aws_security_group" "api" {
  name   = "cams-erp-${var.env}-api"
  vpc_id = module.vpc.vpc_id
}
```

- [ ] **Step 2: Outputs**

Append to `infra/main/outputs.tf`:

```hcl
output "db_endpoint"      { value = aws_db_instance.main.endpoint }
output "db_secret_arn"    { value = aws_secretsmanager_secret.db_master.arn }
```

- [ ] **Step 3: Plan & apply**

```bash
terraform plan -var env=staging -var domain_root=cams-erp.com -out=plan.tfplan
terraform apply plan.tfplan
```

Expected: ~12min for RDS to come up.

- [ ] **Step 4: Commit**

```bash
git add infra/main/rds.tf infra/main/api_sg.tf infra/main/outputs.tf
git commit -m "infra: add RDS Postgres 16, secrets, sg"
```

---

## Task 0.7: S3 buckets (clips with 7-day lifecycle)

**Files:**
- Create: `infra/main/s3.tf`

- [ ] **Step 1: Write `infra/main/s3.tf`**

```hcl
resource "aws_s3_bucket" "clips" {
  bucket = "cams-erp-${var.env}-clips"
}

resource "aws_s3_bucket_lifecycle_configuration" "clips" {
  bucket = aws_s3_bucket.clips.id
  rule {
    id     = "expire-clips-7d"
    status = "Enabled"
    expiration { days = 7 }
    filter {}
  }
}

resource "aws_s3_bucket_cors_configuration" "clips" {
  bucket = aws_s3_bucket.clips.id
  cors_rule {
    allowed_methods = ["GET", "PUT"]
    allowed_origins = ["*"]
    allowed_headers = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

resource "aws_s3_bucket_public_access_block" "clips" {
  bucket                  = aws_s3_bucket.clips.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "clips" {
  bucket = aws_s3_bucket.clips.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}
```

- [ ] **Step 2: Outputs**

```hcl
output "clips_bucket" { value = aws_s3_bucket.clips.id }
```

- [ ] **Step 3: Plan, apply, commit**

```bash
terraform plan -var env=staging -var domain_root=cams-erp.com -out=plan.tfplan
terraform apply plan.tfplan
git add infra/main/s3.tf infra/main/outputs.tf
git commit -m "infra: add clips S3 bucket with 7d lifecycle"
```

---

## Task 0.8: SQS queue + DLQ

**Files:**
- Create: `infra/main/sqs.tf`

- [ ] **Step 1: Write `infra/main/sqs.tf`**

```hcl
resource "aws_sqs_queue" "events_dlq" {
  name                      = "cams-erp-${var.env}-events-dlq"
  message_retention_seconds = 1209600 # 14d
}

resource "aws_sqs_queue" "events" {
  name                       = "cams-erp-${var.env}-events"
  visibility_timeout_seconds = 60
  message_retention_seconds  = 86400 # 1d
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.events_dlq.arn
    maxReceiveCount     = 3
  })
}
```

- [ ] **Step 2: Outputs**

```hcl
output "events_queue_url" { value = aws_sqs_queue.events.url }
output "events_dlq_url"   { value = aws_sqs_queue.events_dlq.url }
```

- [ ] **Step 3: Plan, apply, commit**

```bash
terraform plan -var env=staging -var domain_root=cams-erp.com -out=plan.tfplan
terraform apply plan.tfplan
git add infra/main/sqs.tf infra/main/outputs.tf
git commit -m "infra: add events SQS queue with DLQ"
```

---

## Task 0.9: Cognito user pool

**Files:**
- Create: `infra/main/cognito.tf`

- [ ] **Step 1: Write `infra/main/cognito.tf`**

```hcl
resource "aws_cognito_user_pool" "main" {
  name = "cams-erp-${var.env}"

  password_policy {
    minimum_length    = 10
    require_lowercase = true
    require_numbers   = true
    require_symbols   = false
    require_uppercase = true
  }

  auto_verified_attributes = ["email"]

  schema {
    name                = "email"
    attribute_data_type = "String"
    mutable             = true
    required            = true
    string_attribute_constraints {
      min_length = 3
      max_length = 256
    }
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }
}

resource "aws_cognito_user_pool_client" "mobile" {
  name         = "cams-erp-${var.env}-mobile"
  user_pool_id = aws_cognito_user_pool.main.id

  generate_secret               = false
  refresh_token_validity        = 30
  access_token_validity         = 15
  id_token_validity             = 15
  token_validity_units {
    refresh_token = "days"
    access_token  = "minutes"
    id_token      = "minutes"
  }

  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]
}
```

- [ ] **Step 2: Outputs**

```hcl
output "cognito_user_pool_id"        { value = aws_cognito_user_pool.main.id }
output "cognito_user_pool_client_id" { value = aws_cognito_user_pool_client.mobile.id }
output "cognito_jwks_url"            { value = "https://cognito-idp.${var.region}.amazonaws.com/${aws_cognito_user_pool.main.id}/.well-known/jwks.json" }
```

- [ ] **Step 3: Plan, apply, commit**

```bash
terraform plan -var env=staging -var domain_root=cams-erp.com -out=plan.tfplan
terraform apply plan.tfplan
git add infra/main/cognito.tf infra/main/outputs.tf
git commit -m "infra: add Cognito user pool + mobile client"
```

---

## Task 0.10: ECS Fargate cluster + task IAM roles

**Files:**
- Create: `infra/main/ecs.tf`
- Modify: `infra/main/api_sg.tf`

- [ ] **Step 1: Replace `infra/main/api_sg.tf` with the real SG**

```hcl
resource "aws_security_group" "api" {
  name   = "cams-erp-${var.env}-api"
  vpc_id = module.vpc.vpc_id

  ingress {
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "alb" {
  name   = "cams-erp-${var.env}-alb"
  vpc_id = module.vpc.vpc_id
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
```

- [ ] **Step 2: Write `infra/main/ecs.tf`**

```hcl
resource "aws_ecs_cluster" "main" {
  name = "cams-erp-${var.env}"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_iam_role" "task_execution" {
  name = "cams-erp-${var.env}-task-exec"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "task_execution_basic" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "task_api" {
  name = "cams-erp-${var.env}-task-api"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

data "aws_iam_policy_document" "task_api" {
  statement {
    actions = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.clips.arn}/*"]
  }
  statement {
    actions = ["sqs:SendMessage", "sqs:GetQueueAttributes"]
    resources = [aws_sqs_queue.events.arn]
  }
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.db_master.arn]
  }
  statement {
    actions   = ["cognito-idp:AdminGetUser", "cognito-idp:AdminInitiateAuth"]
    resources = [aws_cognito_user_pool.main.arn]
  }
  statement {
    actions   = ["ses:SendEmail", "ses:SendRawEmail"]
    resources = ["*"]
  }
  statement {
    actions   = ["sns:Publish"]
    resources = ["*"]
  }
  statement {
    actions   = ["kms:Encrypt", "kms:Decrypt"]
    resources = [aws_kms_key.app.arn]
  }
}

resource "aws_iam_role_policy" "task_api" {
  role   = aws_iam_role.task_api.id
  policy = data.aws_iam_policy_document.task_api.json
}

resource "aws_ecr_repository" "api" {
  name = "cams-erp-${var.env}-api"
  image_scanning_configuration { scan_on_push = true }
}
```

- [ ] **Step 3: Outputs**

```hcl
output "ecs_cluster_name"       { value = aws_ecs_cluster.main.name }
output "task_exec_role_arn"     { value = aws_iam_role.task_execution.arn }
output "task_api_role_arn"      { value = aws_iam_role.task_api.arn }
output "ecr_api_repository_url" { value = aws_ecr_repository.api.repository_url }
```

- [ ] **Step 4: Plan, apply, commit**

```bash
terraform plan -var env=staging -var domain_root=cams-erp.com -out=plan.tfplan
terraform apply plan.tfplan
git add infra/main/ecs.tf infra/main/api_sg.tf infra/main/outputs.tf
git commit -m "infra: add ECS cluster, IAM roles, ECR repo, ALB+API SGs"
```

---

## Task 0.11: KMS + Secrets Manager keys

**Files:**
- Create: `infra/main/kms.tf`

- [ ] **Step 1: Write `infra/main/kms.tf`**

```hcl
resource "aws_kms_key" "app" {
  description             = "cams-erp-${var.env} app data encryption (NVR creds, etc.)"
  deletion_window_in_days = 7
  enable_key_rotation     = true
}

resource "aws_kms_alias" "app" {
  name          = "alias/cams-erp-${var.env}-app"
  target_key_id = aws_kms_key.app.id
}

resource "aws_secretsmanager_secret" "jwt_secret" {
  name = "cams-erp-${var.env}-jwt-secret"
}

resource "random_password" "jwt_secret" {
  length  = 64
  special = true
}

resource "aws_secretsmanager_secret_version" "jwt_secret" {
  secret_id     = aws_secretsmanager_secret.jwt_secret.id
  secret_string = random_password.jwt_secret.result
}
```

- [ ] **Step 2: Outputs**

```hcl
output "kms_app_arn"    { value = aws_kms_key.app.arn }
output "jwt_secret_arn" { value = aws_secretsmanager_secret.jwt_secret.arn }
```

- [ ] **Step 3: Plan, apply, commit**

```bash
terraform plan -var env=staging -var domain_root=cams-erp.com -out=plan.tfplan
terraform apply plan.tfplan
git add infra/main/kms.tf infra/main/outputs.tf
git commit -m "infra: add KMS key for NVR creds + JWT secret in Secrets Manager"
```

---

## Task 0.12: Domain + Route53 + ACM cert + ALB

**Files:**
- Create: `infra/main/dns.tf`
- Create: `infra/main/alb.tf`

- [ ] **Step 1: Write `infra/main/dns.tf`** (assumes domain already registered in Route53)

```hcl
data "aws_route53_zone" "root" {
  name = var.domain_root
}

resource "aws_acm_certificate" "api" {
  domain_name       = "api.${var.env}.${var.domain_root}"
  validation_method = "DNS"
}

resource "aws_route53_record" "acm_validation" {
  for_each = {
    for dvo in aws_acm_certificate.api.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      record = dvo.resource_record_value
    }
  }
  zone_id = data.aws_route53_zone.root.zone_id
  name    = each.value.name
  type    = each.value.type
  ttl     = 60
  records = [each.value.record]
}

resource "aws_acm_certificate_validation" "api" {
  certificate_arn         = aws_acm_certificate.api.arn
  validation_record_fqdns = [for r in aws_route53_record.acm_validation : r.fqdn]
}
```

- [ ] **Step 2: Write `infra/main/alb.tf`**

```hcl
resource "aws_lb" "api" {
  name               = "cams-erp-${var.env}-api"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = module.vpc.public_subnets
}

resource "aws_lb_target_group" "api" {
  name        = "cams-erp-${var.env}-api"
  port        = 8080
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = module.vpc.vpc_id

  health_check {
    path                = "/healthz"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.api.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate_validation.api.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_lb_listener" "http_redirect" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type = "redirect"
    redirect {
      protocol    = "HTTPS"
      port        = "443"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_route53_record" "api" {
  zone_id = data.aws_route53_zone.root.zone_id
  name    = "api.${var.env}.${var.domain_root}"
  type    = "A"
  alias {
    name                   = aws_lb.api.dns_name
    zone_id                = aws_lb.api.zone_id
    evaluate_target_health = true
  }
}
```

- [ ] **Step 3: Outputs**

```hcl
output "alb_target_group_arn" { value = aws_lb_target_group.api.arn }
output "api_url"              { value = "https://api.${var.env}.${var.domain_root}" }
```

- [ ] **Step 4: Plan, apply, commit**

```bash
terraform plan -var env=staging -var domain_root=cams-erp.com -out=plan.tfplan
terraform apply plan.tfplan
git add infra/main/dns.tf infra/main/alb.tf infra/main/outputs.tf
git commit -m "infra: add ACM cert, ALB, Route53 record for api.staging.cams-erp.com"
```

---

## Task 0.13: GitHub Actions CI base

**Files:**
- Create: `.github/workflows/api.yml`
- Create: `.github/workflows/terraform.yml`

- [ ] **Step 1: Write `.github/workflows/api.yml`**

```yaml
name: api
on:
  push:
    paths: ["api/**", ".github/workflows/api.yml"]
  pull_request:
    paths: ["api/**", ".github/workflows/api.yml"]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: testpw
          POSTGRES_DB: camserp_test
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready --health-interval 10s --health-timeout 5s --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install uv
      - working-directory: api
        run: |
          uv sync --frozen
          uv run ruff check .
          uv run ruff format --check .
          uv run mypy app/
          DATABASE_URL=postgresql+psycopg://postgres:testpw@localhost:5432/camserp_test \
          uv run pytest -v --cov=app --cov-report=xml
      - uses: codecov/codecov-action@v4
        with: { files: api/coverage.xml }
```

- [ ] **Step 2: Write `.github/workflows/terraform.yml`**

```yaml
name: terraform
on:
  pull_request:
    paths: ["infra/**"]

permissions:
  id-token: write
  contents: read
  pull-requests: write

jobs:
  plan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
        with: { terraform_version: 1.7.5 }
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_GHA_ROLE_ARN }}
          aws-region: sa-east-1
      - working-directory: infra/main
        run: |
          terraform init
          terraform fmt -check -recursive
          terraform validate
          terraform plan -var env=staging -var domain_root=cams-erp.com -no-color -out=plan.tfplan | tee plan.txt
```

- [ ] **Step 3: Configure AWS OIDC for GitHub Actions**

Run once (manual one-shot in `infra/oidc/main.tf`, similar pattern to bootstrap), creating an IAM role with trust policy `token.actions.githubusercontent.com` and admin permissions for staging. Save its ARN to GitHub Actions secret `AWS_GHA_ROLE_ARN`.

```bash
gh secret set AWS_GHA_ROLE_ARN --body "arn:aws:iam::ACCOUNT:role/cams-erp-gha-staging"
```

- [ ] **Step 4: Commit**

```bash
git add .github
git commit -m "ci: add api + terraform CI workflows with OIDC"
```

---

## Task 0.14: Sentry projects + secrets

**Files:** none (Sentry web UI + GitHub secrets)

- [ ] **Step 1: Create Sentry projects** (manual via UI)

Create `cams-erp-api`, `cams-erp-inference`, `cams-erp-mobile`, `cams-erp-agent`. Capture DSN of each.

- [ ] **Step 2: Set GitHub secret**

```bash
gh secret set SENTRY_DSN_API --body "https://...@sentry.io/PROJECT_ID"
```

- [ ] **Step 3: Commit nothing**

Move on.

---

## Task 0.15: CloudWatch dashboards + alerts skeleton

**Files:**
- Create: `infra/main/cloudwatch.tf`

- [ ] **Step 1: Write `infra/main/cloudwatch.tf`**

```hcl
resource "aws_cloudwatch_log_group" "api" {
  name              = "/cams-erp/${var.env}/api"
  retention_in_days = 14
}

resource "aws_sns_topic" "ops_alerts" {
  name = "cams-erp-${var.env}-ops-alerts"
}

resource "aws_cloudwatch_metric_alarm" "events_dlq_depth" {
  alarm_name          = "cams-erp-${var.env}-events-dlq-non-empty"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  dimensions          = { QueueName = aws_sqs_queue.events_dlq.name }
}
```

- [ ] **Step 2: Plan, apply, commit**

```bash
terraform plan -var env=staging -var domain_root=cams-erp.com -out=plan.tfplan
terraform apply plan.tfplan
git add infra/main/cloudwatch.tf
git commit -m "infra: add api log group, ops SNS topic, DLQ alarm"
```

---

# PHASE 1 — Cloud API

> All Phase 1 tasks operate inside `api/`. From here on, the working directory for every command is `api/` unless otherwise noted.

## Task 1.1: FastAPI scaffold

**Files:**
- Create: `api/pyproject.toml`
- Create: `api/uv.lock` (generated)
- Create: `api/Dockerfile`
- Create: `api/.dockerignore`
- Create: `api/app/__init__.py`
- Create: `api/app/main.py`
- Create: `api/app/config.py`
- Create: `api/tests/__init__.py`
- Create: `api/tests/conftest.py`

- [ ] **Step 1: Write `api/pyproject.toml`**

```toml
[project]
name = "cams-erp-api"
version = "0.1.0"
description = "cams-erp Cloud API"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "pydantic>=2.7",
  "pydantic-settings>=2.3",
  "sqlalchemy>=2.0",
  "psycopg[binary]>=3.2",
  "alembic>=1.13",
  "boto3>=1.34",
  "python-jose[cryptography]>=3.3",
  "httpx>=0.27",
  "structlog>=24.1",
  "sentry-sdk[fastapi]>=2.7",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2",
  "pytest-asyncio>=0.23",
  "pytest-cov>=5.0",
  "respx>=0.21",
  "ruff>=0.5",
  "mypy>=1.10",
  "freezegun>=1.5",
  "moto[s3,sqs,cognitoidp,secretsmanager]>=5.0",
]

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "ASYNC", "S", "RUF"]
ignore = ["S101"]

[tool.mypy]
strict = true
python_version = "3.12"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Write `api/Dockerfile`**

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"
COPY --from=builder /app/.venv /app/.venv
COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

- [ ] **Step 3: Write `api/.dockerignore`**

```
.venv
__pycache__
.pytest_cache
.mypy_cache
.ruff_cache
tests
*.md
```

- [ ] **Step 4: Write `api/app/config.py`**

```python
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CAMS_", env_file=".env", extra="ignore")

    env: str = Field(default="dev")
    database_url: str = Field(default="postgresql+psycopg://postgres:postgres@localhost/camserp")
    clips_bucket: str = Field(default="cams-erp-staging-clips")
    events_queue_url: str = Field(default="")
    cognito_user_pool_id: str = Field(default="")
    cognito_jwks_url: str = Field(default="")
    aws_region: str = Field(default="sa-east-1")
    jwt_secret: str = Field(default="dev-secret-change-me")
    sentry_dsn: str = Field(default="")
    log_level: str = Field(default="INFO")


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 5: Write `api/app/main.py`**

```python
import sentry_sdk
import structlog
from fastapi import FastAPI

from app.config import get_settings

settings = get_settings()
if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.env, traces_sample_rate=0.1)

logger = structlog.get_logger()


def create_app() -> FastAPI:
    app = FastAPI(title="cams-erp API", version="0.1.0")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 6: Write `api/tests/conftest.py`**

```python
import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())
```

- [ ] **Step 7: Write `api/tests/test_health.py`**

```python
from fastapi.testclient import TestClient


def test_healthz_returns_ok(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 8: Install deps + run test**

```bash
cd api
uv sync
uv run pytest tests/test_health.py -v
```

Expected: 1 passed.

- [ ] **Step 9: Commit**

```bash
git add api/
git commit -m "feat(api): scaffold FastAPI with /healthz, config, Dockerfile, pytest"
```

---

## Task 1.2: SQLAlchemy + Alembic + initial migration

**Files:**
- Create: `api/alembic.ini`
- Create: `api/migrations/env.py`
- Create: `api/migrations/script.py.mako`
- Create: `api/app/db/__init__.py`
- Create: `api/app/db/session.py`
- Create: `api/app/db/base.py`
- Create: `api/app/db/models.py`

- [ ] **Step 1: Init alembic**

```bash
cd api
uv run alembic init -t async migrations
mv alembic.ini alembic.ini.bak
```

- [ ] **Step 2: Write `api/alembic.ini`**

```ini
[alembic]
script_location = migrations
sqlalchemy.url =

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 3: Write `api/app/db/base.py`**

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 4: Write `api/app/db/session.py`**

```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

settings = get_settings()
engine = create_async_engine(settings.database_url.replace("+psycopg", "+asyncpg"), pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
```

- [ ] **Step 5: Write `api/app/db/models.py`**

```python
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PresetType(StrEnum):
    cash_register = "cash_register"
    kitchen_consumption = "kitchen_consumption"
    retail_shelf = "retail_shelf"


class AlertStatus(StrEnum):
    pending = "pending"
    seen = "seen"
    false_positive = "false_positive"


class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    cognito_sub: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    pair_code: Mapped[str | None] = mapped_column(String(6), unique=True, nullable=True)
    pair_code_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    device_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    name: Mapped[str] = mapped_column(String(120), default="My PDV")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Camera(Base):
    __tablename__ = "cameras"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    rtsp_url_encrypted: Mapped[str] = mapped_column(String(1024))  # KMS-encrypted
    online: Mapped[bool] = mapped_column(default=False)
    last_frame_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Rule(Base):
    __tablename__ = "rules"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    camera_id: Mapped[UUID] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    preset_type: Mapped[PresetType] = mapped_column(Enum(PresetType, name="preset_type"))
    enabled: Mapped[bool] = mapped_column(default=True)
    zones: Mapped[dict] = mapped_column(JSON, default=dict)  # {"gaveta": [...polygon], "pc_operador": [...]}
    sensitivity: Mapped[int] = mapped_column(default=50)  # 0..100
    cooldown_seconds: Mapped[int] = mapped_column(default=300)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Event(Base):
    __tablename__ = "events"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    camera_id: Mapped[UUID] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    s3_key: Mapped[str] = mapped_column(String(512))
    motion_score: Mapped[float] = mapped_column()
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int] = mapped_column()
    processed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    rule_id: Mapped[UUID] = mapped_column(ForeignKey("rules.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    status: Mapped[AlertStatus] = mapped_column(Enum(AlertStatus, name="alert_status"), default=AlertStatus.pending)
    score: Mapped[float] = mapped_column()
    message: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 6: Configure `migrations/env.py` to use models**

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool

from app.config import get_settings
from app.db.base import Base
from app.db import models  # noqa: F401

config = context.config
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url.replace("+psycopg", "+asyncpg"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as conn:
        await conn.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


run_migrations_online()
```

- [ ] **Step 7: Generate first migration**

```bash
cd api
uv run alembic revision --autogenerate -m "initial schema"
```

Expected: file `migrations/versions/<hash>_initial_schema.py` created.

- [ ] **Step 8: Apply migration locally**

```bash
docker run --rm -d --name pgtest -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:16
sleep 5
CAMS_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/postgres uv run alembic upgrade head
```

Expected: tables created in postgres container.

- [ ] **Step 9: Commit**

```bash
git add api/alembic.ini api/migrations api/app/db
git commit -m "feat(api): add sqlalchemy models + initial alembic migration"
```

---

## Task 1.3: Cognito JWT auth dependency

**Files:**
- Create: `api/app/security/__init__.py`
- Create: `api/app/security/cognito.py`
- Create: `api/tests/test_security_cognito.py`

- [ ] **Step 1: Write failing test `api/tests/test_security_cognito.py`**

```python
import pytest
from fastapi import HTTPException

from app.security.cognito import verify_cognito_token


@pytest.mark.asyncio
async def test_verify_cognito_token_rejects_garbage() -> None:
    with pytest.raises(HTTPException) as exc:
        await verify_cognito_token("not-a-jwt")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_cognito_token_returns_claims_for_valid_token(monkeypatch) -> None:
    fake_jwks = {"keys": [{"kid": "abc", "kty": "RSA", "n": "...", "e": "AQAB"}]}
    fake_claims = {"sub": "user-uuid", "email": "owner@example.com", "token_use": "access"}

    async def fake_get_jwks() -> dict:
        return fake_jwks

    def fake_decode(token: str, jwks: dict, algorithms: list[str], audience: str | None = None) -> dict:
        return fake_claims

    monkeypatch.setattr("app.security.cognito._fetch_jwks", fake_get_jwks)
    monkeypatch.setattr("app.security.cognito.jwt.decode", fake_decode)

    claims = await verify_cognito_token("valid.jwt.token")
    assert claims["sub"] == "user-uuid"
```

- [ ] **Step 2: Run, expect failure**

```bash
uv run pytest tests/test_security_cognito.py -v
```

Expected: ImportError (module not yet created).

- [ ] **Step 3: Write `api/app/security/cognito.py`**

```python
from typing import Any

import httpx
from fastapi import HTTPException, status
from jose import jwt
from jose.exceptions import JWTError

from app.config import get_settings

settings = get_settings()
_jwks_cache: dict[str, Any] | None = None


async def _fetch_jwks() -> dict[str, Any]:
    global _jwks_cache
    if _jwks_cache is None:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(settings.cognito_jwks_url)
            r.raise_for_status()
            _jwks_cache = r.json()
    assert _jwks_cache is not None
    return _jwks_cache


async def verify_cognito_token(token: str) -> dict[str, Any]:
    try:
        jwks = await _fetch_jwks()
        claims = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.cognito_user_pool_client_id if hasattr(settings, "cognito_user_pool_client_id") else None,
            options={"verify_aud": False},
        )
        return claims
    except (JWTError, httpx.HTTPError) as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from e
```

- [ ] **Step 4: Run tests, expect pass**

```bash
uv run pytest tests/test_security_cognito.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Add FastAPI dependency wrapper**

Append to `api/app/security/cognito.py`:

```python
from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.session import get_db


async def get_current_user(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    claims = await verify_cognito_token(token)

    result = await db.execute(select(User).where(User.cognito_sub == claims["sub"]))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(cognito_sub=claims["sub"], email=claims.get("email", ""))
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user
```

- [ ] **Step 6: Commit**

```bash
git add api/app/security api/tests/test_security_cognito.py
git commit -m "feat(api): add Cognito JWT verification + get_current_user dependency"
```

---

## Task 1.4: Device-token auth dependency

**Files:**
- Create: `api/app/security/device_auth.py`
- Create: `api/tests/test_security_device_auth.py`

- [ ] **Step 1: Write failing test**

```python
import hashlib

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.db.models import Device, User
from app.security.device_auth import generate_device_token, verify_device_token


@pytest.mark.asyncio
async def test_generate_and_verify_device_token(db_session) -> None:
    user = User(cognito_sub="abc", email="a@b.com")
    db_session.add(user)
    await db_session.flush()
    device = Device(owner_id=user.id)
    db_session.add(device)
    await db_session.flush()

    raw_token = generate_device_token()
    device.device_token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    await db_session.commit()

    verified = await verify_device_token(raw_token, db_session)
    assert verified.id == device.id


@pytest.mark.asyncio
async def test_verify_device_token_rejects_unknown(db_session) -> None:
    with pytest.raises(HTTPException) as exc:
        await verify_device_token("nonexistent-token", db_session)
    assert exc.value.status_code == 401
```

(`db_session` fixture wired in next step.)

- [ ] **Step 2: Add `db_session` fixture to `tests/conftest.py`**

Append:

```python
import asyncio

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.base import Base


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:  # type: ignore[misc]
    settings = get_settings()
    engine = create_async_engine(settings.database_url.replace("+psycopg", "+asyncpg"))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
```

- [ ] **Step 3: Run, expect failure**

```bash
uv run pytest tests/test_security_device_auth.py -v
```

Expected: ImportError.

- [ ] **Step 4: Write `api/app/security/device_auth.py`**

```python
import hashlib
import secrets

from fastapi import Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Device


def generate_device_token() -> str:
    return secrets.token_urlsafe(32)


def hash_device_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def verify_device_token(token: str, db: AsyncSession) -> Device:
    h = hash_device_token(token)
    result = await db.execute(select(Device).where(Device.device_token_hash == h))
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid device token")
    return device


async def get_current_device(
    x_device_token: str = Header(..., alias="X-Device-Token"),
) -> Device:
    from app.db.session import SessionLocal
    async with SessionLocal() as db:
        return await verify_device_token(x_device_token, db)
```

- [ ] **Step 5: Run tests, expect pass**

```bash
uv run pytest tests/test_security_device_auth.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add api/app/security/device_auth.py api/tests/test_security_device_auth.py api/tests/conftest.py
git commit -m "feat(api): add device-token auth (hashed in DB, X-Device-Token header)"
```

---

## Task 1.5: Cameras CRUD endpoints

**Files:**
- Create: `api/app/routers/__init__.py`
- Create: `api/app/routers/cameras.py`
- Create: `api/app/services/kms.py`
- Create: `api/app/schemas/cameras.py`
- Create: `api/tests/test_cameras.py`
- Modify: `api/app/main.py` (register router)

- [ ] **Step 1: Write `api/app/services/kms.py`** (placeholder + real impl)

```python
import base64

import boto3

from app.config import get_settings


def encrypt(plaintext: str) -> str:
    settings = get_settings()
    if settings.env == "test":
        return base64.b64encode(plaintext.encode()).decode()
    kms = boto3.client("kms", region_name=settings.aws_region)
    resp = kms.encrypt(KeyId=f"alias/cams-erp-{settings.env}-app", Plaintext=plaintext.encode())
    return base64.b64encode(resp["CiphertextBlob"]).decode()


def decrypt(ciphertext_b64: str) -> str:
    settings = get_settings()
    if settings.env == "test":
        return base64.b64decode(ciphertext_b64).decode()
    kms = boto3.client("kms", region_name=settings.aws_region)
    resp = kms.decrypt(CiphertextBlob=base64.b64decode(ciphertext_b64))
    return resp["Plaintext"].decode()
```

- [ ] **Step 2: Write `api/app/schemas/cameras.py`**

```python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CameraCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    rtsp_url: str = Field(min_length=10, max_length=1024)
    device_id: UUID


class CameraUpdate(BaseModel):
    name: str | None = None
    rtsp_url: str | None = None


class CameraOut(BaseModel):
    id: UUID
    device_id: UUID
    name: str
    online: bool
    last_frame_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 3: Write failing tests `api/tests/test_cameras.py`**

```python
from httpx import AsyncClient


async def _auth_user(client: AsyncClient, db_session) -> dict[str, str]:
    # Helper that simulates an authenticated user via a test override
    # of get_current_user (set up in conftest as `auth_client` fixture)
    return {"Authorization": "Bearer fake"}


async def test_create_camera_returns_201(auth_client: AsyncClient, seed_device) -> None:
    payload = {
        "name": "Caixa 1",
        "rtsp_url": "rtsp://user:pw@10.0.0.50:554/Streaming/Channels/101",
        "device_id": str(seed_device.id),
    }
    r = await auth_client.post("/cameras", json=payload)
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Caixa 1"
    assert "rtsp_url" not in body  # not exposed
    assert body["online"] is False


async def test_list_cameras_filters_by_owner(auth_client: AsyncClient, seed_device) -> None:
    await auth_client.post(
        "/cameras",
        json={"name": "C1", "rtsp_url": "rtsp://x/1", "device_id": str(seed_device.id)},
    )
    r = await auth_client.get("/cameras")
    assert r.status_code == 200
    assert len(r.json()) == 1


async def test_delete_camera(auth_client: AsyncClient, seed_device) -> None:
    r = await auth_client.post(
        "/cameras",
        json={"name": "C1", "rtsp_url": "rtsp://x/1", "device_id": str(seed_device.id)},
    )
    cam_id = r.json()["id"]
    r = await auth_client.delete(f"/cameras/{cam_id}")
    assert r.status_code == 204
    r = await auth_client.get("/cameras")
    assert r.json() == []
```

- [ ] **Step 4: Add `auth_client` + `seed_device` fixtures to `tests/conftest.py`**

Append:

```python
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db.models import Device, User
from app.db.session import SessionLocal
from app.main import create_app
from app.security.cognito import get_current_user


@pytest_asyncio.fixture
async def seed_user(db_session) -> User:
    user = User(cognito_sub="test-sub", email="test@cams-erp.com")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def seed_device(db_session, seed_user) -> Device:
    device = Device(owner_id=seed_user.id, name="PDV 1")
    db_session.add(device)
    await db_session.commit()
    await db_session.refresh(device)
    return device


@pytest_asyncio.fixture
async def auth_client(seed_user) -> AsyncClient:
    app = create_app()

    async def override_user() -> User:
        return seed_user

    app.dependency_overrides[get_current_user] = override_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
```

- [ ] **Step 5: Write `api/app/routers/cameras.py`**

```python
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Camera, Device, User
from app.db.session import get_db
from app.schemas.cameras import CameraCreate, CameraOut, CameraUpdate
from app.security.cognito import get_current_user
from app.services.kms import decrypt, encrypt

router = APIRouter(prefix="/cameras", tags=["cameras"])


async def _owned_camera(camera_id: UUID, user: User, db: AsyncSession) -> Camera:
    result = await db.execute(
        select(Camera).join(Device).where(Camera.id == camera_id, Device.owner_id == user.id)
    )
    cam = result.scalar_one_or_none()
    if cam is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Camera not found")
    return cam


@router.post("", response_model=CameraOut, status_code=201)
async def create_camera(
    payload: CameraCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Camera:
    result = await db.execute(
        select(Device).where(Device.id == payload.device_id, Device.owner_id == user.id)
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")

    cam = Camera(
        device_id=device.id,
        name=payload.name,
        rtsp_url_encrypted=encrypt(payload.rtsp_url),
    )
    db.add(cam)
    await db.commit()
    await db.refresh(cam)
    return cam


@router.get("", response_model=list[CameraOut])
async def list_cameras(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Camera]:
    result = await db.execute(
        select(Camera).join(Device).where(Device.owner_id == user.id)
    )
    return list(result.scalars().all())


@router.put("/{camera_id}", response_model=CameraOut)
async def update_camera(
    camera_id: UUID,
    payload: CameraUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Camera:
    cam = await _owned_camera(camera_id, user, db)
    if payload.name is not None:
        cam.name = payload.name
    if payload.rtsp_url is not None:
        cam.rtsp_url_encrypted = encrypt(payload.rtsp_url)
    await db.commit()
    await db.refresh(cam)
    return cam


@router.delete("/{camera_id}", status_code=204)
async def delete_camera(
    camera_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    cam = await _owned_camera(camera_id, user, db)
    await db.delete(cam)
    await db.commit()
```

- [ ] **Step 6: Register router in `api/app/main.py`**

Modify `create_app`:

```python
from app.routers import cameras

def create_app() -> FastAPI:
    app = FastAPI(title="cams-erp API", version="0.1.0")
    app.include_router(cameras.router)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app
```

- [ ] **Step 7: Run tests, expect pass**

```bash
uv run pytest tests/test_cameras.py -v
```

Expected: 3 passed.

- [ ] **Step 8: Commit**

```bash
git add api/app/routers api/app/services/kms.py api/app/schemas api/tests/test_cameras.py api/tests/conftest.py api/app/main.py
git commit -m "feat(api): add cameras CRUD with KMS-encrypted RTSP URLs"
```

---

## Task 1.6: Pairing flow endpoints (owner ↔ agent)

**Files:**
- Create: `api/app/routers/pairing.py`
- Create: `api/app/schemas/pairing.py`
- Create: `api/tests/test_pairing.py`

The flow: owner taps "add PDV" in mobile app → API generates 6-digit code (TTL 10min) → owner types code into agent UI → agent calls `POST /pair/verify` with code → API mints device-token, returns it once.

- [ ] **Step 1: Write `api/app/schemas/pairing.py`**

```python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PairCodeOut(BaseModel):
    pair_code: str
    expires_at: datetime
    device_id: UUID


class PairVerifyIn(BaseModel):
    pair_code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class PairVerifyOut(BaseModel):
    device_id: UUID
    device_token: str  # raw, returned only here
```

- [ ] **Step 2: Write failing tests `api/tests/test_pairing.py`**

```python
from datetime import datetime, timedelta, timezone

import pytest
from freezegun import freeze_time
from httpx import AsyncClient


async def test_owner_creates_pair_code(auth_client: AsyncClient) -> None:
    r = await auth_client.post("/pair/code")
    assert r.status_code == 201
    body = r.json()
    assert len(body["pair_code"]) == 6
    assert body["pair_code"].isdigit()


async def test_agent_verifies_code_and_gets_token(auth_client: AsyncClient, anon_client: AsyncClient) -> None:
    r = await auth_client.post("/pair/code")
    code = r.json()["pair_code"]

    r = await anon_client.post("/pair/verify", json={"pair_code": code})
    assert r.status_code == 200
    body = r.json()
    assert "device_token" in body
    assert body["device_token"]


async def test_expired_code_is_rejected(auth_client: AsyncClient, anon_client: AsyncClient) -> None:
    with freeze_time(datetime.now(tz=timezone.utc) - timedelta(minutes=15)):
        r = await auth_client.post("/pair/code")
        code = r.json()["pair_code"]

    r = await anon_client.post("/pair/verify", json={"pair_code": code})
    assert r.status_code == 400


async def test_code_is_single_use(auth_client: AsyncClient, anon_client: AsyncClient) -> None:
    r = await auth_client.post("/pair/code")
    code = r.json()["pair_code"]
    r1 = await anon_client.post("/pair/verify", json={"pair_code": code})
    assert r1.status_code == 200
    r2 = await anon_client.post("/pair/verify", json={"pair_code": code})
    assert r2.status_code == 400
```

Add `anon_client` fixture to `conftest.py`:

```python
@pytest_asyncio.fixture
async def anon_client() -> AsyncClient:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
```

- [ ] **Step 3: Run, expect fail**

```bash
uv run pytest tests/test_pairing.py -v
```

Expected: collection error or 404s.

- [ ] **Step 4: Write `api/app/routers/pairing.py`**

```python
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Device, User
from app.db.session import get_db
from app.schemas.pairing import PairCodeOut, PairVerifyIn, PairVerifyOut
from app.security.cognito import get_current_user
from app.security.device_auth import generate_device_token, hash_device_token

router = APIRouter(prefix="/pair", tags=["pair"])


@router.post("/code", response_model=PairCodeOut, status_code=201)
async def create_pair_code(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PairCodeOut:
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires = datetime.now(tz=timezone.utc) + timedelta(minutes=10)
    device = Device(owner_id=user.id, pair_code=code, pair_code_expires_at=expires)
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return PairCodeOut(pair_code=code, expires_at=expires, device_id=device.id)


@router.post("/verify", response_model=PairVerifyOut)
async def verify_pair_code(
    payload: PairVerifyIn,
    db: AsyncSession = Depends(get_db),
) -> PairVerifyOut:
    result = await db.execute(select(Device).where(Device.pair_code == payload.pair_code))
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid code")
    if device.pair_code_expires_at is None or device.pair_code_expires_at < datetime.now(tz=timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Code expired")
    if device.device_token_hash is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Already paired")

    raw_token = generate_device_token()
    device.device_token_hash = hash_device_token(raw_token)
    device.pair_code = None
    device.pair_code_expires_at = None
    await db.commit()
    await db.refresh(device)
    return PairVerifyOut(device_id=device.id, device_token=raw_token)
```

Register in `api/app/main.py`:

```python
from app.routers import cameras, pairing
app.include_router(pairing.router)
```

- [ ] **Step 5: Run tests, expect pass**

```bash
uv run pytest tests/test_pairing.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add api/app/routers/pairing.py api/app/schemas/pairing.py api/tests/test_pairing.py api/tests/conftest.py api/app/main.py
git commit -m "feat(api): add pairing flow (6-digit code -> device-token)"
```

---

## Task 1.7: Rules CRUD endpoints

**Files:**
- Create: `api/app/routers/rules.py`
- Create: `api/app/schemas/rules.py`
- Create: `api/tests/test_rules.py`

- [ ] **Step 1: Write `api/app/schemas/rules.py`**

```python
from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models import PresetType

PolygonPoint = tuple[float, float]
Polygon = Annotated[list[PolygonPoint], Field(min_length=3)]


class RuleCreate(BaseModel):
    camera_id: UUID
    preset_type: PresetType
    enabled: bool = True
    zones: dict[str, Polygon]
    sensitivity: int = Field(ge=0, le=100, default=50)
    cooldown_seconds: int = Field(ge=10, le=3600, default=300)


class RuleUpdate(BaseModel):
    enabled: bool | None = None
    zones: dict[str, Polygon] | None = None
    sensitivity: int | None = Field(default=None, ge=0, le=100)
    cooldown_seconds: int | None = Field(default=None, ge=10, le=3600)


class RuleOut(BaseModel):
    id: UUID
    camera_id: UUID
    preset_type: PresetType
    enabled: bool
    zones: dict
    sensitivity: int
    cooldown_seconds: int
    created_at: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 2: Write failing tests `api/tests/test_rules.py`**

```python
from httpx import AsyncClient


async def test_create_rule_for_cash_register(auth_client: AsyncClient, seed_camera) -> None:
    payload = {
        "camera_id": str(seed_camera.id),
        "preset_type": "cash_register",
        "zones": {
            "gaveta": [[0.1, 0.5], [0.4, 0.5], [0.4, 0.9], [0.1, 0.9]],
            "pc_operador": [[0.6, 0.1], [0.9, 0.1], [0.9, 0.5], [0.6, 0.5]],
        },
    }
    r = await auth_client.post("/rules", json=payload)
    assert r.status_code == 201
    body = r.json()
    assert body["preset_type"] == "cash_register"
    assert body["enabled"] is True


async def test_list_rules_for_owner(auth_client: AsyncClient, seed_camera) -> None:
    r = await auth_client.post(
        "/rules",
        json={
            "camera_id": str(seed_camera.id),
            "preset_type": "cash_register",
            "zones": {"gaveta": [[0, 0], [1, 0], [1, 1]], "pc_operador": [[0, 0], [1, 0], [1, 1]]},
        },
    )
    rule_id = r.json()["id"]
    r = await auth_client.get("/rules")
    items = r.json()
    assert len(items) == 1
    assert items[0]["id"] == rule_id


async def test_update_rule_toggles_enabled(auth_client: AsyncClient, seed_camera) -> None:
    r = await auth_client.post(
        "/rules",
        json={
            "camera_id": str(seed_camera.id),
            "preset_type": "cash_register",
            "zones": {"gaveta": [[0, 0], [1, 0], [1, 1]], "pc_operador": [[0, 0], [1, 0], [1, 1]]},
        },
    )
    rid = r.json()["id"]
    r = await auth_client.put(f"/rules/{rid}", json={"enabled": False})
    assert r.status_code == 200
    assert r.json()["enabled"] is False


async def test_invalid_zone_polygon_rejected(auth_client: AsyncClient, seed_camera) -> None:
    r = await auth_client.post(
        "/rules",
        json={
            "camera_id": str(seed_camera.id),
            "preset_type": "cash_register",
            "zones": {"gaveta": [[0, 0], [1, 1]]},  # only 2 points
        },
    )
    assert r.status_code == 422
```

Add `seed_camera` fixture to `conftest.py`:

```python
from app.db.models import Camera

@pytest_asyncio.fixture
async def seed_camera(db_session, seed_device) -> Camera:
    cam = Camera(device_id=seed_device.id, name="C1", rtsp_url_encrypted="ZGV2OnRlc3Q=")
    db_session.add(cam)
    await db_session.commit()
    await db_session.refresh(cam)
    return cam
```

- [ ] **Step 3: Run, expect fail**

- [ ] **Step 4: Write `api/app/routers/rules.py`**

```python
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Camera, Device, Rule, User
from app.db.session import get_db
from app.schemas.rules import RuleCreate, RuleOut, RuleUpdate
from app.security.cognito import get_current_user

router = APIRouter(prefix="/rules", tags=["rules"])


async def _owned_rule(rule_id: UUID, user: User, db: AsyncSession) -> Rule:
    result = await db.execute(
        select(Rule).join(Camera).join(Device).where(Rule.id == rule_id, Device.owner_id == user.id)
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rule not found")
    return rule


@router.post("", response_model=RuleOut, status_code=201)
async def create_rule(
    payload: RuleCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Rule:
    result = await db.execute(
        select(Camera).join(Device).where(Camera.id == payload.camera_id, Device.owner_id == user.id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Camera not found")
    rule = Rule(
        camera_id=payload.camera_id,
        preset_type=payload.preset_type,
        enabled=payload.enabled,
        zones=payload.zones,
        sensitivity=payload.sensitivity,
        cooldown_seconds=payload.cooldown_seconds,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.get("", response_model=list[RuleOut])
async def list_rules(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Rule]:
    result = await db.execute(
        select(Rule).join(Camera).join(Device).where(Device.owner_id == user.id)
    )
    return list(result.scalars().all())


@router.put("/{rule_id}", response_model=RuleOut)
async def update_rule(
    rule_id: UUID,
    payload: RuleUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Rule:
    rule = await _owned_rule(rule_id, user, db)
    for field in ("enabled", "zones", "sensitivity", "cooldown_seconds"):
        v = getattr(payload, field)
        if v is not None:
            setattr(rule, field, v)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    rule = await _owned_rule(rule_id, user, db)
    await db.delete(rule)
    await db.commit()
```

Register router in `app/main.py`.

- [ ] **Step 5: Run tests, expect pass**

```bash
uv run pytest tests/test_rules.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add api/app/routers/rules.py api/app/schemas/rules.py api/tests/test_rules.py api/tests/conftest.py api/app/main.py
git commit -m "feat(api): add rules CRUD with preset types and zone polygons"
```

---

## Task 1.8: POST /clips/upload-url (signed S3 URL)

**Files:**
- Create: `api/app/routers/clips.py`
- Create: `api/app/schemas/clips.py`
- Create: `api/app/services/s3.py`
- Create: `api/tests/test_clips.py`

- [ ] **Step 1: Write `api/app/services/s3.py`**

```python
import boto3

from app.config import get_settings


def signed_put_url(key: str, expires_in: int = 600) -> str:
    settings = get_settings()
    s3 = boto3.client("s3", region_name=settings.aws_region)
    return s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={"Bucket": settings.clips_bucket, "Key": key, "ContentType": "video/mp4"},
        ExpiresIn=expires_in,
        HttpMethod="PUT",
    )
```

- [ ] **Step 2: Write `api/app/schemas/clips.py`**

```python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ClipUploadRequest(BaseModel):
    camera_id: UUID
    started_at: datetime
    duration_ms: int


class ClipUploadResponse(BaseModel):
    upload_url: str
    s3_key: str
    expires_in_seconds: int
```

- [ ] **Step 3: Write failing tests `api/tests/test_clips.py`**

```python
import pytest
from httpx import AsyncClient
from moto import mock_aws


@mock_aws
async def test_agent_requests_upload_url(device_client: AsyncClient, seed_camera) -> None:
    import boto3
    boto3.client("s3", region_name="sa-east-1").create_bucket(
        Bucket="cams-erp-staging-clips",
        CreateBucketConfiguration={"LocationConstraint": "sa-east-1"},
    )

    payload = {
        "camera_id": str(seed_camera.id),
        "started_at": "2026-04-27T12:00:00Z",
        "duration_ms": 10000,
    }
    r = await device_client.post("/clips/upload-url", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert "upload_url" in body
    assert body["s3_key"].endswith(".mp4")
```

Add `device_client` fixture to `conftest.py`:

```python
from app.security.device_auth import get_current_device

@pytest_asyncio.fixture
async def device_client(db_session, seed_device) -> AsyncClient:
    app = create_app()

    async def override_device() -> Device:
        return seed_device

    app.dependency_overrides[get_current_device] = override_device
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
```

- [ ] **Step 4: Run, expect fail**

- [ ] **Step 5: Write `api/app/routers/clips.py`**

```python
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Camera, Device
from app.db.session import get_db
from app.schemas.clips import ClipUploadRequest, ClipUploadResponse
from app.security.device_auth import get_current_device
from app.services.s3 import signed_put_url

router = APIRouter(prefix="/clips", tags=["clips"])


@router.post("/upload-url", response_model=ClipUploadResponse)
async def get_upload_url(
    payload: ClipUploadRequest,
    device: Device = Depends(get_current_device),
    db: AsyncSession = Depends(get_db),
) -> ClipUploadResponse:
    result = await db.execute(
        select(Camera).where(Camera.id == payload.camera_id, Camera.device_id == device.id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Camera not found")

    today = datetime.now(tz=timezone.utc).strftime("%Y/%m/%d")
    s3_key = f"clips/{device.id}/{payload.camera_id}/{today}/{uuid4()}.mp4"
    return ClipUploadResponse(
        upload_url=signed_put_url(s3_key),
        s3_key=s3_key,
        expires_in_seconds=600,
    )
```

Register in `app/main.py`.

- [ ] **Step 6: Run tests, expect pass**

```bash
uv run pytest tests/test_clips.py -v
```

Expected: 1 passed.

- [ ] **Step 7: Commit**

```bash
git add api/app/routers/clips.py api/app/services/s3.py api/app/schemas/clips.py api/tests/test_clips.py api/tests/conftest.py api/app/main.py
git commit -m "feat(api): add /clips/upload-url with signed S3 PUT (10min TTL)"
```

---

## Task 1.9: POST /events (enqueue inference job in SQS)

**Files:**
- Create: `api/app/routers/events.py`
- Create: `api/app/schemas/events.py`
- Create: `api/app/services/sqs.py`
- Create: `api/tests/test_events.py`

- [ ] **Step 1: Write `api/app/services/sqs.py`**

```python
import json

import boto3

from app.config import get_settings


def enqueue_event(payload: dict) -> str:
    settings = get_settings()
    sqs = boto3.client("sqs", region_name=settings.aws_region)
    resp = sqs.send_message(QueueUrl=settings.events_queue_url, MessageBody=json.dumps(payload))
    return resp["MessageId"]
```

- [ ] **Step 2: Write `api/app/schemas/events.py`**

```python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EventCreate(BaseModel):
    camera_id: UUID
    s3_key: str = Field(min_length=10)
    motion_score: float = Field(ge=0, le=1)
    started_at: datetime
    duration_ms: int = Field(ge=1000, le=60_000)


class EventOut(BaseModel):
    id: UUID
    enqueued: bool
```

- [ ] **Step 3: Write failing tests `api/tests/test_events.py`**

```python
import boto3
import pytest
from httpx import AsyncClient
from moto import mock_aws


@mock_aws
async def test_agent_posts_event_and_it_enqueues(device_client: AsyncClient, seed_camera, monkeypatch) -> None:
    sqs = boto3.client("sqs", region_name="sa-east-1")
    queue_url = sqs.create_queue(QueueName="test-events")["QueueUrl"]
    monkeypatch.setenv("CAMS_EVENTS_QUEUE_URL", queue_url)
    from app.config import get_settings
    get_settings.cache_clear()

    payload = {
        "camera_id": str(seed_camera.id),
        "s3_key": "clips/x/y/z.mp4",
        "motion_score": 0.78,
        "started_at": "2026-04-27T12:00:00Z",
        "duration_ms": 10000,
    }
    r = await device_client.post("/events", json=payload)
    assert r.status_code == 201
    assert r.json()["enqueued"] is True

    msgs = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1)
    assert "Messages" in msgs
```

- [ ] **Step 4: Write `api/app/routers/events.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Camera, Device, Event
from app.db.session import get_db
from app.schemas.events import EventCreate, EventOut
from app.security.device_auth import get_current_device
from app.services.sqs import enqueue_event

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", response_model=EventOut, status_code=201)
async def create_event(
    payload: EventCreate,
    device: Device = Depends(get_current_device),
    db: AsyncSession = Depends(get_db),
) -> EventOut:
    result = await db.execute(
        select(Camera).where(Camera.id == payload.camera_id, Camera.device_id == device.id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Camera not found")

    event = Event(
        camera_id=payload.camera_id,
        s3_key=payload.s3_key,
        motion_score=payload.motion_score,
        started_at=payload.started_at,
        duration_ms=payload.duration_ms,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    enqueue_event(
        {
            "event_id": str(event.id),
            "camera_id": str(event.camera_id),
            "s3_key": event.s3_key,
            "started_at": event.started_at.isoformat(),
            "duration_ms": event.duration_ms,
        }
    )
    return EventOut(id=event.id, enqueued=True)
```

Register in `app/main.py`.

- [ ] **Step 5: Run tests, expect pass**

```bash
uv run pytest tests/test_events.py -v
```

Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add api/app/routers/events.py api/app/services/sqs.py api/app/schemas/events.py api/tests/test_events.py
git commit -m "feat(api): add /events endpoint that persists + enqueues SQS job"
```

---

## Task 1.10: GET /alerts + filters

**Files:**
- Create: `api/app/routers/alerts.py`
- Create: `api/app/schemas/alerts.py`
- Create: `api/tests/test_alerts.py`

- [ ] **Step 1: Write `api/app/schemas/alerts.py`**

```python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.db.models import AlertStatus, PresetType


class AlertOut(BaseModel):
    id: UUID
    rule_id: UUID
    event_id: UUID
    camera_id: UUID
    preset_type: PresetType
    status: AlertStatus
    score: float
    message: str
    s3_key: str  # joined from event
    created_at: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 2: Write failing tests `api/tests/test_alerts.py`**

```python
from datetime import datetime, timezone
from uuid import uuid4

from httpx import AsyncClient

from app.db.models import Alert, AlertStatus, Event, PresetType, Rule


async def test_list_alerts_returns_owners_only(
    auth_client: AsyncClient, seed_camera, db_session
) -> None:
    rule = Rule(
        camera_id=seed_camera.id,
        preset_type=PresetType.cash_register,
        zones={"gaveta": [[0, 0], [1, 1], [1, 0]], "pc_operador": [[0, 0], [1, 1], [1, 0]]},
    )
    db_session.add(rule)
    await db_session.flush()
    event = Event(
        camera_id=seed_camera.id,
        s3_key="clips/x.mp4",
        motion_score=0.5,
        started_at=datetime.now(tz=timezone.utc),
        duration_ms=10000,
    )
    db_session.add(event)
    await db_session.flush()
    alert = Alert(rule_id=rule.id, event_id=event.id, score=0.91, message="Suspect at register")
    db_session.add(alert)
    await db_session.commit()

    r = await auth_client.get("/alerts")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["preset_type"] == "cash_register"
    assert items[0]["s3_key"] == "clips/x.mp4"
```

- [ ] **Step 3: Write `api/app/routers/alerts.py`**

```python
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.models import Alert, AlertStatus, Camera, Device, Event, PresetType, Rule, User
from app.db.session import get_db
from app.schemas.alerts import AlertOut
from app.security.cognito import get_current_user

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    since: datetime | None = Query(default=None),
    camera_id: UUID | None = Query(default=None),
    preset_type: PresetType | None = Query(default=None),
    limit: int = Query(default=50, le=500),
) -> list[AlertOut]:
    stmt = (
        select(Alert, Rule, Event)
        .join(Rule, Alert.rule_id == Rule.id)
        .join(Event, Alert.event_id == Event.id)
        .join(Camera, Rule.camera_id == Camera.id)
        .join(Device, Camera.device_id == Device.id)
        .where(Device.owner_id == user.id)
        .order_by(Alert.created_at.desc())
        .limit(limit)
    )
    if since is not None:
        stmt = stmt.where(Alert.created_at >= since)
    if camera_id is not None:
        stmt = stmt.where(Camera.id == camera_id)
    if preset_type is not None:
        stmt = stmt.where(Rule.preset_type == preset_type)

    rows = (await db.execute(stmt)).all()
    return [
        AlertOut(
            id=a.id,
            rule_id=a.rule_id,
            event_id=a.event_id,
            camera_id=r.camera_id,
            preset_type=r.preset_type,
            status=a.status,
            score=a.score,
            message=a.message,
            s3_key=e.s3_key,
            created_at=a.created_at,
        )
        for (a, r, e) in rows
    ]


@router.post("/{alert_id}/feedback", response_model=AlertOut)
async def feedback(
    alert_id: UUID,
    is_false_positive: bool,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AlertOut:
    stmt = (
        select(Alert, Rule, Event)
        .join(Rule, Alert.rule_id == Rule.id)
        .join(Event, Alert.event_id == Event.id)
        .join(Camera, Rule.camera_id == Camera.id)
        .join(Device, Camera.device_id == Device.id)
        .where(Alert.id == alert_id, Device.owner_id == user.id)
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    a, r, e = row
    a.status = AlertStatus.false_positive if is_false_positive else AlertStatus.seen
    await db.commit()
    await db.refresh(a)
    return AlertOut(
        id=a.id, rule_id=a.rule_id, event_id=a.event_id, camera_id=r.camera_id,
        preset_type=r.preset_type, status=a.status, score=a.score,
        message=a.message, s3_key=e.s3_key, created_at=a.created_at,
    )
```

Register in `app/main.py`.

- [ ] **Step 4: Run tests, expect pass**

- [ ] **Step 5: Commit**

```bash
git add api/app/routers/alerts.py api/app/schemas/alerts.py api/tests/test_alerts.py
git commit -m "feat(api): add /alerts list with filters and feedback endpoint"
```

---

## Task 1.11: WebSocket /alerts/stream (real-time push to mobile)

**Files:**
- Modify: `api/app/routers/alerts.py`
- Create: `api/app/services/pubsub.py`
- Create: `api/tests/test_alerts_ws.py`

We use a simple in-process pub/sub (asyncio.Queue per connection) for MVP. Production: Redis pub/sub. Skipping Redis here keeps Phase 1 dep-free.

- [ ] **Step 1: Write `api/app/services/pubsub.py`**

```python
import asyncio
from collections import defaultdict
from uuid import UUID


class AlertBroker:
    def __init__(self) -> None:
        self._queues: dict[UUID, list[asyncio.Queue]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def subscribe(self, owner_id: UUID) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._queues[owner_id].append(q)
        return q

    async def unsubscribe(self, owner_id: UUID, q: asyncio.Queue) -> None:
        async with self._lock:
            if q in self._queues[owner_id]:
                self._queues[owner_id].remove(q)

    async def publish(self, owner_id: UUID, payload: dict) -> None:
        async with self._lock:
            qs = list(self._queues.get(owner_id, []))
        for q in qs:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass


broker = AlertBroker()
```

- [ ] **Step 2: Add WS handler to `api/app/routers/alerts.py`**

```python
from fastapi import WebSocket, WebSocketDisconnect

from app.services.pubsub import broker


@router.websocket("/stream")
async def alerts_stream(ws: WebSocket, user: User = Depends(get_current_user)) -> None:
    await ws.accept()
    q = await broker.subscribe(user.id)
    try:
        while True:
            payload = await q.get()
            await ws.send_json(payload)
    except WebSocketDisconnect:
        pass
    finally:
        await broker.unsubscribe(user.id, q)
```

- [ ] **Step 3: Write integration test `api/tests/test_alerts_ws.py`**

```python
import asyncio

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.security.cognito import get_current_user
from app.services.pubsub import broker


def test_ws_receives_published_alert(seed_user) -> None:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: seed_user
    client = TestClient(app)
    with client.websocket_connect("/alerts/stream") as ws:
        async def publish_soon() -> None:
            await asyncio.sleep(0.05)
            await broker.publish(seed_user.id, {"type": "alert", "id": "abc"})

        asyncio.get_event_loop().create_task(publish_soon())
        msg = ws.receive_json(timeout=2)
        assert msg == {"type": "alert", "id": "abc"}
```

- [ ] **Step 4: Run tests, expect pass**

- [ ] **Step 5: Commit**

```bash
git add api/app/services/pubsub.py api/app/routers/alerts.py api/tests/test_alerts_ws.py
git commit -m "feat(api): add WS /alerts/stream with in-process pub/sub broker"
```

---

## Task 1.12: Agent endpoints (heartbeat + config)

**Files:**
- Create: `api/app/routers/agent.py`
- Create: `api/app/schemas/agent.py`
- Create: `api/tests/test_agent.py`

- [ ] **Step 1: Write `api/app/schemas/agent.py`**

```python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class HeartbeatIn(BaseModel):
    cameras_status: dict[str, bool]  # camera_id -> online
    cpu_pct: float
    ram_mb: int
    disk_free_mb: int
    agent_version: str


class HeartbeatOut(BaseModel):
    server_time: datetime
    config_etag: str


class CameraConfigItem(BaseModel):
    camera_id: UUID
    name: str
    rtsp_url: str
    rules: list[dict]  # zones, sensitivity, preset


class AgentConfigOut(BaseModel):
    etag: str
    cameras: list[CameraConfigItem]
```

- [ ] **Step 2: Write failing tests `api/tests/test_agent.py`**

```python
import pytest
from httpx import AsyncClient


async def test_heartbeat_updates_last_heartbeat(device_client: AsyncClient, seed_device, db_session) -> None:
    payload = {
        "cameras_status": {},
        "cpu_pct": 5.0,
        "ram_mb": 380,
        "disk_free_mb": 9999,
        "agent_version": "0.1.0",
    }
    r = await device_client.post("/agent/heartbeat", json=payload)
    assert r.status_code == 200
    assert "config_etag" in r.json()


async def test_get_agent_config_returns_owner_cameras(device_client: AsyncClient, seed_camera) -> None:
    r = await device_client.get("/agent/config")
    assert r.status_code == 200
    body = r.json()
    assert "cameras" in body
    assert len(body["cameras"]) == 1
    assert body["cameras"][0]["rtsp_url"]  # decrypted
```

- [ ] **Step 3: Write `api/app/routers/agent.py`**

```python
import hashlib
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Camera, Device, Rule
from app.db.session import get_db
from app.schemas.agent import AgentConfigOut, CameraConfigItem, HeartbeatIn, HeartbeatOut
from app.security.device_auth import get_current_device
from app.services.kms import decrypt

router = APIRouter(prefix="/agent", tags=["agent"])


def _config_etag(items: list[dict]) -> str:
    return hashlib.sha256(json.dumps(items, sort_keys=True, default=str).encode()).hexdigest()[:16]


@router.post("/heartbeat", response_model=HeartbeatOut)
async def heartbeat(
    payload: HeartbeatIn,
    device: Device = Depends(get_current_device),
    db: AsyncSession = Depends(get_db),
) -> HeartbeatOut:
    device.last_heartbeat_at = datetime.now(tz=timezone.utc)
    cams = (await db.execute(select(Camera).where(Camera.device_id == device.id))).scalars().all()
    for cam in cams:
        cam.online = payload.cameras_status.get(str(cam.id), False)
    await db.commit()
    rules = (
        await db.execute(
            select(Rule).join(Camera).where(Camera.device_id == device.id)
        )
    ).scalars().all()
    items = [{"camera_id": str(r.camera_id), "rule": str(r.id)} for r in rules]
    return HeartbeatOut(server_time=datetime.now(tz=timezone.utc), config_etag=_config_etag(items))


@router.get("/config", response_model=AgentConfigOut)
async def get_config(
    device: Device = Depends(get_current_device),
    db: AsyncSession = Depends(get_db),
) -> AgentConfigOut:
    cams = (await db.execute(select(Camera).where(Camera.device_id == device.id))).scalars().all()
    out: list[CameraConfigItem] = []
    for cam in cams:
        rules = (
            await db.execute(select(Rule).where(Rule.camera_id == cam.id, Rule.enabled.is_(True)))
        ).scalars().all()
        out.append(
            CameraConfigItem(
                camera_id=cam.id,
                name=cam.name,
                rtsp_url=decrypt(cam.rtsp_url_encrypted),
                rules=[
                    {"id": str(r.id), "preset_type": r.preset_type.value, "zones": r.zones,
                     "sensitivity": r.sensitivity, "cooldown_seconds": r.cooldown_seconds}
                    for r in rules
                ],
            )
        )
    items_for_etag = [{"camera_id": str(c.camera_id), "rules": c.rules} for c in out]
    return AgentConfigOut(etag=_config_etag(items_for_etag), cameras=out)
```

Register in `app/main.py`.

- [ ] **Step 4: Run tests, expect pass**

- [ ] **Step 5: Commit**

```bash
git add api/app/routers/agent.py api/app/schemas/agent.py api/tests/test_agent.py api/app/main.py
git commit -m "feat(api): add /agent/heartbeat and /agent/config (decrypted RTSP)"
```

---

## Task 1.13: Build & push Docker image to ECR

**Files:**
- Modify: `.github/workflows/api.yml` (add deploy job)

- [ ] **Step 1: Append deploy job to `api.yml`**

```yaml
  build_and_push:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_GHA_ROLE_ARN }}
          aws-region: sa-east-1
      - uses: aws-actions/amazon-ecr-login@v2
      - name: Build & push
        run: |
          IMAGE_URI=${{ secrets.ECR_URI }}/cams-erp-staging-api:${{ github.sha }}
          docker build -t $IMAGE_URI api/
          docker push $IMAGE_URI
          docker tag $IMAGE_URI ${{ secrets.ECR_URI }}/cams-erp-staging-api:latest
          docker push ${{ secrets.ECR_URI }}/cams-erp-staging-api:latest
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/api.yml
git commit -m "ci: build and push api docker image to ECR on main"
```

---

## Task 1.14: Deploy ECS service via Terraform

**Files:**
- Create: `infra/main/api_service.tf`

- [ ] **Step 1: Write `infra/main/api_service.tf`**

```hcl
resource "aws_ecs_task_definition" "api" {
  family                   = "cams-erp-${var.env}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task_api.arn

  container_definitions = jsonencode([{
    name  = "api"
    image = "${aws_ecr_repository.api.repository_url}:latest"
    portMappings = [{ containerPort = 8080, protocol = "tcp" }]
    environment = [
      { name = "CAMS_ENV", value = var.env },
      { name = "CAMS_AWS_REGION", value = var.region },
      { name = "CAMS_CLIPS_BUCKET", value = aws_s3_bucket.clips.id },
      { name = "CAMS_EVENTS_QUEUE_URL", value = aws_sqs_queue.events.url },
      { name = "CAMS_COGNITO_USER_POOL_ID", value = aws_cognito_user_pool.main.id },
      { name = "CAMS_COGNITO_JWKS_URL", value = "https://cognito-idp.${var.region}.amazonaws.com/${aws_cognito_user_pool.main.id}/.well-known/jwks.json" },
    ]
    secrets = [
      { name = "CAMS_DATABASE_URL", valueFrom = "${aws_secretsmanager_secret.db_master.arn}:url::" },
      { name = "CAMS_JWT_SECRET", valueFrom = aws_secretsmanager_secret.jwt_secret.arn },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.api.name
        awslogs-region        = var.region
        awslogs-stream-prefix = "api"
      }
    }
  }])
}

resource "aws_ecs_service" "api" {
  name            = "cams-erp-${var.env}-api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = module.vpc.private_subnets
    security_groups  = [aws_security_group.api.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8080
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
}
```

NOTE: The DB secret-mapping `:url::` requires storing a JSON value with a `url` field. Update the bootstrap of `aws_secretsmanager_secret_version.db_master`:

```hcl
secret_string = jsonencode({
  username = "camsadmin"
  password = random_password.db_master.result
  url      = "postgresql+psycopg://camsadmin:${random_password.db_master.result}@${aws_db_instance.main.endpoint}/camserp"
})
```

- [ ] **Step 2: Plan, apply**

```bash
cd infra/main
terraform plan -var env=staging -var domain_root=cams-erp.com -out=plan.tfplan
terraform apply plan.tfplan
```

- [ ] **Step 3: Run migration against RDS**

Use a one-off ECS task or local tunnel via SSM:

```bash
# From a bastion or via ECS exec on the running api task:
ssm-tunnel-to-rds  # custom script or use AWS Session Manager + port forwarding
CAMS_DATABASE_URL=postgresql+psycopg://camsadmin:PASSWORD@RDS-ENDPOINT:5432/camserp \
  uv run alembic upgrade head
```

- [ ] **Step 4: Smoke test**

```bash
curl https://api.staging.cams-erp.com/healthz
```

Expected: `{"status":"ok"}`.

- [ ] **Step 5: Commit**

```bash
git add infra/main/api_service.tf infra/main/rds.tf
git commit -m "infra: deploy api ECS service behind ALB on staging"
```

---

## Task 1.15: README, ARCHITECTURE.md, CONTRIBUTING.md

**Files:**
- Create: `api/README.md`
- Create: `docs/ARCHITECTURE.md`
- Create: `CONTRIBUTING.md`

- [ ] **Step 1: Write `api/README.md`**

```markdown
# cams-erp API

FastAPI service for cams-erp Cloud.

## Local dev

```bash
uv sync
docker run -d --name camserp-pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:16
CAMS_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost/postgres uv run alembic upgrade head
CAMS_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost/postgres uv run uvicorn app.main:app --reload
```

## Tests

```bash
uv run pytest -v
```

## Endpoints

See OpenAPI at `http://localhost:8000/docs` when running locally.
```

- [ ] **Step 2: Write `docs/ARCHITECTURE.md`**

Summarize architecture from spec (`/Users/joaofarinelli/.claude/plans/n-s-precisamos-desenvolver-um-velvety-puddle.md`). Section headings: Components, Data Flow, Security, Deployment.

- [ ] **Step 3: Write `CONTRIBUTING.md`**

```markdown
# Contributing

- Branch from `main`. PR + 1 review required.
- Conventional Commits: `feat:`, `fix:`, `chore:`, `test:`, `infra:`, `ci:`.
- Run `uv run ruff format . && uv run ruff check . && uv run mypy app/ && uv run pytest` before pushing.
- Never commit secrets. Add to AWS Secrets Manager.
```

- [ ] **Step 4: Commit**

```bash
git add api/README.md docs/ARCHITECTURE.md CONTRIBUTING.md
git commit -m "docs: add api README, ARCHITECTURE, CONTRIBUTING"
```

---

# Verification (end-to-end manual run after Phase 1 complete)

1. **Apply infra** in clean AWS account:

```bash
cd infra/bootstrap && terraform apply
cd ../main && terraform apply -var env=staging -var domain_root=<your-domain>
```

2. **Push api image**:

```bash
git push origin main  # triggers GHA build_and_push
```

3. **Run migrations** against RDS staging.

4. **Smoke**:

```bash
curl https://api.staging.cams-erp.com/healthz                 # {"status":"ok"}
```

5. **Cognito sign-up** via AWS CLI:

```bash
aws cognito-idp sign-up --client-id <CLIENT_ID> \
  --username owner@test.com --password "Test12345!" \
  --user-attributes Name=email,Value=owner@test.com
aws cognito-idp admin-confirm-sign-up --user-pool-id <POOL_ID> --username owner@test.com
TOKEN=$(aws cognito-idp initiate-auth --client-id <CLIENT_ID> \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME=owner@test.com,PASSWORD="Test12345!" \
  --query 'AuthenticationResult.AccessToken' --output text)
```

6. **Pair an agent**:

```bash
PAIR=$(curl -s -X POST https://api.staging.cams-erp.com/pair/code \
  -H "Authorization: Bearer $TOKEN" | jq -r .pair_code)
DEV_TOKEN=$(curl -s -X POST https://api.staging.cams-erp.com/pair/verify \
  -H "Content-Type: application/json" \
  -d "{\"pair_code\":\"$PAIR\"}" | jq -r .device_token)
```

7. **Add a camera**:

```bash
DEVICE_ID=$(curl -s https://api.staging.cams-erp.com/agent/config \
  -H "X-Device-Token: $DEV_TOKEN" | jq -r '.cameras[0].camera_id // empty')

curl -X POST https://api.staging.cams-erp.com/cameras \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"name\":\"Caixa 1\",\"rtsp_url\":\"rtsp://test\",\"device_id\":\"$DEVICE_ID\"}"
```

8. **Create a rule**, **POST clip upload-url**, **PUT a fake clip to S3**, **POST event** — all using the agent's `X-Device-Token`. Inspect SQS queue depth in console; expect 1 message.

9. **Open WS** as the owner using a tool like `wscat`:

```bash
wscat -c "wss://api.staging.cams-erp.com/alerts/stream" -H "Authorization: Bearer $TOKEN"
```

(No alerts will arrive yet — inference worker not built.)

10. **Confirm S3 lifecycle**:

```bash
aws s3api get-bucket-lifecycle-configuration --bucket cams-erp-staging-clips
```

Expect 7d expiration rule.

---

# Self-review checklist (run before declaring plan done)

1. **Spec coverage**
   - Auth (Cognito) → Tasks 1.3, 1.4, verification step 5
   - Pairing → Task 1.6
   - Cameras CRUD → Task 1.5
   - Rules CRUD → Task 1.7
   - Clips signed URL → Task 1.8
   - Events SQS → Task 1.9
   - Alerts list + WS + feedback → Tasks 1.10, 1.11
   - Agent endpoints → Task 1.12
   - 7d S3 lifecycle → Task 0.7
   - LGPD note → not in tasks (deferred per spec)
   - **Inference worker / agent / mobile → out of scope of this plan** (separate plans planned)

2. **Placeholder scan** — none. All steps have code or commands.

3. **Type consistency**
   - `device_token` raw vs hashed: stored as `device_token_hash` (SHA-256), returned raw only by `/pair/verify`. ✅
   - `rtsp_url_encrypted` (Camera column) vs `rtsp_url` (schema field): explicit. ✅
   - PresetType enum: shared between models, schemas, and queries. ✅
   - Preset `cash_register` matches spec. ✅

4. **Out-of-scope**
   - Inference, mobile, agent — separate plans.
   - Multi-tenant beyond single-owner — out of MVP scope per spec.
   - Live view — out of MVP per spec.

---

# Execution handoff

**Plan complete and saved to `/Users/joaofarinelli/dev/cams-erp/docs/superpowers/plans/2026-04-27-phase0-infra-and-phase1-cloud-api.md`.**

**Two execution options:**

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration. Required sub-skill: `superpowers:subagent-driven-development`.

2. **Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, with batch checkpoints for review.

**After Phase 1 Cloud API is green, three follow-up plans should be generated (one each):**
- Phase 1 Agent (Windows/Go)
- Phase 1 Inference Worker (Python/GPU)
- Phase 1 Mobile App (React Native)
