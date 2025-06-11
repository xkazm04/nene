import logging
from datetime import datetime
from typing import Optional, Dict
import time

from models.research_models import (
    LLMResearchRequest,
    ExpertOpinion,
    ExpertPerspective
)
from schemas.research import (
    ResearchRequestAPI,
    EnhancedLLMResearchResponse
)
from services.llm_research.llm_research_legacy import llm_research_service
from services.llm_research.db_research import db_research_service, ResearchRequest
from services.profile import profile_service
from services.web_research.research_orchestrator import research_orchestrator
from services.llm_clients.gemini_client import gemini_client

logger = logging.getLogger(__name__)

class FactCheckingCoreService:
    """
    Core service for fact-checking operations.
    Handles the complete fact-checking pipeline including profile management,
    duplicate detection, LLM research, and database storage.
    Enhanced with web content extraction capabilities.
    """
    
    def __init__(self):
        self.llm_service = llm_research_service
        self.db_service = db_research_service
        self.profile_service = profile_service
        self.research_orchestrator = research_orchestrator
        self.web_client = gemini_client  
        
        logger.info("FactCheckingCoreService initialized with web content extraction capabilities")
    
    async def process_research_request(self, request: ResearchRequestAPI) -> EnhancedLLMResearchResponse:
        """
        Process a complete fact-checking research request with web content extraction.
        
        Args:
            request: Research request containing statement, source, context, etc.
            
        Returns:
            EnhancedLLMResearchResponse: Complete fact-check result with web content
            
        Raises:
            Exception: If research processing fails
        """
        processing_start_time = time.time()
        
        try:
            logger.info(f"Processing research request with web extraction for statement: {request.statement[:100]}...")
            logger.info(f"Source: {request.source}, Country: {request.country}, Category: {request.category}")
            
            # Step 1: Process speaker profile (non-blocking)
            profile_id = self._process_speaker_profile(request.source)
            
            # Step 2: Check for duplicate statements
            duplicate_result = self._check_for_duplicates(request, profile_id)
            if duplicate_result:
                logger.info("Returning existing duplicate result")
                return duplicate_result
            
            # Step 3: Extract web content first
            web_context = await self._extract_web_content(request)
            
            # Step 4: Perform LLM research with web context
            llm_result = self._perform_llm_research_with_web_context(request, profile_id, web_context)
            
            # Step 5: Perform focused research enhancement 
            enhanced_llm_result = await self._perform_focused_research(request, llm_result, processing_start_time)
            
            # Step 6: Create enhanced response with research data
            enhanced_response = self._create_enhanced_response(request, enhanced_llm_result, profile_id, web_context)
            
            # Step 7: Save to database (non-blocking)
            database_id = self._save_to_database(request, enhanced_llm_result, profile_id)
            
            # Set the database_id on the response
            enhanced_response.database_id = database_id
            
            # Add processing metadata
            total_time = time.time() - processing_start_time
            logger.info(f"Research completed successfully with web content in {total_time:.2f} seconds")
            if profile_id:
                logger.info(f"Associated with profile: {profile_id}")
            
            return enhanced_response
            
        except Exception as e:
            error_msg = f"Failed to process research request: {str(e)}"
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
    
    async def _extract_web_content(self, request: ResearchRequestAPI) -> str:
        """
        Extract web content - simplified version using working orchestrator
        """
        try:
            if not hasattr(self, 'research_orchestrator'):
                # Import here to avoid circular imports
                from services.web_research.research_orchestrator import research_orchestrator
                self.research_orchestrator = research_orchestrator
            
            logger.info("Extracting web content using simplified method...")
            
            # Convert to internal request
            internal_request = LLMResearchRequest(
                statement=request.statement,
                source=request.source,
                context=request.context,
                datetime=request.datetime,
                statement_date=request.statement_date,
                country=request.country,
                category=request.category,
            )
            
            # Get web context
            web_context = await self.research_orchestrator.get_enhanced_web_context_for_db(internal_request)
            
            logger.info(f"Web content extraction completed ({len(web_context)} characters)")
            return web_context
                
        except Exception as e:
            logger.error(f"Web content extraction failed: {e}")
            return self._create_fallback_web_context(request.statement, f"Extraction error: {str(e)}")
    
    def _format_web_context_for_llm(self, extraction_result: Dict, request: ResearchRequestAPI) -> str:
        """Format extracted web content for LLM consumption"""
        
        context_parts = [
            f"=== WEB CONTENT ANALYSIS ===",
            f"Statement: {request.statement}",
            f"Category: {request.category or 'other'}",
            f"Web sources processed: {extraction_result.get('function_calls_made', 0)}",
            f"URLs analyzed: {len(extraction_result.get('urls_processed', []))}"
        ]
        
        # Add structured analysis if available
        structured_analysis = extraction_result.get('structured_analysis', {})
        if structured_analysis:
            context_parts.append(f"\n=== VERIFICATION STATUS ===")
            context_parts.append(f"Status: {structured_analysis.get('verification_status', 'Unknown')}")
            context_parts.append(f"Confidence: {structured_analysis.get('confidence_level', 0)}%")
            context_parts.append(f"Source quality: {structured_analysis.get('web_sources_quality', 'Unknown')}")
            
            # Add key findings
            key_findings = structured_analysis.get('key_findings', [])
            if key_findings:
                context_parts.append(f"\n=== KEY FINDINGS FROM WEB ===")
                for i, finding in enumerate(key_findings[:5], 1):
                    context_parts.append(f"{i}. {finding}")
            
            # Add supporting evidence
            supporting = structured_analysis.get('supporting_evidence', [])
            if supporting:
                context_parts.append(f"\n=== SUPPORTING EVIDENCE ===")
                for i, evidence in enumerate(supporting[:3], 1):
                    context_parts.append(f"{i}. {evidence}")
            
            # Add contradicting evidence
            contradicting = structured_analysis.get('contradicting_evidence', [])
            if contradicting:
                context_parts.append(f"\n=== CONTRADICTING EVIDENCE ===")
                for i, evidence in enumerate(contradicting[:3], 1):
                    context_parts.append(f"{i}. {evidence}")
            
            # Add fact-check summary
            summary = structured_analysis.get('fact_check_summary', '')
            if summary:
                context_parts.append(f"\n=== WEB FACT-CHECK SUMMARY ===")
                context_parts.append(summary)
        
        # Add URLs processed
        urls_processed = extraction_result.get('urls_processed', [])
        if urls_processed:
            context_parts.append(f"\n=== SOURCES ANALYZED ===")
            for i, url in enumerate(urls_processed[:5], 1):
                context_parts.append(f"{i}. {url}")
        
        # Add content insights
        web_content = extraction_result.get('web_content', [])
        if web_content:
            context_parts.append(f"\n=== CONTENT INSIGHTS ===")
            for i, insight in enumerate(web_content[:3], 1):
                content_text = insight.get('content', '')[:200]
                context_parts.append(f"{i}. {content_text}...")
        
        # Add raw content summary (truncated)
        content_summary = extraction_result.get('content_summary', '')
        if content_summary and len(content_summary) > 100:
            summary_excerpt = content_summary[:400] + "..." if len(content_summary) > 400 else content_summary
            context_parts.append(f"\n=== RAW WEB CONTENT SUMMARY ===")
            context_parts.append(summary_excerpt)
        
        return '\n'.join(context_parts)
    
    def _create_search_fallback_context(self, extraction_result: Dict, request: ResearchRequestAPI) -> str:
        """Create context when search worked but content extraction failed"""
        
        context_parts = [
            f"=== LIMITED WEB SEARCH RESULTS ===",
            f"Statement: {request.statement}",
            f"Search status: Completed with limited extraction",
            f"URLs found: {len(extraction_result.get('urls_processed', []))}"
        ]
        
        if extraction_result.get('urls_processed'):
            context_parts.append(f"\n=== URLS DISCOVERED ===")
            for i, url in enumerate(extraction_result['urls_processed'][:3], 1):
                context_parts.append(f"{i}. {url}")
        
        if extraction_result.get('content_summary'):
            context_parts.append(f"\n=== SEARCH RESPONSE ===")
            context_parts.append(extraction_result['content_summary'][:300] + "...")
        
        context_parts.append(f"\nNote: Limited content extraction - analysis based on search results only")
        
        return '\n'.join(context_parts)
    
    def _create_fallback_web_context(self, statement: str, reason: str) -> str:
        """Create fallback context when web extraction completely fails"""
        return f"""=== WEB EXTRACTION FAILED ===
Statement: {statement}
Status: Web content extraction unavailable
Reason: {reason}
Timestamp: {datetime.now().isoformat()}
Note: Analysis will rely on LLM training data only
"""
    
    def _perform_llm_research_with_web_context(
        self, 
        request: ResearchRequestAPI, 
        profile_id: Optional[str], 
        web_context: str
    ) -> object:
        """
        Perform LLM research enhanced with web context.
        
        Args:
            request: Research request
            profile_id: Profile ID if available
            web_context: Extracted web content context
            
        Returns:
            LLM research result enhanced with web content
        """
        # Combine original context with web context
        enhanced_context = f"{request.context}\n\n{web_context}" if request.context else web_context
        
        llm_request = LLMResearchRequest(
            statement=request.statement,
            source=request.source,
            context=enhanced_context,  # Enhanced with web content
            country=request.country,
            category=request.category,
            profile_id=profile_id
        )
        
        logger.info("Starting LLM research with web content enhancement")
        result = self.llm_service.research_statement(llm_request)
        
        # Ensure profile_id is set in result
        if profile_id and not result.profile_id:
            result.profile_id = profile_id
        
        # Mark that this research includes web content
        if hasattr(result, 'research_method'):
            result.research_method = f"{result.research_method} + Web Content"
        
        logger.info(f"LLM research with web content completed - Status: {result.status}")
        return result
    
    async def _perform_focused_research(
        self, 
        request: ResearchRequestAPI, 
        llm_result: object,
        processing_start_time: float
    ) -> object:
        """
        Perform focused research enhancement on LLM result.
        
        Args:
            request: Original research request
            llm_result: Base LLM research result (already enhanced with web content)
            processing_start_time: When processing started
            
        Returns:
            Enhanced LLM result with focused research data
        """
        try:
            logger.info("Starting focused research enhancement...")
            
            # Convert request to LLM format for orchestrator
            llm_request = LLMResearchRequest(
                statement=request.statement,
                source=request.source,
                context=request.context,
                country=request.country,
                category=request.category,
                profile_id=getattr(llm_result, 'profile_id', None)
            )
            
            # Perform focused research using the orchestrator
            enhanced_result = await self.research_orchestrator.perform_focused_research(
                request=llm_request,
                llm_response=llm_result
            )
            
            logger.info("Focused research enhancement completed")
            return enhanced_result
            
        except Exception as e:
            logger.error(f"Focused research failed, using web-enhanced LLM result: {e}")
            # Return LLM result that already has web content enhancement
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
    
    def _create_enhanced_response(
        self, 
        request: ResearchRequestAPI, 
        llm_result: object, 
        profile_id: Optional[str],
        web_context: str = ""
    ) -> EnhancedLLMResearchResponse:
        """
        Create enhanced response with request metadata and web content data.
        Enhanced with web content extraction information.
        """
        try:
            # Collect any research errors
            research_errors = []
            fallback_reason = None
            
            # Check for web extraction issues
            if "WEB EXTRACTION FAILED" in web_context:
                research_errors.append("Web content extraction failed")
            elif "LIMITED WEB SEARCH" in web_context:
                research_errors.append("Limited web content extraction")
            
            # Extract web metadata
            web_metadata = self._extract_web_content_metadata(web_context)
            
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
                        expected_sources = ['llm_training_data', 'web_search', 'web_content']
                        missing_sources = [s for s in expected_sources if s not in research_sources]
                        if missing_sources:
                            research_errors.append(f"Failed sources: {', '.join(missing_sources)}")
                            
                except Exception as metadata_error:
                    logger.warning(f"Failed to extract research sources from metadata: {metadata_error}")
                    research_errors.append("Could not parse research metadata")
        
            # Set fallback reason based on available research methods
            research_method = getattr(llm_result, 'research_method', 'Unknown')
            if 'web content' not in research_method.lower() and web_metadata.get('sources_processed', 0) == 0:
                fallback_reason = "Web content extraction unavailable"
            
            # Convert datetime to string if needed
            request_datetime = request.datetime
            if hasattr(request_datetime, 'isoformat'):
                request_datetime = request_datetime.isoformat()
            elif isinstance(request_datetime, str):
                request_datetime = request_datetime
            else:
                request_datetime = str(request_datetime)
            
            processed_at = datetime.utcnow().isoformat()
            
            # Create web findings from extracted content
            web_findings = []
            if web_metadata.get('sources_processed', 0) > 0:
                web_findings.append(f"Analyzed content from {web_metadata['sources_processed']} web sources")
                if web_metadata.get('verification_status'):
                    web_findings.append(f"Web verification: {web_metadata['verification_status']}")
                if web_metadata.get('key_findings_count', 0) > 0:
                    web_findings.append(f"Extracted {web_metadata['key_findings_count']} key findings from web content")
            
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
                
                # Enhanced focused research fields
                expert_perspectives=getattr(llm_result, 'expert_perspectives', []),
                key_findings=getattr(llm_result, 'key_findings', []),
                research_summary=getattr(llm_result, 'research_summary', getattr(llm_result, 'verdict', '')),
                additional_context=getattr(llm_result, 'additional_context', ''),
                confidence_score=getattr(llm_result, 'confidence_score', 70),
                research_metadata=research_metadata,
                llm_findings=getattr(llm_result, 'llm_findings', []),
                web_findings=getattr(llm_result, 'web_findings', []) + web_findings,
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
            
            # Create minimal fallback response
            request_datetime_str = request.datetime.isoformat() if hasattr(request.datetime, 'isoformat') else str(request.datetime)
            
            return EnhancedLLMResearchResponse(
                valid_sources=getattr(llm_result, 'valid_sources', ''),
                verdict=getattr(llm_result, 'verdict', 'Analysis completed with limited data'),
                status=getattr(llm_result, 'status', 'UNVERIFIABLE'),
                research_method='LLM with Web Content (Response Creation Failed)',
                request_statement=request.statement,
                request_source=request.source,
                request_context=request.context,
                request_datetime=request_datetime_str,
                processed_at=datetime.utcnow().isoformat(),
                research_errors=[f"Response creation failed: {str(e)}"],
                fallback_reason="Enhanced response creation failed"
            )
    
    def _extract_web_content_metadata(self, web_context: str) -> Dict[str, any]:
        """Extract metadata from web content context"""
        metadata = {
            'sources_processed': 0,
            'urls_found': 0,
            'verification_status': None,
            'key_findings_count': 0
        }
        
        try:
            for line in web_context.split('\n'):
                if 'Web sources processed:' in line:
                    metadata['sources_processed'] = int(line.split('Web sources processed:')[1].strip())
                elif 'URLs analyzed:' in line:
                    metadata['urls_found'] = int(line.split('URLs analyzed:')[1].strip())
                elif 'Status:' in line and '===' not in line:
                    metadata['verification_status'] = line.split('Status:')[1].strip()
            
            # Count key findings
            if '=== KEY FINDINGS FROM WEB ===' in web_context:
                findings_section = web_context.split('=== KEY FINDINGS FROM WEB ===')[1]
                if '===' in findings_section:
                    findings_section = findings_section.split('===')[0]
                finding_lines = [line for line in findings_section.split('\n') if line.strip().startswith(('1.', '2.', '3.', '4.', '5.'))]
                metadata['key_findings_count'] = len(finding_lines)
                
        except Exception as e:
            logger.warning(f"Failed to extract web content metadata: {e}")
        
        return metadata
    
    def _save_to_database(
        self, 
        request: ResearchRequestAPI, 
        llm_result: object, 
        profile_id: Optional[str]
    ) -> Optional[str]:
        """
        Save research result to database using original Supabase SDK approach.
        
        Args:
            request: Research request
            llm_result: LLM research result (with web content and focused research data)
            profile_id: Profile ID if available
            
        Returns:
            Database ID if successful, None otherwise
        """
        try:
            logger.info("Saving research result with web content to database...")
            
            # Create ResearchRequest object using the original working approach
            research_request = ResearchRequest(
                statement=request.statement,
                source=request.source,
                context=request.context,
                datetime=request.datetime,
                statement_date=getattr(request, 'statement_date', None),
                country=request.country,
                category=request.category,
                profile_id=profile_id
            )
            
            # Use the original db_service method that was working
            database_id = self.db_service.save_research_result(research_request, llm_result)
            
            if database_id:
                logger.info(f"Saved research result with web content to database with ID: {database_id}")
                return database_id
            else:
                logger.error("Failed to save research result to database")
                return None
                
        except Exception as e:
            logger.error(f"Error saving to database: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def _convert_existing_result_to_response(
        self, 
        request: ResearchRequestAPI, 
        existing_result: dict, 
        existing_id: str
    ) -> EnhancedLLMResearchResponse:
        """
        Convert existing database result to enhanced response format.
        Enhanced to properly handle expert_perspectives from database.
        
        Args:
            request: Current research request
            existing_result: Existing database result
            existing_id: Database ID of existing result
            
        Returns:
            Enhanced response based on existing data
        """
        # Parse expert perspectives from database
        expert_perspectives = []
        perspectives_data = existing_result.get("expert_perspectives", [])
        
        if perspectives_data:
            for perspective_dict in perspectives_data:
                try:
                    perspective = ExpertPerspective(**perspective_dict)
                    expert_perspectives.append(perspective)
                except Exception as e:
                    logger.warning(f"Failed to parse expert perspective: {e}")
                    continue
        
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
            experts=ExpertOpinion(**existing_result.get("experts", {})) if existing_result.get("experts") else None,
            research_method=existing_result.get("research_method", "Database Retrieval"),
            profile_id=existing_result.get("profile_id"),
            
            # Enhanced fields with expert perspectives
            expert_perspectives=expert_perspectives,  # Properly parsed expert perspectives
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
            processed_at=existing_result.get("processed_at", datetime.utcnow().isoformat()),
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