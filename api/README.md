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
