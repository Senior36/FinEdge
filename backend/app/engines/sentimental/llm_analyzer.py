import json
import asyncio
from typing import Dict, Any, List
import httpx

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class LLMAnalyzer:
    def __init__(self):
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        # Support both OPENROUTER_API_KEY and LLM_API_KEY for compatibility
        self.api_key = getattr(settings, 'OPENROUTER_API_KEY', None) or settings.LLM_API_KEY
        self.model = settings.LLM_MODEL

    async def analyze_news_article(
        self,
        ticker: str,
        title: str,
        body: str
    ) -> Dict[str, Any]:
        if not body or len(body) < 200:
            return {
                "score": 0.0,
                "verdict": "HOLD",
                "reasoning": "Insufficient context for analysis.",
                "confidence": 0.0
            }

        system_message = {
            "role": "system",
            "content": "You are a financial sentiment analyst. Analyze news articles for stock market sentiment and provide a JSON response with these fields: score (number, -1 to 1), verdict (BUY/SELL/HOLD), reasoning (string), confidence (number, 0 to 1)."
        }

        user_message = {
            "role": "user",
            "content": f"""Analyze the following news article for {ticker}:

Title: {title}

Content: {body[:8000]}

Provide a JSON response with:
1. score: Sentiment score from -1 (very negative) to 1 (very positive)
2. verdict: Trading recommendation (BUY, SELL, or HOLD)
3. reasoning: Brief explanation for verdict
4. confidence: Confidence level (0 to 1)"""
        }

        payload = {
            "model": self.model,
            "messages": [system_message, user_message],
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
            "max_tokens": 1000
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://finedge.com",
            "X-Title": "FinEdge"
        }

        max_retries = 2
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        self.api_url,
                        json=payload,
                        headers=headers
                    )

                    if response.status_code == 200:
                        result_data = response.json()
                        content = result_data.get("choices", [{}])[0].get("message", {}).get("content", "{}")

                        try:
                            result = json.loads(content)
                            logger.info(f"LLM analysis for {ticker}: {result.get('verdict')}")
                            return result
                        except json.JSONDecodeError:
                            logger.error(f"Failed to parse LLM response: {content}")
                            return self._fallback_response()

                    else:
                        logger.warning(f"LLM API returned status {response.status_code}: {response.text}")
                        await asyncio.sleep(2)

            except Exception as e:
                logger.warning(f"LLM analysis attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)

        return self._fallback_response()

    def _fallback_response(self) -> Dict[str, Any]:
        return {
            "score": 0.0,
            "verdict": "HOLD",
            "reasoning": "Analysis failed due to API limitations.",
            "confidence": 0.0
        }

    async def analyze_news_batch(
        self,
        articles: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        results = []

        for article in articles:
            analysis = await self.analyze_news_article(
                ticker=article.get('ticker', ''),
                title=article.get('title', ''),
                body=article.get('body', '')
            )
            results.append({
                **article,
                'sentiment_score': analysis.get('score', 0.0),
                'verdict': analysis.get('verdict', 'HOLD'),
                'reasoning': analysis.get('reasoning', ''),
                'confidence': analysis.get('confidence', 0.0)
            })

        return results
