import logging
from datetime import datetime
from typing import Optional
import time

from models.research_models import (
    LLMResearchRequest,
    ExpertOpinion,
)
from schemas.research import (
    ResearchRequestAPI,
    EnhancedLLMResearchResponse
)
from services.llm_research.llm_research_legacy import llm_research_service
from services.llm_research.db_research import db_research_service, ResearchRequest
from services.profile import profile_service
from services.web_research.research_orchestrator import ResearchOrchestrator

logger = logging.getLogger(__name__)

class FactCheckingCoreService:
    """
    Core service for fact-checking operations.
    Handles the complete fact-checking pipeline including profile management,
    duplicate detection, LLM research, and database storage.
    Enhanced with tri-factor research capabilities.
    """
    
    def __init__(self):
        self.llm_service = llm_research_service
        self.db_service = db_research_service
        self.profile_service = profile_service
        self.research_orchestrator = ResearchOrchestrator()
        logger.info("FactCheckingCoreService initialized with tri-factor research capabilities")
    
    async def process_research_request(self, request: ResearchRequestAPI) -> EnhancedLLMResearchResponse:
        """
        Process a complete fact-checking research request using tri-factor research.
        
        Args:
            request: Research request containing statement, source, context, etc.
            
        Returns:
            EnhancedLLMResearchResponse: Complete fact-check result with tri-factor research
            
        Raises:
            Exception: If research processing fails
        """
        processing_start_time = time.time()
        
        try:
            logger.info(f"Processing tri-factor research request for statement: {request.statement[:100]}...")
            logger.info(f"Source: {request.source}, Country: {request.country}, Category: {request.category}")
            
            # Step 1: Process speaker profile (non-blocking)
            profile_id = self._process_speaker_profile(request.source)
            
            # Step 2: Check for duplicate statements
            duplicate_result = self._check_for_duplicates(request, profile_id)
            if duplicate_result:
                logger.info("Returning existing duplicate result")
                return duplicate_result
            
            # Step 3: Perform base LLM research
            llm_result = self._perform_llm_research(request, profile_id)
            
            # Step 4: Perform tri-factor research enhancement 
            # IMPORTANT: Make sure this is properly awaited
            enhanced_llm_result = await self._perform_tri_factor_research(request, llm_result, processing_start_time)
            
            # Step 5: Create enhanced response with tri-factor data
            enhanced_response = self._create_enhanced_response(request, enhanced_llm_result, profile_id)
            
            # Step 6: Save to database (non-blocking)
            database_id = self._save_to_database(request, enhanced_llm_result, profile_id)
            
            # IMPORTANT: Set the database_id on the response
            enhanced_response.database_id = database_id
            
            # Add processing metadata
            total_time = time.time() - processing_start_time
            logger.info(f"Tri-factor research completed successfully in {total_time:.2f} seconds")
            if profile_id:
                logger.info(f"Associated with profile: {profile_id}")
            
            return enhanced_response
            
        except Exception as e:
            error_msg = f"Failed to process tri-factor research request: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Create a minimal error response instead of raising
            try:
                request_datetime_str = request.datetime.isoformat() if hasattr(request.datetime, 'isoformat') else str(request.datetime)
                
                error_response = EnhancedLLMResearchResponse(
                    valid_sources="Error occurred during research",
                    verdict=f"Research failed: {str(e)}",
                    status="UNVERIFIABLE",
                    research_method="Error Recovery",
                    request_statement=request.statement,
                    request_source=request.source,
                    request_context=request.context,
                    request_datetime=request_datetime_str,
                    processed_at=datetime.utcnow().isoformat(),
                    research_errors=[str(e)],
                    fallback_reason="Processing error occurred"
                )
                
                logger.info("Returning error response instead of raising exception")
                return error_response
                
            except Exception as fallback_error:
                logger.error(f"Failed to create error response: {fallback_error}")
                raise Exception(error_msg)
    
    async def _perform_tri_factor_research(
        self, 
        request: ResearchRequestAPI, 
        llm_result: object,
        processing_start_time: float
    ) -> object:
        """
        Perform tri-factor research enhancement on LLM result.
        
        Args:
            request: Original research request
            llm_result: Base LLM research result
            processing_start_time: When processing started
            
        Returns:
            Enhanced LLM result with tri-factor research data
        """
        try:
            logger.info("Starting tri-factor research enhancement...")
            
            # Convert request to LLM format for orchestrator
            llm_request = LLMResearchRequest(
                statement=request.statement,
                source=request.source,
                context=request.context,
                country=request.country,
                category=request.category,
                profile_id=getattr(llm_result, 'profile_id', None)
            )
            
            # Perform tri-factor research
            enhanced_result = await self.research_orchestrator.perform_tri_factor_research(
                request=llm_request,
                llm_response=llm_result
            )
            
            logger.info("Tri-factor research enhancement completed")
            return enhanced_result
            
        except Exception as e:
            logger.error(f"Tri-factor research failed, falling back to LLM-only: {e}")
            # Return original LLM result if tri-factor fails
            return llm_result
    
    def _process_speaker_profile(self, source: str) -> Optional[str]:
        """
        Process speaker profile for the given source.
        Creates or retrieves profile ID for the speaker.
        
        Args:
            source: Speaker/source name
            
        Returns:
            Profile ID if successful, None otherwise
        """
        try:
            if not source or source.strip() == "":
                logger.debug("No source provided, skipping profile processing")
                return None
            
            logger.info(f"Processing speaker profile for: {source}")
            profile_id = self.profile_service.process_speaker_profile(source)
            
            if profile_id:
                logger.info(f"Speaker profile processed successfully: {profile_id}")
            else:
                logger.warning("Failed to process speaker profile")
            
            return profile_id
            
        except Exception as e:
            logger.error(f"Speaker profile processing failed: {str(e)}")
            return None
    
    def _check_for_duplicates(self, request: ResearchRequestAPI, profile_id: Optional[str]) -> Optional[EnhancedLLMResearchResponse]:
        """
        Check for duplicate statements in the database.
        
        Args:
            request: Research request
            profile_id: Profile ID if available
            
        Returns:
            Existing result if duplicate found, None otherwise
        """
        try:
            logger.info("Checking for duplicate statements...")
            
            existing_id = self.db_service.check_duplicate_statement(request.statement)
            
            if existing_id:
                logger.info(f"Duplicate statement found: {existing_id}")
                existing_result = self.db_service.get_research_result(existing_id)
                
                if existing_result:
                    return self._convert_existing_result_to_response(request, existing_result, existing_id)
            
            logger.info("No duplicate statements found")
            return None
            
        except Exception as e:
            logger.error(f"Duplicate check failed: {str(e)}")
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
        
        logger.info("Starting base LLM research")
        result = self.llm_service.research_statement(llm_request)
        
        # Ensure profile_id is set in result
        if profile_id and not result.profile_id:
            result.profile_id = profile_id
        
        logger.info(f"Base LLM research completed - Status: {result.status}")
        return result
    
    def _create_enhanced_response(
        self, 
        request: ResearchRequestAPI, 
        llm_result: object, 
        profile_id: Optional[str]
    ) -> EnhancedLLMResearchResponse:
        """
        Create enhanced response with request metadata and tri-factor research data.
        Enhanced with proper error handling and type conversion.
        """
        try:
            # Collect any research errors
            research_errors = []
            fallback_reason = None
            
            # Check for web search errors
            if hasattr(llm_result, 'additional_context') and 'error' in str(llm_result.additional_context):
                research_errors.append("Web search encountered issues")
            
            research_metadata = getattr(llm_result, 'research_metadata', None)
            if research_metadata:
                research_sources = []
                try:
                    # Handle ResearchMetadata Pydantic model (most common case)
                    if hasattr(research_metadata, 'research_sources'):
                        research_sources = research_metadata.research_sources
                    # Handle dictionary format (legacy case)
                    elif isinstance(research_metadata, dict):
                        research_sources = research_metadata.get('research_sources', [])
                    # Handle Pydantic model with model_dump method
                    elif hasattr(research_metadata, 'model_dump'):
                        metadata_dict = research_metadata.model_dump()
                        research_sources = metadata_dict.get('research_sources', [])
                    # Handle Pydantic model with dict method (older versions)
                    elif hasattr(research_metadata, 'dict'):
                        metadata_dict = research_metadata.dict()
                        research_sources = metadata_dict.get('research_sources', [])
                    
                    if research_sources:
                        expected_sources = ['llm_training_data', 'web_search', 'resource_analysis']
                        missing_sources = [s for s in expected_sources if s not in research_sources]
                        if missing_sources:
                            research_errors.append(f"Failed sources: {', '.join(missing_sources)}")
                            
                except Exception as metadata_error:
                    logger.warning(f"Failed to extract research sources from metadata: {metadata_error}")
                    logger.warning(f"Metadata type: {type(research_metadata)}")
                    logger.warning(f"Metadata content: {research_metadata}")
                    research_errors.append("Could not parse research metadata")
        
            # Set fallback reason if only LLM research was successful
            research_method = getattr(llm_result, 'research_method', 'Unknown')
            if 'llm' in research_method.lower() and 'tri-factor' not in research_method.lower():
                fallback_reason = "External research services unavailable"
            
            # Convert datetime to string if needed
            request_datetime = request.datetime
            if hasattr(request_datetime, 'isoformat'):
                request_datetime = request_datetime.isoformat()
            elif isinstance(request_datetime, str):
                request_datetime = request_datetime
            else:
                request_datetime = str(request_datetime)
            
            processed_at = datetime.utcnow().isoformat()
            
            return EnhancedLLMResearchResponse(
                # Original LLM result fields
                valid_sources=getattr(llm_result, 'valid_sources', ''),
                verdict=getattr(llm_result, 'verdict', ''),
                status=getattr(llm_result, 'status', 'UNVERIFIABLE'),
                correction=getattr(llm_result, 'correction', None),
                country=getattr(llm_result, 'country', request.country),
                category=getattr(llm_result, 'category', request.category),
                resources_agreed=getattr(llm_result, 'resources_agreed', None),
                resources_disagreed=getattr(llm_result, 'resources_disagreed', None),
                experts=getattr(llm_result, 'experts', None),
                research_method=research_method,
                profile_id=profile_id,
                
                # Enhanced tri-factor fields
                expert_perspectives=getattr(llm_result, 'expert_perspectives', []),
                key_findings=getattr(llm_result, 'key_findings', []),
                research_summary=getattr(llm_result, 'research_summary', getattr(llm_result, 'verdict', '')),
                additional_context=getattr(llm_result, 'additional_context', ''),
                confidence_score=getattr(llm_result, 'confidence_score', 70),
                research_metadata=research_metadata,
                llm_findings=getattr(llm_result, 'llm_findings', []),
                web_findings=getattr(llm_result, 'web_findings', []),
                resource_findings=getattr(llm_result, 'resource_findings', []),
                
                # Request metadata
                request_statement=request.statement,
                request_source=request.source,
                request_context=request.context,
                request_datetime=request_datetime,
                request_country=request.country,
                request_category=request.category,
                processed_at=processed_at,
                
                # Error handling metadata
                research_errors=research_errors,
                fallback_reason=fallback_reason
            )
            
        except Exception as e:
            logger.error(f"Failed to create enhanced response: {e}")
            logger.error(f"LLM result type: {type(llm_result)}")
            logger.error(f"LLM result attributes: {dir(llm_result) if hasattr(llm_result, '__dict__') else 'No __dict__'}")
            
            # Create minimal fallback response
            request_datetime_str = request.datetime.isoformat() if hasattr(request.datetime, 'isoformat') else str(request.datetime)
            
            return EnhancedLLMResearchResponse(
                valid_sources=getattr(llm_result, 'valid_sources', ''),
                verdict=getattr(llm_result, 'verdict', 'Analysis completed with limited data'),
                status=getattr(llm_result, 'status', 'UNVERIFIABLE'),
                research_method='LLM Only (Enhanced Response Failed)',
                request_statement=request.statement,
                request_source=request.source,
                request_context=request.context,
                request_datetime=request_datetime_str,
                processed_at=datetime.utcnow().isoformat(),
                research_errors=[f"Response creation failed: {str(e)}"],
                fallback_reason="Enhanced response creation failed"
            )
    
    def _save_to_database(
        self, 
        request: ResearchRequestAPI, 
        llm_result: object, 
        profile_id: Optional[str]
    ) -> Optional[str]:
        """
        Save research result to database.
        
        Args:
            request: Research request
            llm_result: LLM research result (with tri-factor data)
            profile_id: Profile ID if available
            
        Returns:
            Database ID if successful, None otherwise
        """
        try:
            logger.info("Saving tri-factor research result to database...")
            
            research_request = ResearchRequest(
                statement=request.statement,
                source=request.source,
                context=request.context,
                datetime=request.datetime,
                country=request.country,
                category=request.category,
                profile_id=profile_id
            )
            
            # Create the database record
            db_record = {
                'statement': request.statement,
                'source': request.source,
                'context': request.context,
                'request_datetime': request.datetime,
                'statement_date': request.statement_date,
                'country': request.country,
                'category': request.category,
                'valid_sources': llm_result.valid_sources,
                'verdict': llm_result.verdict,
                'status': llm_result.status,
                'correction': llm_result.correction,
                'resources_agreed': llm_result.llm_findings,  # Map to new schema
                'resources_disagreed': llm_result.web_findings,  # Map to new schema
                'experts': llm_result.resource_findings,  # Map to new schema
                'profile_id': profile_id
            }
            
            # Save to database using your database manager
            query = """
            INSERT INTO research_results (
                statement, source, context, request_datetime, statement_date,
                country, category, valid_sources, verdict, status, correction,
                resources_agreed, resources_disagreed, experts, profile_id
            ) VALUES (
                %(statement)s, %(source)s, %(context)s, %(request_datetime)s, %(statement_date)s,
                %(country)s, %(category)s, %(valid_sources)s, %(verdict)s, %(status)s, %(correction)s,
                %(resources_agreed)s, %(resources_disagreed)s, %(experts)s, %(profile_id)s
            ) RETURNING id
            """
            
            result = self.db_manager.execute_query(query, db_record)
            
            if result:
                database_id = str(result[0]['id'])
                logger.info(f"Saved research result to database with ID: {database_id}")
                return database_id
            else:
                logger.error("Failed to save research result to database")
                return None
                
        except Exception as e:
            logger.error(f"Error saving to database: {str(e)}")
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
            request: Current research request
            existing_result: Existing database result
            existing_id: Database ID of existing result
            
        Returns:
            Enhanced response based on existing data
        """
        return EnhancedLLMResearchResponse(
            # Core result fields
            valid_sources=existing_result.get("valid_sources", ""),
            verdict=existing_result.get("verdict", ""),
            status=existing_result.get("status", "UNVERIFIABLE"),
            correction=existing_result.get("correction"),
            country=existing_result.get("country"),
            category=existing_result.get("category"),
            resources_agreed=existing_result.get("resources_agreed", {}),
            resources_disagreed=existing_result.get("resources_disagreed", {}),
            experts=ExpertOpinion(**existing_result.get("experts", {})),
            research_method=existing_result.get("research_method", "Database Retrieval"),
            profile_id=existing_result.get("profile_id"),
            
            # Enhanced fields (may be empty for legacy results)
            expert_perspectives=existing_result.get("expert_perspectives", []),
            key_findings=existing_result.get("key_findings", []),
            research_summary=existing_result.get("research_summary", existing_result.get("verdict", "")),
            additional_context=existing_result.get("additional_context", ""),
            confidence_score=existing_result.get("confidence_score", 70),
            research_metadata=existing_result.get("research_metadata"),
            llm_findings=existing_result.get("llm_findings", []),
            web_findings=existing_result.get("web_findings", []),
            resource_findings=existing_result.get("resource_findings", []),
            
            # Request metadata
            request_statement=request.statement,
            request_source=request.source,
            request_context=request.context,
            request_datetime=request.datetime,
            request_country=request.country,
            request_category=request.category,
            processed_at=datetime.fromisoformat(existing_result.get("processed_at", datetime.utcnow().isoformat())),
            database_id=existing_id,
            is_duplicate=True
        )
    
    def get_research_result(self, research_id: str) -> Optional[dict]:
        """
        Get research result by ID.
        
        Args:
            research_id: Database ID of research result
            
        Returns:
            Research result data or None
        """
        try:
            return self.db_service.get_research_result(research_id)
        except Exception as e:
            logger.error(f"Failed to get research result {research_id}: {str(e)}")
            return None
    
    def search_research_results(self, **kwargs) -> list:
        """
        Search research results with filters.
        
        Args:
            **kwargs: Search parameters
            
        Returns:
            List of research results
        """
        try:
            return self.db_service.search_research_results(**kwargs)
        except Exception as e:
            logger.error(f"Failed to search research results: {str(e)}")
            return []

# Create service instance
fact_checking_core_service = FactCheckingCoreService()