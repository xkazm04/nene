import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import os
import re

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class EnhancedWebResearch:
    """
    Enhanced web research service - lets LLM handle source categorization
    Single responsibility: Extract web context and provide ALL sources for LLM analysis
    """
    
    def __init__(self):
        self.api_key = os.getenv('GOOGLE_API_KEY')
        self.client = None
        self._initialize_genai()
    
    def _initialize_genai(self):
        """Initialize new Google Genai client"""
        if not self.api_key:
            logger.error("GOOGLE_API_KEY not found")
            return
        
        try:
            self.client = genai.Client(api_key=self.api_key)
            logger.info("Enhanced web research service initialized with Google Genai client")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Genai client: {e}")
            self.client = None
    
    def is_available(self) -> bool:
        """Check if service is ready"""
        return self.client is not None
    
    async def research_statement(self, statement: str, category: str = "other") -> str:
        """
        Main research method - returns formatted context for db_research
        
        Args:
            statement: Statement to fact-check
            category: Statement category
            
        Returns:
            Formatted context string for LLM consumption
        """
        if not self.is_available():
            logger.warning("Web research unavailable - Google Genai client not initialized")
            return self._create_unavailable_context(statement)
        
        try:
            logger.info(f"Researching statement with Google search: {statement[:100]}...")
            
            # Perform Google search with grounding
            search_results = await self._perform_google_search_with_grounding(statement, category)
            
            # Format results for LLM consumption
            formatted_context = self._format_context_for_llm(
                statement, category, search_results
            )
            
            logger.info("Google search with grounding completed successfully")
            return formatted_context
            
        except Exception as e:
            logger.error(f"Google search failed: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return self._create_error_context(statement, str(e))
    
    async def _perform_google_search_with_grounding(self, statement: str, category: str) -> Dict[str, Any]:
        """Perform Google search and extract grounding metadata"""
        
        search_prompt = f"""
Search for reliable information about this statement: "{statement}"

Find credible sources that can help verify or refute this claim. 
Focus on finding:
1. Official government sources and institutions
2. Reputable news organizations and fact-checkers  
3. Academic or research sources
4. Expert statements and data

Provide specific facts, quotes, and source information in your response.
"""
        
        try:
            logger.info("=== Starting Google Search with grounding ===")
            
            google_search_tool = types.Tool(
                google_search=types.GoogleSearch()  
            )
            
            config = types.GenerateContentConfig(
                tools=[google_search_tool],
                temperature=0.1,
            )
            
            # Perform search
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.models.generate_content(
                    model='gemini-2.0-flash-001',
                    contents=search_prompt,
                    config=config
                )
            )
            
            logger.info(f"=== Google search response received ===")
            
            # Process response with grounding extraction
            return self._process_search_with_grounding(response, statement)
            
        except Exception as e:
            logger.error(f"Google search failed: {e}")
            return {
                'error': str(e), 
                'search_performed': False,
                'content': '', 
                'grounding_sources': [],
                'all_sources': []
            }
    
    def _process_search_with_grounding(self, response, statement: str) -> Dict[str, Any]:
        """Process search response and extract grounding metadata"""
        
        result = {
            'search_performed': False,
            'content': '',
            'grounding_sources': [],
            'all_sources': [],
            'key_findings': [],
            'statement': statement,
            'raw_grounding_data': None
        }
        
        try:
            # Extract main content
            if hasattr(response, 'text') and response.text:
                result['content'] = response.text
                result['search_performed'] = True
                logger.info(f"Extracted response content: {len(response.text)} characters")
            
            # Extract grounding metadata (the key improvement!)
            if hasattr(response, 'candidates'):
                for candidate in response.candidates:
                    if hasattr(candidate, 'grounding_metadata'):
                        grounding_data = candidate.grounding_metadata
                        result['raw_grounding_data'] = str(grounding_data)
                        
                        # Extract grounding sources
                        if hasattr(grounding_data, 'grounding_chunks'):
                            for chunk in grounding_data.grounding_chunks:
                                if hasattr(chunk, 'web') and chunk.web:
                                    source = {
                                        'url': chunk.web.uri if hasattr(chunk.web, 'uri') else 'Unknown',
                                        'title': chunk.web.title if hasattr(chunk.web, 'title') else 'Unknown Title',
                                        'domain': chunk.web.domain if hasattr(chunk.web, 'domain') else self._extract_domain_from_url(chunk.web.uri if hasattr(chunk.web, 'uri') else ''),
                                        'source_type': 'grounding'
                                    }
                                    result['grounding_sources'].append(source)
                        
                        logger.info(f"Found {len(result['grounding_sources'])} grounding sources")
            
            # Extract additional URLs from content (as fallback)
            if result['content']:
                content_urls = self._extract_all_urls_from_content(result['content'])
                for url in content_urls:
                    if not any(s['url'] == url for s in result['grounding_sources']):
                        result['all_sources'].append({
                            'url': url,
                            'title': self._extract_domain_from_url(url),
                            'source_type': 'content'
                        })
                
                # Extract key findings
                result['key_findings'] = self._extract_key_findings(result['content'])
            
            # Combine all sources
            result['all_sources'] = result['grounding_sources'] + result['all_sources']
            
            logger.info(f"Total sources found: {len(result['all_sources'])}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to process search response: {e}")
            result['error'] = str(e)
            return result
    
    def _extract_domain_from_url(self, url: str) -> str:
        """Extract domain from URL"""
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.lower()
            return domain.replace('www.', '')
        except:
            return 'unknown'
    
    def _extract_all_urls_from_content(self, content: str) -> List[str]:
        """Extract ALL URLs from content (no filtering)"""
        url_pattern = r'https?://[^\s\)\]\}\n\'"<>]+'
        urls = re.findall(url_pattern, content, re.IGNORECASE)
        
        # Basic cleaning only
        cleaned_urls = []
        for url in urls:
            url = url.strip('.,;)]}"\'\n <>').rstrip('/')
            if len(url) > 10 and url.startswith(('http://', 'https://')):
                cleaned_urls.append(url)
        
        return list(set(cleaned_urls))[:20]  # Limit to 20 URLs
    
    def _extract_key_findings(self, content: str) -> List[str]:
        """Extract key factual findings from search content"""
        findings = []
        
        # Look for sentences with specific patterns
        patterns = [
            r'(?i)according to ([^,]+), (.+?)(?=\.|according|however|but|\n)',
            r'(?i)(\d+(?:\.\d+)?%?) (.+?)(?=\.|,|according|however|\n)',
            r'(?i)(?:study|report|analysis|survey) (?:found|showed|indicated|revealed) (.+?)(?=\.|study|report|\n)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            for match in matches:
                if isinstance(match, tuple):
                    finding = ' '.join(str(m) for m in match).strip()
                else:
                    finding = str(match).strip()
                
                finding = re.sub(r'\s+', ' ', finding).replace('\n', ' ')
                
                if 20 < len(finding) < 200:
                    findings.append(finding)
        
        return findings[:5]
    
    def _format_context_for_llm(self, statement: str, category: str, search_results: Dict[str, Any]) -> str:
        """Format search results for LLM consumption with ALL sources"""
        
        timestamp = datetime.now().isoformat()
        
        context_parts = [
            "=== GOOGLE SEARCH WITH GROUNDING RESULTS ===",
            f"Statement: {statement}",
            f"Category: {category}",
            f"Research timestamp: {timestamp}",
            f"Search performed: {search_results.get('search_performed', False)}",
            f"Grounding sources found: {len(search_results.get('grounding_sources', []))}",
            f"Total sources discovered: {len(search_results.get('all_sources', []))}"
        ]
        
        # Add ALL sources for LLM to analyze
        all_sources = search_results.get('all_sources', [])
        if all_sources:
            context_parts.append("\n=== ALL SOURCES FOR LLM ANALYSIS ===")
            context_parts.append("INSTRUCTION: Analyze each source below and categorize in resources_agreed/disagreed")
            for i, source in enumerate(all_sources, 1):
                context_parts.append(f"{i}. {source['title']} - {source['url']} (type: {source['source_type']})")
        
        # Add grounding metadata for debugging
        if search_results.get('raw_grounding_data'):
            context_parts.append(f"\n=== GROUNDING METADATA (DEBUG) ===")
            context_parts.append(search_results['raw_grounding_data'][:1000] + "..." if len(search_results['raw_grounding_data']) > 1000 else search_results['raw_grounding_data'])
        
        # Add key findings
        findings = search_results.get('key_findings', [])
        if findings:
            context_parts.append("\n=== KEY FINDINGS FROM SEARCH ===")
            for i, finding in enumerate(findings, 1):
                context_parts.append(f"{i}. {finding}")
        
        # Add search content
        content = search_results.get('content', '')
        if content and len(content) > 100:
            content_excerpt = content[:1500] + "..." if len(content) > 1500 else content
            context_parts.append(f"\n=== SEARCH RESPONSE CONTENT ===")
            context_parts.append(content_excerpt)
        
        # Add processing summary
        context_parts.append(f"\n=== PROCESSING SUMMARY ===")
        context_parts.append(f"Sources for LLM analysis: {len(all_sources)}")
        context_parts.append(f"Grounding sources: {len(search_results.get('grounding_sources', []))}")
        context_parts.append(f"Key insights: {len(findings)}")
        context_parts.append("LLM MUST categorize all sources above into resources_agreed/disagreed")
        
        if search_results.get('error'):
            context_parts.append(f"\nSearch error: {search_results['error']}")
        
        return '\n'.join(context_parts)
    
    def _create_unavailable_context(self, statement: str) -> str:
        """Context when service unavailable"""
        return f"""=== GOOGLE SEARCH UNAVAILABLE ===
Statement: {statement}
Status: Google Genai client not initialized
Research timestamp: {datetime.now().isoformat()}
Note: Analysis will use LLM training data only

=== PROCESSING SUMMARY ===
Sources for LLM analysis: 0
Search performed: False"""
    
    def _create_error_context(self, statement: str, error: str) -> str:
        """Context when search fails"""
        return f"""=== GOOGLE SEARCH FAILED ===
Statement: {statement}
Error: {error}
Research timestamp: {datetime.now().isoformat()}
Note: Analysis will use LLM training data only

=== PROCESSING SUMMARY ===
Sources for LLM analysis: 0
Search performed: False"""

# Create service instance
enhanced_web_research = EnhancedWebResearch()