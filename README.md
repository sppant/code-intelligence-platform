# Code Intelligence Platform

Analyzes public Git repositories and builds a structured, queryable representation of their codebase — architecture, dependencies, symbols, and change impact.

> **Status:** Day 3 complete — repo ingestion, language detection, AST/tree-sitter symbol extraction, a module-level dependency graph, a (same-file + import-resolved) call graph, circular-dependency detection, architecture insights (fan-in/out, large/isolated files), and change-impact analysis, all persisted and queryable through GraphQL, with a Repository Overview, Code Explorer, interactive Architecture Graph, Architecture Insights, and Impact Analysis in the React UI — plus live-feeling job progress via polling. No Docker/Redis anywhere in the stack (see "Background jobs without a queue" below) -- it runs on plain Node + Python + PostgreSQL, matching the target shared-hosting deployment. Incremental analysis, performance benchmarks, and the AI layer are later milestones.

## Architecture

```
React / TypeScript / Vite  →  Python / FastAPI / GraphQL  →  PostgreSQL
```

No Docker, no Redis, no message broker. The target production environment is shared Plesk hosting, which doesn't support custom daemons or containers, so the architecture is deliberately plain: a Python web process and a Postgres database, nothing else required to run it. See "Background jobs" below for how analysis work still happens off the request path without a queue.

The Python analysis engine (`analysis-engine/`) is the deterministic source of truth. It parses source with real ASTs (`tree-sitter` for TS/JS, the stdlib `ast` module for Python), extracts top-level symbols (functions/classes/variables/interfaces/type-aliases) and import/export edges, and resolves those edges into a module-level dependency graph — it can answer structural questions like "what does this module depend on" entirely on its own, with no database and no LLM involved. (Call-graph resolution -- "who calls this function" -- is Day 3.) The backend persists what the engine produces; an optional AI layer (future work) only explains results the engine already computed — it never originates structural facts.

```
Repository URL
      │
      ▼
GraphQL mutation (backend) ──creates──▶ analysis_jobs row (pending)
                                                │
                                                ▼
                                   BackgroundTasks.add_task
                                   (same process, after the response is sent)
                                                │
                                                ▼
                              claim (atomic UPDATE, see jobs/claims.py)
                                                │
                         ┌──────────────────────┼───────────────────────┐
                         │                      │                       │
                 normal in-process      app startup reconciles   cron sweep script
                 request path           any stuck pending/        (jobs/sweep.py) re-claims
                                         stale-running job         anything still stuck
                         │                      │                       │
                         └──────────────────────┴───────────────────────┘
                                                ▼
                              analysis-engine (no DB access):
                              clone → detect languages → parse → extract symbols/imports → resolve graph
                                                │
                                                ▼
                    persists Analysis + File + Symbol + DependencyEdge rows, job → completed/failed
```

### Background jobs without a queue

Shared Plesk hosting runs Python apps under Passenger, which can recycle the web process between requests — so a plain in-memory background task isn't *guaranteed* to run to completion. Three things work together instead of a Redis/Celery-style queue:

1. **In-process task** (`backend/src/backend/jobs/tasks.py::run_analysis_job`) — the `analyzeRepository` mutation schedules it via FastAPI's `BackgroundTasks`, so it runs in the same process right after the response is sent. This is the fast path for the overwhelming majority of requests.
2. **Startup reconciliation** (`main.py`'s `lifespan`) — on every process start, re-claims any job still `pending` or stuck `running` past the staleness threshold, so a process recycle mid-job just delays it rather than losing it.
3. **Cron sweep** (`backend/src/backend/jobs/sweep.py`) — a standalone script, meant to be invoked periodically by Plesk's Scheduled Tasks, that does the same reconciliation independently of the web process's lifecycle. Backstops the (unlikely but possible) case where no web request restarts the process for a while.

All three funnel through one atomic claim (`backend/src/backend/jobs/claims.py`): `UPDATE analysis_jobs SET status='running', started_at=now() WHERE status='pending' OR (status='running' AND started_at < now() - staleness_threshold) RETURNING id`. Postgres row-level locking makes this safe against two of these three paths firing at the same moment — the loser's `WHERE` no longer matches the row the winner just updated.

This also means Docker/a real queue can be introduced later without a rewrite: `run_analysis_job`/`execute_claimed_job` are plain async functions with no framework coupling — wrapping one in an arq/Celery task body later is a small, additive change, not a redesign.

## Local development

Requires Node.js, a Python toolchain with [uv](https://docs.astral.sh/uv/), and a local PostgreSQL server — no Docker.

```bash
# 1. Frontend dependencies
cd frontend && pnpm install && cd ..

# 2. Python dependencies (uv workspace covers backend + analysis-engine)
uv sync

# 3. Environment variables
cp .env.example .env   # edit DATABASE_URL if your local Postgres differs

# 4. Start Postgres and create the database (macOS/Homebrew shown; adjust for your OS)
brew install postgresql@16   # if not already installed
brew services start postgresql@16
psql postgres -c "CREATE USER cip WITH PASSWORD 'cip_dev_password' CREATEDB;"
createdb -O cip cip

# 5. Run database migrations
cd backend && uv run alembic upgrade head && cd ..

# 6. Start the backend
cd backend && uv run uvicorn backend.main:app --reload --port 8000 && cd ..

# 7. Start the frontend (separate terminal)
cd frontend && pnpm dev
```

- Frontend: http://localhost:5173
- Backend REST health check: http://localhost:8000/health
- Backend GraphQL: http://localhost:8000/graphql

Try it: paste `https://github.com/pypa/sampleproject` into the landing page and click "Analyze Repository" — the page polls job status and automatically navigates to the Repository Overview once analysis completes, from which the Code Explorer (file tree + per-file symbols + search) and Architecture Graph (interactive, click-to-highlight) tabs are reachable. Or run the mutation directly:

```bash
curl -s -X POST http://localhost:8000/graphql -H "Content-Type: application/json" \
  -d '{"query":"mutation($url: String!) { analyzeRepository(repoUrl: $url) { id status } }","variables":{"url":"https://github.com/pypa/sampleproject"}}'
```

Poll the job (or just check Postgres) until `status` is `completed` — no worker process to start, the backend alone will finish it:

```bash
psql -U cip -d cip -h localhost -c "select status from analysis_jobs order by created_at desc limit 1;"
```

## Deploying to Plesk

- **Frontend:** `pnpm build` in `frontend/`, serve the resulting `dist/` as static files (Plesk's docroot or its Node.js extension).
- **Backend:** run under Plesk's Python application support (Passenger), app entry point `backend.main:app`. Install dependencies into the venv Plesk manages — Plesk's Python tooling expects pip-installable requirements, so export them from `uv` (`uv export --project backend --no-dev > requirements.txt`) rather than driving `uv` itself in that environment.
- **Database:** Plesk's hosted PostgreSQL (or an external managed instance). Run `alembic upgrade head` once per deploy.
- **Environment variables:** set via Plesk's "Environment Variables" panel for the app, matching `.env.example`.
- **Background jobs:** register `jobs/sweep.py` as a Plesk Scheduled Task, e.g. every 5 minutes (comfortably under the 10-minute staleness default):
  ```
  */5 * * * * cd /var/www/vhosts/<domain>/backend && .venv/bin/python -m backend.jobs.sweep >> ../logs/sweep.log 2>&1
  ```

## Monorepo layout

- `frontend/` — React + TypeScript + Vite UI, GraphQL via `urql`.
- `backend/` — FastAPI + Strawberry GraphQL API, SQLAlchemy/Alembic persistence, in-process background tasks (see above). The **only** component that talks to Postgres.
- `analysis-engine/` — pure Python library with no database dependency: repository ingestion (validated clone, size/timeout guards), language detection, per-file parsing, and symbol/import extraction resolved into a module-level dependency graph. Usable standalone (CLI, tests) without the web app.

## Testing

```bash
uv run --project analysis-engine pytest analysis-engine/tests
uv run --project backend pytest backend/tests   # exercises the real local Postgres
```

Fixture-free for now — tests exercise the clone/validation logic, language detection, both parsers (`ast` for Python, `tree-sitter` for TS/JS), symbol/import extraction and path resolution (Python absolute/relative imports, TS/JS relative specifiers with index-file fallback, external/unresolved imports), the job-claiming logic (including a concurrency test that two simultaneous claims on one job resolve to exactly one winner), and the GraphQL resolvers (nested analysis shape, symbol search) directly against a real local Postgres. Repo-level fixtures and Playwright E2E tests land with later milestones.

## Known limitations

Import resolution is repo-root-relative only: a Python `src/` layout (import paths resolved via an installed package, not the physical directory tree) or a TypeScript path alias (`tsconfig.json` `paths`, workspace packages) won't resolve to an in-repo file even when the dependency is real -- it's recorded as an external/unresolved edge instead. Symbol extraction is top-level only (no nested functions/methods as their own symbols). See `analysis_engine/extraction/resolution.py`.

The call graph only resolves plain-name calls (`foo()`) to a same-file or import-resolved top-level function/class -- method/attribute calls (`obj.method()`) are never resolved (no type inference), and neither are Python star imports (`from x import *`) or TypeScript default/namespace imports, since none of those can be statically bound to a specific name without guessing. "Architectural boundary violations" from the original spec's wishlist isn't attempted -- it needs a concept of user-defined architectural layers this project doesn't have. All of this is deliberate scope, not an oversight -- see `analysis_engine/extraction/call_resolution.py` and `analysis_engine/graph/insights.py`.

## Security model

Repositories are untrusted input. Today's guards: strict URL validation (must be `https://github.com/<owner>/<repo>`, reconstructed into a canonical clone URL rather than ever passed raw to a shell), `git clone` via an explicit argument list (no `shell=True`), a hard clone timeout, a post-clone size cap, and job-scoped scratch directories that are always cleaned up. Sandboxed execution, rate limiting, secret scanning, and a full threat model are deferred to a later hardening pass.

## Environment variables

See `.env.example`. `MAX_REPO_SIZE_MB` and `CLONE_TIMEOUT_SECONDS` bound the ingestion step; `STALE_JOB_THRESHOLD_MINUTES` controls the background-job staleness window described above; `VITE_GRAPHQL_URL` is read by the Vite dev server.
