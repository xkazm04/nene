from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime
from dataclasses import dataclass
from typing import List

@dataclass
class TweetData:
    """Data structure for extracted tweet information"""
    username: str
    content: str
    posted_at: datetime
    tweet_id: str
    tweet_url: str
    user_display_name: Optional[str] = None
    user_verified: bool = False
    retweet_count: Optional[int] = None
    like_count: Optional[int] = None
    reply_count: Optional[int] = None
    quote_count: Optional[int] = None
    extraction_method: Optional[str] = None
    media_urls: List[str] = None

    def __post_init__(self):
        if self.media_urls is None:
            self.media_urls = []

class ExtractionStrategy(ABC):
    """Base class for extraction strategies"""
    
    @abstractmethod
    async def extract(self, tweet_url: str) -> Optional[TweetData]:
        """Extract tweet data using this strategy"""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get strategy name"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this strategy is available (dependencies installed, etc.)"""
        pass