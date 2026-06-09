# Agent Notes

This repository is the public portfolio version of a full-stack marketplace BI system. Keep it clean, reproducible, and safe to inspect.

## Project Shape

- Backend: FastAPI under `backend/`
- Frontend: Next.js App Router under `frontend/`
- Database: Supabase Postgres schema under `backend/db/migrations/`
- Tests: Python test suite under `tests/`
- Deployment examples: `Dockerfile`, `railway.json`, `vercel.json`, and `Procfile`

## Public Repository Rules

- Do not commit real `.env`, `frontend/.env.local`, raw marketplace exports, logs, generated reports, screenshots containing real business data, Supabase project files, Vercel project files, or build outputs.
- Keep `.env.example` and `frontend/.env.local.example` as placeholders only.
- Backend secrets such as `SUPABASE_SERVICE_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, Twilio tokens, and Resend keys must remain server-side only.
- Frontend code may only use public variables prefixed with `NEXT_PUBLIC_`.
- Public docs should explain the architecture and engineering decisions without exposing private sales data, customer data, credentials, or live production access details.

## Business Logic

The core domain is fashion marketplace analytics across Myntra, Ajio, Nykaa, Flipkart, Amazon, and TataCliq.

Important metrics:

- MTD sales and quantity
- Returns value, returns quantity, and return percentage
- ROS, DOI, inventory depth, OOS rate, broken stock rate
- Marketplace contribution and regional sales distribution
- Category mix and Potential NOOS approval candidates

Category values include:

- `NOOS`
- `NOOS(Green)`
- `NOOS(Yellow)`
- `NOOS(Red)`
- `NOOS(Potential)`
- `Green`
- `Yellow`
- `Red`
- `Dead`
- `OOS`
- `Winter`
- `Dog styles`
- `Discontinue`
- `Watchlist`
- `RED(Repeat)`
- `New Launch`
- `Potential NOOS`
- `Unknown`

Category assignment logic lives in `backend/services/category_engine.py`. Do not simplify threshold or priority rules without adding tests.

## Ingestion

Upload processors live in `backend/services/data_ingestion.py` and `backend/routers/upload.py`.

Supported inputs:

- SKU mapping reports
- Sale grade master
- Myntra order exports
- Unicommerce sales exports
- Inventory snapshots
- Returns reports
- PLA ads reports
- Visibility reports
- Replenishment plans

Upload detection should rely on file columns and content, not filename conventions.

## Auth And Security

- Supabase Auth protects dashboard routes.
- FastAPI routes require a bearer token and role checks.
- Roles are stored in `public.user_roles`.
- Admin-only operations include uploads, user management, target management, and category rebuilds.
- CSV and Excel exports must use `backend/services/export_safety.py` to prevent spreadsheet formula injection.
- Large uploads should go directly to the FastAPI backend, not through a serverless frontend proxy.

## Frontend Conventions

- Preserve the clean dashboard aesthetic: light theme, restrained colors, dense but readable operational layouts.
- Use existing components from `frontend/components/ui/`, `frontend/components/charts/`, and `frontend/components/layout/`.
- Use `frontend/lib/api.ts` for browser API calls.
- Use `frontend/lib/server-api.ts` for server-rendered dashboard data because it attaches the Supabase session token.
- Use Indian number formatting helpers in `frontend/lib/formatters.ts`.

## Testing

Run these checks before publishing material changes:

```powershell
python -m pytest -q
npm run build
```

For focused backend syntax checks:

```powershell
python -m py_compile backend/main.py backend/security.py
```

## Deployment Notes

- Railway can run the FastAPI backend from the root `Dockerfile`.
- Vercel can run the Next.js frontend with the root `vercel.json`.
- Set public frontend environment variables in Vercel:
  - `NEXT_PUBLIC_SUPABASE_URL`
  - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
  - `NEXT_PUBLIC_API_URL`
- Set backend secrets in Railway or the chosen backend host:
  - `SUPABASE_URL`
  - `SUPABASE_ANON_KEY`
  - `SUPABASE_SERVICE_KEY`
  - Optional AI, Twilio, and Resend keys
