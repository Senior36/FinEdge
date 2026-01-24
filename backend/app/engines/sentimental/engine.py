from typing import Dict, Any, List, Optional, Literal
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
import json

from app.engines.sentimental.llm_analyzer import LLMAnalyzer
from app.integrations.news_api import NewsAPIClient
from app.services.cache_manager import CacheManager
from app.schemas.sentimental import (
    SentimentalAnalysisResponse,
    NewsSentimentBreakdown,
    NewsArticle
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SentimentalEngine:
    def __init__(self):
        self.llm_analyzer = LLMAnalyzer()
        self.news_client = NewsAPIClient()
        self.cache_manager = CacheManager()

    async def analyze(
        self,
        ticker: str,
        market: str,
        db: AsyncSession,
        days: int = 7,
        max_articles: int = 10
    ) -> SentimentalAnalysisResponse:
        logger.info(f"Starting sentimental analysis for {ticker} ({market})")

        cached_news = await self.cache_manager.get_cached_news(db, ticker, market)

        if cached_news:
            logger.info(f"Using cached data for {ticker}")
            return self._parse_cached_response(cached_news.content, ticker, market)

        articles = await self._fetch_articles(ticker, market, days, max_articles)

        if not articles:
            logger.warning(f"No articles found for {ticker}")
            return self._empty_response(ticker, market)

        analyzed_articles = await self.llm_analyzer.analyze_news_batch(articles)

        await self._cache_articles(db, ticker, market, analyzed_articles)

        return self._build_response(analyzed_articles, ticker, market, cached=False)

    async def _fetch_articles(
        self,
        ticker: str,
        market: str,
        days: int,
        max_articles: int
    ) -> List[Dict[str, Any]]:
        company_names = {
            'AAPL': 'Apple Inc',
            'MSFT': 'Microsoft Corporation',
            'NVDA': 'NVIDIA Corporation',
            'GOOGL': 'Alphabet Inc',
            'AMZN': 'Amazon.com Inc',
            'META': 'Meta Platforms Inc',
            'TSLA': 'Tesla Inc',
            'RELIANCE.NS': 'Reliance Industries',
            'TCS.NS': 'Tata Consultancy Services',
            'INFY.NS': 'Infosys Ltd',
            'HDFCBANK.NS': 'HDFC Bank Ltd',
            'ICICIBANK.NS': 'ICICI Bank Ltd'
        }

        company_name = company_names.get(ticker, ticker)

        articles = await self.news_client.fetch_news(
            company_name=company_name,
            ticker=ticker,
            days=days,
            max_articles=max_articles
        )

        return articles

    async def _cache_articles(
        self,
        db: AsyncSession,
        ticker: str,
        market: str,
        articles: List[Dict[str, Any]]
    ) -> None:
        content = json.dumps(articles)
        await self.cache_manager.save_cached_news(db, ticker, market, content)

    def _build_response(
        self,
        articles: List[Dict[str, Any]],
        ticker: str,
        market: str,
        cached: bool
    ) -> SentimentalAnalysisResponse:
        breakdown = self._calculate_breakdown(articles)

        if breakdown.article_count == 0:
            return self._empty_response(ticker, market)

        overall_score = breakdown.average_score
        overall_sentiment: Literal["Positive", "Negative", "Neutral"] = self._score_to_sentiment(overall_score)
        trend: Literal["Improving", "Declining", "Stable"] = self._calculate_trend(articles)
        confidence = self._calculate_confidence(breakdown)

        top_articles = sorted(
            articles,
            key=lambda x: abs(x.get('sentiment_score', 0)),
            reverse=True
        )[:5]

        influential_articles = [
            {
                'title': a.get('title'),
                'sentiment': a.get('sentiment_score'),
                'verdict': a.get('verdict'),
                'reasoning': a.get('reasoning'),
                'source': a.get('source'),
                'url': a.get('url')
            }
            for a in top_articles
        ]

        return SentimentalAnalysisResponse(
            ticker=ticker,
            market=market,
            overall_sentiment=overall_sentiment,
            score=round(overall_score, 3),
            news_breakdown=breakdown.model_dump(),
            trend=trend,
            confidence=round(confidence, 2),
            analysis_summary=self._generate_summary(breakdown, overall_sentiment, trend),
            influential_articles=influential_articles,
            cached=cached,
            analyzed_at=datetime.now(timezone.utc)
        )

    def _parse_cached_response(
        self,
        cached_content: str,
        ticker: str,
        market: str
    ) -> SentimentalAnalysisResponse:
        articles = json.loads(cached_content)
        return self._build_response(articles, ticker, market, cached=True)

    def _empty_response(self, ticker: str, market: str) -> SentimentalAnalysisResponse:
        return SentimentalAnalysisResponse(
            ticker=ticker,
            market=market,
            overall_sentiment="Neutral",
            score=0.0,
            news_breakdown={
                'ticker': ticker,
                'article_count': 0,
                'positive_count': 0,
                'negative_count': 0,
                'neutral_count': 0,
                'average_score': 0.0,
                'top_positive_articles': [],
                'top_negative_articles': []
            },
            trend="Stable",
            confidence=0.0,
            analysis_summary=f"No news data available for {ticker}",
            influential_articles=[],
            cached=False,
            analyzed_at=datetime.now(timezone.utc)
        )

    def _calculate_breakdown(self, articles: List[Dict[str, Any]]) -> NewsSentimentBreakdown:
        if not articles:
            return NewsSentimentBreakdown(
                ticker='',
                article_count=0,
                positive_count=0,
                negative_count=0,
                neutral_count=0,
                average_score=0.0,
                top_positive_articles=[],
                top_negative_articles=[]
            )

        scores = [a.get('sentiment_score', 0) for a in articles]
        average_score = sum(scores) / len(scores) if scores else 0

        positive = [a for a in articles if a.get('sentiment_score', 0) > 0.05]
        negative = [a for a in articles if a.get('sentiment_score', 0) < -0.05]
        neutral = [a for a in articles if -0.05 <= a.get('sentiment_score', 0) <= 0.05]

        top_positive = sorted(
            positive,
            key=lambda x: x.get('sentiment_score', 0),
            reverse=True
        )[:3]

        top_negative = sorted(
            negative,
            key=lambda x: x.get('sentiment_score', 0)
        )[:3]

        return NewsSentimentBreakdown(
            ticker=articles[0].get('ticker', ''),
            article_count=len(articles),
            positive_count=len(positive),
            negative_count=len(negative),
            neutral_count=len(neutral),
            average_score=average_score,
            top_positive_articles=[
                {
                    'title': a.get('title'),
                    'score': a.get('sentiment_score'),
                    'verdict': a.get('verdict'),
                    'source': a.get('source')
                }
                for a in top_positive
            ],
            top_negative_articles=[
                {
                    'title': a.get('title'),
                    'score': a.get('sentiment_score'),
                    'verdict': a.get('verdict'),
                    'source': a.get('source')
                }
                for a in top_negative
            ]
        )

    def _score_to_sentiment(self, score: float) -> str:
        if score > 0.05:
            return "Positive"
        elif score < -0.05:
            return "Negative"
        return "Neutral"

    def _calculate_trend(self, articles: List[Dict[str, Any]]) -> str:
        if len(articles) < 3:
            return "Stable"

        scores = [a.get('sentiment_score', 0) for a in articles[:3]]
        recent_avg = sum(scores) / len(scores)

        if len(articles) >= 6:
            recent_scores = [a.get('sentiment_score', 0) for a in articles[3:6]]
            previous_avg = sum(recent_scores) / len(recent_scores)
            change = recent_avg - previous_avg

            if change > 0.1:
                return "Improving"
            elif change < -0.1:
                return "Declining"

        if recent_avg > 0.1:
            return "Improving"
        elif recent_avg < -0.1:
            return "Declining"

        return "Stable"

    def _calculate_confidence(self, breakdown: NewsSentimentBreakdown) -> float:
        if breakdown.article_count == 0:
            return 0.0

        total_articles = breakdown.article_count
        article_count_factor = min(total_articles / 10, 1.0)

        verdict_distribution = [
            breakdown.positive_count,
            breakdown.negative_count,
            breakdown.neutral_count
        ]
        max_verdict_count = max(verdict_distribution)
        consensus_factor = max_verdict_count / total_articles

        return (article_count_factor * 0.5) + (consensus_factor * 0.5)

    def _generate_summary(
        self,
        breakdown: NewsSentimentBreakdown,
        sentiment: str,
        trend: str
    ) -> str:
        return (f"Based on {breakdown.article_count} news articles, "
                f"sentiment is {sentiment} with an average score of {breakdown.average_score:.3f}. "
                f"{breakdown.positive_count} positive, {breakdown.negative_count} negative, "
                f"{breakdown.neutral_count} neutral articles. Trend: {trend}.")
