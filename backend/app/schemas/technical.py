from datetime import datetime
from typing import List, Literal

from pydantic import BaseModel, Field


class TechnicalAnalysisRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=20, description="US stock ticker symbol")
    model_version: Literal["v1.1", "v1.2"] = Field("v1.1", description="Technical model selector")
    history_bars: int = Field(60, ge=30, le=120, description="Number of historical 1-minute candles")
    forecast_bars: int = Field(50, ge=10, le=100, description="Number of future 1-minute candles")


class TechnicalCandle(BaseModel):
    timestamp: datetime
    open: float = Field(..., gt=0)
    high: float = Field(..., gt=0)
    low: float = Field(..., gt=0)
    close: float = Field(..., gt=0)
    volume: int = Field(..., ge=0)
    is_prediction: bool = False


class TechnicalAnalysisResponse(BaseModel):
    ticker: str
    timeframe: Literal["1Min"] = "1Min"
    model_version: Literal["v1.1", "v1.2"]
    data_source: str
    latest_price: float = Field(..., gt=0)
    history_bars: List[TechnicalCandle]
    forecast_bars: List[TechnicalCandle]
    generated_at: datetime
