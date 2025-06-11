import logging
from typing import Dict, Any
from datetime import datetime

from services.llm_clients.gemini_client import gemini_client

logger = logging.getLogger(__name__)

class WebService:
    """Enhanced web service with better context formatting for LLM consumption"""
    
    def __init__(self):
        self.client = gemini_client
        logger.info("Web service initialized")
    
    async def extract_web_context_for_db(self, statement: str, category: str = "other") -> str:
        """
        Extract web context for database research with enhanced formatting
        """
        if not self.client.is_available():
            return self._create_fallback_context(statement, "Gemini client not available")
        
        try:
            logger.info(f"Extracting web context: {statement[:50]}...")
            
            # Use function calling to extract content
            extraction_result = await self.client.enhanced_search_with_content_extraction(
                statement, category
            )
            
            # Check if we got actual content
            function_calls = extraction_result.get('function_calls_made', 0)
            urls_found = len(extraction_result.get('urls_processed', []))
            
            if function_calls > 0 or urls_found > 0:
                # Successfully extracted content or found URLs
                context = self._format_enhanced_web_context(extraction_result, statement, category)
                logger.info(f"Successfully extracted web context: {function_calls} extractions, {urls_found} URLs")
                return context
            else:
                # No content or URLs found
                logger.warning("No content or URLs found")
                return self._create_fallback_context(statement, "No relevant content found")
                
        except Exception as e:
            logger.error(f"Web context extraction failed: {e}")
            return self._create_fallback_context(statement, f"Extraction error: {str(e)}")
    
    def _format_enhanced_web_context(self, extraction_result: Dict[str, Any], statement: str, category: str) -> str:
        """Format extracted web content for optimal LLM consumption"""
        
        context_parts = [
            f"=== WEB RESEARCH ANALYSIS ===",
            f"Statement: {statement}",
            f"Category: {category}",
            f"Sources processed: {extraction_result.get('function_calls_made', 0)}",
            f"URLs found: {len(extraction_result.get('urls_processed', []))}"
        ]
        
        # Add URLs with validation status
        urls = extraction_result.get('urls_processed', [])
        if urls:
            context_parts.append(f"\n=== SOURCES ANALYZED ===")
            for i, url in enumerate(urls[:5], 1):
                credibility = self._assess_url_credibility(url)
                context_parts.append(f"{i}. {url} (Credibility: {credibility})")
        
        # Add structured analysis if available
        structured_analysis = extraction_result.get('structured_analysis', {})
        if structured_analysis:
            context_parts.append(f"\n=== FACT-CHECK ANALYSIS ===")
            
            # Verification status
            verification = structured_analysis.get('verification_status', 'Unknown')
            context_parts.append(f"Verification Status: {verification}")
            
            # Confidence level
            confidence = structured_analysis.get('confidence_level', 0)
            context_parts.append(f"Confidence Level: {confidence}%")
            
            # Key findings
            key_findings = structured_analysis.get('key_findings', [])
            if key_findings:
                context_parts.append(f"\n=== KEY FINDINGS ===")
                for i, finding in enumerate(key_findings[:5], 1):
                    context_parts.append(f"{i}. {finding}")
            
            # Supporting evidence
            supporting = structured_analysis.get('supporting_evidence', [])
            if supporting:
                context_parts.append(f"\n=== SUPPORTING EVIDENCE ===")
                for i, evidence in enumerate(supporting[:3], 1):
                    context_parts.append(f"{i}. {evidence}")
            
            # Contradicting evidence
            contradicting = structured_analysis.get('contradicting_evidence', [])
            if contradicting:
                context_parts.append(f"\n=== CONTRADICTING EVIDENCE ===")
                for i, evidence in enumerate(contradicting[:3], 1):
                    context_parts.append(f"{i}. {evidence}")
            
            # Fact-check summary
            summary = structured_analysis.get('fact_check_summary', '')
            if summary:
                context_parts.append(f"\n=== FACT-CHECK SUMMARY ===")
                context_parts.append(summary)
        
        # Add web content insights
        web_content = extraction_result.get('web_content', [])
        if web_content:
            context_parts.append(f"\n=== EXTRACTED CONTENT ===")
            for i, insight in enumerate(web_content[:3], 1):
                content_text = insight.get('content', '')[:250]
                source = insight.get('source_url', 'Unknown source')
                extraction_method = insight.get('extraction_method', 'unknown')
                context_parts.append(f"{i}. From {source} ({extraction_method}): {content_text}...")
        
        # Add validation metrics
        context_parts.append(f"\n=== VALIDATION METRICS ===")
        context_parts.append(f"Content extractions: {extraction_result.get('function_calls_made', 0)}")
        context_parts.append(f"URLs discovered: {len(urls)}")
        context_parts.append(f"High-credibility sources: {sum(1 for url in urls if self._assess_url_credibility(url) == 'high')}")
        
        # Add full analysis for context (truncated)
        content_summary = extraction_result.get('content_summary', '')
        if content_summary and len(content_summary) > 200:
            summary_excerpt = content_summary[:1000] + "..." if len(content_summary) > 1000 else content_summary
            context_parts.append(f"\n=== FULL ANALYSIS ===")
            context_parts.append(summary_excerpt)
        
        return '\n'.join(context_parts)
    
    def _assess_url_credibility(self, url: str) -> str:
        """Assess URL credibility for validation metrics"""
        url_lower = url.lower()
        
        high_credibility_domains = [
            'reuters.com', 'apnews.com', 'bbc.com', 'npr.org',
            'factcheck.org', 'politifact.com', 'snopes.com',
            'cdc.gov', 'who.int', 'nih.gov', 'gov', '.edu',
            'nature.com', 'science.org', 'nejm.org'
        ]
        
        medium_credibility_domains = [
            'cnn.com', 'washingtonpost.com', 'nytimes.com',
            'bloomberg.com', 'wsj.com', 'guardian.com'
        ]
        
        for domain in high_credibility_domains:
            if domain in url_lower:
                return "high"
        
        for domain in medium_credibility_domains:
            if domain in url_lower:
                return "medium"
        
        return "unknown"
    
    def _create_fallback_context(self, statement: str, reason: str) -> str:
        """Create fallback context when extraction fails"""
        return f"""=== WEB EXTRACTION FAILED ===
Statement: {statement}
Status: {reason}
Timestamp: {datetime.now().isoformat()}
Note: Analysis will rely on LLM training data only

=== VALIDATION METRICS ===
Content extractions: 0
URLs discovered: 0
High-credibility sources: 0
"""

# Create service instance
web_service = WebService()