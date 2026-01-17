"""
Brain Capital - AI Sentiment Filter Module

Fetches and manages the Crypto Fear & Greed Index for intelligent
risk adjustment during extreme market conditions.

Features:
- Fetches Fear & Greed Index from Alternative.me API
- Caches values in Redis for efficient access
- Calculates risk adjustments based on sentiment:
  * Index > 80 (Extreme Greed) + LONG = reduce risk by 20%
  * Index < 20 (Extreme Fear) + SHORT = reduce risk by 20%
- Provides status endpoint for dashboard display
"""

import logging
import httpx
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger("Sentiment")

# Fear & Greed Index API
FEAR_GREED_API_URL = "https://api.alternative.me/fng/"

# Redis keys for sentiment data
REDIS_KEY_SENTIMENT = "market:sentiment:fear_greed"
REDIS_KEY_SENTIMENT_TIMESTAMP = "market:sentiment:timestamp"
REDIS_KEY_SENTIMENT_CLASSIFICATION = "market:sentiment:classification"

# Sentiment thresholds
EXTREME_FEAR_THRESHOLD = 20  # Index < 20 = Extreme Fear
EXTREME_GREED_THRESHOLD = 80  # Index > 80 = Extreme Greed
RISK_REDUCTION_PERCENT = 20  # Reduce risk by 20% during extreme conditions

# Sentiment classifications
SENTIMENT_CLASSIFICATIONS = {
    "extreme_fear": {"min": 0, "max": 20, "label": "Extreme Fear", "color": "#ff3d00"},
    "fear": {"min": 21, "max": 40, "label": "Fear", "color": "#ff9100"},
    "neutral": {"min": 41, "max": 60, "label": "Neutral", "color": "#ffc400"},
    "greed": {"min": 61, "max": 80, "label": "Greed", "color": "#76ff03"},
    "extreme_greed": {"min": 81, "max": 100, "label": "Extreme Greed", "color": "#00e676"},
}


class SentimentManager:
    """
    Manages market sentiment data for AI-powered risk adjustments.
    
    Uses Redis for caching and provides methods for:
    - Fetching current Fear & Greed Index
    - Calculating risk adjustments based on sentiment
    - Providing sentiment data for dashboard display
    """
    
    def __init__(self, redis_client=None):
        """
        Initialize the SentimentManager.
        
        Args:
            redis_client: Async Redis client for caching sentiment data
        """
        self.redis = redis_client
        self._fallback_sentiment = {
            "value": 50,  # Neutral
            "classification": "neutral",
            "timestamp": None,
            "source": "fallback"
        }
        logger.info("🧠 SentimentManager initialized")
    
    def set_redis_client(self, redis_client):
        """Set the Redis client for caching."""
        self.redis = redis_client
        logger.info("🔗 Redis client set for SentimentManager")
    
    async def fetch_fear_greed_index(self) -> Dict[str, Any]:
        """
        Fetch the current Fear & Greed Index from Alternative.me API.
        
        Returns:
            dict with 'value', 'classification', 'timestamp', 'source'
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(FEAR_GREED_API_URL)
                response.raise_for_status()
                data = response.json()
                
                if data.get("data") and len(data["data"]) > 0:
                    fng_data = data["data"][0]
                    value = int(fng_data.get("value", 50))
                    classification = self._classify_sentiment(value)
                    
                    result = {
                        "value": value,
                        "classification": classification,
                        "value_classification": fng_data.get("value_classification", ""),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "api_timestamp": fng_data.get("timestamp"),
                        "source": "api"
                    }
                    
                    logger.info(f"📊 Fear & Greed Index fetched: {value} ({classification})")
                    return result
                else:
                    logger.warning("⚠️ Fear & Greed API returned empty data")
                    return self._fallback_sentiment
                    
        except httpx.TimeoutException:
            logger.error("⏱️ Fear & Greed API timeout")
            return await self._get_cached_sentiment() or self._fallback_sentiment
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Fear & Greed API HTTP error: {e.response.status_code}")
            return await self._get_cached_sentiment() or self._fallback_sentiment
        except Exception as e:
            logger.error(f"❌ Fear & Greed API error: {e}")
            return await self._get_cached_sentiment() or self._fallback_sentiment
    
    def _classify_sentiment(self, value: int) -> str:
        """Classify sentiment value into category."""
        for classification, ranges in SENTIMENT_CLASSIFICATIONS.items():
            if ranges["min"] <= value <= ranges["max"]:
                return classification
        return "neutral"
    
    async def update_sentiment(self) -> Dict[str, Any]:
        """
        Fetch and cache the current sentiment in Redis.
        
        This method should be called hourly by a cron job.
        
        Returns:
            dict with sentiment data
        """
        sentiment = await self.fetch_fear_greed_index()
        
        if self.redis and sentiment.get("source") == "api":
            try:
                await self.redis.set(
                    REDIS_KEY_SENTIMENT, 
                    str(sentiment["value"]),
                    ex=7200  # Expire after 2 hours (buffer for hourly update)
                )
                await self.redis.set(
                    REDIS_KEY_SENTIMENT_CLASSIFICATION,
                    sentiment["classification"],
                    ex=7200
                )
                await self.redis.set(
                    REDIS_KEY_SENTIMENT_TIMESTAMP,
                    sentiment["timestamp"],
                    ex=7200
                )
                logger.info(f"✅ Sentiment cached in Redis: {sentiment['value']}")
            except Exception as e:
                logger.error(f"❌ Failed to cache sentiment in Redis: {e}")
        
        return sentiment
    
    async def _get_cached_sentiment(self) -> Optional[Dict[str, Any]]:
        """Get cached sentiment from Redis."""
        if not self.redis:
            return None
        
        try:
            value = await self.redis.get(REDIS_KEY_SENTIMENT)
            if value:
                classification = await self.redis.get(REDIS_KEY_SENTIMENT_CLASSIFICATION)
                timestamp = await self.redis.get(REDIS_KEY_SENTIMENT_TIMESTAMP)
                
                return {
                    "value": int(value),
                    "classification": classification.decode() if isinstance(classification, bytes) else classification,
                    "timestamp": timestamp.decode() if isinstance(timestamp, bytes) else timestamp,
                    "source": "cache"
                }
        except RuntimeError as e:
            if "attached to a different loop" in str(e):
                logger.debug(f"Sentiment cache skipped due to event loop conflict: {e}")
            else:
                logger.error(f"❌ Failed to get cached sentiment: {e}")
        except Exception as e:
            logger.error(f"❌ Failed to get cached sentiment: {e}")
        
        return None
    
    async def get_current_sentiment(self) -> Dict[str, Any]:
        """
        Get the current sentiment (from cache or API).
        
        Returns:
            dict with sentiment data
        """
        # Try cache first
        cached = await self._get_cached_sentiment()
        if cached:
            return cached
        
        # Fetch fresh if no cache
        return await self.fetch_fear_greed_index()
    
    async def calculate_risk_adjustment(
        self, 
        side: str, 
        base_risk: float
    ) -> Tuple[float, Optional[str]]:
        """
        Calculate adjusted risk based on market sentiment.
        
        AI Sentiment Filter Logic:
        - If Index > 80 (Extreme Greed) AND side == 'LONG': reduce risk by 20%
          (Prevent buying at market tops)
        - If Index < 20 (Extreme Fear) AND side == 'SHORT': reduce risk by 20%
          (Prevent selling at market bottoms)
        
        Args:
            side: Trade side ('LONG' or 'SHORT')
            base_risk: Base risk percentage (e.g., 3.0 for 3%)
        
        Returns:
            tuple of (adjusted_risk, adjustment_reason)
            - adjusted_risk: The final risk percentage
            - adjustment_reason: Human-readable reason or None if no adjustment
        """
        sentiment = await self.get_current_sentiment()
        value = sentiment.get("value", 50)
        side_upper = side.upper()
        
        adjustment_reason = None
        adjusted_risk = base_risk
        
        # Extreme Greed + LONG = reduce risk (prevent buying tops)
        if value > EXTREME_GREED_THRESHOLD and side_upper == "LONG":
            reduction = base_risk * (RISK_REDUCTION_PERCENT / 100)
            adjusted_risk = base_risk - reduction
            adjustment_reason = f"AI Sentiment: Extreme Greed ({value}) - LONG risk reduced by {RISK_REDUCTION_PERCENT}%"
            logger.info(f"🧠 {adjustment_reason}: {base_risk}% → {adjusted_risk}%")
        
        # Extreme Fear + SHORT = reduce risk (prevent selling bottoms)
        elif value < EXTREME_FEAR_THRESHOLD and side_upper == "SHORT":
            reduction = base_risk * (RISK_REDUCTION_PERCENT / 100)
            adjusted_risk = base_risk - reduction
            adjustment_reason = f"AI Sentiment: Extreme Fear ({value}) - SHORT risk reduced by {RISK_REDUCTION_PERCENT}%"
            logger.info(f"🧠 {adjustment_reason}: {base_risk}% → {adjusted_risk}%")
        
        return adjusted_risk, adjustment_reason
    
    async def get_sentiment_status(self) -> Dict[str, Any]:
        """
        Get full sentiment status for API/dashboard display.
        
        Returns:
            dict with:
            - value: Current Fear & Greed Index (0-100)
            - classification: 'extreme_fear', 'fear', 'neutral', 'greed', 'extreme_greed'
            - label: Human-readable label
            - color: Color code for display
            - risk_adjustments: Current risk adjustment rules
            - last_updated: Timestamp
        """
        sentiment = await self.get_current_sentiment()
        value = sentiment.get("value", 50)
        classification = sentiment.get("classification", "neutral")
        
        # Get classification details
        class_details = SENTIMENT_CLASSIFICATIONS.get(classification, {
            "label": "Unknown",
            "color": "#808080"
        })
        
        # Determine active risk adjustments
        adjustments = []
        if value > EXTREME_GREED_THRESHOLD:
            adjustments.append({
                "affected": "LONG",
                "adjustment": f"-{RISK_REDUCTION_PERCENT}% risk",
                "reason": "Extreme Greed - preventing buying tops"
            })
        elif value < EXTREME_FEAR_THRESHOLD:
            adjustments.append({
                "affected": "SHORT",
                "adjustment": f"-{RISK_REDUCTION_PERCENT}% risk",
                "reason": "Extreme Fear - preventing selling bottoms"
            })
        
        return {
            "value": value,
            "classification": classification,
            "label": class_details.get("label", classification.replace("_", " ").title()),
            "color": class_details.get("color", "#808080"),
            "risk_adjustments": adjustments,
            "is_extreme": value < EXTREME_FEAR_THRESHOLD or value > EXTREME_GREED_THRESHOLD,
            "last_updated": sentiment.get("timestamp"),
            "source": sentiment.get("source", "unknown")
        }


# Singleton instance for the sentiment manager (set in worker startup)
_sentiment_manager: Optional[SentimentManager] = None


def get_sentiment_manager() -> Optional[SentimentManager]:
    """Get the global sentiment manager instance."""
    return _sentiment_manager


def set_sentiment_manager(manager: SentimentManager):
    """Set the global sentiment manager instance."""
    global _sentiment_manager
    _sentiment_manager = manager
    logger.info("🧠 Global SentimentManager instance set")


async def update_market_sentiment(redis_client=None) -> Dict[str, Any]:
    """
    Utility function to update market sentiment.
    
    Can be called directly or via ARQ task.
    
    Args:
        redis_client: Optional Redis client (uses global manager if not provided)
    
    Returns:
        dict with sentiment data
    """
    global _sentiment_manager
    
    if redis_client:
        manager = SentimentManager(redis_client)
    elif _sentiment_manager:
        manager = _sentiment_manager
    else:
        manager = SentimentManager()
    
    return await manager.update_sentiment()
