from fastapi import APIRouter, HTTPException
import logging

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
    Research a statement using the core fact-checking service.
    
    Args:
        request: Research request containing the statement, source, context, datetime, etc.
        
    Returns:
        EnhancedLLMResearchResponse: Complete fact-check result with request data
        
    Raises:
        HTTPException: If research fails
    """
    try:
        logger.info(f"Starting fact-check research for statement: {request.statement[:100]}...")
        
        # Use core service for complete fact-checking pipeline
        result = fact_checking_core_service.process_research_request(request)
        
        logger.info("Fact-check research completed successfully")
        return result
        
    except Exception as e:
        error_msg = f"Failed to research statement: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)

@router.get("/research/{research_id}")
async def get_research_result(research_id: str):
    """
    Retrieve a saved research result by ID.
    
    Args:
        research_id: Database ID of the research result
        
    Returns:
        Dict containing the research result data
        
    Raises:
        HTTPException: If research result not found
    """
    try:
        logger.info(f"Retrieving research result: {research_id}")
        
        result = fact_checking_core_service.get_research_result(research_id)
        
        if not result:
            logger.warning(f"Research result not found: {research_id}")
            raise HTTPException(status_code=404, detail="Research result not found")
        
        logger.info(f"Successfully retrieved research result: {research_id}")
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
    offset: int = 0
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
        
    Returns:
        List of research results
    """
    try:
        logger.info(f"Searching research results with filters")
        
        results = fact_checking_core_service.search_research_results(
            search_text=search,
            status_filter=status,
            country_filter=country,
            category_filter=category,
            profile_filter=profile,
            limit=limit,
            offset=offset
        )
        
        logger.info(f"Found {len(results)} research results")
        return {
            "results": results,
            "count": len(results),
            "limit": limit,
            "offset": offset
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
    """Health check endpoint for fact-checking service."""
    return {"status": "healthy", "service": "fact-checking"}