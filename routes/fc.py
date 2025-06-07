from fastapi import APIRouter, HTTPException
import logging
import asyncio

from models.transcription_models import (
    TranscriptionAnalysisInput,
    EnhancedTranscriptionAnalysisResult
)
from schemas.research import (
    AnalysisRequest,
    ResearchRequestAPI,
    EnhancedLLMResearchResponse
)
from services.media.llm_transcription_analysis import llm_analysis_service
from services.core import fact_checking_core_service

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(tags=["fact-checking"])

@router.post("/extract", response_model=EnhancedTranscriptionAnalysisResult)
async def analyze_for_fact_checking(request: AnalysisRequest) -> EnhancedTranscriptionAnalysisResult:
    """
    Analyze transcription for political statements worthy of fact-checking with enhanced metadata.
    
    Args:
        request: Analysis request containing speaker info and transcription
        
    Returns:
        EnhancedTranscriptionAnalysisResult: List of statements with metadata
        
    Raises:
        HTTPException: If analysis fails
    """
    try:
        logger.info(f"Starting enhanced fact-check analysis for speaker: {request.speaker}")
        
        # Convert request to input model
        input_data = TranscriptionAnalysisInput(
            language_code=request.language_code,
            speaker=request.speaker,
            context=request.context,
            transcription=request.transcription
        )
        
        # Perform enhanced analysis
        result = llm_analysis_service.analyze_transcription(input_data)
        
        logger.info(f"Enhanced fact-check analysis completed for {request.speaker}")
        logger.info(f"Found {result.total_statements} statements for fact-checking")
        logger.info(f"Detected language: {result.detected_language}")
        logger.info(f"Dominant categories: {[cat.value for cat in (result.dominant_categories or [])]}")
        
        return result
        
    except Exception as e:
        error_msg = f"Failed to analyze transcription: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)

@router.post("/research", response_model=EnhancedLLMResearchResponse)
async def research_statement(request: ResearchRequestAPI) -> EnhancedLLMResearchResponse:
    """
    Research a statement using the enhanced tri-factor fact-checking service.
    """
    try:
        logger.info(f"Starting tri-factor research for statement: {request.statement[:100]}...")
        logger.info(f"Research will include: LLM data + Web search + Resource analysis")
        
        # Execute the tri-factor research (FIXED: Direct await call)
        result = await fact_checking_core_service.process_research_request(request)
        
        # Log research completion with metadata
        research_sources = []
        if hasattr(result, 'research_metadata') and result.research_metadata:
            research_sources = result.research_metadata.research_sources
        
        logger.info(f"Tri-factor research completed successfully")
        logger.info(f"Research sources used: {', '.join(research_sources) if research_sources else 'LLM only'}")
        logger.info(f"Final confidence score: {getattr(result, 'confidence_score', 'N/A')}")
        
        return result
        
    except Exception as e:
        error_msg = f"Failed to research statement with tri-factor method: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)

@router.get("/research/{research_id}")
async def get_research_result(research_id: str):
    """
    Retrieve a saved research result by ID.
    
    Args:
        research_id: Database ID of the research result
        
    Returns:
        Dict containing the research result data (may include tri-factor research data)
        
    Raises:
        HTTPException: If research result not found
    """
    try:
        logger.info(f"Retrieving research result: {research_id}")
        
        result = fact_checking_core_service.get_research_result(research_id)
        
        if not result:
            logger.warning(f"Research result not found: {research_id}")
            raise HTTPException(status_code=404, detail="Research result not found")
        
        # Add metadata about research method used
        research_method = result.get('research_method', 'Unknown')
        is_tri_factor = 'tri-factor' in research_method.lower() if research_method else False
        
        logger.info(f"Successfully retrieved research result: {research_id}")
        logger.info(f"Research method: {research_method}")
        if is_tri_factor:
            logger.info("Result includes tri-factor research data")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to retrieve research result: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/research")
async def search_research_results(
    search: str = None,
    status: str = None,
    country: str = None,
    category: str = None,
    profile: str = None,
    limit: int = 50,
    offset: int = 0,
    tri_factor_only: bool = False  # New parameter to filter tri-factor results
):
    """
    Search research results with optional filters.
    
    Args:
        search: Text to search for
        status: Filter by status
        country: Filter by country
        category: Filter by category
        profile: Filter by profile ID
        limit: Maximum results to return
        offset: Number of results to skip
        tri_factor_only: Only return results from tri-factor research
        
    Returns:
        List of research results with metadata about research methods used
    """
    try:
        logger.info(f"Searching research results with filters")
        if tri_factor_only:
            logger.info("Filtering for tri-factor research results only")
        
        results = fact_checking_core_service.search_research_results(
            search_text=search,
            status_filter=status,
            country_filter=country,
            category_filter=category,
            profile_filter=profile,
            limit=limit,
            offset=offset
        )
        
        # Filter tri-factor results if requested
        if tri_factor_only:
            original_count = len(results)
            results = [
                r for r in results 
                if r.get('research_method', '').lower().find('tri-factor') >= 0
            ]
            logger.info(f"Filtered {original_count} results to {len(results)} tri-factor results")
        
        # Add metadata about research methods
        tri_factor_count = sum(
            1 for r in results 
            if r.get('research_method', '').lower().find('tri-factor') >= 0
        )
        
        logger.info(f"Found {len(results)} research results ({tri_factor_count} tri-factor)")
        
        return {
            "results": results,
            "count": len(results),
            "tri_factor_count": tri_factor_count,
            "legacy_count": len(results) - tri_factor_count,
            "limit": limit,
            "offset": offset,
            "filters_applied": {
                "search": search,
                "status": status,
                "country": country,
                "category": category,
                "profile": profile,
                "tri_factor_only": tri_factor_only
            }
        }
        
    except Exception as e:
        error_msg = f"Failed to search research results: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/categories")
async def get_available_categories():
    """Get list of available statement categories."""
    try:
        categories = llm_analysis_service.get_available_categories()
        return {
            "categories": categories,
            "count": len(categories)
        }
    except Exception as e:
        error_msg = f"Failed to get categories: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/health")
async def health_check():
    """Health check endpoint for fact-checking service with tri-factor research status."""
    try:
        import os
        
        # FIXED: Use GEMINI_API_KEY instead of GOOGLE_API_KEY
        gemini_available = bool(os.getenv('GOOGLE_API_KEY'))
        firecrawl_available = bool(os.getenv('FIRECRAWL_API_KEY'))
        
        # Check if Firecrawl SDK is available
        try:
            import firecrawl
            firecrawl_sdk_available = True
        except ImportError:
            firecrawl_sdk_available = False
            firecrawl_available = False
        
        return {
            "status": "healthy", 
            "service": "fact-checking",
            "research_capabilities": {
                "llm_research": True,  # Always available
                "web_search": gemini_available,
                "resource_analysis": firecrawl_available,
                "firecrawl_sdk": firecrawl_sdk_available,
                "tri_factor_ready": gemini_available  # Minimum requirement
            },
            "version": "tri-factor-v1.1-sdk"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "degraded",
            "service": "fact-checking", 
            "error": str(e),
            "version": "tri-factor-v1.1-sdk"
        }