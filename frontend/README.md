# Frontend

React 19 + TypeScript + Vite UI for the Code Intelligence Platform. See the [root README](../README.md) for what the project does, how to run the full stack, and the architecture.

```bash
pnpm install
pnpm dev            # http://localhost:5173 (expects the backend at VITE_GRAPHQL_URL)
pnpm build          # tsc -b && vite build
pnpm lint           # oxlint
pnpm test:e2e       # Playwright critical-flow test (needs backend + Postgres running)
```

Routes (`src/App.tsx`): landing/history, repository overview, Code Explorer, Architecture Graph, Architecture Insights, and per-symbol Impact Analysis. Data access goes through `urql` (`src/graphql/`).
