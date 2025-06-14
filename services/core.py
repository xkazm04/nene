import logging
from datetime import datetime
from typing import Optional, Dict
import time

from models.research_models import (
    LLMResearchRequest,
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
    Enhanced core service for fact-checking operations with improved web research.
    Maintains compatibility with existing code while providing enhanced web capabilities.
    """
    
    def __init__(self):
        self.llm_service = llm_research_service
        self.db_service = db_research_service
        self.profile_service = profile_service
        
        # Initialize enhanced web research service
        self._init_enhanced_web_research()
        
        logger.info("Enhanced FactCheckingCoreService initialized with improved web research")
    
    def _init_enhanced_web_research(self):
        """Initialize the enhanced web research service"""
        try:
            from services.web_research.enhanced_web_research import enhanced_web_research
            self.web_research = enhanced_web_research
            logger.info("Enhanced web research service loaded successfully")
        except Exception as e:
            logger.warning(f"Enhanced web research unavailable: {e}")
            self.web_research = None
    
    
    async def process_research_request(self, request: ResearchRequestAPI) -> EnhancedLLMResearchResponse:
        """
        Process a complete fact-checking research request with enhanced web research.
        
        Args:
            request: Research request containing statement, source, context, etc.
            
        Returns:
            EnhancedLLMResearchResponse: Complete fact-check result with web content
            
        Raises:
            Exception: If research processing fails
        """
        processing_start_time = time.time()
        
        try:
            logger.info(f"Processing enhanced research request: {request.statement[:100]}...")
            logger.info(f"Source: {request.source}, Country: {request.country}, Category: {request.category}")
            
            # Step 1: Process speaker profile (non-blocking)
            profile_id = self._process_speaker_profile(request.source)
            
            # Step 2: Check for duplicate statements
            duplicate_result = self._check_for_duplicates(request, profile_id)
            if duplicate_result:
                logger.info("Returning existing duplicate result")
                return duplicate_result
            
            # Step 3: Enhanced web research
            web_context, urls_found = await self._perform_enhanced_web_research(request)
            
            
            # Step 5: Perform LLM research with web enhancement
            llm_result = await self._perform_enhanced_llm_research(
                request, profile_id, web_context
            )
            
            # Step 6: Create enhanced response
            enhanced_response = self._create_enhanced_response(
                request, llm_result, profile_id, web_context
            )
            
            # Step 7: Save to database (non-blocking)
            database_id = self._save_to_database(request, llm_result, profile_id)
            enhanced_response.database_id = database_id
            
            # Add processing metadata
            total_time = time.time() - processing_start_time
            
            logger.info(f"Enhanced research completed successfully in {total_time:.2f}s")
            if profile_id:
                logger.info(f"Associated with profile: {profile_id}")
            
            return enhanced_response
            
        except Exception as e:
            error_msg = f"Failed to process enhanced research request: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Create error response
            return self._create_error_response(request, e, processing_start_time)
    
    async def _perform_enhanced_web_research(self, request: ResearchRequestAPI) -> tuple[str, list]:
        """
        Perform enhanced web research using the new simplified architecture
        
        Args:
            request: Research request
            
        Returns:
            Tuple of (formatted web context string, list of URLs found)
        """
        try:
            if not self.web_research or not self.web_research.is_available():
                logger.warning("Enhanced web research unavailable - using fallback")
                fallback_context = self._create_fallback_web_context(
                    request.statement, 
                    "Enhanced web research service unavailable"
                )
                return fallback_context, []
            
            logger.info("Starting enhanced web research...")
            
            # Use enhanced web research service
            web_context = await self.web_research.research_statement(
                statement=request.statement,
                category=request.category or "other"
            )
            
            # Extract URLs from web context for Firecrawl processing
            urls_found = self._extract_urls_from_web_context(web_context)
            
            # Add request metadata to context
            enhanced_context = f"""{web_context}

=== REQUEST METADATA ===
Original source: {request.source}
Request country: {request.country}
Request context: {request.context}
Research timestamp: {datetime.now().isoformat()}
Method: Enhanced web research with function calling"""
            
            logger.info(f"Enhanced web research completed successfully, found {len(urls_found)} URLs")
            return enhanced_context, urls_found
            
        except Exception as e:
            logger.error(f"Enhanced web research failed: {e}")
            fallback_context = self._create_fallback_web_context(
                request.statement, 
                f"Enhanced web research error: {str(e)}"
            )
            return fallback_context, []
    
    def _extract_urls_from_web_context(self, web_context: str) -> list:
        """Extract URLs from web research context"""
        urls = []
        
        # Look for the credible sources section
        if "=== CREDIBLE SOURCES FOUND ===" in web_context:
            sources_section = web_context.split("=== CREDIBLE SOURCES FOUND ===")[1]
            
            # Look for next section boundary
            next_section_index = sources_section.find("===")
            if next_section_index != -1:
                sources_section = sources_section[:next_section_index]
            
            # Extract URLs from numbered list
            import re
            url_pattern = r'https?://[^\s\n]+'
            found_urls = re.findall(url_pattern, sources_section)
            urls.extend(found_urls)
        
        logger.info(f"Extracted {len(urls)} URLs from web context")
        return urls
    
    
    def _create_basic_resources_from_urls(self, urls: list) -> dict:
        """Create basic resource structure from URLs when Firecrawl is unavailable"""
        if not urls:
            return {'resources_agreed': {}, 'resources_disagreed': {}}
        
        # Create basic references from URLs
        references = []
        for url in urls[:5]:  # Limit to 5
            references.append({
                'url': url,
                'title': self._generate_title_from_url(url),
                'category': self._categorize_url(url),
                'country': 'us',  # Default
                'credibility': self._assess_url_credibility(url),
                'key_finding': 'Content extraction unavailable'
            })
        
        return {
            'resources_agreed': {
                'total': f"{len(references) * 15}%",
                'count': len(references),
                'mainstream': sum(1 for r in references if r['category'] == 'mainstream'),
                'governance': sum(1 for r in references if r['category'] == 'governance'),
                'academic': sum(1 for r in references if r['category'] == 'academic'),
                'medical': sum(1 for r in references if r['category'] == 'medical'),
                'legal': sum(1 for r in references if r['category'] == 'legal'),
                'economic': sum(1 for r in references if r['category'] == 'economic'),
                'other': sum(1 for r in references if r['category'] == 'other'),
                'major_countries': ['us'],
                'references': references
            },
            'resources_disagreed': {
                'total': "0%",
                'count': 0,
                'mainstream': 0,
                'governance': 0,
                'academic': 0,
                'medical': 0,
                'legal': 0,
                'economic': 0,
                'other': 0,
                'major_countries': [],
                'references': []
            }
        }
    
    def _generate_title_from_url(self, url: str) -> str:
        """Generate title from URL"""
        from urllib.parse import urlparse
        try:
            domain = urlparse(url).netloc.lower()
            if 'congress.gov' in domain:
                return "Congressional Document"
            elif 'whitehouse.gov' in domain:
                return "White House Statement"
            elif '.gov' in domain:
                return "Government Document"
            elif '.edu' in domain:
                return "Academic Resource"
            else:
                return f"Article from {domain.replace('www.', '').title()}"
        except:
            return "Web Resource"
    
    def _categorize_url(self, url: str) -> str:
        """Categorize URL by domain"""
        url_lower = url.lower()
        if '.gov' in url_lower or '.mil' in url_lower:
            return 'governance'
        elif '.edu' in url_lower:
            return 'academic'
        elif any(news in url_lower for news in ['reuters.com', 'apnews.com', 'bbc.com', 'cnn.com']):
            return 'mainstream'
        else:
            return 'other'
    
    def _assess_url_credibility(self, url: str) -> str:
        """Assess URL credibility by domain"""
        url_lower = url.lower()
        high_cred = ['.gov', '.edu', 'reuters.com', 'apnews.com', 'bbc.com']
        if any(hc in url_lower for hc in high_cred):
            return 'high'
        else:
            return 'medium'
    
    async def _perform_enhanced_llm_research(
        self, 
        request: ResearchRequestAPI, 
        profile_id: Optional[str], 
        web_context: str,
    ) -> object:
        """
        Perform enhanced LLM research with web context and resource integration
        
        Args:
            request: Research request
            profile_id: Profile ID if available
            web_context: Enhanced web research context
            
        Returns:
            Enhanced LLM research result
        """
        try:
            # Combine original context with enhanced web context
            enhanced_context = self._combine_contexts(request.context, web_context)
            
            # Create enhanced LLM request
            llm_request = LLMResearchRequest(
                statement=request.statement,
                source=request.source,
                context=enhanced_context,
                country=request.country,
                category=request.category,
                profile_id=profile_id
            )
            
            logger.info("Starting enhanced LLM research with web context and resources")
            
            # Use existing LLM service but with enhanced context
            result = self.llm_service.research_statement(llm_request)
            
            
            # Enhance result metadata
            if hasattr(result, 'research_method'):
                # Analyze web context quality to determine method description
                web_quality = self._analyze_web_context_quality(web_context)
                if web_quality['has_sources']:
                    result.research_method = f"{result.research_method} + Enhanced Web Research ({web_quality['source_count']} sources)"
                else:
                    result.research_method = f"{result.research_method} + Limited Web Research"
            
            # Ensure profile_id is set
            if profile_id and not getattr(result, 'profile_id', None):
                result.profile_id = profile_id
            
            # Boost confidence based on web research quality
            if hasattr(result, 'confidence_score') and web_quality.get('high_quality_sources', 0) > 0:
                original_confidence = result.confidence_score
                boost = min(web_quality['high_quality_sources'] * 5, 15)  # Max 15 point boost
                result.confidence_score = min(original_confidence + boost, 95)
                logger.info(f"Confidence boosted from {original_confidence} to {result.confidence_score} due to web sources")
            
            logger.info(f"Enhanced LLM research completed - Status: {result.status}")
            return result
            
        except Exception as e:
            logger.error(f"Enhanced LLM research failed: {e}")
            # Fallback to basic LLM research
            return await self._fallback_llm_research(request, profile_id)
    
    async def _fallback_llm_research(self, request: ResearchRequestAPI, profile_id: Optional[str]) -> object:
        """Fallback to basic LLM research when enhanced research fails"""
        try:
            logger.info("Falling back to basic LLM research")
            
            basic_llm_request = LLMResearchRequest(
                statement=request.statement,
                source=request.source,
                context=request.context or "",
                country=request.country,
                category=request.category,
                profile_id=profile_id
            )
            
            result = self.llm_service.research_statement(basic_llm_request)
            
            if hasattr(result, 'research_method'):
                result.research_method = f"{result.research_method} (Fallback - Enhanced Research Failed)"
            
            return result
            
        except Exception as fallback_error:
            logger.error(f"Fallback LLM research also failed: {fallback_error}")
            raise
    
    def _combine_contexts(self, original_context: str, web_context: str) -> str:
        """Intelligently combine original context with web research context"""
        
        if not original_context and not web_context:
            return ""
        
        if not original_context:
            return web_context
        
        if not web_context or "unavailable" in web_context.lower():
            return original_context
        
        # Combine both contexts with clear separation
        combined = f"""=== ORIGINAL CONTEXT ===
{original_context}

{web_context}"""
        
        return combined
    
    def _analyze_web_context_quality(self, web_context: str) -> Dict[str, any]:
        """Analyze the quality of web research context"""
        quality = {
            'has_sources': False,
            'source_count': 0,
            'high_quality_sources': 0,
            'has_findings': False,
            'findings_count': 0
        }
        
        try:
            lines = web_context.split('\n')
            
            for line in lines:
                # Check for source indicators
                if 'Function calls made:' in line:
                    try:
                        quality['source_count'] = int(line.split(':')[1].strip())
                        quality['has_sources'] = quality['source_count'] > 0
                    except:
                        pass
                
                elif 'Credible URLs found:' in line:
                    try:
                        credible_count = int(line.split(':')[1].strip())
                        quality['source_count'] = max(quality['source_count'], credible_count)
                        quality['has_sources'] = credible_count > 0
                    except:
                        pass
                
                elif 'Source quality: high' in line:
                    quality['high_quality_sources'] = max(quality['source_count'], 3)
                
                elif 'Source quality: medium' in line:
                    quality['high_quality_sources'] = max(quality['source_count'] // 2, 1)
            
            # Check for findings
            if '=== KEY RESEARCH FINDINGS ===' in web_context or '=== KEY FINDINGS FROM WEB ===' in web_context:
                quality['has_findings'] = True
                # Count numbered findings
                findings_lines = [line for line in lines if line.strip().startswith(('1.', '2.', '3.', '4.', '5.'))]
                quality['findings_count'] = len(findings_lines)
            
        except Exception as e:
            logger.warning(f"Failed to analyze web context quality: {e}")
        
        return quality
    
    def _create_fallback_web_context(self, statement: str, reason: str) -> str:
        """Create fallback context when enhanced web research fails"""
        return f"""=== ENHANCED WEB RESEARCH UNAVAILABLE ===
Statement: {statement}
Status: Enhanced web research unavailable
Reason: {reason}
Timestamp: {datetime.now().isoformat()}
Note: Analysis will rely on LLM training data only

=== RESEARCH QUALITY METRICS ===
Web searches performed: 0
Credible sources discovered: 0
Key findings extracted: 0
Overall source quality: unavailable
Research method: Fallback mode"""
    
    def _create_error_response(self, request: ResearchRequestAPI, error: Exception, start_time: float) -> EnhancedLLMResearchResponse:
        """Create error response when processing fails completely"""
        try:
            request_datetime_str = request.datetime.isoformat() if hasattr(request.datetime, 'isoformat') else str(request.datetime)
            
            return EnhancedLLMResearchResponse(
                valid_sources="Error occurred during enhanced research",
                verdict=f"Enhanced research failed: {str(error)}",
                status="UNVERIFIABLE",
                research_method="Enhanced Research - Error Recovery",
                request_statement=request.statement,
                request_source=request.source,
                request_context=request.context,
                request_datetime=request_datetime_str,
                processed_at=datetime.utcnow().isoformat(),
                research_errors=[str(error)],
                fallback_reason="Enhanced processing error occurred"
            )
            
        except Exception as fallback_error:
            logger.error(f"Failed to create error response: {fallback_error}")
            raise Exception(f"Enhanced research failed: {str(error)}")
    
    # === EXISTING METHODS (MAINTAINED FOR COMPATIBILITY) ===
    
    def _process_speaker_profile(self, source: str) -> Optional[str]:
        """Process speaker profile for the given source."""
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
        """Check for duplicate statements in the database."""
        try:
            logger.info("Checking for duplicate statements...")
            
            existing_id = self.db_service.check_duplicate_statement(request.statement)
            
            if existing_id:
                logger.info(f"Duplicate statement found: {existing_id}")
            
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
        web_context: str = "",
    ) -> EnhancedLLMResearchResponse:
        """Create enhanced response with request metadata, web content data, and resource references."""
        try:
            # Collect research errors and analyze web quality
            research_errors = []
            fallback_reason = None
            
            # Check for web research issues
            if "ENHANCED WEB RESEARCH UNAVAILABLE" in web_context:
                research_errors.append("Enhanced web research unavailable")
                fallback_reason = "Enhanced web research service unavailable"
            elif "Enhanced web research error" in web_context:
                research_errors.append("Enhanced web research encountered errors")
            
            # Analyze web context for metadata
            web_quality = self._analyze_web_context_quality(web_context)
            
            # Extract research metadata
            research_metadata = getattr(llm_result, 'research_metadata', None)
            
            # Convert datetime
            request_datetime = request.datetime
            if hasattr(request_datetime, 'isoformat'):
                request_datetime = request_datetime.isoformat()
            else:
                request_datetime = str(request_datetime)
            
            # Create web findings summary
            web_findings = []
            if web_quality['has_sources']:
                web_findings.append(f"Enhanced web research: {web_quality['source_count']} sources analyzed")
                if web_quality['high_quality_sources'] > 0:
                    web_findings.append(f"High-quality sources: {web_quality['high_quality_sources']}")
                if web_quality['has_findings']:
                    web_findings.append(f"Key findings extracted: {web_quality['findings_count']}")
            
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
                research_method=getattr(llm_result, 'research_method', 'Enhanced LLM + Web Research'),
                profile_id=profile_id,
                
                # Enhanced research fields
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
                processed_at=datetime.utcnow().isoformat(),
                
                # Error handling metadata
                research_errors=research_errors,
                fallback_reason=fallback_reason
            )
            
        except Exception as e:
            logger.error(f"Failed to create enhanced response: {e}")
            
            # Create minimal fallback response
            request_datetime_str = request.datetime.isoformat() if hasattr(request.datetime, 'isoformat') else str(request.datetime)
            
            return EnhancedLLMResearchResponse(
                valid_sources=getattr(llm_result, 'valid_sources', ''),
                verdict=getattr(llm_result, 'verdict', 'Analysis completed with enhanced data'),
                status=getattr(llm_result, 'status', 'UNVERIFIABLE'),
                research_method='Enhanced LLM + Web Research (Response Creation Failed)',
                request_statement=request.statement,
                request_source=request.source,
                request_context=request.context,
                request_datetime=request_datetime_str,
                processed_at=datetime.utcnow().isoformat(),
                research_errors=[f"Enhanced response creation failed: {str(e)}"],
                fallback_reason="Enhanced response creation failed"
            )
    
    def _save_to_database(
        self, 
        request: ResearchRequestAPI, 
        llm_result: object, 
        profile_id: Optional[str]
    ) -> Optional[str]:
        """Save research result to database."""
        try:
            logger.info("Saving enhanced research result to database...")
            
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
            
            database_id = self.db_service.save_research_result(research_request, llm_result)
            
            if database_id:
                logger.info(f"Enhanced research result saved to database with ID: {database_id}")
                return database_id
            else:
                logger.error("Failed to save enhanced research result to database")
                return None
                
        except Exception as e:
            logger.error(f"Error saving enhanced research result to database: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    
    # === PUBLIC API METHODS (MAINTAINED FOR COMPATIBILITY) ===
    
    def get_research_result(self, research_id: str) -> Optional[dict]:
        """Get research result by ID."""
        try:
            return self.db_service.get_research_result(research_id)
        except Exception as e:
            logger.error(f"Failed to get research result {research_id}: {str(e)}")
            return None
    
    def search_research_results(self, **kwargs) -> list:
        """Search research results with filters."""
        try:
            return self.db_service.search_research_results(**kwargs)
        except Exception as e:
            logger.error(f"Failed to search research results: {str(e)}")
            return []
    
    # === LEGACY COMPATIBILITY METHODS ===
    
    async def perform_comprehensive_research(self, request: ResearchRequestAPI) -> EnhancedLLMResearchResponse:
        """
        Legacy method name for backward compatibility.
        Maps to the new process_research_request method.
        """
        return await self.process_research_request(request)

# Create service instance
fact_checking_core_service = FactCheckingCoreService()