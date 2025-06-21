import logging
import time
import traceback
from datetime import datetime
from typing import Optional
from schemas.research import (
    ResearchRequestAPI,
    EnhancedLLMResearchResponse,
    ResearchRequest
)
from services.llm_research.db_research import db_research_service
from services.profile import profile_service
from services.llm_research.db_profile import ProfileService
from utils.research_extractions import ResearchExtractionUtils

logger = logging.getLogger(__name__)

class FactCheckingCoreService:
    """
    Core service for fact-checking operations with web research integration.
    Uses unified db_research_service for all LLM operations.
    """
    
    def __init__(self):
        self.db_service = db_research_service  # Use unified service
        self.profile_service = profile_service
        self.profile_processor = ProfileService(profile_service)
        self.extraction_utils = ResearchExtractionUtils()
        
        # Initialize web research service
        self._init_web_research()
        
        logger.info("FactCheckingCoreService initialized with unified LLM research")
    
    def _init_web_research(self):
        """Initialize the web research service"""
        try:
            from services.web_research.enhanced_web_research import enhanced_web_research
            self.web_research = enhanced_web_research
            logger.info("Web research service loaded successfully")
        except Exception as e:
            logger.warning(f"Web research unavailable: {e}")
            self.web_research = None
    
    async def process_research_request(self, request: ResearchRequestAPI) -> EnhancedLLMResearchResponse:
        """
        Process a complete fact-checking research request with web research integration.
        
        Args:
            request: Research request containing statement, source, context, etc.
            
        Returns:
            EnhancedLLMResearchResponse: Complete fact-check result with web content
            
        Raises:
            Exception: If research processing fails
        """
        processing_start_time = time.time()
        
        try:
            logger.info(f"Processing research request: {request.statement[:100]}...")
            logger.info(f"Source: {request.source}, Country: {request.country}, Category: {request.category}")
            
            # Step 1: Process speaker profile with metadata extraction
            profile_id = await self.profile_processor.process_enhanced_speaker_profile(request.source)
            
            # Step 2: Web research
            web_context, urls_found = await self._perform_web_research(request)
            
            # Step 3: Perform LLM research with web context (handles duplicate checking and saving internally)
            llm_result = await self._perform_llm_research(
                request, profile_id, web_context
            )
            
            # Step 4: Create response
            response = self._create_response(
                request, llm_result, profile_id, web_context
            )
            
            # Step 5: Set database ID from LLM result (already saved by db_research_service)
            response.database_id = getattr(llm_result, 'research_id', None)
            
            # Add processing metadata
            total_time = time.time() - processing_start_time
            
            logger.info(f"Research completed successfully in {total_time:.2f}s")
            if profile_id:
                logger.info(f"Associated with profile: {profile_id}")
            
            return response
            
        except Exception as e:
            error_msg = f"Failed to process research request: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Create error response
            return self._create_error_response(request, e, processing_start_time)
    
    # ===== LLM RESEARCH METHODS =====
    
    async def _perform_llm_research(
        self, 
        request: ResearchRequestAPI, 
        profile_id: Optional[str], 
        web_context: str,
    ) -> object:
        """Perform LLM research with web context using unified service"""
        try:
            logger.info("Performing LLM research with unified service")
            
            # Create ResearchRequest object for the database service
            db_request = ResearchRequest(
                statement=request.statement,
                source=request.source,
                context=request.context,
                datetime=request.datetime,
                country=request.country,
                category=request.category.value if request.category else None,
                profile_id=profile_id
            )
            
            # Use unified service with web context (handles duplicate checking and saving internally)
            if web_context and len(web_context) > 100:
                logger.info("Using web-integrated research")
                return await self.db_service.research_with_web_context(db_request, web_context)
            else:
                logger.info("Using standard LLM research")
                return await self.db_service.research_statement(db_request)
            
        except Exception as e:
            logger.error(f"LLM research failed: {e}")
            # Fallback to basic research
            return await self._fallback_llm_research(request, profile_id)
    
    async def _fallback_llm_research(self, request: ResearchRequestAPI, profile_id: Optional[str]) -> object:
        """Fallback to basic LLM research"""
        logger.info("Using fallback LLM research")
        
        db_request = ResearchRequest(
            statement=request.statement,
            source=request.source,
            context=request.context,
            datetime=request.datetime,
            country=request.country,
            category=request.category.value if request.category else None,
            profile_id=profile_id
        )
        
        return await self.db_service.research_statement(db_request)

    # ===== WEB RESEARCH METHODS =====
    
    async def _perform_web_research(self, request: ResearchRequestAPI) -> tuple[str, list]:
        """
        Perform web research using the simplified architecture
        
        Args:
            request: Research request
            
        Returns:
            Tuple of (formatted web context string, list of URLs found)
        """
        try:
            if not self.web_research or not self.web_research.is_available():
                logger.warning("Web research unavailable - using fallback")
                fallback_context = self.extraction_utils.create_fallback_web_context(
                    request.statement, 
                    "Web research service unavailable"
                )
                return fallback_context, []
            
            logger.info("Starting web research...")
            
            # Use web research service
            web_context = await self.web_research.research_statement(
                statement=request.statement,
                category=request.category or "other"
            )
            
            # Extract URLs from web context for metadata
            urls_found = self.extraction_utils.extract_urls_from_web_context(web_context)
            
            # Add request metadata to context
            context_with_metadata = f"""{web_context}

=== REQUEST METADATA ===
Original source: {request.source}
Request country: {request.country}
Request context: {request.context}
Research timestamp: {datetime.now().isoformat()}
Method: Web research with unified LLM analysis"""
            
            logger.info(f"Web research completed with {len(urls_found)} URLs found")
            return context_with_metadata, urls_found
            
        except Exception as e:
            logger.error(f"Web research failed: {e}")
            fallback_context = self.extraction_utils.create_fallback_web_context(
                request.statement, 
                f"Web research error: {str(e)}"
            )
            return fallback_context, []
    
    def _create_response(
        self, 
        request: ResearchRequestAPI, 
        llm_result: object, 
        profile_id: Optional[str],
        web_context: str = "",
    ) -> EnhancedLLMResearchResponse:
        """Create response from LLM result"""
        
        # Extract research_metadata from LLM result if available
        research_metadata = getattr(llm_result, 'research_metadata', None) or \
                          getattr(llm_result, 'additional_context', None) or \
                          "Standard fact-checking analysis completed."
        
        response = EnhancedLLMResearchResponse(
            valid_sources=getattr(llm_result, 'valid_sources', '0'),
            verdict=getattr(llm_result, 'verdict', 'Analysis completed'),
            status=getattr(llm_result, 'status', 'UNVERIFIABLE'),
            correction=getattr(llm_result, 'correction'),
            country=getattr(llm_result, 'country') or request.country,
            category=getattr(llm_result, 'category') or (request.category.value if request.category else 'other'),
            resources_agreed=getattr(llm_result, 'resources_agreed'),
            resources_disagreed=getattr(llm_result, 'resources_disagreed'),
            experts=getattr(llm_result, 'experts'),
            research_method=getattr(llm_result, 'research_method', 'unified_research'),
            profile_id=profile_id,
            expert_perspectives=getattr(llm_result, 'expert_perspectives', []),
            key_findings=getattr(llm_result, 'key_findings', []),
            research_summary=getattr(llm_result, 'research_summary', ''),
            confidence_score=getattr(llm_result, 'confidence_score', 50),
            research_metadata=research_metadata,
            request_statement=request.statement,
            request_source=request.source,
            request_context=request.context,
            request_datetime=request.datetime.isoformat(),
            request_country=request.country,
            request_category=request.category.value if request.category else None,
            processed_at=datetime.now().isoformat(),
        )
        
        return response
    
    def _create_error_response(self, request: ResearchRequestAPI, error: Exception, start_time: float) -> EnhancedLLMResearchResponse:
        """Create error response for failed research"""
        total_time = time.time() - start_time
        
        return EnhancedLLMResearchResponse(
            valid_sources="0 (Error occurred)",
            verdict=f"Research failed: {str(error)}",
            status="UNVERIFIABLE",
            correction=None,
            country=request.country,
            category=request.category.value if request.category else "other",
            research_method="error_recovery",
            expert_perspectives=[],
            key_findings=[],
            research_summary="",
            confidence_score=20,
            research_metadata=f"Error occurred after {total_time:.2f}s",
            request_statement=request.statement,
            request_source=request.source,
            request_context=request.context,
            request_datetime=request.datetime.isoformat(),
            request_country=request.country,
            request_category=request.category.value if request.category else None,
            processed_at=datetime.now().isoformat(),
            research_errors=[str(error)],
            fallback_reason=f"Processing error: {type(error).__name__}"
        )
    
    # ===== PUBLIC API METHODS (MAINTAINED FOR COMPATIBILITY) =====
    
    def get_research_result(self, research_id: str) -> Optional[dict]:
        """Get research result by ID"""
        return self.db_service.db_ops.get_research_result(research_id)
    
    def search_research_results(self, **kwargs) -> list:
        """Search research results"""
        return self.db_service.db_ops.search_research_results(**kwargs)
    
    # ===== LEGACY COMPATIBILITY METHODS ===
    
    async def perform_comprehensive_research(self, request: ResearchRequestAPI) -> EnhancedLLMResearchResponse:
        """Legacy method - redirects to new process_research_request"""
        return await self.process_research_request(request)

# Create service instance
fact_checking_core_service = FactCheckingCoreService()