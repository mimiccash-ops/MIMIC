"""
MIMIC - Twitter/X Auto-Poster for Successful Trades

This script automatically posts to Twitter/X when trades with ROI > threshold are closed.
It can be run as a standalone worker or integrated into the main trading engine.

Features:
- Posts tweets for trades with ROI >= configured threshold (default 50%)
- Rate limiting to avoid spam (max 1 tweet per minute, 50 per day)
- Queue-based processing for reliability
- Supports both standalone mode and integration with trading engine
- Emoji-rich formatted tweets with hashtags for engagement

Setup:
1. Create a Twitter Developer account: https://developer.twitter.com
2. Create an App with Read and Write permissions
3. Generate Access Token and Secret
4. Set environment variables or configure in config.ini:
   - TWITTER_API_KEY
   - TWITTER_API_SECRET
   - TWITTER_ACCESS_TOKEN
   - TWITTER_ACCESS_SECRET
   - TWITTER_MIN_ROI_THRESHOLD (optional, default 50.0)

Usage:
    Standalone mode (monitors database for new trades):
        python post_to_twitter.py
    
    Integration mode (call from trading engine):
        from post_to_twitter import TwitterPoster
        poster = TwitterPoster()
        poster.post_trade(symbol='BTCUSDT', roi=75.5, pnl=150.0)
"""

import tweepy
import logging
import time
import threading
from datetime import datetime, timezone, timedelta
from collections import deque
from queue import Queue, Empty
from typing import Optional, Dict, Any
import random

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TwitterPoster")


class TwitterPoster:
    """
    Twitter/X poster for successful trades.
    
    Rate limits:
    - Minimum 60 seconds between tweets
    - Maximum 50 tweets per 24 hours
    """
    
    # Tweet templates with variety for engagement
    TWEET_TEMPLATES = [
        "🔥 Another {roi:.1f}% ROI trade on #MIMIC!\n\n💰 {symbol} closed with ${pnl:.2f} profit\n\n📈 Copy pro traders now: {link}\n\n#Bitcoin #Trading #Crypto #CopyTrading",
        "💎 {roi:.1f}% ROI just hit! 🚀\n\n{symbol} trade closed: +${pnl:.2f}\n\nMIMIC copy trading is 🔥\n\n👉 {link}\n\n#Crypto #Trading #MIMIC",
        "📊 Trade Alert: {symbol}\n\n✅ ROI: {roi:.1f}%\n💵 Profit: ${pnl:.2f}\n\nAutomatic copy trading FTW! 🎯\n\n{link}\n\n#CryptoTrading #Bitcoin #MIMIC",
        "🎯 BOOM! {roi:.1f}% ROI\n\n{symbol} just printed ${pnl:.2f} 💰\n\nCopy the best traders automatically 🤖\n\n{link}\n\n#Trading #Crypto #MIMIC #Binance",
        "⚡ {symbol}: +{roi:.1f}% ROI!\n\n${pnl:.2f} profit locked in ✅\n\nMIMIC copy trading = passive profits 📈\n\nStart now: {link}\n\n#CryptoTrading #Bitcoin #MIMIC",
    ]
    
    # Bonus emojis for extra high ROI trades
    HIGH_ROI_PREFIX = [
        "🚀🚀🚀 MEGA TRADE! ",
        "💎💎💎 DIAMOND HANDS PAID OFF! ",
        "🔥🔥🔥 ON FIRE! ",
        "⚡⚡⚡ LIGHTNING TRADE! ",
        "🎰 JACKPOT! ",
    ]
    
    def __init__(self, 
                 api_key: str = None, 
                 api_secret: str = None,
                 access_token: str = None, 
                 access_secret: str = None,
                 min_roi_threshold: float = None,
                 site_url: str = None):
        """
        Initialize the Twitter poster.
        
        Args:
            api_key: Twitter API key (or set TWITTER_API_KEY env var)
            api_secret: Twitter API secret (or set TWITTER_API_SECRET env var)
            access_token: Twitter access token (or set TWITTER_ACCESS_TOKEN env var)
            access_secret: Twitter access secret (or set TWITTER_ACCESS_SECRET env var)
            min_roi_threshold: Minimum ROI % to trigger a tweet (default: 50.0)
            site_url: Site URL for tweet links (default: https://mimic.cash)
        """
        # Load config
        try:
            from config import Config
            self.api_key = api_key or Config.TWITTER_API_KEY
            self.api_secret = api_secret or Config.TWITTER_API_SECRET
            self.access_token = access_token or Config.TWITTER_ACCESS_TOKEN
            self.access_secret = access_secret or Config.TWITTER_ACCESS_SECRET
            self.min_roi_threshold = min_roi_threshold or Config.TWITTER_MIN_ROI_THRESHOLD
            self.site_url = site_url or Config.SITE_URL
            self.enabled = Config.TWITTER_ENABLED
        except ImportError:
            import os
            self.api_key = api_key or os.environ.get('TWITTER_API_KEY', '')
            self.api_secret = api_secret or os.environ.get('TWITTER_API_SECRET', '')
            self.access_token = access_token or os.environ.get('TWITTER_ACCESS_TOKEN', '')
            self.access_secret = access_secret or os.environ.get('TWITTER_ACCESS_SECRET', '')
            self.min_roi_threshold = min_roi_threshold or float(os.environ.get('TWITTER_MIN_ROI_THRESHOLD', '50.0'))
            self.site_url = site_url or os.environ.get('SITE_URL', 'https://mimic.cash')
            self.enabled = bool(self.api_key and self.api_secret and self.access_token and self.access_secret)
        
        # Rate limiting
        self.last_tweet_time: Optional[datetime] = None
        self.tweet_history: deque = deque(maxlen=50)  # Track last 50 tweets for daily limit
        self.min_interval_seconds = 60  # Minimum 60 seconds between tweets
        self.max_tweets_per_day = 50
        
        # Queue for processing trades
        self.tweet_queue: Queue = Queue()
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Initialize Twitter client
        self.client: Optional[tweepy.Client] = None
        if self.enabled:
            self._init_client()
    
    def _init_client(self):
        """Initialize the Twitter API v2 client."""
        try:
            self.client = tweepy.Client(
                consumer_key=self.api_key,
                consumer_secret=self.api_secret,
                access_token=self.access_token,
                access_token_secret=self.access_secret,
                wait_on_rate_limit=True
            )
            # Test the connection
            me = self.client.get_me()
            if me.data:
                logger.info(f"✅ Twitter connected as @{me.data.username}")
            else:
                logger.warning("⚠️ Twitter client initialized but couldn't verify account")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Twitter client: {e}")
            self.client = None
            self.enabled = False
    
    def _can_tweet(self) -> tuple[bool, str]:
        """
        Check if we can send a tweet based on rate limits.
        
        Returns:
            (can_tweet, reason)
        """
        now = datetime.now(timezone.utc)
        
        # Check minimum interval
        if self.last_tweet_time:
            elapsed = (now - self.last_tweet_time).total_seconds()
            if elapsed < self.min_interval_seconds:
                return False, f"Rate limit: {self.min_interval_seconds - elapsed:.0f}s remaining"
        
        # Check daily limit
        cutoff = now - timedelta(hours=24)
        recent_tweets = [t for t in self.tweet_history if t > cutoff]
        if len(recent_tweets) >= self.max_tweets_per_day:
            return False, f"Daily limit reached ({self.max_tweets_per_day} tweets/day)"
        
        return True, "OK"
    
    def _format_tweet(self, symbol: str, roi: float, pnl: float) -> str:
        """
        Format a tweet for a successful trade.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            roi: Return on investment percentage
            pnl: Profit/Loss in USD
        
        Returns:
            Formatted tweet text
        """
        # Clean up symbol (remove USDT suffix for readability)
        clean_symbol = symbol.replace('USDT', '').replace('BUSD', '')
        
        # Select a random template
        template = random.choice(self.TWEET_TEMPLATES)
        
        # Add prefix for extra high ROI trades (100%+)
        prefix = ""
        if roi >= 100:
            prefix = random.choice(self.HIGH_ROI_PREFIX)
        
        tweet = prefix + template.format(
            symbol=clean_symbol,
            roi=roi,
            pnl=abs(pnl),  # Always show positive
            link=self.site_url
        )
        
        # Ensure tweet is within character limit (280 chars)
        if len(tweet) > 280:
            # Truncate and add ellipsis
            tweet = tweet[:277] + "..."
        
        return tweet
    
    def post_trade(self, symbol: str, roi: float, pnl: float, async_post: bool = True) -> Dict[str, Any]:
        """
        Post a trade to Twitter if it meets the ROI threshold.
        
        Args:
            symbol: Trading pair symbol
            roi: Return on investment percentage
            pnl: Profit/Loss in USD
            async_post: If True, queue the post for async processing
        
        Returns:
            Dict with status and message
        """
        # Check if enabled
        if not self.enabled or not self.client:
            return {'success': False, 'message': 'Twitter posting is not configured'}
        
        # Check ROI threshold
        if roi < self.min_roi_threshold:
            return {'success': False, 'message': f'ROI {roi:.1f}% below threshold {self.min_roi_threshold}%'}
        
        # Check rate limits
        can_tweet, reason = self._can_tweet()
        if not can_tweet:
            if async_post:
                # Queue for later
                self.tweet_queue.put({
                    'symbol': symbol,
                    'roi': roi,
                    'pnl': pnl,
                    'timestamp': datetime.now(timezone.utc)
                })
                return {'success': True, 'message': f'Queued for later: {reason}'}
            return {'success': False, 'message': reason}
        
        if async_post:
            self.tweet_queue.put({
                'symbol': symbol,
                'roi': roi,
                'pnl': pnl,
                'timestamp': datetime.now(timezone.utc)
            })
            return {'success': True, 'message': 'Tweet queued for posting'}
        
        # Post immediately
        return self._do_post(symbol, roi, pnl)
    
    def _do_post(self, symbol: str, roi: float, pnl: float) -> Dict[str, Any]:
        """Actually post the tweet to Twitter."""
        try:
            tweet_text = self._format_tweet(symbol, roi, pnl)
            
            response = self.client.create_tweet(text=tweet_text)
            
            if response.data:
                tweet_id = response.data['id']
                now = datetime.now(timezone.utc)
                self.last_tweet_time = now
                self.tweet_history.append(now)
                
                logger.info(f"✅ Tweet posted: {tweet_id} - {symbol} {roi:.1f}% ROI")
                return {
                    'success': True, 
                    'message': 'Tweet posted successfully',
                    'tweet_id': tweet_id,
                    'tweet_text': tweet_text
                }
            else:
                logger.error("❌ Tweet failed: No response data")
                return {'success': False, 'message': 'Tweet failed: No response data'}
                
        except tweepy.TweepyException as e:
            logger.error(f"❌ Twitter API error: {e}")
            return {'success': False, 'message': f'Twitter API error: {str(e)}'}
        except Exception as e:
            logger.error(f"❌ Unexpected error posting tweet: {e}")
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    def start_worker(self):
        """Start the background worker thread for processing queued tweets."""
        if self._running:
            return
        
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        logger.info("🐦 Twitter poster worker started")
    
    def stop_worker(self):
        """Stop the background worker thread."""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        logger.info("🐦 Twitter poster worker stopped")
    
    def _worker_loop(self):
        """Background worker loop for processing tweet queue."""
        while self._running:
            try:
                # Wait for a tweet in the queue (with timeout for clean shutdown)
                try:
                    trade = self.tweet_queue.get(timeout=1.0)
                except Empty:
                    continue
                
                # Check if we can tweet now
                can_tweet, reason = self._can_tweet()
                if not can_tweet:
                    # Put it back in the queue and wait
                    self.tweet_queue.put(trade)
                    time.sleep(10)  # Wait 10 seconds before retrying
                    continue
                
                # Post the tweet
                self._do_post(
                    symbol=trade['symbol'],
                    roi=trade['roi'],
                    pnl=trade['pnl']
                )
                
                # Mark task as done
                self.tweet_queue.task_done()
                
            except Exception as e:
                logger.error(f"Worker error: {e}")
                time.sleep(5)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get posting statistics."""
        now = datetime.now(timezone.utc)
        cutoff_24h = now - timedelta(hours=24)
        tweets_24h = len([t for t in self.tweet_history if t > cutoff_24h])
        
        return {
            'enabled': self.enabled,
            'min_roi_threshold': self.min_roi_threshold,
            'tweets_last_24h': tweets_24h,
            'max_tweets_per_day': self.max_tweets_per_day,
            'tweets_remaining': self.max_tweets_per_day - tweets_24h,
            'queue_size': self.tweet_queue.qsize(),
            'last_tweet': self.last_tweet_time.isoformat() if self.last_tweet_time else None,
            'site_url': self.site_url
        }


# Global poster instance
_poster: Optional[TwitterPoster] = None


def get_twitter_poster() -> TwitterPoster:
    """Get or create the global Twitter poster instance."""
    global _poster
    if _poster is None:
        _poster = TwitterPoster()
    return _poster


def init_twitter_poster() -> TwitterPoster:
    """Initialize and return the Twitter poster with worker started."""
    poster = get_twitter_poster()
    if poster.enabled:
        poster.start_worker()
    return poster


def post_successful_trade(symbol: str, roi: float, pnl: float) -> Dict[str, Any]:
    """
    Convenience function to post a successful trade.
    
    Args:
        symbol: Trading pair symbol
        roi: Return on investment percentage
        pnl: Profit/Loss in USD
    
    Returns:
        Dict with status and message
    """
    poster = get_twitter_poster()
    return poster.post_trade(symbol, roi, pnl)


# ==================== STANDALONE MODE ====================

def run_standalone():
    """
    Run the Twitter poster in standalone mode.
    
    This mode monitors the database for new high-ROI trades
    and posts them to Twitter automatically.
    """
    import sys
    import os
    
    # Add parent directory to path for imports
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    try:
        from flask import Flask
        from config import Config
        from models import db, TradeHistory
        
        # Create minimal Flask app for database access
        app = Flask(__name__)
        app.config.from_object(Config)
        db.init_app(app)
        
        poster = init_twitter_poster()
        
        if not poster.enabled:
            logger.error("❌ Twitter is not configured. Please set API credentials.")
            logger.info("See config.ini.example for setup instructions.")
            return
        
        logger.info(f"🐦 Twitter Poster started (threshold: {poster.min_roi_threshold}% ROI)")
        logger.info(f"📊 Monitoring for high-ROI trades...")
        
        # Track last processed trade ID
        last_processed_id = 0
        
        with app.app_context():
            # Get the last trade ID to start from
            last_trade = TradeHistory.query.order_by(TradeHistory.id.desc()).first()
            if last_trade:
                last_processed_id = last_trade.id
            
            logger.info(f"Starting from trade ID: {last_processed_id}")
            
            while True:
                try:
                    # Check for new high-ROI trades
                    new_trades = TradeHistory.query.filter(
                        TradeHistory.id > last_processed_id,
                        TradeHistory.roi >= poster.min_roi_threshold,
                        TradeHistory.pnl > 0  # Only profitable trades
                    ).order_by(TradeHistory.id.asc()).all()
                    
                    for trade in new_trades:
                        logger.info(f"🎯 Found high-ROI trade: {trade.symbol} {trade.roi:.1f}% ROI")
                        result = poster.post_trade(
                            symbol=trade.symbol,
                            roi=trade.roi,
                            pnl=trade.pnl
                        )
                        logger.info(f"   Result: {result['message']}")
                        last_processed_id = trade.id
                    
                    # Sleep between checks
                    time.sleep(10)  # Check every 10 seconds
                    
                except KeyboardInterrupt:
                    logger.info("Shutting down...")
                    break
                except Exception as e:
                    logger.error(f"Error in main loop: {e}")
                    time.sleep(30)  # Wait longer on errors
        
        poster.stop_worker()
        
    except ImportError as e:
        logger.error(f"Import error: {e}")
        logger.error("Make sure you're running from the project directory")


if __name__ == '__main__':
    print("""
╔═══════════════════════════════════════════════════════════════╗
║           MIMIC - Twitter Auto-Poster for Trades              ║
╠═══════════════════════════════════════════════════════════════╣
║  This script monitors for high-ROI trades and posts them      ║
║  to Twitter/X automatically.                                  ║
║                                                               ║
║  Configuration:                                               ║
║  - Set TWITTER_API_KEY, TWITTER_API_SECRET                    ║
║  - Set TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET            ║
║  - Optional: TWITTER_MIN_ROI_THRESHOLD (default: 50%)         ║
╚═══════════════════════════════════════════════════════════════╝
    """)
    run_standalone()
