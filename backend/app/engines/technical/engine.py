from __future__ import annotations

import math
import random
from datetime import timedelta, timezone, datetime
from statistics import mean, pstdev
from typing import Literal, List, Tuple

from app.integrations.alpaca_api import AlpacaMarketDataClient
from app.schemas.technical import (
    TechnicalAnalysisRequest,
    TechnicalAnalysisResponse,
    TechnicalCandle,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TechnicalAnalysisEngine:
    def __init__(self) -> None:
        self.market_data_client = AlpacaMarketDataClient()

    async def analyze(self, request: TechnicalAnalysisRequest) -> TechnicalAnalysisResponse:
        ticker = request.ticker.upper()
        history_bars, data_source = await self.market_data_client.fetch_recent_minute_bars(
            ticker=ticker,
            limit=request.history_bars,
        )

        if len(history_bars) < 20:
            raise ValueError(f"Not enough 1-minute bars available for {ticker}")

        forecast = self._generate_forecast(
            ticker=ticker,
            history_bars=history_bars,
            forecast_count=request.forecast_bars,
            model_version=request.model_version,
        )

        return TechnicalAnalysisResponse(
            ticker=ticker,
            model_version=request.model_version,
            data_source=data_source,
            latest_price=history_bars[-1].close,
            history_bars=history_bars,
            forecast_bars=forecast,
            generated_at=datetime.now(timezone.utc),
        )

    def _generate_forecast(
        self,
        ticker: str,
        history_bars: List[TechnicalCandle],
        forecast_count: int,
        model_version: Literal["v8.5", "v8.6"],
    ) -> List[TechnicalCandle]:
        closes = [candle.close for candle in history_bars]
        returns = self._returns(closes)
        recent_returns = returns[-20:] or [0.0]
        recent_closes = closes[-20:]
        recent_volumes = [candle.volume for candle in history_bars[-20:]]

        trend = mean(recent_returns[-8:] or [0.0])
        momentum = mean(recent_returns[-3:] or [0.0])
        volatility = max(pstdev(recent_returns), 0.00055)
        average_volume = max(int(mean(recent_volumes or [1000])), 1000)
        anchor_price = mean(recent_closes)

        params = self._model_params(model_version)
        seed = f"{ticker}:{model_version}:{history_bars[-1].timestamp.isoformat()}"
        rng = random.Random(seed)
        phase = rng.uniform(0.0, math.pi)

        forecast: List[TechnicalCandle] = []
        rolling_closes = closes[:]
        last_candle = history_bars[-1]
        prev_close = last_candle.close
        current_time = last_candle.timestamp
        state_return = momentum

        for step in range(forecast_count):
            current_time = current_time + timedelta(minutes=1)
            local_anchor = mean(rolling_closes[-15:])
            displacement = (prev_close - local_anchor) / local_anchor
            cycle = math.sin((step + 1) / params["cycle_period"] + phase) * volatility * params["cycle_strength"]
            shock = rng.gauss(0, volatility * params["volatility_multiplier"])
            drift = (
                trend * params["trend_weight"]
                + state_return * params["momentum_memory"]
                - displacement * params["reversion_weight"]
            )
            raw_return = drift + cycle + shock
            bounded_return = max(min(raw_return, volatility * params["return_cap"]), -volatility * params["return_cap"])

            open_price = prev_close
            close_price = max(prev_close * (1 + bounded_return), 0.01)
            wick_noise = max(abs(bounded_return) * 0.7, volatility * params["wick_multiplier"])
            upper_wick = abs(rng.gauss(volatility * 0.6, wick_noise))
            lower_wick = abs(rng.gauss(volatility * 0.6, wick_noise))
            high_price = max(open_price, close_price) * (1 + min(upper_wick, volatility * 3.5))
            low_price = min(open_price, close_price) * (1 - min(lower_wick, volatility * 3.5))
            volume = int(max(100, average_volume * (0.82 + rng.random() * 0.36)))

            candle = TechnicalCandle(
                timestamp=current_time,
                open=round(open_price, 4),
                high=round(high_price, 4),
                low=round(low_price, 4),
                close=round(close_price, 4),
                volume=volume,
                is_prediction=True,
            )
            forecast.append(candle)
            rolling_closes.append(candle.close)
            prev_close = candle.close
            state_return = bounded_return
            anchor_price = (anchor_price * 0.92) + (candle.close * 0.08)

        return forecast

    def _returns(self, closes: List[float]) -> List[float]:
        returns: List[float] = []
        for idx in range(1, len(closes)):
            previous = closes[idx - 1]
            current = closes[idx]
            if previous <= 0:
                returns.append(0.0)
            else:
                returns.append((current - previous) / previous)
        return returns

    def _model_params(self, model_version: Literal["v8.5", "v8.6"]) -> dict[str, float]:
        if model_version == "v8.6":
            return {
                "trend_weight": 0.52,
                "momentum_memory": 0.22,
                "reversion_weight": 0.10,
                "cycle_strength": 0.28,
                "cycle_period": 4.8,
                "volatility_multiplier": 1.10,
                "wick_multiplier": 0.95,
                "return_cap": 3.0,
            }
        return {
            "trend_weight": 0.44,
            "momentum_memory": 0.18,
            "reversion_weight": 0.14,
            "cycle_strength": 0.22,
            "cycle_period": 5.6,
            "volatility_multiplier": 0.92,
            "wick_multiplier": 0.82,
            "return_cap": 2.6,
        }
