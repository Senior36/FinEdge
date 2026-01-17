from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.sentimental import (
    SentimentalAnalysisRequest,
    SentimentalAnalysisResponse
)
from app.engines.sentimental.engine import SentimentalEngine
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/analyze", tags=["sentimental"])
sentimental_engine = SentimentalEngine()


@router.post("/sentimental", response_model=SentimentalAnalysisResponse)
async def analyze_sentiment(
    request: SentimentalAnalysisRequest,
    db: AsyncSession = Depends(get_db)
) -> SentimentalAnalysisResponse:
    try:
        logger.info(f"Received sentimental analysis request for {request.ticker}")

        response = await sentimental_engine.analyze(
            ticker=request.ticker.upper(),
            market=request.market,
            db=db,
            days=7,
            max_articles=10
        )

        return response

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Error during sentimental analysis: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to perform sentimental analysis")


@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "sentimental"}
