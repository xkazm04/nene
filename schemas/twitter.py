from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
from schemas.research import EnhancedLLMResearchResponse

class TwitterResearchRequest(BaseModel):
    """Request model for Twitter research endpoints"""
    tweet_url: str = Field(..., description="Twitter/X tweet URL to analyze")
    additional_context: Optional[str] = Field(None, description="Additional context for the research")
    country: Optional[str] = Field(None, description="Country context for fact-checking")

    @validator('tweet_url')
    def validate_tweet_url(cls, v):
        """Validate that the URL is a valid Twitter/X URL"""
        import re
        patterns = [
            r'https?://(www\.)?(twitter\.com|x\.com)/\w+/status/\d+',
            r'https?://(www\.)?(mobile\.twitter\.com|mobile\.x\.com)/\w+/status/\d+'
        ]
        
        if not any(re.match(pattern, v) for pattern in patterns):
            raise ValueError('Invalid Twitter/X URL format. Expected format: https://x.com/username/status/1234567890')
        
        return v

class TwitterExtractionResponse(BaseModel):
    """Response model for extracted Twitter data"""
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
    extraction_method: str

# DEPRECATED: Use EnhancedLLMResearchResponse directly instead
class TwitterResearchResponseSync(BaseModel):
    """
    DEPRECATED: Legacy response model for Twitter research results
    Use EnhancedLLMResearchResponse directly for consistency with fc.py
    """
    tweet_data: TwitterExtractionResponse
    research_result: EnhancedLLMResearchResponse
    research_method: str
    
    class Config:
        deprecated = True

# Legacy alias for backward compatibility
TwitterResearchResponse = TwitterResearchResponseSync