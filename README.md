# Code Intelligence Platform

Analyzes public Git repositories and builds a structured, queryable representation of their codebase — architecture, dependencies, symbols, and change impact.

> Status: Day 1 foundation in progress.

## Architecture principle

The Python analysis engine (AST parsing + dependency graph construction) is the deterministic source of truth. It can answer structural questions — "who calls this function", "what depends on this module" — entirely on its own. The optional AI layer only explains results the engine already produced; it never originates structural facts.

## Monorepo layout

- `frontend/` — React + TypeScript + Vite UI
- `backend/` — FastAPI + Strawberry GraphQL API, Postgres persistence, arq background worker
- `analysis-engine/` — pure Python library: repo ingestion, language detection, parsing, dependency graph (no DB dependency)
- `infra/` — Docker Compose for local development
