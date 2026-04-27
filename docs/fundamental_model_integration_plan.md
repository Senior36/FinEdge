# Fundamental Model Integration Plan

## Purpose

This document explains how to turn the current `fundamental_model/` research pipeline into a production feature inside the FinEdge system described by `prd.md` and `Architecture.md`.

The goal is to expose fundamental analysis through the same product path as the existing sentiment and technical engines:

1. Next.js frontend sends a ticker to the backend.
2. FastAPI routes the request to a dedicated fundamental engine.
3. The engine fetches or reuses financial data, scores the company, caches the result, stores analysis history, and returns a UI-friendly response.
4. Docker hosts the backend, frontend, and database with required model artifacts and API keys available at runtime.

## Current State

### Product and Architecture Expectations

The PRD defines the Fundamental engine as:

- Fetch financial reports.
- Calculate ratios such as P/E, ROE, and debt-to-equity.
- Analyze trends.
- Compare against peers.
- Generate a rating.

The architecture expects a FastAPI backend with modular engines under `backend/app/engines/`, routes under `backend/app/routers/`, schemas under `backend/app/schemas/`, cache/history persistence in PostgreSQL, and a Next.js frontend using REST APIs.

### Existing Backend

The backend already has the pattern we should follow:

- `backend/app/routers/sentimental.py` exposes `POST /api/analyze/sentimental`, calls an engine, and saves `AnalysisHistory`.
- `backend/app/routers/technical.py` exposes `POST /api/analyze/technical` and calls `TechnicalAnalysisEngine`.
- `backend/app/main.py` includes sentiment, technical, and user routers.
- `backend/app/config.py` uses Pydantic settings for environment-driven secrets.
- `backend/app/models/analysis_history.py` already stores JSON analysis results.

Missing backend pieces:

- No `backend/app/routers/fundamental.py`.
- No `backend/app/schemas/fundamental.py`.
- No `backend/app/engines/fundamental/`.
- No financial report cache model/table.
- No EODHD or fundamental data integration in `backend/app/integrations/`.

### Existing Frontend

The frontend has a polished fundamental UI, but it is static:

- `frontend/components/pages/fundamental/FundamentalAnalysisPage.tsx` contains `FUNDAMENTAL_PROFILES` for MSFT, AAPL, and NVDA.
- The page simulates analysis with a `setTimeout`.
- `frontend/components/pages/dashboard/DashboardPage.tsx` uses `FUNDAMENTAL_PROFILES` directly for combined analysis.
- `frontend/lib/api.ts` has `sentimentApi` and `technicalApi`, but no `fundamentalApi`.
- `frontend/types/index.ts` exports sentiment, technical, and auth types, but no fundamental types.

### Existing Raw Fundamental Model

The raw model under `fundamental_model/fundamental_model/` is an offline pipeline:

- `src/step2_fetch_fundamentals.py` fetches company fundamentals from EODHD.
- `src/step3_fetch_prices.py` fetches price history.
- `src/step4_build_features.py` builds point-in-time quarterly features and ranked peer features in `data/processed/features.csv`.
- `src/step5_train_and_backtest.py` trains and evaluates ML models.
- `src/step6_generate_signals.py` loads trained models, scores latest rows, and writes signal CSVs.
- `outputs/signals/signals_20260412.csv` shows current target signals for GOOGL, TSLA, AAPL, MSFT, and META.
- `outputs/signals/top7_buys_20260412.csv` shows top ranked names across the universe.

Important production issues:

- The model config currently hardcodes an EODHD API key. This must move to environment variables before integration.
- The committed outputs include CSV signals and `features.csv`, but trained `.pkl` model artifacts are not present in the repository.
- The scripts are designed for batch execution, not low-latency request handling.
- The model is currently US-market focused. Indian market support needs a separate data strategy or a deliberate v1 limitation.
- Heavy ML/training dependencies should not be added blindly to the FastAPI request image unless we decide the API must perform live inference from model artifacts.

## Recommended Integration Strategy

Use a two-layer approach:

1. Batch pipeline layer: refresh fundamentals, features, model artifacts, and signal snapshots on a schedule.
2. API serving layer: serve the latest fundamental analysis from cached/persisted artifacts and perform only lightweight transformations in request time.

Do not train or rebuild the full feature dataset inside `POST /api/analyze/fundamental`. Training and feature rebuilds are too slow, require broad universe data, and would make the API unreliable under concurrent users.

The first product version should serve the latest generated fundamental signal plus a structured explanation and metrics derived from the latest financial data. Later, we can add on-demand refresh for a ticker when cached data is stale.

## Target Backend Design

### New API Endpoint

Add:

```http
POST /api/analyze/fundamental
```

Request shape:

```json
{
  "ticker": "AAPL",
  "market": "US",
  "include_peer_context": true
}
```

Initial response shape should be close to the existing frontend `FundamentalProfile`, but normalized for API use:

```json
{
  "ticker": "AAPL",
  "market": "US",
  "company_name": "Apple Inc.",
  "sector": "Technology",
  "rating": "HOLD",
  "score": 6.3,
  "model_score": 0.633,
  "universe_percentile": 0.686,
  "relative_rank": 3,
  "key_metrics": {
    "pe_ratio": 28.4,
    "roe": 1.38,
    "debt_to_equity": 1.52,
    "free_cash_flow_margin": 0.26,
    "revenue_growth_yoy": 0.06
  },
  "trends": {
    "revenue": "Stable",
    "earnings": "Improving",
    "cash_flow": "Stable"
  },
  "peer_context": {
    "sector_percentile": 0.69,
    "universe_percentile": 0.69,
    "top_comparable_strengths": []
  },
  "strengths": [],
  "concerns": [],
  "analysis_summary": "A concise investor-readable explanation.",
  "data_source": "eodhd",
  "cached": true,
  "generated_at": "2026-04-24T00:00:00Z"
}
```

### New Backend Files

Add these backend modules:

- `backend/app/schemas/fundamental.py`: Pydantic request and response DTOs.
- `backend/app/routers/fundamental.py`: FastAPI router matching the sentiment/technical router style.
- `backend/app/engines/fundamental/__init__.py`: engine export.
- `backend/app/engines/fundamental/engine.py`: orchestrates cache lookup, artifact lookup, optional live data fetch, explanation building, and response mapping.
- `backend/app/integrations/eodhd_api.py`: async EODHD client using `httpx`.
- `backend/app/models/cache_financial_report.py`: raw EODHD report cache.
- `backend/app/models/cache_fundamental_analysis.py`: latest normalized fundamental analysis cache, if we want quick API responses without repeatedly parsing raw reports.

Wire these into:

- `backend/app/routers/__init__.py`
- `backend/app/main.py`
- `backend/app/models/__init__.py`

### Engine Responsibilities

`FundamentalAnalysisEngine` should be responsible for:

- Normalizing ticker and market input.
- Rejecting unsupported markets or unsupported tickers with clear errors.
- Checking cached analysis first.
- Loading latest signal rows from a configured artifact path or database table.
- Fetching raw fundamentals from EODHD only when needed.
- Computing lightweight ratios and trend summaries from cached raw report data.
- Building investor-readable strengths, concerns, and summary fields.
- Returning a deterministic response shape for the frontend.
- Saving results to `AnalysisHistory` with `analysis_types=["fundamental"]`.

### Artifact Strategy

For v1, use file or database artifacts created by the batch pipeline:

- `features.csv`: source of latest rows and rank features.
- `signals_YYYYMMDD.csv`: source of model score, signal, relative rank, and universe percentile.
- Optional model artifacts: later, include `final_model.pkl` and sector model `.pkl` files if the API needs to score fresh rows.

Recommended v1 serving path:

1. Add a small script that exports the latest signal snapshot to a stable file name such as `outputs/signals/latest_signals.csv`.
2. Mount or copy that file into the backend container under `/app/artifacts/fundamental/latest_signals.csv`.
3. The backend reads the artifact at startup or per request with a short in-memory TTL.
4. If the ticker is missing from the artifact, return a supported coverage error or fall back to ratio-only analysis.

Recommended v2 serving path:

1. Add a `fundamental_signals` database table.
2. Batch job writes latest signals into Postgres.
3. API reads from Postgres instead of CSV files.

### Data and Cache Tables

Add tables aligned with `Architecture.md`:

- `cache_financial_reports`
  - `id`
  - `ticker`
  - `market`
  - `report_type`
  - `report_period`
  - `content`
  - `cached_at`
  - `expires_at`

- `cache_fundamental_analysis`
  - `id`
  - `ticker`
  - `market`
  - `source_signal_date`
  - `result`
  - `cached_at`
  - `expires_at`

Financial reports can live until superseded by a newer filing. Normalized analysis can use a shorter TTL, for example 24 hours, because market price and percentile context can change.

## Docker and Runtime Plan

### Immediate Docker Changes

Update root `docker-compose.yml`:

- Add `EODHD_API_KEY: ${EODHD_API_KEY}` to the backend environment.
- Add a backend volume for fundamental artifacts during development:
  - `./fundamental_model/fundamental_model/outputs/signals:/app/artifacts/fundamental/signals:ro`
  - optionally `./fundamental_model/fundamental_model/data/processed:/app/artifacts/fundamental/processed:ro`

Update `backend/.env.example`:

- Add `EODHD_API_KEY=your_eodhd_api_key_here`.
- Add `FUNDAMENTAL_ARTIFACT_DIR=/app/artifacts/fundamental`.
- Add `FUNDAMENTAL_DEFAULT_MARKET=US`.

Update `backend/app/config.py`:

- Add optional `EODHD_API_KEY`.
- Add `FUNDAMENTAL_ARTIFACT_DIR`.
- Add configurable cache TTL values if needed.

### Dependency Strategy

For the API container, start with lightweight dependencies:

- `pandas`
- `numpy`
- `httpx` is already present

Do not add `lightgbm`, `catboost`, `optuna`, or `shap` to the API image for the first backend integration unless live inference is explicitly required. Those belong in a separate batch/model image.

If we later need the API to score fresh feature rows with `.pkl` models, create either:

- A separate `fundamental-worker` Docker service for batch scoring, or
- A heavier backend image variant that includes ML dependencies and verified model artifacts.

### Batch Job Options

Option A - simple and fastest:

- Run the existing fundamental scripts manually or with a scheduled host cron.
- Write latest CSV outputs.
- Backend reads mounted latest CSV.

Option B - production-ready:

- Add a Docker service named `fundamental-worker`.
- It uses a dedicated Dockerfile with the full `fundamental_model/requirements.txt`.
- It runs refresh commands on a schedule or via a manual admin endpoint.
- It writes results to Postgres or a shared artifact volume.

Option C - future scalable:

- Use Celery plus Redis.
- API enqueues refresh jobs.
- Worker writes artifacts and statuses.

For this product stage, use Option A for the first usable integration, then move to Option B when the API contract and UI are working.

## Frontend Integration Plan

### API Client and Types

Add:

- `frontend/types/fundamental.ts`
- export it from `frontend/types/index.ts`
- `fundamentalApi.analyze()` in `frontend/lib/api.ts`

The frontend DTO can initially mirror the backend response and include UI helper transformations in the page component.

### Fundamental Page

Refactor `frontend/components/pages/fundamental/FundamentalAnalysisPage.tsx`:

- Keep the current visual layout.
- Move static `FUNDAMENTAL_PROFILES` to a fallback/demo fixture or remove it once API coverage is stable.
- Replace `setTimeout` analysis with `fundamentalApi.analyze({ ticker, market: "US" })`.
- Allow tickers supported by the backend instead of only MSFT, AAPL, and NVDA.
- Render loading, API error, and unsupported ticker states.
- Map API fields into the existing cards:
  - `rating`, `score`, and `analysis_summary` into headline cards.
  - `key_metrics` into score bands and ratio checks.
  - `peer_context` into peer ranking sections.
  - `strengths` and `concerns` into existing strengths/risks sections.

### Dashboard

Update `frontend/components/pages/dashboard/DashboardPage.tsx`:

- Import and call `fundamentalApi`.
- Replace direct `FUNDAMENTAL_PROFILES[ticker]` usage.
- Run `fundamentalApi`, `technicalApi`, and `sentimentApi` with `Promise.allSettled`.
- Treat each engine as independently available so a failure in one engine does not block the combined result.

## Implementation Phases

### Phase 1 - Productize Static Signal Serving

Objective: make the fundamental model accessible from the product without running heavy ML in the API.

Tasks:

1. Remove hardcoded model secrets and add env-driven EODHD settings.
2. Add `latest_signals.csv` export or select the newest `signals_*.csv` file from artifact storage.
3. Add backend fundamental schemas, router, and engine.
4. Add fundamental artifact reader for signal CSVs.
5. Add response mapping from signal rows plus cached report metrics.
6. Save results to `AnalysisHistory`.
7. Add `fundamentalApi` and frontend types.
8. Replace the fundamental page mock request path with the backend API.
9. Update Docker Compose env and artifact mounts.

Expected result:

- `POST /api/analyze/fundamental` works from Docker.
- The frontend fundamental page displays live backend data.
- The dashboard can include fundamental results in combined analysis.

### Phase 2 - Add Financial Report Cache and Ratio Calculations

Objective: enrich the response beyond model signal CSV data.

Tasks:

1. Add `EODHDClient`.
2. Add financial report cache model/table.
3. Port safe ratio helpers from `step4_build_features.py` into backend-friendly pure functions.
4. Compute the key metrics required by the PRD:
   - P/E
   - ROE
   - debt-to-equity
   - free cash flow margin
   - revenue growth
   - earnings growth
5. Add trend summaries from recent quarterly statements.
6. Add peer/sector percentile fields from feature rank columns where available.

Expected result:

- The API returns both model signal and explainable fundamental metrics.
- Cached financial reports reduce EODHD calls.

### Phase 3 - Separate Batch Worker

Objective: refresh artifacts reliably without manual script execution.

Tasks:

1. Create `fundamental_model/Dockerfile`.
2. Add a `fundamental-worker` service or scheduled host command.
3. Move `fundamental_model/config.py` settings to environment variables.
4. Add a stable output contract:
   - latest signal CSV
   - model metadata JSON
   - data freshness timestamp
5. Optionally write latest signals into Postgres instead of mounted files.

Expected result:

- Model data refreshes independently of the API container.
- API remains fast and stateless.

### Phase 4 - Combined Analysis Orchestrator

Objective: match the architecture's combined analysis endpoint.

Tasks:

1. Add `backend/app/services/analysis_orchestrator.py`.
2. Add `POST /api/analyze/combined`.
3. Execute selected engines concurrently.
4. Aggregate scores while preserving individual engine details.
5. Update frontend dashboard and analyze page to call the combined endpoint.

Expected result:

- The product can run any combination of sentiment, technical, and fundamental engines.

## Risks and Decisions

### Decision: API Should Serve, Not Train

The raw model performs universe-wide data fetching, feature building, model training, and scoring. This is not appropriate inside an API request. The backend should serve latest artifacts and optionally perform lightweight calculations.

### Decision: Start with US Market

The current raw model uses US tickers and EODHD US exchange assumptions. The API should either reject `market="IN"` for fundamental analysis in v1 or return a clear "not supported yet" response.

### Risk: Missing Trained Model Artifacts

The scripts expect trained model `.pkl` files, but they are not currently present. Phase 1 should use existing signal CSVs. Phase 3 should define how trained artifacts are generated, stored, versioned, and deployed.

### Risk: Secret Handling

The raw model currently stores an API key in source. Before any production work, move this to `.env`, rotate the exposed key, and ensure no new secrets are committed.

### Risk: UI Contract Mismatch

The current frontend `FundamentalProfile` is very rich and manually curated. The first backend response will likely be less narrative. We should keep the visual shell but map the backend data honestly, avoiding fake fair value scenarios unless we implement a real valuation model.

## Suggested First Implementation Order

1. Create backend schemas and endpoint for `POST /api/analyze/fundamental`.
2. Implement an artifact reader that loads the latest `signals_*.csv`.
3. Return a minimal but real response with ticker, rating, score, relative rank, universe percentile, generated timestamp, and summary.
4. Add Docker env and artifact mount.
5. Add frontend `fundamentalApi` and replace the fundamental page mock flow.
6. Add EODHD report cache and richer metrics.
7. Add a batch worker once the end-to-end product path is working.

This order gets the model visible in the product quickly while keeping the backend deployable and avoiding a fragile all-at-once ML migration.
