from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging
from services.llm_transcription_analysis import (
    llm_analysis_service, 
    TranscriptionAnalysisInput, 
    TranscriptionAnalysisResult
)
from services.llm_research import (
    llm_research_service,
    LLMResearchRequest,
    LLMResearchResponse
)

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(tags=["fact-checking"])

class AnalysisRequest(BaseModel):
    language_code: str = "eng"
    speaker: str
    context: str
    transcription: str

class ResearchRequest(BaseModel):
    statement: str
    source: str = "Unknown"
    context: str = ""

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

@router.post("/research", response_model=LLMResearchResponse)
async def research_statement(request: ResearchRequest) -> LLMResearchResponse:
    """
    Research a statement using LLM knowledge base for fact-checking.
    
    Args:
        request: Research request containing the statement, source, and context
        
    Returns:
        LLMResearchResponse: Fact-check result with verdict, status, and resources
        
    Raises:
        HTTPException: If research fails
    """
    try:
        logger.info(f"Starting LLM research for statement: {request.statement[:100]}...")
        
        # Create LLM research request
        llm_request = LLMResearchRequest(
            statement=request.statement,
            source=request.source,
            context=request.context
        )
        
        # Perform research using LLM
        result = llm_research_service.research_statement(llm_request)
        
        logger.info("LLM research completed successfully")
        logger.info(f"Status: {result.status}")
        logger.info(f"Valid sources: {result.valid_sources}")
        
        return result
        
    except Exception as e:
        error_msg = f"Failed to research statement: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)

@router.get("/health")
async def health_check():
    """Health check endpoint for fact-checking service."""
    return {"status": "healthy", "service": "fact-checking"}

# Example responses:
# 
# POST /extract response:
# {
#     "statements": [
#         {
#             "statement": "I reduced China from 145% that I set down to 100 and then down to another number"
#         },
#         {
#             "statement": "I gave the European Union a 50% tax, uh, tariff"
#         },
#         {
#             "statement": "Six months ago, this country was stone-cold dead"
#         }
#     ],
#     "total_statements": 3,
#     "analysis_summary": "Found 3 fact-checkable statements related to specific numerical claims and historical facts. The statements concern tariff rates imposed on China and the European Union, as well as the economic state of the country six months prior to the press conference."
# }
#
# POST /research response:
# {
#     "valid_sources": "12 (67% agreement across 18 unique sources)",
#     "verdict": "The Amazon rainforest produces approximately 6-9% of the world's oxygen, not 20% as commonly claimed.",
#     "status": "FALSE",
#     "resources": [
#         "https://www.nationalgeographic.com/environment/article/why-amazon-doesnt-produce-20-percent-worlds-oxygen",
#         "https://www.scientificamerican.com/article/why-the-amazon-doesnt-really-produce-20-percent-of-the-worlds-oxygen/",
#         "https://academic.oup.com/bioscience/article/70/10/891/5895115"
#     ]
# }