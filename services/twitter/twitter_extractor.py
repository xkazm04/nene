import os
import re
import logging
from typing import Optional, List
import asyncio

from .strategies.base import TweetData, ExtractionStrategy
from .strategies.api_strategy import TwitterAPIStrategy

logger = logging.getLogger(__name__)

class TwitterExtractorService:
    """Enhanced Twitter extraction service with multiple strategies"""
    
    def __init__(self, 
                 twitter_bearer_token: Optional[str] = None,
                 strategy_order: Optional[List[str]] = None):
        
        self.twitter_bearer_token = twitter_bearer_token or os.getenv('TWITTER_BEARER_TOKEN')
        self.strategies: List[ExtractionStrategy] = []
        
        # Default strategy order
        default_order = [
            'TwitterAPI',
            'SyncPlaywright'
        ]
        
        strategy_order = strategy_order or default_order
        
        # Initialize all strategies
        all_strategies = {}
        
        # Add Twitter API if token is available
        if self.twitter_bearer_token:
            all_strategies['TwitterAPI'] = TwitterAPIStrategy(self.twitter_bearer_token)
    
        
        # Add strategies in specified order, only if available
        for strategy_name in strategy_order:
            if strategy_name in all_strategies:
                strategy = all_strategies[strategy_name]
                if strategy.is_available():
                    self.strategies.append(strategy)
                    logger.info(f"Enabled strategy: {strategy.get_name()}")
                else:
                    logger.debug(f"Strategy {strategy_name} not available (missing dependencies)")
            else:
                logger.debug(f"Strategy {strategy_name} not configured")
        
        if not self.strategies:
            logger.warning("No extraction strategies are available!")
        else:
            logger.info(f"Initialized TwitterExtractorService with {len(self.strategies)} available strategies")
    
    async def extract_tweet_data(self, tweet_url: str) -> TweetData:
        """Extract tweet data using the best available method"""
        
        # Validate URL
        if not self.validate_tweet_url(tweet_url):
            raise ValueError(f"Invalid Twitter/X URL: {tweet_url}")
        
        if not self.strategies:
            raise Exception("No extraction strategies are available")
        
        errors = []
        
        # Try each strategy in order
        for strategy in self.strategies:
            try:
                logger.info(f"Attempting extraction with {strategy.get_name()}")
                result = await strategy.extract(tweet_url)
                
                if result and self._validate_extraction(result):
                    logger.info(f"Successfully extracted tweet using {strategy.get_name()}")
                    return result
                else:
                    error_msg = f"{strategy.get_name()}: Invalid data extracted"
                    errors.append(error_msg)
                    logger.debug(error_msg)
                    
            except Exception as e:
                error_msg = f"{strategy.get_name()}: {str(e)}"
                errors.append(error_msg)
                logger.warning(error_msg)
        
        # All strategies failed
        raise Exception(f"All extraction strategies failed. Errors: {'; '.join(errors)}")
    
    def setup_manual_login(self):
        """Setup manual login for Playwright strategy"""
        for strategy in self.strategies:
            if hasattr(strategy, 'manual_login_helper'):
                strategy.manual_login_helper()
                return
        print("No Playwright strategy available for manual login")
    
    def validate_tweet_url(self, url: str) -> bool:
        """Validate Twitter/X URL format"""
        patterns = [
            r'https?://(www\.)?(twitter\.com|x\.com)/\w+/status/\d+',
            r'https?://(www\.)?(mobile\.twitter\.com|mobile\.x\.com)/\w+/status/\d+'
        ]
        return any(re.match(pattern, url) for pattern in patterns)
    
    def _validate_extraction(self, tweet_data: TweetData) -> bool:
        """Validate extracted data quality"""
        if not tweet_data:
            logger.debug("Validation failed: No tweet data")
            return False
        
        # Check essential fields
        if not tweet_data.content or len(tweet_data.content.strip()) < 5:
            logger.debug(f"Validation failed: Content too short or empty ('{tweet_data.content}')")
            return False
        
        if tweet_data.username in ['unknown', ''] or not tweet_data.username:
            logger.debug(f"Validation failed: Username missing or unknown ('{tweet_data.username}')")
            return False
        
        if tweet_data.tweet_id in ['unknown', ''] or not tweet_data.tweet_id:
            logger.debug(f"Validation failed: Tweet ID missing or unknown ('{tweet_data.tweet_id}')")
            return False
        
        # Check for common extraction errors
        error_indicators = [
            'something went wrong',
            'try again',
            'page not found',
            'tweet unavailable',
            'account suspended',
            'content extraction failed',
            'this tweet is unavailable'
        ]
        
        content_lower = tweet_data.content.lower()
        for indicator in error_indicators:
            if indicator in content_lower:
                logger.debug(f"Validation failed: Content contains error indicator '{indicator}'")
                return False
        
        logger.debug(f"Validation passed: Tweet data is valid (content: {len(tweet_data.content)} chars)")
        return True
    
    async def cleanup(self):
        """Cleanup resources used by strategies"""
        for strategy in self.strategies:
            if hasattr(strategy, 'cleanup'):
                try:
                    if asyncio.iscoroutinefunction(strategy.cleanup):
                        await strategy.cleanup()
                    else:
                        strategy.cleanup()
                except Exception as e:
                    logger.warning(f"Failed to cleanup {strategy.get_name()}: {e}")
    
    def get_available_strategies(self) -> List[str]:
        """Get list of available strategy names"""
        return [strategy.get_name() for strategy in self.strategies]

# Create service instance with default configuration
twitter_extractor_service = TwitterExtractorService()