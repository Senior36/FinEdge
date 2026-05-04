# Sentimental Model Integration Plan

## Purpose

This document explains how to connect the research code in `Sentimental_Model/` to the FinEdge Docker application without falling back to dummy sentiment behavior.

The target production path is:

1. The sentimental model pipeline fetches ticker news, scores articles with the selected real scorer, builds daily sentiment signals, and writes versioned artifacts.
2. Docker mounts those artifacts into the FastAPI backend as read-only model outputs.
3. `POST /api/analyze/sentimental` reads the latest real model artifact for the requested ticker, maps it into the existing API response, saves history, and fails clearly when no real artifact exists.
4. `/api/analyze/sentimental/health` reports whether Docker is actually seeing real sentimental artifacts.

The backend should not silently substitute static or dummy sentiment. If the required model artifact is missing, stale, empty, or uncovered for a ticker, the API should return a validation error that says exactly what artifact is missing.

## Current State

### Existing Backend Sentiment Flow

The app already exposes sentiment analysis through:

- `backend/app/routers/sentimental.py`
- `backend/app/engines/sentimental/engine.py`
- `backend/app/engines/sentimental/llm_analyzer.py`
- `backend/app/schemas/sentimental.py`

The current backend path fetches recent EventRegistry news with `NewsAPIClient`, then sends each article to `LLMAnalyzer`, which calls OpenRouter directly at request time. It aggregates the resulting article scores into `SentimentalAnalysisResponse`.

This is live analysis, but it is not the real `Sentimental_Model/` research pipeline. It also has fallback behavior inside `LLMAnalyzer._fallback_response()` that returns neutral article scores when OpenRouter analysis fails. For production model integration, that fallback should be treated as a degraded live scorer, not as proof that the research model is connected.

### Existing Docker Flow

The root `docker-compose.yml` builds the backend from `./backend`, mounts `./backend:/app`, and already mounts fundamental model artifacts:

```yaml
volumes:
  - ./backend:/app
  - ./fundamental_model/outputs:/artifacts/fundamental:ro
```

The backend compose file under `backend/docker-compose.yml` does the same with a relative path from the backend folder.

Sentimental model artifacts are not mounted today. Docker currently has no explicit `SENTIMENTAL_ARTIFACT_DIR`, no `SENTIMENTAL_REQUIRE_MODEL_ARTIFACT`, and no health check proving the real sentimental model outputs are available inside the container.

### Existing Sentimental Model Folder

`Sentimental_Model/` is a research pipeline, not a backend package yet.

Important files:

- `Sentimental_Model/sentiment_benchmark.py`
  - Defines the original benchmark pipeline.
  - Fetches prices with `yfinance`.
  - Fetches news with `eventregistry`.
  - Scores articles with OpenRouter models, FinBERT, and VADER.
  - Writes cached score JSON under `data/score_cache/`.
  - Writes `data/leaderboard.csv`.
  - Contains reusable functions such as `fetch_news`, `get_prices`, `aggregate_daily`, `build_sentiment_ema`, and `compute_impulse_signal`.
- `Sentimental_Model/test_experiment.py`
  - Reuses the benchmark infrastructure.
  - Adds the context-aware prompt.
  - Adds walk-forward allocation features and allocation backtests.
  - Uses four OpenRouter scorers: `gpt54`, `opus47`, `gemini31_pro`, and `mimo_v2_pro`.
  - Writes `data/test_trades_ctx1y_allocator_GOOGL.csv`.
- `Sentimental_Model/audit_ridge.py`
  - Rebuilds scored article frames from cached JSON and audits strategy behavior.
- `Sentimental_Model/plot.py`
  - Reads saved trade CSVs and generates plots.

Important current artifacts:

- `Sentimental_Model/data/test_GOOGL_news_ctx_alloc_1y.csv`
  - Article-level news cache.
  - Columns include `id`, `title`, `published`, `body`, and `source`.
- `Sentimental_Model/data/score_cache/test_ctx1y_gemini31_pro.json`
  - Article score cache.
  - Values include `score`, `confidence`, `materiality`, `horizon`, `event_type`, and `reasoning`.
- `Sentimental_Model/data/test_trades_ctx1y_allocator_GOOGL.csv`
  - Allocation/trade output.
  - Columns include `date`, `close`, `direction`, `trade_value`, `exp_from`, `exp_to`, `raw_target_exp`, `chosen_exp`, `predicted_edge`, `model_ready`, `model_rows`, `signal`, `model`, and `strategy`.
- `Sentimental_Model/data/leaderboard.csv`
  - Benchmark metrics by scorer.
  - Columns include `model`, `IC_1d`, `roll_IC`, `hit`, `sharpe`, `PSR`, `DSR`, `return`, `max_dd`, and `final_$`.

### Key Production Gaps

- `sentiment_benchmark.py` currently contains hardcoded API keys. These must be removed before any Docker integration or commit that treats the folder as production code.
- The research folder name uses `Sentimental_Model`, while most app code uses `sentimental`. Docker paths should use the exact folder name on disk and the app setting should be explicit.
- The backend does not mount `Sentimental_Model/data`.
- The backend does not know how to read sentimental artifacts.
- The backend sentiment response does not include model provenance such as artifact path, scorer name, model signal, or artifact timestamp.
- The frontend already calls the sentiment API, but it cannot distinguish a true model artifact response from a fallback live neutral response.
- The model pipeline is ticker-specific today. Existing artifacts are centered on `GOOGL`, with some older TSLA/INTC data files. The first production integration should declare coverage explicitly instead of pretending all tickers are covered.

## Recommended Strategy

Use the same pattern as the fundamental model integration: serve generated model artifacts in request time, and keep heavy research/backtest work out of the FastAPI request path.

The first Docker-ready version should not run `test_experiment.py` inside `POST /api/analyze/sentimental`. That script fetches news, calls paid LLM APIs, computes backtests, and may take too long for an interactive API request.

Instead:

1. Create a deterministic artifact export step from `Sentimental_Model/`.
2. Mount the exported artifacts into Docker.
3. Add a backend artifact reader that maps latest ticker/scorer outputs to the current `SentimentalAnalysisResponse`.
4. Add fail-closed settings and health output so we can verify the real model is connected.

Later, a scheduled worker can refresh the artifacts daily or on demand.

## Target Artifact Contract

Create a new artifact directory:

```text
Sentimental_Model/outputs/
  latest/
    GOOGL.json
  runs/
    20260427/
      GOOGL.json
      manifest.json
  score_cache/
    test_ctx1y_gemini31_pro.json
```

The backend should only read from `outputs/`, not directly from exploratory files under `data/`, once the export exists.

### Ticker Artifact Shape

Each ticker file should be a single JSON document:

```json
{
  "ticker": "GOOGL",
  "market": "US",
  "as_of": "2026-04-27T00:00:00Z",
  "source_model": "gemini31_pro",
  "source_model_id": "google/gemini-3.1-pro-preview",
  "strategy": "v1",
  "article_count": 50,
  "score": 0.18,
  "overall_sentiment": "Positive",
  "trend": "Improving",
  "confidence": 0.72,
  "model_signal": 0.94,
  "allocation": {
    "direction": "BUY",
    "raw_target_exposure": 1.04,
    "chosen_exposure": 2.50,
    "predicted_edge": 0.0098,
    "model_ready": true,
    "model_rows": 1268
  },
  "news_breakdown": {
    "ticker": "GOOGL",
    "article_count": 50,
    "positive_count": 20,
    "negative_count": 12,
    "neutral_count": 18,
    "average_score": 0.18,
    "top_positive_articles": [],
    "top_negative_articles": []
  },
  "influential_articles": [
    {
      "title": "Example title",
      "sentiment": 0.55,
      "verdict": "BUY",
      "reasoning": "Two-sentence model reasoning.",
      "source": "Example Source",
      "url": null,
      "event_type": "ai_announcement",
      "materiality": 0.6,
      "horizon": "weeks"
    }
  ],
  "analysis_summary": "GOOGL has positive model sentiment based on the latest scored article artifact.",
  "provenance": {
    "artifact_version": "20260427",
    "news_file": "test_GOOGL_news_ctx_alloc_1y.csv",
    "score_cache_file": "test_ctx1y_gemini31_pro.json",
    "trade_file": "test_trades_ctx1y_allocator_GOOGL.csv"
  }
}
```

### Manifest Shape

Each run should include:

```json
{
  "run_id": "20260427",
  "generated_at": "2026-04-27T00:00:00Z",
  "default_model": "gemini31_pro",
  "covered_tickers": ["GOOGL"],
  "files": ["GOOGL.json"],
  "source_artifacts": {
    "news": "data/test_GOOGL_news_ctx_alloc_1y.csv",
    "score_cache": "data/score_cache/test_ctx1y_gemini31_pro.json",
    "trades": "data/test_trades_ctx1y_allocator_GOOGL.csv",
    "leaderboard": "data/leaderboard.csv"
  }
}
```

This manifest gives the backend a simple way to report health and ticker coverage.

## Backend Implementation Plan

### 1. Add Settings

Add these fields to `backend/app/config.py`:

```python
SENTIMENTAL_ARTIFACT_DIR: str = "/artifacts/sentimental"
SENTIMENTAL_REQUIRE_MODEL_ARTIFACT: bool = True
SENTIMENTAL_DEFAULT_MODEL: str = "gemini31_pro"
SENTIMENTAL_MAX_ARTIFACT_AGE_HOURS: int = 72
SENTIMENTAL_ALLOW_LIVE_FALLBACK: bool = False
```

Default production behavior should require artifacts and disallow live fallback. A developer can set `SENTIMENTAL_ALLOW_LIVE_FALLBACK=true` locally when intentionally testing the old OpenRouter-per-request flow.

### 2. Add Docker Mounts

Root `docker-compose.yml` backend service:

```yaml
volumes:
  - ./backend:/app
  - ./fundamental_model/outputs:/artifacts/fundamental:ro
  - ./Sentimental_Model/outputs:/artifacts/sentimental:ro
environment:
  SENTIMENTAL_ARTIFACT_DIR: /artifacts/sentimental
  SENTIMENTAL_REQUIRE_MODEL_ARTIFACT: "true"
  SENTIMENTAL_DEFAULT_MODEL: gemini31_pro
  SENTIMENTAL_ALLOW_LIVE_FALLBACK: "false"
```

`backend/docker-compose.yml` backend service:

```yaml
volumes:
  - .:/app
  - ../fundamental_model/outputs:/artifacts/fundamental:ro
  - ../Sentimental_Model/outputs:/artifacts/sentimental:ro
environment:
  SENTIMENTAL_ARTIFACT_DIR: /artifacts/sentimental
  SENTIMENTAL_REQUIRE_MODEL_ARTIFACT: "true"
  SENTIMENTAL_DEFAULT_MODEL: gemini31_pro
  SENTIMENTAL_ALLOW_LIVE_FALLBACK: "false"
```

Also add these settings to `backend/.env.example`.

### 3. Add an Artifact Reader

Create `backend/app/engines/sentimental/artifacts.py`.

Responsibilities:

- Resolve `Path(settings.SENTIMENTAL_ARTIFACT_DIR)`.
- Read `latest/{ticker}.json`.
- Validate required fields before returning data.
- Expose `artifact_status()`.
- Fail closed when `SENTIMENTAL_REQUIRE_MODEL_ARTIFACT=true`.

Suggested interface:

```python
class SentimentalArtifactStore:
    def load_latest(self, ticker: str, market: str) -> dict[str, Any] | None:
        ...

    def artifact_status(self) -> dict[str, Any]:
        ...
```

Status fields should include:

- `artifact_dir`
- `artifact_dir_exists`
- `require_model_artifact`
- `latest_dir_exists`
- `manifest_exists`
- `covered_tickers`
- `default_model`
- `artifact_file_count`
- `latest_artifact_mtime`
- `using_real_model_artifacts`

### 4. Update `SentimentalEngine`

Change `SentimentalEngine.analyze()` to prefer artifacts:

1. Normalize ticker and market.
2. Try `SentimentalArtifactStore.load_latest(ticker, market)`.
3. If the artifact exists, map it to `SentimentalAnalysisResponse`.
4. If it does not exist and `SENTIMENTAL_REQUIRE_MODEL_ARTIFACT=true`, raise `ValueError`.
5. Only use the old live OpenRouter path when `SENTIMENTAL_ALLOW_LIVE_FALLBACK=true`.

The old live flow can remain for development, but it must be labeled as live fallback and should not be used silently in Docker.

### 5. Update Schemas

The current `SentimentalAnalysisResponse` can support the existing UI, but we should add provenance fields so the frontend can display and debug real model status.

Add optional fields:

```python
source: Literal["model_artifact", "live_fallback"] = "model_artifact"
source_model: Optional[str] = None
source_model_id: Optional[str] = None
model_signal: Optional[float] = None
artifact_version: Optional[str] = None
artifact_path: Optional[str] = None
```

If adding fields is too much for the first patch, at minimum put equivalent values under `news_breakdown["provenance"]`, but typed top-level fields are cleaner.

### 6. Update Router Health

Replace the current generic sentiment health response:

```python
return {"status": "healthy", "service": "sentimental"}
```

with:

```python
status = sentimental_engine.artifact_status()
return {
    "status": "healthy" if status["using_real_model_artifacts"] else "degraded",
    "service": "sentimental",
    **status,
}
```

Expected Docker verification:

```bash
curl http://localhost:8000/api/analyze/sentimental/health
```

The response should contain:

```json
{
  "service": "sentimental",
  "using_real_model_artifacts": true,
  "covered_tickers": ["GOOGL"]
}
```

### 7. Keep History Saving

`backend/app/routers/sentimental.py` already saves to `AnalysisHistory`. Keep that path, but make sure the saved result includes model provenance. This makes it possible to audit whether a historical sentiment result came from a real artifact or a live fallback.

## Sentimental Model Export Plan

### 1. Create a Production Export Script

Add:

```text
Sentimental_Model/export_artifacts.py
```

The script should:

- Read the selected news CSV.
- Read the selected score cache JSON.
- Read the selected trade/allocation CSV.
- Select the latest row for each ticker/model/strategy.
- Reconstruct article-level model scores from cache entries where possible.
- Compute counts, average score, top positive articles, top negative articles, trend, and confidence.
- Write `outputs/runs/{run_id}/{ticker}.json`.
- Copy or link latest files into `outputs/latest/{ticker}.json`.
- Write `outputs/runs/{run_id}/manifest.json`.
- Write or update `outputs/latest/manifest.json`.

Initial command:

```bash
python Sentimental_Model/export_artifacts.py --ticker GOOGL --model gemini31_pro --strategy v1 --run-id 20260427
```

### 2. Remove Hardcoded Secrets

Before connecting this code to Docker, remove hardcoded key constants from `Sentimental_Model/sentiment_benchmark.py`:

```python
EVENT_REGISTRY_KEY = os.getenv("NEWS_API_KEY", "")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
```

Fail early when either key is required but missing.

### 3. Add a Minimal Requirements File

Create:

```text
Sentimental_Model/requirements.txt
```

Likely dependencies:

```text
pandas
numpy
requests
scipy
scikit-learn
yfinance
eventregistry
plotly
```

Keep optional research dependencies out of the backend image unless the backend truly imports the research pipeline. The FastAPI backend artifact reader should only need the Python standard library plus existing backend dependencies.

### 4. Optional Docker Profile for Refresh

Add a separate compose service only for artifact refresh:

```yaml
sentimental-refresh:
  build:
    context: ./Sentimental_Model
    dockerfile: Dockerfile
  command: python export_artifacts.py --ticker GOOGL --model gemini31_pro --strategy v1
  volumes:
    - ./Sentimental_Model/data:/model/data
    - ./Sentimental_Model/outputs:/model/outputs
  environment:
    NEWS_API_KEY: ${NEWS_API_KEY}
    OPENROUTER_API_KEY: ${OPENROUTER_API_KEY}
  profiles:
    - refresh
```

This should be separate from the request-serving backend. Run it manually with:

```bash
docker compose --profile refresh run --rm sentimental-refresh
```

The normal app startup should not call paid APIs or run a long backtest.

## Frontend Integration Plan

The frontend already calls `sentimentApi.analyze()`, stores the response, and renders `SentimentResults`.

Required updates:

- Extend `frontend/types/sentiment.ts` with provenance fields:
  - `source`
  - `source_model`
  - `source_model_id`
  - `model_signal`
  - `artifact_version`
- In `SentimentResults`, show concise model provenance where useful.
- In dashboard error handling, preserve backend `400` details so a missing artifact message is visible.
- Do not create client-side static sentiment fallbacks for missing model outputs.

The UI should say the model is unavailable when the backend says the artifact is missing. It should not fabricate neutral sentiment.

## Docker Verification Checklist

After implementing the backend and export script:

1. Generate artifacts:

```bash
python Sentimental_Model/export_artifacts.py --ticker GOOGL --model gemini31_pro --strategy v1
```

2. Confirm host artifacts exist:

```bash
ls Sentimental_Model/outputs/latest
```

Expected:

```text
GOOGL.json
manifest.json
```

3. Start Docker:

```bash
docker compose up --build
```

4. Confirm backend sees real artifacts:

```bash
curl http://localhost:8000/api/analyze/sentimental/health
```

Expected:

```json
{
  "status": "healthy",
  "service": "sentimental",
  "using_real_model_artifacts": true
}
```

5. Confirm analysis uses artifact source:

```bash
curl -X POST http://localhost:8000/api/analyze/sentimental \
  -H "Content-Type: application/json" \
  -d "{\"ticker\":\"GOOGL\",\"market\":\"US\"}"
```

Expected response fields:

```json
{
  "ticker": "GOOGL",
  "market": "US",
  "source": "model_artifact",
  "source_model": "gemini31_pro",
  "cached": true
}
```

6. Confirm missing ticker fails clearly:

```bash
curl -X POST http://localhost:8000/api/analyze/sentimental \
  -H "Content-Type: application/json" \
  -d "{\"ticker\":\"AAPL\",\"market\":\"US\"}"
```

Expected while only GOOGL is covered:

```json
{
  "detail": "No sentimental model artifact is available for AAPL..."
}
```

## Suggested Implementation Phases

### Phase 1: Artifact Serving

- Add settings.
- Add Docker mounts.
- Add artifact store.
- Add health endpoint details.
- Map `outputs/latest/{ticker}.json` into the existing response.
- Fail closed by default.

This phase proves the app is linked to the real model artifacts in Docker.

### Phase 2: Export Script

- Build `Sentimental_Model/export_artifacts.py`.
- Remove hardcoded secrets.
- Add `Sentimental_Model/requirements.txt`.
- Generate `outputs/latest/GOOGL.json`.
- Add a small validation command that fails if required fields are missing.

This phase gives the backend a stable contract and keeps exploratory files out of request time.

### Phase 3: Refresh Service

- Add optional `sentimental-refresh` compose profile.
- Add a simple Dockerfile for `Sentimental_Model/`.
- Run refresh manually or on a scheduler.
- Keep backend startup independent from refresh.

This phase makes artifact generation repeatable in Docker.

### Phase 4: Multi-Ticker Expansion

- Parameterize `STOCK_NAME`, `STOCK_TICKER`, `STOCK_SECTOR`, concepts, and person concepts.
- Generate artifacts for each supported ticker.
- Expand `manifest.json` coverage.
- Add coverage-aware frontend messaging.

This phase avoids claiming broad ticker support before the pipeline has real artifacts for those tickers.

## Acceptance Criteria

- Docker mounts `./Sentimental_Model/outputs` into `/artifacts/sentimental:ro`.
- Backend settings include `SENTIMENTAL_REQUIRE_MODEL_ARTIFACT=true`.
- `/api/analyze/sentimental/health` reports `using_real_model_artifacts: true` when artifacts are present.
- `POST /api/analyze/sentimental` returns `source: "model_artifact"` for covered tickers.
- Missing covered artifacts return a clear `400` instead of neutral dummy data.
- The frontend shows unavailable/error state instead of static or fabricated sentiment.
- Hardcoded API keys are removed from the sentimental model code before production use.
- The backend request path does not run the full research backtest.

## Open Decisions

- Default serving model: use `gemini31_pro` first because the current experiment artifacts and plots focus on it, or choose based on `leaderboard.csv`.
- Default strategy: use `v1` initially for compatibility with plotted outputs, or expose allocator-specific signal fields from `test_trades_ctx1y_allocator_GOOGL.csv`.
- Artifact freshness: start with 72 hours, then tighten once refresh is automated.
- Ticker coverage: first pass should probably be `GOOGL` only, because that is the cleanest current artifact set.
- Naming: the product code says `sentimental`, while the common financial term is `sentiment`. Keep API compatibility for now and avoid renaming routes during this integration.
