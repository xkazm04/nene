import logging
from datetime import datetime
from typing import Optional

from models.research_models import (
    LLMResearchRequest,
    ExpertOpinion,
    StatementCategory
)
from schemas.research import (
    ResearchRequestAPI,
    EnhancedLLMResearchResponse
)
from services.llm_research.llm_research_legacy import llm_research_service
from services.llm_research.db_research import db_research_service, ResearchRequest
from services.profile import profile_service

logger = logging.getLogger(__name__)

class FactCheckingCoreService:
    """
    Core service for fact-checking operations.
    Handles the complete fact-checking pipeline including profile management,
    duplicate detection, LLM research, and database storage.
    """
    
    def __init__(self):
        self.llm_service = llm_research_service
        self.db_service = db_research_service
        self.profile_service = profile_service
        logger.info("FactCheckingCoreService initialized successfully")
    
    def process_research_request(self, request: ResearchRequestAPI) -> EnhancedLLMResearchResponse:
        """
        Process a complete fact-checking research request.
        
        Args:
            request: Research request containing statement, source, context, etc.
            
        Returns:
            EnhancedLLMResearchResponse: Complete fact-check result
            
        Raises:
            Exception: If research processing fails
        """
        try:
            logger.info(f"Processing fact-check request for statement: {request.statement[:100]}...")
            logger.info(f"Source: {request.source}, Country: {request.country}, Category: {request.category}")
            
            # Step 1: Process speaker profile (non-blocking)
            profile_id = self._process_speaker_profile(request.source)
            
            # Step 2: Check for duplicate statements
            duplicate_result = self._check_for_duplicates(request, profile_id)
            if duplicate_result:
                logger.info("Returning existing duplicate result")
                return duplicate_result
            
            # Step 3: Perform LLM research
            llm_result = self._perform_llm_research(request, profile_id)
            
            # Step 4: Create enhanced response
            enhanced_response = self._create_enhanced_response(request, llm_result, profile_id)
            
            # Step 5: Save to database (non-blocking)
            database_id = self._save_to_database(request, llm_result, profile_id)
            enhanced_response.database_id = database_id
            
            logger.info("Fact-checking research completed successfully")
            if profile_id:
                logger.info(f"Associated with profile: {profile_id}")
            
            return enhanced_response
            
        except Exception as e:
            error_msg = f"Failed to process research request: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def _process_speaker_profile(self, source: str) -> Optional[str]:
        """
        Process speaker profile and get/create profile ID.
        Non-blocking - errors are logged but don't stop the flow.
        
        Args:
            source: Speaker name/source
            
        Returns:
            Optional[str]: Profile ID if successful, None if failed
        """
        if not source or not source.strip() or source == "Unknown":
            logger.debug("No valid source provided for profile processing")
            return None
        
        try:
            profile_id = self.profile_service.get_or_create_profile(source)
            if profile_id:
                logger.debug(f"Profile processed for speaker: {source} -> {profile_id}")
                return profile_id
            else:
                logger.warning(f"Failed to process profile for speaker: {source}")
                return None
        except Exception as profile_error:
            logger.error(f"Profile processing failed for speaker '{source}': {str(profile_error)}")
            return None
    
    def _check_for_duplicates(self, request: ResearchRequestAPI, profile_id: Optional[str]) -> Optional[EnhancedLLMResearchResponse]:
        """
        Check for duplicate statements and return existing result if found.
        
        Args:
            request: Research request
            profile_id: Profile ID if available
            
        Returns:
            Optional[EnhancedLLMResearchResponse]: Existing result if duplicate found
        """
        try:
            existing_id = self.db_service.check_duplicate_statement(request.statement)
            if existing_id:
                logger.info(f"Duplicate statement found - retrieving existing result: {existing_id}")
                existing_result = self.db_service.get_research_result(existing_id)
                
                if existing_result:
                    return self._convert_existing_result_to_response(request, existing_result, existing_id)
                
        except Exception as dup_error:
            logger.warning(f"Error checking for duplicates: {dup_error}. Proceeding with new analysis.")
        
        return None
    
    def _perform_llm_research(self, request: ResearchRequestAPI, profile_id: Optional[str]) -> object:
        """
        Perform LLM research on the statement.
        
        Args:
            request: Research request
            profile_id: Profile ID if available
            
        Returns:
            LLM research result
        """
        llm_request = LLMResearchRequest(
            statement=request.statement,
            source=request.source,
            context=request.context,
            country=request.country,
            category=request.category,
            profile_id=profile_id
        )
        
        logger.info("Starting LLM research")
        result = self.llm_service.research_statement(llm_request)
        
        # Ensure profile_id is set in result
        if profile_id and not result.profile_id:
            result.profile_id = profile_id
        
        logger.info(f"LLM research completed - Status: {result.status}")
        return result
    
    def _create_enhanced_response(
        self, 
        request: ResearchRequestAPI, 
        llm_result: object, 
        profile_id: Optional[str]
    ) -> EnhancedLLMResearchResponse:
        """
        Create enhanced response from LLM result.
        
        Args:
            request: Original request
            llm_result: LLM research result
            profile_id: Profile ID if available
            
        Returns:
            EnhancedLLMResearchResponse: Enhanced response
        """
        return EnhancedLLMResearchResponse(
            request=request,
            valid_sources=llm_result.valid_sources,
            verdict=llm_result.verdict,
            status=llm_result.status,
            correction=llm_result.correction,
            country=llm_result.country,
            category=llm_result.category,
            resources_agreed=llm_result.resources_agreed,
            resources_disagreed=llm_result.resources_disagreed,
            experts=llm_result.experts,
            processed_at=datetime.utcnow(),
            is_duplicate=False,
            profile_id=profile_id
        )
    
    def _save_to_database(
        self, 
        request: ResearchRequestAPI, 
        llm_result: object, 
        profile_id: Optional[str]
    ) -> Optional[str]:
        """
        Save research result to database (non-blocking).
        
        Args:
            request: Research request
            llm_result: LLM research result
            profile_id: Profile ID if available
            
        Returns:
            Optional[str]: Database ID if successful
        """
        try:
            db_request = ResearchRequest(
                statement=request.statement,
                source=request.source,
                context=request.context,
                datetime=request.datetime,
                statement_date=request.statement_date,
                country=request.country,
                category=request.category.value if request.category else None,
                profile_id=profile_id
            )
            
            database_id = self.db_service.save_research_result(db_request, llm_result)
            
            if database_id:
                logger.info(f"Research result saved to database with ID: {database_id}")
            
            return database_id
            
        except Exception as db_error:
            logger.error(f"Failed to save research result to database: {str(db_error)}")
            logger.warning("Continuing despite database save failure")
            return None
    
    def _convert_existing_result_to_response(
        self, 
        request: ResearchRequestAPI, 
        existing_result: dict, 
        existing_id: str
    ) -> EnhancedLLMResearchResponse:
        """
        Convert existing database result to enhanced response format.
        
        Args:
            request: Original request
            existing_result: Existing database result
            existing_id: Database ID of existing result
            
        Returns:
            EnhancedLLMResearchResponse: Converted response
        """
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
            profile_id=existing_result.get("profile_id")
        )
    
    def get_research_result(self, research_id: str) -> Optional[dict]:
        """
        Retrieve a research result by ID.
        
        Args:
            research_id: Database ID of research result
            
        Returns:
            Optional[dict]: Research result if found
        """
        return self.db_service.get_research_result(research_id)
    
    def search_research_results(self, **kwargs) -> list:
        """
        Search research results with filters.
        
        Args:
            **kwargs: Search filters
            
        Returns:
            list: List of research results
        """
        return self.db_service.search_research_results(**kwargs)

# Create service instance
fact_checking_core_service = FactCheckingCoreService()