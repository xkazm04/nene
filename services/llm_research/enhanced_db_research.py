import logging
from datetime import datetime
from typing import Optional
from models.research_models import LLMResearchRequest, LLMResearchResponse
from services.llm_clients.groq_client import GroqLLMClient
from services.llm_clients.gemini_client import GeminiClient
from utils.response_parser import ResponseParser
from prompts.fc_prompt import factcheck_prompt

logger = logging.getLogger(__name__)

class EnhancedDatabaseResearch:
    """
    Enhanced database research that properly uses web context and grounding metadata
    Single responsibility: Perform LLM fact-checking with web-enhanced context
    """
    
    def __init__(self):
        self.groq_client = GroqLLMClient()
        self.gemini_client = GeminiClient()
        self.parser = ResponseParser()
        logger.info("Enhanced database research service initialized")
    
    async def research_with_web_context(
        self, 
        request: LLMResearchRequest, 
        web_context: str
    ) -> LLMResearchResponse:
        """
        Perform LLM research using web-enhanced context with grounding metadata
        
        Args:
            request: Research request
            web_context: Web research context from orchestrator
            
        Returns:
            Enhanced LLM research response
        """
        try:
            logger.info(f"Performing enhanced research: {request.statement[:50]}...")
            
            # Extract grounding sources from web context
            grounding_sources = self._extract_grounding_sources(web_context)
            
            # Build enhanced prompt with web context and sources
            enhanced_prompt = self._build_enhanced_prompt_with_sources(
                request, web_context, grounding_sources
            )
            
            # Create enhanced request
            enhanced_request = self._create_enhanced_request(request, web_context)
            
            # Perform LLM research
            if self.groq_client.is_available():
                logger.info("Using Groq for enhanced research with grounding sources")
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.groq_client.generate_completion(enhanced_prompt)
                )
            elif self.gemini_client.is_available():
                logger.info("Using Gemini for enhanced research with grounding sources")
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.gemini_client.generate_completion(enhanced_prompt)
                )
            else:
                logger.error("No LLM clients available")
                return self.parser.create_error_response(
                    request, "No LLM clients available"
                )
            
            # Parse and enhance response
            parsed_response = self.parser.parse_response(response, request)
            enhanced_response = self._enhance_response_with_web_info(
                parsed_response, web_context, grounding_sources
            )
            
            logger.info("Enhanced research completed successfully")
            return enhanced_response
            
        except Exception as e:
            logger.error(f"Enhanced research failed: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return self.parser.create_error_response(
                request, f"Enhanced research failed: {str(e)}"
            )
    
    def _extract_grounding_sources(self, web_context: str) -> list:
        """Extract grounding sources from web context"""
        sources = []
        
        try:
            # Look for grounding metadata in log output
            if "grounding_chunks=" in web_context:
                # Extract the grounding metadata section
                grounding_section = web_context.split("grounding_chunks=")[1]
                
                # Extract URLs from grounding chunks
                import re
                url_pattern = r"'uri': '([^']+)'"
                grounding_urls = re.findall(url_pattern, grounding_section)
                
                # Extract domain/title info
                title_pattern = r"'title': '([^']+)'"
                titles = re.findall(title_pattern, grounding_section)
                
                # Combine URLs and titles
                for i, url in enumerate(grounding_urls):
                    title = titles[i] if i < len(titles) else "Unknown Source"
                    sources.append({
                        'url': url,
                        'title': title,
                        'source_type': 'grounding'
                    })
            
            # Also extract URLs from credible sources section
            if "=== CREDIBLE SOURCES DISCOVERED ===" in web_context:
                sources_section = web_context.split("=== CREDIBLE SOURCES DISCOVERED ===")[1]
                next_section = sources_section.find("===")
                if next_section != -1:
                    sources_section = sources_section[:next_section]
                
                # Extract numbered URLs
                url_pattern = r'https?://[^\s\n]+'
                credible_urls = re.findall(url_pattern, sources_section)
                
                for url in credible_urls:
                    if not any(s['url'] == url for s in sources):  # Avoid duplicates
                        sources.append({
                            'url': url,
                            'title': self._extract_domain_name(url),
                            'source_type': 'credible'
                        })
            
            logger.info(f"Extracted {len(sources)} grounding sources from web context")
            return sources
            
        except Exception as e:
            logger.warning(f"Failed to extract grounding sources: {e}")
            return []
    
    def _extract_domain_name(self, url: str) -> str:
        """Extract clean domain name from URL"""
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.lower()
            return domain.replace('www.', '').title()
        except:
            return "Unknown Source"
    
    def _build_enhanced_prompt_with_sources(
        self, 
        request: LLMResearchRequest, 
        web_context: str, 
        grounding_sources: list
    ) -> str:
        """Build enhanced prompt with web context and source analysis instructions"""
        
        web_info = self._analyze_web_context(web_context)
        
        # Create sources list for LLM to analyze
        sources_list = ""
        if grounding_sources:
            sources_list = "\n=== SOURCES FOUND BY WEB SEARCH ===\n"
            for i, source in enumerate(grounding_sources[:10], 1):  # Limit to 10
                sources_list += f"{i}. {source['title']} - {source['url']}\n"
            sources_list += "\nINSTRUCTIONS: Analyze each source above and categorize them in your response.\n"
        
        enhanced_prompt = f"""
You are a professional fact-checker with access to current web research and training data.

FACT-CHECK REQUEST:
Statement: "{request.statement}"
Source: {request.source}
Category: {request.category}
Country: {request.country}

WEB RESEARCH STATUS:
- Search performed: {web_info['search_performed']}
- Grounding sources found: {len(grounding_sources)}
- Content extracted: {web_info['has_content']}
- Source quality: {web_info['source_quality']}

{sources_list}

{web_context}

ENHANCED SOURCE ANALYSIS INSTRUCTIONS:
1. **MANDATORY**: For each source found above, you MUST categorize it and include it in resources_agreed or resources_disagreed
2. **Source Categories**: Use these categories for any source worldwide:
   - mainstream: Major news outlets (BBC, CNN, Reuters, Guardian, etc.)
   - governance: Government sites (.gov, official agencies, parliament sites, etc.)
   - academic: Universities, research institutions (.edu, academic journals)
   - medical: Health organizations (WHO, CDC, medical institutions)
   - legal: Courts, legal databases, law firms
   - economic: Central banks, financial institutions, economic research
   - other: Everything else (blogs, independent media, etc.)

3. **Country Identification**: Identify country using ISO codes (us, gb, de, fr, etc.)

4. **Credibility Assessment**: 
   - high: Government sources, major academic institutions, established international organizations
   - medium: Established news outlets, recognized think tanks
   - low: Blogs, opinion sites, unverified sources

5. **Agreement Analysis**: Determine if each source SUPPORTS, OPPOSES, or is NEUTRAL toward the statement
   - resources_agreed: Sources that support or verify the statement
   - resources_disagreed: Sources that contradict or refute the statement

6. **Extract Key Findings**: For each source, extract the specific data point or quote that supports/opposes the statement

CRITICAL REQUIREMENT:
- If you found sources above, you MUST populate resources_agreed and/or resources_disagreed
- Do NOT leave both sections empty if sources were provided
- Each source must have a specific "key_finding" that relates to the statement

Now perform comprehensive fact-checking using the factcheck_prompt format:

{factcheck_prompt}
"""
        
        return enhanced_prompt
    
    def _analyze_web_context(self, web_context: str) -> dict:
        """Analyze web context to extract key metrics"""
        
        info = {
            'search_performed': False,
            'credible_sources': 0,
            'key_findings': 0,
            'source_quality': 'unknown',
            'has_content': False
        }
        
        try:
            lines = web_context.split('\n')
            for line in lines:
                if 'Search successful: True' in line:
                    info['search_performed'] = True
                elif 'Credible sources found:' in line:
                    try:
                        info['credible_sources'] = int(line.split(':')[1].strip())
                    except:
                        pass
                elif 'Source quality:' in line:
                    info['source_quality'] = line.split(':')[1].strip()
            
            # Check for grounding metadata
            if 'grounding_metadata' in web_context:
                info['search_performed'] = True
            
            # Count key findings
            if '=== KEY FINDINGS FROM SEARCH ===' in web_context:
                findings_section = web_context.split('=== KEY FINDINGS FROM SEARCH ===')[1]
                if '===' in findings_section:
                    findings_section = findings_section.split('===')[0]
                info['key_findings'] = len([line for line in findings_section.split('\n') if line.strip().startswith(('1.', '2.', '3.', '4.', '5.'))])
            
            # Check for substantial content
            info['has_content'] = len(web_context) > 500 and 'SEARCH RESPONSE CONTENT' in web_context
            
        except Exception as e:
            logger.warning(f"Failed to analyze web context: {e}")
        
        return info
    
    def _create_enhanced_request(self, request: LLMResearchRequest, web_context: str) -> LLMResearchRequest:
        """Create enhanced request with web context"""
        
        # Add web context to existing context
        existing_context = getattr(request, 'context', '') or ''
        enhanced_context = f"{existing_context}\n\nWEB_RESEARCH_CONTEXT:\n{web_context}" if existing_context else f"WEB_RESEARCH_CONTEXT:\n{web_context}"
        
        # Create new request with enhanced context
        enhanced_request = LLMResearchRequest(
            statement=request.statement,
            source=request.source,
            context=enhanced_context,
            country=request.country,
            category=request.category,
            profile_id=request.profile_id
        )
        
        return enhanced_request
    
    def _enhance_response_with_web_info(
        self, 
        response: LLMResearchResponse, 
        web_context: str,
        grounding_sources: list
    ) -> LLMResearchResponse:
        """Enhance LLM response with web research metadata"""
        
        web_info = self._analyze_web_context(web_context)
        
        # Update research method
        if grounding_sources:
            response.research_method = f"LLM + Enhanced Web Search ({len(grounding_sources)} grounding sources)"
        elif web_info['search_performed']:
            response.research_method = "LLM + Web Search (limited sources)"
        else:
            response.research_method = "LLM + Failed Web Search"
        
        # Boost confidence if we have grounding sources
        if grounding_sources:
            gov_sources = sum(1 for s in grounding_sources if '.gov' in s['url'] or 'whitehouse' in s['url'])
            if gov_sources >= 2:
                response.confidence_score = min(response.confidence_score + 20, 95)
            elif gov_sources >= 1:
                response.confidence_score = min(response.confidence_score + 10, 90)
            elif len(grounding_sources) >= 3:
                response.confidence_score = min(response.confidence_score + 5, 85)
        
        # Add web research summary to additional context
        web_summary = f"""
WEB RESEARCH SUMMARY:
- Search performed: {web_info['search_performed']}
- Grounding sources: {len(grounding_sources)}
- Key findings: {web_info['key_findings']}
- Source quality: {web_info['source_quality']}
- Research timestamp: {datetime.now().isoformat()}
"""
        
        existing_context = getattr(response, 'additional_context', '') or ''
        response.additional_context = existing_context + web_summary
        
        return response

# Create service instance
enhanced_db_research = EnhancedDatabaseResearch()