# Code Intelligence Platform

Analyzes public Git repositories and builds a structured, queryable representation of their codebase — architecture, dependencies, symbols, and change impact.

> **Status:** Day 1 foundation complete — repo ingestion, language detection, and a shallow per-file parse pass, end to end through a GraphQL API and a React UI. Full AST symbol extraction, the dependency graph, impact analysis, and the AI layer are later milestones.

## Architecture principle

The Python analysis engine (`analysis-engine/`) is the deterministic source of truth. It parses source with real ASTs (`tree-sitter` for TS/JS, the stdlib `ast` module for Python) and will build an explicit code graph from that — it can answer structural questions like "who calls this function" or "what depends on this module" entirely on its own, with no database and no LLM involved. The backend persists what the engine produces; an optional AI layer (future work) only explains results the engine already computed — it never originates structural facts.

```
Repository URL
      │
      ▼
GraphQL mutation (backend) ──creates──▶ analysis_jobs row ──enqueues──▶ arq job
                                                                           │
                                                                           ▼
                                                      analysis-engine (no DB access):
                                                      clone → detect languages → parse
                                                                           │
                                                                           ▼
                                                      worker persists Analysis + File rows
```

## Local development

Requires Docker. First time:

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml --env-file .env up --build
docker compose -f infra/docker-compose.yml --env-file .env exec backend uv run alembic upgrade head
```

- Frontend: http://localhost:5173
- Backend REST health check: http://localhost:8000/health
- Backend GraphQL (with playground): http://localhost:8000/graphql
- Postgres is exposed on the host at `localhost:5433` (not 5432) to avoid colliding with a locally-installed Postgres; containers talk to each other over the internal `postgres:5432` address regardless.

Try it: paste `https://github.com/pypa/sampleproject` into the landing page and click "Analyze Repository" — or run the mutation directly:

```bash
curl -s -X POST http://localhost:8000/graphql -H "Content-Type: application/json" \
  -d '{"query":"mutation($url: String!) { analyzeRepository(repoUrl: $url) { id status } }","variables":{"url":"https://github.com/pypa/sampleproject"}}'
```

Poll the job (or just check Postgres) until `status` is `completed`:

```bash
docker exec infra-postgres-1 psql -U cip -d cip -c "select status from analysis_jobs order by created_at desc limit 1;"
```

## Monorepo layout

- `frontend/` — React + TypeScript + Vite UI, GraphQL via `urql`.
- `backend/` — FastAPI + Strawberry GraphQL API, SQLAlchemy/Alembic persistence, `arq` background worker. The **only** component that talks to Postgres.
- `analysis-engine/` — pure Python library with no database dependency: repository ingestion (validated clone, size/timeout guards), language detection, and per-file parsing. Usable standalone (CLI, tests) without the web app.
- `infra/` — Docker Compose for local development.

## Testing

```bash
uv run --project analysis-engine pytest analysis-engine/tests
uv run --project backend pytest backend/tests
```

Fixture-free for now — tests exercise the clone/validation logic, language detection, and both parsers (`ast` for Python, `tree-sitter` for TS/JS) directly against in-memory/tmp-dir inputs. Repo-level fixtures and Playwright E2E tests land with the Day 3–4 milestones.

## Security model (Day 1 scope)

Repositories are untrusted input. Today's guards: strict URL validation (must be `https://github.com/<owner>/<repo>`, reconstructed into a canonical clone URL rather than ever passed raw to a shell), `git clone` via an explicit argument list (no `shell=True`), a hard clone timeout, a post-clone size cap, and job-scoped scratch directories that are always cleaned up. Sandboxed execution, rate limiting, secret scanning, and a full threat model are deferred to a later hardening pass — see the build plan for the complete list.

## Environment variables

See `.env.example`. `MAX_REPO_SIZE_MB` and `CLONE_TIMEOUT_SECONDS` bound the ingestion step; `VITE_GRAPHQL_URL` is read by the Vite dev server (must be set at container/process start, not just in a `.env` file inside `frontend/`).
