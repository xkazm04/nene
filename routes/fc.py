from fastapi import APIRouter, HTTPException
from datetime import datetime
import logging
from services.llm_transcription_analysis import (
    llm_analysis_service, 
    TranscriptionAnalysisInput, 
    TranscriptionAnalysisResult
)
from services.llm_research import llm_research_service
from models.research_models import (
    LLMResearchRequest,
    ExpertOpinion,
    StatementCategory
)
from schemas.research import (
    AnalysisRequest,
    ResearchRequestAPI,
    EnhancedLLMResearchResponse
)
from services.db_research import db_research_service, ResearchRequest
from services.profile import profile_service  # Add this import

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(tags=["fact-checking"])

@router.post("/extract", response_model=TranscriptionAnalysisResult)
async def analyze_for_fact_checking(request: AnalysisRequest) -> TranscriptionAnalysisResult:
    """
    Analyze transcription for political statements worthy of fact-checking.
    
    Args:
        request: Analysis request containing speaker info and transcription
        
    Returns:
        TranscriptionAnalysisResult: List of statements identified for fact-checking
        
    Raises:
        HTTPException: If analysis fails
    """
    try:
        logger.info(f"Starting fact-check analysis for speaker: {request.speaker}")
        
        # Convert request to input model
        input_data = TranscriptionAnalysisInput(
            language_code=request.language_code,
            speaker=request.speaker,
            context=request.context,
            transcription=request.transcription
        )
        
        # Perform analysis
        result = llm_analysis_service.analyze_transcription(input_data)
        
        logger.info(f"Fact-check analysis completed for {request.speaker}")
        logger.info(f"Found {result.total_statements} statements for fact-checking")
        
        return result
        
    except Exception as e:
        error_msg = f"Failed to analyze transcription: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)

@router.post("/research", response_model=EnhancedLLMResearchResponse)
async def research_statement(request: ResearchRequestAPI) -> EnhancedLLMResearchResponse:
    """
    Research a statement using LLM knowledge base for fact-checking.
    
    Args:
        request: Research request containing the statement, source, context, datetime, statement_date, country, and category
        
    Returns:
        EnhancedLLMResearchResponse: Complete fact-check result with request data
        
    Raises:
        HTTPException: If research fails
    """
    try:
        logger.info(f"Starting LLM research for statement: {request.statement[:100]}...")
        logger.info(f"Source: {request.source}, Country: {request.country}, Category: {request.category}")
        
        # Process speaker profile (non-blocking) and get profile_id
        profile_id = None
        if request.source and request.source.strip() and request.source != "Unknown":
            try:
                profile_id = profile_service.get_or_create_profile(request.source)
                if profile_id:
                    logger.debug(f"Profile processed for speaker: {request.source} -> {profile_id}")
                else:
                    logger.warning(f"Failed to process profile for speaker: {request.source}")
            except Exception as profile_error:
                # Non-blocking: log error but continue with research
                logger.error(f"Profile processing failed for speaker '{request.source}': {str(profile_error)}")
        
        # Check for duplicates first
        database_id = None
        is_duplicate = False
        
        try:
            existing_id = db_research_service.check_duplicate_statement(request.statement)
            if existing_id:
                logger.info(f"Duplicate statement found - retrieving existing result: {existing_id}")
                existing_result = db_research_service.get_research_result(existing_id)
                
                if existing_result:
                    # Return existing result instead of processing again
                    return EnhancedLLMResearchResponse(
                        request=request,
                        valid_sources=existing_result.get("valid_sources", ""),
                        verdict=existing_result.get("verdict", ""),
                        status=existing_result.get("status", "UNVERIFIABLE"),
                        correction=existing_result.get("correction"),
                        country=existing_result.get("country"),
                        category=StatementCategory(existing_result.get("category")) if existing_result.get("category") else None,
                        resources_agreed=existing_result.get("resources_agreed", {}),
                        resources_disagreed=existing_result.get("resources_disagreed", {}),
                        experts=ExpertOpinion(**existing_result.get("experts", {})),
                        processed_at=datetime.fromisoformat(existing_result.get("processed_at", datetime.utcnow().isoformat())),
                        database_id=existing_id,
                        is_duplicate=True,
                        profile_id=existing_result.get("profile_id")  # Include profile_id from existing result
                    )
        except Exception as dup_error:
            logger.warning(f"Error checking for duplicates: {dup_error}. Proceeding with new analysis.")
        
        # Create LLM research request
        llm_request = LLMResearchRequest(
            statement=request.statement,
            source=request.source,
            context=request.context,
            country=request.country,
            category=request.category,
            profile_id=profile_id  # Include profile_id in LLM request
        )
        
        # Perform research using LLM
        result = llm_research_service.research_statement(llm_request)
        
        # Set profile_id in result if not already set
        if profile_id and not result.profile_id:
            result.profile_id = profile_id
        
        # Create enhanced response with request data and safe field access
        enhanced_result = EnhancedLLMResearchResponse(
            request=request,
            valid_sources=result.valid_sources,
            verdict=result.verdict,
            status=result.status,
            correction=result.correction,
            country=result.country,
            category=result.category,
            resources_agreed=result.resources_agreed,  
            resources_disagreed=result.resources_disagreed,
            experts=result.experts,
            processed_at=datetime.utcnow(),
            is_duplicate=is_duplicate,
            profile_id=profile_id  # Include profile_id in response
        )
        
        # Try to save to database (non-blocking)
        try:
            # Convert API request to database request model
            db_request = ResearchRequest(
                statement=request.statement,
                source=request.source,
                context=request.context,
                datetime=request.datetime,
                statement_date=request.statement_date,
                country=request.country,
                category=request.category.value if request.category else None,
                profile_id=profile_id  # Include profile_id in database request
            )
            
            database_id = db_research_service.save_research_result(db_request, result)
            enhanced_result.database_id = database_id
            
            if database_id:
                logger.info(f"Research result saved to database with ID: {database_id}")
            
        except Exception as db_error:
            # Log database error but don't fail the API response
            logger.error(f"Failed to save research result to database: {str(db_error)}")
            logger.error(f"Database error type: {type(db_error).__name__}")
            logger.warning("API request will continue despite database save failure")
        
        logger.info("LLM research completed successfully")
        logger.info(f"Status: {result.status}, Country: {result.country}, Category: {result.category}")
        if profile_id:
            logger.info(f"Speaker profile ID: {profile_id}")
        
        return enhanced_result
        
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
        
        result = db_research_service.get_research_result(research_id)
        
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
    profile: str = None,  # Add profile filter
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
        logger.info(f"Searching research results: search='{search}', status='{status}', country='{country}', category='{category}', profile='{profile}'")
        
        results = db_research_service.search_research_results(
            search_text=search,
            status_filter=status,
            country_filter=country,
            category_filter=category,
            profile_filter=profile,  # Include profile filter
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

@router.get("/health")
async def health_check():
    """Health check endpoint for fact-checking service."""
    return {"status": "healthy", "service": "fact-checking"}