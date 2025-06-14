import logging
from typing import  Dict, Any
from datetime import datetime

from services.llm_clients.gemini_client import gemini_client

logger = logging.getLogger(__name__)

class EnhancedWebService:
    """Enhanced web service that provides actual web content to database research"""
    
    def __init__(self):
        self.enhanced_client = gemini_client
        logger.info("Enhanced web service initialized with function calling capabilities")
    
    async def extract_web_context_for_db(self, statement: str, category: str = "other") -> str:
        """
        Extract web context specifically for database research enhancement.
        This method provides actual web content that can be used by the LLM.
        """
        if not self.enhanced_client.is_available():
            return self._create_fallback_context(statement, "Enhanced Gemini client not available")
        
        try:
            logger.info(f"Extracting web context for database research: {statement[:50]}...")
            
            # Use enhanced content extraction
            extraction_result = await self.enhanced_client.enhanced_search_with_content_extraction(
                statement, category
            )
            
            if extraction_result.get('function_calls_made', 0) > 0:
                # Successfully extracted content
                context = self._format_web_context(extraction_result, statement, category)
                logger.info(f"Successfully extracted web context from {extraction_result['function_calls_made']} sources")
                return context
            else:
                # No content extracted, but may have search results
                fallback_context = self._create_search_only_context(extraction_result, statement, category)
                logger.warning("No web content extracted, providing search-only context")
                return fallback_context
                
        except Exception as e:
            logger.error(f"Web context extraction failed: {e}")
            return self._create_fallback_context(statement, f"Extraction error: {str(e)}")
    
    def _format_web_context(self, extraction_result: Dict[str, Any], statement: str, category: str) -> str:
        """Format extracted web content into structured context for database research"""
        
        context_parts = [
            f"STATEMENT: {statement}",
            f"CATEGORY: {category}",
            f"WEB_EXTRACTION_TIMESTAMP: {extraction_result['search_timestamp']}",
            f"SOURCES_PROCESSED: {extraction_result['function_calls_made']}",
            f"URLS_FOUND: {len(extraction_result['urls_processed'])}"
        ]
        
        # Add URLs found
        if extraction_result['urls_processed']:
            context_parts.append("SOURCES_ANALYZED:")
            for i, url in enumerate(extraction_result['urls_processed'][:5], 1):
                context_parts.append(f"  {i}. {url}")
        
        # Add structured analysis if available
        structured_analysis = extraction_result.get('structured_analysis')
        if structured_analysis:
            context_parts.append(f"WEB_VERIFICATION_STATUS: {structured_analysis.get('verification_status', 'Unknown')}")
            context_parts.append(f"WEB_CONFIDENCE_LEVEL: {structured_analysis.get('confidence_level', 0)}%")
            
            # Add key findings
            key_findings = structured_analysis.get('key_findings', [])
            if key_findings:
                context_parts.append("WEB_KEY_FINDINGS:")
                for i, finding in enumerate(key_findings[:3], 1):
                    context_parts.append(f"  {i}. {finding}")
            
            # Add supporting evidence
            supporting = structured_analysis.get('supporting_evidence', [])
            if supporting:
                context_parts.append("WEB_SUPPORTING_EVIDENCE:")
                for i, evidence in enumerate(supporting[:2], 1):
                    context_parts.append(f"  {i}. {evidence}")
            
            # Add contradicting evidence
            contradicting = structured_analysis.get('contradicting_evidence', [])
            if contradicting:
                context_parts.append("WEB_CONTRADICTING_EVIDENCE:")
                for i, evidence in enumerate(contradicting[:2], 1):
                    context_parts.append(f"  {i}. {evidence}")
            
            # Add fact-check summary
            summary = structured_analysis.get('fact_check_summary')
            if summary:
                context_parts.append(f"WEB_FACT_CHECK_SUMMARY: {summary}")
        
        # Add extracted content insights
        web_content = extraction_result.get('web_content', [])
        if web_content:
            context_parts.append("WEB_CONTENT_INSIGHTS:")
            for i, insight in enumerate(web_content[:5], 1):
                context_parts.append(f"  {i}. {insight.get('content', '')[:150]}...")
        
        # Add raw content summary
        content_summary = extraction_result.get('content_summary', '')
        if content_summary and len(content_summary) > 100:
            # Truncate for context
            summary_excerpt = content_summary[:500] + "..." if len(content_summary) > 500 else content_summary
            context_parts.append(f"WEB_CONTENT_SUMMARY: {summary_excerpt}")
        
        return '\n'.join(context_parts)
    
    def _create_search_only_context(self, extraction_result: Dict[str, Any], statement: str, category: str) -> str:
        """Create context when search worked but no content was extracted"""
        
        context_parts = [
            f"STATEMENT: {statement}",
            f"CATEGORY: {category}",
            f"WEB_SEARCH_TIMESTAMP: {extraction_result['search_timestamp']}",
            f"SEARCH_STATUS: Completed but limited content extraction",
            f"URLS_FOUND: {len(extraction_result['urls_processed'])}"
        ]
        
        if extraction_result['urls_processed']:
            context_parts.append("URLS_DISCOVERED:")
            for i, url in enumerate(extraction_result['urls_processed'][:3], 1):
                context_parts.append(f"  {i}. {url}")
        
        if extraction_result.get('content_summary'):
            context_parts.append(f"SEARCH_RESPONSE: {extraction_result['content_summary'][:300]}...")
        
        context_parts.append("NOTE: Limited web content extraction - relying primarily on search results")
        
        return '\n'.join(context_parts)
    
    def _create_fallback_context(self, statement: str, reason: str) -> str:
        """Create fallback context when web extraction fails"""
        return f"""
        STATEMENT: {statement}
        WEB_EXTRACTION_STATUS: Failed - {reason}
        WEB_SEARCH_TIMESTAMP: {datetime.now().isoformat()}
        CONTEXT_AVAILABLE: Limited - using training data only
        FALLBACK_NOTE: Web content extraction unavailable, relying on LLM training data for analysis
        ERROR_DETAILS: {reason}
        """

# Create enhanced service instance
gemini_service = EnhancedWebService()