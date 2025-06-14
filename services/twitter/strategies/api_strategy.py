import os
import re
import logging
from datetime import datetime
from typing import Optional
import httpx

from .base import ExtractionStrategy, TweetData

logger = logging.getLogger(__name__)

class TwitterAPIStrategy(ExtractionStrategy):
    """Official Twitter API v2 strategy"""
    
    def __init__(self, bearer_token: Optional[str] = None):
        self.bearer_token = bearer_token or os.getenv('TWITTER_BEARER_TOKEN')
    
    async def extract(self, tweet_url: str) -> Optional[TweetData]:
        """Extract using official Twitter API v2"""
        if not self.bearer_token:
            return None
            
        try:
            # Parse tweet ID
            tweet_id_match = re.search(r'status/(\d+)', tweet_url)
            if not tweet_id_match:
                return None
            
            tweet_id = tweet_id_match.group(1)
            
            url = f"https://api.twitter.com/2/tweets/{tweet_id}"
            params = {
                'expansions': 'author_id,attachments.media_keys',
                'tweet.fields': 'created_at,public_metrics,text',
                'user.fields': 'username,name,verified',
                'media.fields': 'url,preview_image_url'
            }
            
            headers = {
                'Authorization': f'Bearer {self.bearer_token}'
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if 'data' not in data:
                        return None
                    
                    tweet = data['data']
                    user = data['includes']['users'][0] if 'includes' in data and 'users' in data['includes'] else {}
                    
                    # Extract media URLs
                    media_urls = []
                    if 'includes' in data and 'media' in data['includes']:
                        for media in data['includes']['media']:
                            if 'url' in media:
                                media_urls.append(media['url'])
                    
                    return TweetData(
                        username=user.get('username', 'unknown'),
                        content=tweet['text'],
                        posted_at=datetime.fromisoformat(tweet['created_at'].replace('Z', '+00:00')),
                        tweet_id=tweet_id,
                        tweet_url=tweet_url,
                        user_display_name=user.get('name'),
                        user_verified=user.get('verified', False),
                        retweet_count=tweet.get('public_metrics', {}).get('retweet_count'),
                        like_count=tweet.get('public_metrics', {}).get('like_count'),
                        reply_count=tweet.get('public_metrics', {}).get('reply_count'),
                        quote_count=tweet.get('public_metrics', {}).get('quote_count'),
                        media_urls=media_urls,
                        extraction_method=self.get_name()
                    )
                elif response.status_code == 429:
                    logger.warning("Twitter API rate limit exceeded")
                    return None
                else:
                    logger.warning(f"Twitter API failed with status {response.status_code}: {response.text}")
                    return None
        
        except Exception as e:
            logger.error(f"Twitter API extraction failed: {e}")
            return None
    
    def get_name(self) -> str:
        return "Twitter API v2"
    
    def is_available(self) -> bool:
        return bool(self.bearer_token)