from models.research_models import LLMResearchRequest
from prompts.fc_prompt import factcheck_prompt
import logging
from datetime import datetime
from typing import Optional
import re

logger = logging.getLogger(__name__)

class PromptBuilder:
    """Builder for creating prompts for different LLM clients."""
    
    def get_system_prompt(self) -> str:
        """Get the system prompt for LLM fact-checking."""
        return f"""You are a professional fact-checker with access to extensive knowledge across multiple domains including science, politics, economics, history, and current events.

Your task is to fact-check statements using your trained knowledge base. You must be thorough, accurate, and unbiased in your analysis.

{factcheck_prompt}"""

    def get_user_prompt(self, request: LLMResearchRequest) -> str:
        """Get the user prompt with the specific research request."""
        return f"""Please fact-check the following statement using your knowledge base and provide expert perspectives:

STATEMENT: "{request.statement}"
SOURCE: {request.source}
CONTEXT: {request.context}
SPEAKER_COUNTRY: {request.country or 'Unknown'}
STATEMENT_CATEGORY: {request.category or 'Unknown'}

ANALYSIS REQUIREMENTS:
- Consider the political and cultural context of the speaker's country if provided
- Focus on domain-specific expertise relevant to the statement category
- Include country and category fields in your response
- Provide comprehensive fact-checking as per the specified JSON format

Analyze this statement thoroughly and provide a comprehensive fact-check result. Consider:
1. The accuracy of any numerical claims or statistics
2. The scientific consensus on the topic
3. Historical context and evolution of understanding
4. How the statement might mislead even if partially true
5. The reliability and motivation of the stated source
6. Country-specific context and political landscape if applicable
7. Category-specific expertise and domain knowledge

Provide your analysis in the specified JSON format including:
- Standard fact-check elements (sources, verdict, status, correction, country, category, resources)
- Four expert perspectives (critic, devil, nerd, psychic) offering different analytical angles

Each expert perspective should be clear, concise (max 3 sentences), and provide unique insights into the statement."""

    def get_gemini_prompt(self, request: LLMResearchRequest) -> str:
        """Get enhanced prompt for Gemini with internet search capabilities."""
        return f"""You are a professional fact-checker with access to current internet information and extensive knowledge across multiple domains.

Your task is to fact-check the following statement using both your knowledge base AND current internet search capabilities to find the most up-to-date information:

STATEMENT: "{request.statement}"
SOURCE: {request.source}
CONTEXT: {request.context}
SPEAKER_COUNTRY: {request.country or 'Unknown'}
STATEMENT_CATEGORY: {request.category or 'Unknown'}

{factcheck_prompt}

ADDITIONAL REQUIREMENTS:
- If country is provided, consider local context and political landscape of that country
- If category is provided, focus on domain-specific expertise and sources relevant to that category
- Include the country and category in your response using the provided values
- Use your internet search capabilities to find the most current information available
"""

    def build_complete_research_prompt(
        self,
        statement: str,
        source: str,
        context: str,
        category: Optional[str] = None,
        country: Optional[str] = None
    ) -> str:
        """Build complete research prompt with enhanced web context integration"""
        
        # Import the prompt here to avoid circular imports
        from prompts.fc_prompt import factcheck_prompt
        
        # Extract web context information for better prompt construction
        web_context_info = self._extract_web_context_info(context)
        
        # Build enhanced context section
        enhanced_context = self._build_enhanced_context_section(
            statement, source, context, category, country, web_context_info
        )
        
        # Combine with fact-check prompt
        complete_prompt = f"""
{enhanced_context}

{factcheck_prompt}

Now analyze this statement: "{statement}"
"""
        
        logger.info(f"Built enhanced prompt with web context: {web_context_info['has_web_content']}")
        return complete_prompt
    
    def _extract_web_context_info(self, context: str) -> dict:
        """Extract information about web context availability"""
        info = {
            'has_web_content': False,
            'sources_processed': 0,
            'urls_found': 0,
            'verification_status': None,
            'confidence_level': 0,
            'credible_sources': 0
        }
        
        if '=== WEB RESEARCH ANALYSIS ===' in context:
            info['has_web_content'] = True
            
            # Extract metrics
            try:
                for line in context.split('\n'):
                    if 'Sources processed:' in line:
                        info['sources_processed'] = int(line.split('Sources processed:')[1].strip())
                    elif 'URLs found:' in line:
                        info['urls_found'] = int(line.split('URLs found:')[1].strip())
                    elif 'Verification Status:' in line:
                        info['verification_status'] = line.split('Verification Status:')[1].strip()
                    elif 'Confidence Level:' in line:
                        confidence_text = line.split('Confidence Level:')[1].strip()
                        confidence_match = re.search(r'(\d+)', confidence_text)
                        if confidence_match:
                            info['confidence_level'] = int(confidence_match.group(1))
                    elif 'High-credibility sources:' in line:
                        info['credible_sources'] = int(line.split('High-credibility sources:')[1].strip())
            except Exception as e:
                logger.warning(f"Failed to extract web context metrics: {e}")
        
        return info
    
    def _build_enhanced_context_section(
        self,
        statement: str,
        source: str,
        context: str,
        category: Optional[str],
        country: Optional[str],
        web_info: dict
    ) -> str:
        """Build enhanced context section with web research integration"""
        
        context_parts = [
            "=== FACT-CHECK REQUEST ===",
            f"Statement to analyze: {statement}",
            f"Source: {source}",
            f"Category: {category or 'Not specified'}",
            f"Country: {country or 'Not specified'}",
            f"Analysis timestamp: {datetime.now().isoformat()}"
        ]
        
        # Add web research status
        if web_info['has_web_content']:
            context_parts.append(f"\n=== WEB RESEARCH STATUS ===")
            context_parts.append(f"Web research: COMPLETED")
            context_parts.append(f"Sources processed: {web_info['sources_processed']}")
            context_parts.append(f"URLs analyzed: {web_info['urls_found']}")
            context_parts.append(f"High-credibility sources: {web_info['credible_sources']}")
            
            if web_info['verification_status']:
                context_parts.append(f"Web verification status: {web_info['verification_status']}")
            if web_info['confidence_level'] > 0:
                context_parts.append(f"Web confidence level: {web_info['confidence_level']}%")
            
            context_parts.append(f"\nIMPORTANT: Use the web research findings below to enhance your analysis.")
            context_parts.append(f"Pay special attention to the sources processed and their credibility levels.")
        else:
            context_parts.append(f"\n=== WEB RESEARCH STATUS ===")
            context_parts.append(f"Web research: FAILED or UNAVAILABLE")
            context_parts.append(f"Relying on: LLM training data only")
            context_parts.append(f"Note: Analysis may be limited without current web sources")
        
        # Add the full context
        if context and context.strip():
            context_parts.append(f"\n=== RESEARCH CONTEXT ===")
            context_parts.append(context)
        
        # Add analysis instructions based on web context availability
        if web_info['has_web_content']:
            context_parts.append(f"\n=== ANALYSIS INSTRUCTIONS ===")
            context_parts.append(f"1. Prioritize findings from the web research above")
            context_parts.append(f"2. Cross-reference web findings with your training data")
            context_parts.append(f"3. Note any discrepancies between web sources and training data")
            context_parts.append(f"4. Give higher weight to high-credibility sources")
            context_parts.append(f"5. Incorporate web verification status in your final assessment")
            
            # Adjust resource counts based on web findings
            if web_info['sources_processed'] > 0:
                context_parts.append(f"6. Update resources_agreed/disagreed counts to reflect web sources")
        else:
            context_parts.append(f"\n=== ANALYSIS INSTRUCTIONS ===")
            context_parts.append(f"1. Analysis based on training data only")
            context_parts.append(f"2. Clearly indicate limited source availability")
            context_parts.append(f"3. Set appropriate confidence levels reflecting data limitations")
            context_parts.append(f"4. Mark status as UNVERIFIABLE if insufficient training data")
        
        return '\n'.join(context_parts)

# Create prompt builder instance  
prompt_builder = PromptBuilder()