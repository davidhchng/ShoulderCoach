# ShoulderCoach

Monorepo: `backend/` (FastAPI + SQLite) and `frontend/` (Next.js 16, app router).

## Backend

Run from `backend/`: `uvicorn app.main:app`
Tests: `python -m pytest tests/ -q`
Seed (1-2 hrs, run once): `python -m app.data.seed`

Key files:
- `app/engine/base.py` — DecisionResult dataclass + DecisionEngine ABC
- `app/engine/registry.py` — maps decision_type string to engine class
- `app/database.py` — all DDL; `create_all_tables()` called on startup
- `app/data/fetcher.py` — rate-limited nba_api (0.6s sleep, 3x retry)
- `app/narrative/narrator.py` — GPT-4o narration; always has plaintext fallback
- `app/routers/decisions.py` — generic POST /api/decisions/{type}
- `app/routers/meta.py` — GET /api/decisions (engine list + schemas)

Invariants:
- Engines compute stats deterministically from SQLite; OpenAI only narrates
- Every stat shows n=; n<30 → low_sample_warning; n<5 → insufficient_data
- INSERT OR IGNORE everywhere in seed; fetch_log prevents re-fetching

## Frontend

Run from `frontend/`: `npm run dev`
Build: `npx next build`

Next.js 16 — read `node_modules/next/dist/docs/` before editing. `params` is now a Promise, use `await props.params`. Global helpers `PageProps<'/path'>` and `LayoutProps<'/path'>` require no imports.

Key files:
- `src/app/page.tsx` — home (server component, fetches decisions)
- `src/app/decide/[type]/page.tsx` — server shell; passes meta to DecisionPage
- `src/app/decide/[type]/DecisionPage.tsx` — client component (state, form, submit)
- `src/components/InputField.tsx` — renders button_group / toggle / slider from schema
- `src/components/DecisionCard.tsx` — result display
- `src/components/ConfidenceBadge.tsx` — color-coded by sample size
- `src/lib/api.ts` — fetch wrappers (fetchDecisions, postDecision, parseDecisionInputs)

Env: set `NEXT_PUBLIC_API_URL` (default: http://localhost:8000)
