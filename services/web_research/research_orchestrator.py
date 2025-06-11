import logging

from models.research_models import LLMResearchRequest, LLMResearchResponse
from .web_service import web_service

logger = logging.getLogger(__name__)

class ResearchOrchestrator:
    """Enhanced research orchestrator with actual web content extraction"""
    
    def __init__(self):
        self.web_service = web_service 
    
    async def get_enhanced_web_context_for_db(self, request: LLMResearchRequest) -> str:
        """
        Get enhanced web context with actual content extraction for database research
        """
        try:
            logger.info(f"Getting enhanced web context for database research: {request.statement[:50]}...")
            
            # Extract category from request
            category = getattr(request, 'category', 'other')
            if category:
                category = str(category).lower()
            
            # Get enhanced context with actual content extraction
            enhanced_context = await self.web_service.extract_web_context_for_db( 
                statement=request.statement,
                category=category
            )
            
            # Add metadata about the enhancement
            metadata = f"\n\nENHANCED_WEB_RESEARCH_METADATA:\n- Extraction method: Function calling with content scraping\n- SDK: google-genai with automatic function calling\n- Content extraction: Enabled"
            
            full_context = enhanced_context + metadata
            
            logger.info(f"Providing enhanced web context to database research ({len(full_context)} characters)")
            return full_context
                
        except Exception as e:
            logger.error(f"Failed to get enhanced web context for database research: {e}")
            return f"Enhanced web context extraction failed for: {request.statement}\nError: {str(e)}\nFallback: Using LLM training data only"
    
    async def perform_enhanced_research(
        self,
        request: LLMResearchRequest,
        llm_response: LLMResearchResponse
    ) -> LLMResearchResponse:
        """
        Perform enhanced research with actual web content extraction
        """
        try:
            logger.info(f"Starting enhanced research with content extraction for: {request.statement[:50]}...")
            
            # Get enhanced web context with actual content
            enhanced_web_context = await self.get_enhanced_web_context_for_db(request)
            
            # Add enhanced web context to the response
            if hasattr(llm_response, 'additional_context'):
                current_context = getattr(llm_response, 'additional_context', '')
                if current_context:
                    llm_response.additional_context = f"{current_context}\n\nENHANCED_WEB_RESEARCH_CONTEXT:\n{enhanced_web_context}"
                else:
                    llm_response.additional_context = f"ENHANCED_WEB_RESEARCH_CONTEXT:\n{enhanced_web_context}"
            
            # Update research method
            if hasattr(llm_response, 'research_method'):
                current_method = getattr(llm_response, 'research_method', 'LLM Research')
                llm_response.research_method = f"{current_method} + Enhanced Web Content Extraction"
            
            # Extract and add web findings - Updated to match the actual context format
            if 'Sources processed:' in enhanced_web_context:  # Fixed: Updated to match actual format from web_service
                web_findings = self._extract_web_findings(enhanced_web_context)
                if hasattr(llm_response, 'web_findings'):
                    llm_response.web_findings = web_findings
                elif hasattr(llm_response, 'key_findings'):
                    current_findings = getattr(llm_response, 'key_findings', [])
                    llm_response.key_findings = current_findings + web_findings
            
            # Boost confidence if we got actual web content - Updated to match actual format
            if 'Sources processed:' in enhanced_web_context and hasattr(llm_response, 'confidence_score'):  # Fixed: Updated pattern
                try:
                    sources_line = [line for line in enhanced_web_context.split('\n') if 'Sources processed:' in line][0]
                    sources_count = int(sources_line.split('Sources processed:')[1].strip())
                    if sources_count > 0:
                        confidence_boost = min(sources_count * 5, 15)  # Up to 15 point boost
                        llm_response.confidence_score = min(llm_response.confidence_score + confidence_boost, 95)
                        logger.info(f"Boosted confidence by {confidence_boost} points due to {sources_count} web sources")
                except Exception as parse_error:
                    logger.warning(f"Failed to parse sources count: {parse_error}")
            
            logger.info("Enhanced research with content extraction completed")
            return llm_response
            
        except Exception as e:
            logger.error(f"Enhanced research failed: {e}")
            return llm_response
    
    def _extract_web_findings(self, web_context: str) -> list:
        """Extract web findings from the enhanced context - Updated to match actual format"""
        findings = []
        
        try:
            # Look for key findings in the actual format used by web_service
            if '=== KEY FINDINGS ===' in web_context:
                findings_section = web_context.split('=== KEY FINDINGS ===')[1]
                # Split by next section or end
                if '===' in findings_section:
                    findings_section = findings_section.split('===')[0]
                
                for line in findings_section.split('\n'):
                    line = line.strip()
                    if line.startswith(('1.', '2.', '3.', '4.', '5.')) and len(line) > 10:
                        finding = line[2:].strip()
                        findings.append(f"Web research: {finding}")
            
            # Also extract from content excerpts
            if '=== CONTENT EXCERPTS ===' in web_context:
                excerpts_section = web_context.split('=== CONTENT EXCERPTS ===')[1]
                if '===' in excerpts_section:
                    excerpts_section = excerpts_section.split('===')[0]
                
                excerpt_count = 0
                for line in excerpts_section.split('\n'):
                    line = line.strip()
                    if line.startswith(('1.', '2.', '3.')) and 'From' in line and len(line) > 20:
                        excerpt_count += 1
                
                if excerpt_count > 0:
                    findings.append(f"Web research: Extracted content from {excerpt_count} web sources")
            
        except Exception as e:
            logger.warning(f"Failed to extract web findings: {e}")
        
        return findings[:5]  # Limit to top 5
    
    # Add compatibility method for the core service
    async def perform_focused_research(
        self,
        request: LLMResearchRequest,
        llm_response: LLMResearchResponse
    ) -> LLMResearchResponse:
        """
        Compatibility method for perform_focused_research called by core.py
        """
        return await self.perform_enhanced_research(request, llm_response)

# Create enhanced orchestrator instance
research_orchestrator = ResearchOrchestrator()