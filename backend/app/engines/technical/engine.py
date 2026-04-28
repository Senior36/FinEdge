from __future__ import annotations

from app.config import settings
from app.engines.technical.model_runtime import TechnicalArtifactStore, TechnicalModelRuntime
from app.schemas.technical import TechnicalAnalysisRequest, TechnicalAnalysisResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TechnicalAnalysisEngine:
    def __init__(self) -> None:
        self.artifact_store = TechnicalArtifactStore()
        self.model_runtime = TechnicalModelRuntime(self.artifact_store)

    async def analyze(self, request: TechnicalAnalysisRequest) -> TechnicalAnalysisResponse:
        ticker = request.ticker.upper()
        status = self.artifact_status()
        if settings.TECHNICAL_REQUIRE_MODEL_ARTIFACT and not status["using_real_model_artifacts"]:
            missing = ", ".join(status.get("missing_files") or [])
            raise ValueError(
                "Real technical model artifacts are not ready. "
                f"Resolved artifact dir: {status['resolved_artifact_dir']}. "
                f"Missing: {missing or 'unknown'}"
            )

        if request.model_version != "final_1d":
            logger.info(
                "Technical request asked for deprecated %s; using real final_1d artifact model",
                request.model_version,
            )

        result = await self.model_runtime.predict(
            ticker=ticker,
            history_bars=request.history_bars,
            forecast_bars=request.forecast_bars,
        )

        return TechnicalAnalysisResponse(
            ticker=ticker,
            timeframe="1D",
            model_version="final_1d",
            source="model_artifact",
            source_model=result.source_model,
            artifact_version=result.artifact_version,
            artifact_path=result.artifact_path,
            data_source=result.data_source,
            inference_input_bars=result.inference_input_bars,
            required_input_bars=result.required_input_bars,
            latest_price=result.latest_price,
            history_bars=result.history,
            forecast_bars=result.forecast,
            generated_at=result.generated_at,
            ensemble_weights=result.ensemble_weights,
            expert_versions=result.expert_versions,
            policy=result.policy,
            regime=result.regime,
        )

    def artifact_status(self) -> dict:
        return self.artifact_store.status()
