from fastapi import APIRouter, HTTPException
import logging
import time

from schemas.research import ResearchRequestAPI, EnhancedLLMResearchResponse
from schemas.twitter import (
    TwitterResearchRequest,
    TwitterExtractionResponse,
    TwitterResearchResponseSync 
)
from services.core import fact_checking_core_service
from services.twitter.twitter_extractor import twitter_extractor_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["twitter-x"])

@router.post("/research", response_model=EnhancedLLMResearchResponse)
async def research_twitter_statement(request: TwitterResearchRequest) -> EnhancedLLMResearchResponse:
    """
    Research a statement from a Twitter/X tweet using the enhanced tri-factor fact-checking service.
    
    **Returns the same EnhancedLLMResearchResponse format as /fc/research for consistency.**
    
    **Limitations**: Free tier = 1 request per 15 minutes.
    
    This endpoint:
    1. Extracts tweet content, username, and metadata from the provided URL
    2. Runs the extracted tweet content through the tri-factor research pipeline
    3. Returns the same research format as regular quote analysis
    
    Args:
        request: Twitter research request containing tweet URL and optional context
        
    Returns:
        EnhancedLLMResearchResponse: Same format as /fc/research endpoint
        
    Raises:
        HTTPException: If tweet extraction or research fails
    """
    start_time = time.time()
    
    try:
        logger.info(f"Starting Twitter fact-check research for URL: {request.tweet_url}")
        
        # Step 1: Validate URL format
        if not twitter_extractor_service.validate_tweet_url(request.tweet_url):
            raise HTTPException(
                status_code=400, 
                detail="Invalid Twitter/X URL format. Expected: https://x.com/username/status/1234567890"
            )
        
        # Step 2: Extract tweet data
        logger.info("Extracting tweet data...")
        tweet_data = await twitter_extractor_service.extract_tweet_data(request.tweet_url)
        
        if not tweet_data:
            raise HTTPException(
                status_code=400, 
                detail="Failed to extract tweet data. The tweet may be private, deleted, or the URL is invalid."
            )
        
        logger.info(f"Successfully extracted tweet from @{tweet_data.username}: {tweet_data.content[:100]}...")
        
        # Step 3: Prepare research request using same format as fc.py
        # Combine tweet content with additional context
        context_parts = []
        if request.additional_context:
            context_parts.append(f"Additional context: {request.additional_context}")
        
        context_parts.append(f"Source: Tweet by @{tweet_data.username} on {tweet_data.posted_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        if tweet_data.user_display_name:
            context_parts.append(f"User display name: {tweet_data.user_display_name}")
        if tweet_data.user_verified:
            context_parts.append("Account is verified")
        
        # Add engagement metrics if available
        engagement_info = []
        if tweet_data.like_count is not None:
            engagement_info.append(f"{tweet_data.like_count:,} likes")
        if tweet_data.retweet_count is not None:
            engagement_info.append(f"{tweet_data.retweet_count:,} retweets")
        if tweet_data.reply_count is not None:
            engagement_info.append(f"{tweet_data.reply_count:,} replies")
        
        if engagement_info:
            context_parts.append(f"Engagement: {', '.join(engagement_info)}")
        
        context_parts.append(f"Original tweet URL: {request.tweet_url}")
        context_parts.append(f"Extraction method: {tweet_data.extraction_method}")
        
        combined_context = "\n".join(context_parts)
        
        # Create research request using same format as fc.py
        research_request = ResearchRequestAPI(
            statement=tweet_data.content,
            source=f"@{tweet_data.username}",
            context=combined_context,
            datetime=tweet_data.posted_at,
            country=request.country,
            category=None  # Let the system auto-detect category
        )
        
        # Step 4: Perform research using same core service as fc.py
        logger.info("Starting tri-factor research on tweet content...")
        research_result = await fact_checking_core_service.process_research_request(research_request)
        
        # Step 5: Enhance research result with Twitter-specific metadata
        if hasattr(research_result, 'research_method'):
            research_result.research_method = f"Twitter/X Analysis + {research_result.research_method}"
        
        # Add Twitter metadata to research summary
        twitter_metadata = f"""

=== TWITTER/X SOURCE METADATA ===
Username: @{tweet_data.username}
Display Name: {tweet_data.user_display_name or 'N/A'}
Verified Account: {'Yes' if tweet_data.user_verified else 'No'}
Tweet ID: {tweet_data.tweet_id}
Posted: {tweet_data.posted_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
Extraction Method: {tweet_data.extraction_method}
"""
        
        if hasattr(research_result, 'research_summary'):
            research_result.research_summary = f"{research_result.research_summary}{twitter_metadata}"
        
        # Add Twitter-specific findings
        twitter_findings = []
        if tweet_data.user_verified:
            twitter_findings.append("Source account is verified")
        if tweet_data.like_count and tweet_data.like_count > 1000:
            twitter_findings.append(f"High engagement: {tweet_data.like_count:,} likes")
        twitter_findings.append(f"Content extracted via {tweet_data.extraction_method}")
        
        if hasattr(research_result, 'web_findings') and research_result.web_findings:
            research_result.web_findings.extend(twitter_findings)
        else:
            research_result.web_findings = twitter_findings
        
        processing_time = time.time() - start_time
        
        logger.info(f"Twitter fact-check completed successfully in {processing_time:.2f} seconds")
        logger.info(f"Research status: {getattr(research_result, 'status', 'Unknown')}")
        logger.info(f"Confidence score: {getattr(research_result, 'confidence_score', 'N/A')}")
        
        # Return the same EnhancedLLMResearchResponse format as fc.py
        return research_result
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        error_msg = f"Failed to research Twitter statement: {str(e)}"
        logger.error(error_msg)
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/extract", response_model=TwitterExtractionResponse)
async def extract_twitter_content(request: TwitterResearchRequest) -> TwitterExtractionResponse:
    """
    Extract content and metadata from a Twitter/X tweet URL without performing research.
    
    This endpoint only extracts tweet data and can be used for preview or testing purposes.
    
    Args:
        request: Twitter research request containing tweet URL
        
    Returns:
        TwitterExtractionResponse: Extracted tweet data
        
    Raises:
        HTTPException: If tweet extraction fails
    """
    try:
        logger.info(f"Extracting Twitter content for URL: {request.tweet_url}")
        
        # Validate URL format
        if not twitter_extractor_service.validate_tweet_url(request.tweet_url):
            raise HTTPException(
                status_code=400, 
                detail="Invalid Twitter/X URL format. Expected: https://x.com/username/status/1234567890"
            )
        
        # Extract tweet data
        tweet_data = await twitter_extractor_service.extract_tweet_data(request.tweet_url)
        
        if not tweet_data:
            raise HTTPException(
                status_code=400, 
                detail="Failed to extract tweet data. The tweet may be private, deleted, or the URL is invalid."
            )
        
        # Convert to response format
        response = TwitterExtractionResponse(
            username=tweet_data.username,
            content=tweet_data.content,
            posted_at=tweet_data.posted_at,
            tweet_id=tweet_data.tweet_id,
            tweet_url=tweet_data.tweet_url,
            user_display_name=tweet_data.user_display_name,
            user_verified=tweet_data.user_verified,
            retweet_count=tweet_data.retweet_count,
            like_count=tweet_data.like_count,
            reply_count=tweet_data.reply_count,
            extraction_method=tweet_data.extraction_method
        )
        
        logger.info(f"Successfully extracted tweet from @{tweet_data.username}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to extract Twitter content: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)