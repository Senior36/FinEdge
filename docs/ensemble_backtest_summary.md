# Ensemble Backtest Summary

## Problem Statement

FinEdge had three separate model paths: fundamental, sentimental, and technical. Each could produce its own signal, but there was no backend pipeline that treated them as one final model. The aggregate model is now sentiment-led: sentimental output chooses BUY/HOLD/SELL, while technical and fundamental outputs support the trade by scaling the target long exposure up or down.

The main challenge was that each model stores history differently. Sentimental has a trade log, fundamental uses CSV signal artifacts, and technical is mainly built around live inference/artifacts rather than a simple historical trade log.

After that, a second technical-model gap came up: the backend only served the one-day technical artifact path. The new one-minute artifact bundle needed the same production-style path so it can fetch Alpaca one-minute bars, load the saved experts, and return predicted minute candles.

## What Was Added

- Added ensemble request/response schemas in `backend/app/schemas/ensemble.py`.
- Added the ensemble backtest engine in `backend/app/engines/ensemble/backtest.py`.
- Added an ensemble FastAPI router in `backend/app/routers/ensemble.py`.
- Registered the router in `backend/app/main.py` and `backend/app/routers/__init__.py`.
- Added frontend API/types support in `frontend/types/ensemble.ts`, `frontend/types/index.ts`, and `frontend/lib/api.ts`.
- Added focused backend tests in `backend/tests/test_ensemble_backtest.py`.
- Added `final_1min` technical inference support in `backend/app/engines/technical/minute_runtime.py`.
- Wired `final_1min` through `backend/app/engines/technical/engine.py`, `backend/app/schemas/technical.py`, and `frontend/types/technical.ts`.
- Added config support for `TECHNICAL_INTRADAY_ARTIFACT_DIR`, `TECHNICAL_INTRADAY_WARMUP_BARS`, `ALPACA_STOCK_FEED`, and common Alpaca secret env var names.

## How It Works

The backtest engine loads available model signals into a shared format:

`date`, `ticker`, `model`, `raw_signal`, `normalized_score`, `confidence`, `signal_label`, `source`.

It then normalizes each model to a `-1` to `+1` score:

- Fundamental: maps `score`/`model_score` or BUY/HOLD/SELL labels.
- Sentimental: parses the trade log or CSV trade rows and converts target exposure into a normalized score.
- Technical: reads a backtest signal CSV if present, or uses a clearly marked deterministic price-momentum proxy when no technical backtest artifact exists.

For each date, the engine starts from the sentimental signal:

- Sentimental `BUY` opens or rebalances a long position.
- Sentimental `SELL` exits to cash.
- Sentimental `HOLD` leaves the current position unchanged.

Technical and fundamental scores are supporting modules. When sentiment says `BUY`, the simulator starts from `base_long_exposure` and applies:

- `technical_exposure_weight * technical_score`
- `fundamental_exposure_weight * fundamental_score`

The result is clipped between `0` and `target_long_exposure`. With the default settings, a sentiment BUY starts at 60% exposure, can scale toward 100% with supportive technical/fundamental signals, and can shrink when either support module is negative. Support modules do not override sentimental SELL or HOLD.

The simulator then runs a long/cash portfolio:

- BUY targets the sentiment-led scaled long exposure.
- SELL exits to cash.
- HOLD keeps the current position.
- Transaction costs, trades, equity curve, drawdown, Sharpe, win rate, and model coverage are included in the response.

For the one-minute technical model, the request uses the same technical endpoint with `model_version: "final_1min"`. The runtime loads `Technical_Model/final_artifacts`, fetches live one-minute Alpaca bars, builds the core/technical/regime feature frames, runs the saved expert ensemble and RL policy, and returns `1Min` history and forecast candles.

## API Endpoint

The new endpoint is:

```text
POST /api/analyze/ensemble/backtest
```

There is also a health endpoint:

```text
GET /api/analyze/ensemble/health
```

## Verification

Backend unit tests cover:

- Sentimental trade-log parsing.
- Fundamental CSV parsing.
- Sentiment-led BUY sizing with supportive technical/fundamental signals.
- Sentiment-led BUY sizing with negative support.
- SELL exit behavior in a long/cash portfolio.
- HOLD behavior with no rebalance.

The focused test command passed:

```text
python3 -m unittest discover -s "backend/tests" -t "backend"
```

Frontend type-checking was not run because `npm` was unavailable in the environment.
