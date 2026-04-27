# Contributing

- Branch from `main`. PR + 1 review required.
- Conventional Commits: `feat:`, `fix:`, `chore:`, `test:`, `infra:`, `ci:`, `docs:`.
- Run `uv run ruff format . && uv run ruff check . && uv run mypy app/ && uv run pytest` before pushing.
- Never commit secrets. Add to AWS Secrets Manager.
