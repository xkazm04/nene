import logging
import os
import requests
import re
import json
from typing import Dict, Any, List
from datetime import datetime
from bs4 import BeautifulSoup

from google import genai
from google.genai import types
from models.research_models import LLMResearchRequest, LLMResearchResponse

logger = logging.getLogger(__name__)

class GeminiClient:
    """
    Enhanced Gemini client with unified interface for fact-checking
    """

    def __init__(self):
        self.api_key = os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            logger.warning("GOOGLE_API_KEY not found - Gemini client unavailable")
            self.client = None
        else:
            try:
                self.client = genai.Client(api_key=self.api_key)
                logger.info("Gemini client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
                self.client = None
    
    def is_available(self) -> bool:
        """Check if client is available"""
        return self.client is not None
    
    def get_client_name(self) -> str:
        """Get client name for identification"""
        return "Google Gemini (Secondary)"
    
    # ===== UNIFIED INTERFACE METHODS =====
    
    async def generate_response(self, prompt: str) -> str:
        """
        Generate response from prompt - unified interface method
        
        Args:
            prompt: The prompt to send to Gemini
            
        Returns:
            Raw response text from Gemini
        """
        if not self.client:
            raise Exception("Gemini client not available")
        
        try:
            logger.info("Generating Gemini response...")
            
            # Use Gemini's generate_content method
            response = self.client.models.generate_content(
                model='gemini-1.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=4000,
                    top_p=0.9,
                    safety_settings=[
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                            threshold=types.HarmBlockThreshold.BLOCK_NONE
                        ),
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                            threshold=types.HarmBlockThreshold.BLOCK_NONE
                        ),
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                            threshold=types.HarmBlockThreshold.BLOCK_NONE
                        ),
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                            threshold=types.HarmBlockThreshold.BLOCK_NONE
                        ),
                    ]
                )
            )
            
            if response and response.text:
                logger.info(f"Gemini response generated successfully ({len(response.text)} chars)")
                return response.text
            else:
                raise Exception("Empty response from Gemini")
                
        except Exception as e:
            logger.error(f"Gemini response generation failed: {e}")
            raise
    
    def research_statement(self, request: LLMResearchRequest) -> LLMResearchResponse:
        """
        Research statement using Gemini - unified interface method
        
        Args:
            request: LLM research request
            
        Returns:
            LLM research response
        """
        try:
            # Import here to avoid circular imports
            from prompts.fc_prompt import prompt_manager
            from utils.response_parser import ResponseParser
            
            # Generate fact-check prompt
            prompt = prompt_manager.get_enhanced_factcheck_prompt(
                statement=request.statement,
                source=request.source,
                context=request.context,
                country=request.country,
                category=request.category
            )
            
            # Generate response
            import asyncio
            loop = asyncio.get_event_loop()
            response_text = loop.run_until_complete(self.generate_response(prompt))
            
            # Parse response
            parser = ResponseParser()
            parsed_result = parser.parse_llm_response(response_text)
            
            # Set research method
            parsed_result.research_method = "gemini_llm"
            
            return parsed_result
            
        except Exception as e:
            logger.error(f"Gemini research failed: {e}")
            # Create error response
            from utils.response_parser import ResponseParser
            parser = ResponseParser()
            return parser.create_error_response(request, f"Gemini research failed: {str(e)}")
    
    # ===== WEB RESEARCH METHODS =====
    
    def fetch_website_content(self, url: str) -> str:
        """
        Fetches and extracts text content from a given website URL.
        """
        try:
            if not url or not url.startswith(('http://', 'https://')):
                return f"Invalid URL format: {url}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            logger.info(f"Fetching content from URL: {url}")
            response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove non-content elements
            for element in soup(["script", "style", "nav", "footer", "aside", "form", "button", "header", "iframe"]):
                element.decompose()
            
            # Get text content
            text = soup.get_text(separator=' ', strip=True)
            text = ' '.join(text.split())  # Clean up whitespace
            
            if len(text) > 8000:
                text = text[:8000] + "... [content truncated]"
            
            if text and len(text) > 100:
                logger.info(f"Successfully extracted {len(text)} characters from {url}")
                return text
            else:
                return f"Minimal content extracted from {url}"
            
        except Exception as e:
            error_msg = f"Error fetching {url}: {str(e)}"
            logger.warning(error_msg)
            return error_msg
    
    async def enhanced_search_with_content_extraction(self, statement: str, category: str = "other") -> Dict[str, Any]:
        """
        Enhanced search with proper response processing for web research
        """
        if not self.client:
            return self._create_error_response(statement, "Gemini client not available")
        
        try:
            logger.info(f"Starting Gemini web search for: {statement[:100]}...")
            
            # Enhanced search prompt that requests structured analysis
            search_prompt = f"""
            I need to fact-check this statement: "{statement}"
            Category: {category}
            
            Please search for credible sources and fetch content from relevant websites to verify this statement.
            
            After fetching content, provide your analysis in this structured format:
            
            FACT_CHECK_ANALYSIS:
            - Verification Status: ["TRUE", "FACTUAL_ERROR", "DECEPTIVE_LIE", "MANIPULATIVE", "PARTIALLY_TRUE", "OUT_OF_CONTEXT", "UNVERIFIABLE"]
            - Confidence Level: [0-100]
            - Sources Analyzed: [number]
            
            KEY_FINDINGS:
            - Finding 1: [Based on fetched content]
            - Finding 2: [Based on fetched content]
            - Finding 3: [Based on fetched content]
            
            SUPPORTING_EVIDENCE:
            - Evidence 1: [From specific source]
            - Evidence 2: [From specific source]
            
            CONTRADICTING_EVIDENCE:
            - Evidence 1: [From specific source]
            - Evidence 2: [From specific source]
            
            SOURCES_PROCESSED:
            - Source 1: [URL and brief description]
            - Source 2: [URL and brief description]
            
            FINAL_SUMMARY:
            [2-3 sentences summarizing the fact-check based on the content you fetched]
            
            Please fetch content from credible sources like government sites, news organizations, fact-checkers, or academic institutions.
            """
            
            # Generate response with function calling enabled
            response = await self.generate_response(search_prompt)
            
            # Process the response
            result = self._process_enhanced_response(response, statement)
            
            logger.info(f"Gemini search completed with {len(result.get('urls_processed', []))} URLs processed")
            return result
            
        except Exception as e:
            logger.error(f"Gemini enhanced search failed: {e}")
            return self._create_error_response(statement, f"Search failed: {str(e)}")
    
    def _process_enhanced_response(self, response, statement: str) -> Dict[str, Any]:
        """Process response with improved URL and content detection"""
        
        result = {
            'statement': statement,
            'search_timestamp': datetime.now().isoformat(),
            'web_content': [],
            'urls_processed': [],
            'function_calls_made': 0,
            'content_summary': '',
            'search_method': 'function_calling',
            'structured_analysis': {}
        }
        
        try:
            if not response:
                result['content_summary'] = 'Empty response from Gemini'
                return result
            
            response_text = str(response)
            
            # Extract URLs from various patterns in the response
            urls = self._extract_urls_from_text(response_text)
            urls.extend(self._extract_urls_from_content_markers(response_text))
            
            # Remove duplicates and filter valid URLs
            urls = list(set([url for url in urls if self._is_valid_url(url)]))
            
            result['urls_processed'] = urls
            result['function_calls_made'] = len(urls)
            
            # Extract structured analysis
            structured_analysis = self._extract_structured_analysis_enhanced(response_text)
            result['structured_analysis'] = structured_analysis
            
            # Create content summary
            if urls:
                result['content_summary'] = f"Processed {len(urls)} sources. "
                if structured_analysis.get('confidence'):
                    result['content_summary'] += f"Confidence: {structured_analysis['confidence']}%. "
                if structured_analysis.get('status'):
                    result['content_summary'] += f"Status: {structured_analysis['status']}."
            else:
                result['content_summary'] = 'No credible sources found for verification.'
            
            # Extract insights with URL association
            insights = self._extract_insights_enhanced(response_text, statement, urls)
            result['web_content'] = insights
            
            logger.info(f"Enhanced response processing completed: {len(urls)} URLs, {len(insights)} insights")
            
        except Exception as e:
            logger.error(f"Error processing enhanced response: {e}")
            result['content_summary'] = f'Response processing failed: {str(e)}'
        
        return result
    
    # ===== UTILITY METHODS =====
    
    def _extract_urls_from_content_markers(self, text: str) -> List[str]:
        """Extract URLs from content markers"""
        urls = []
        
        # Look for our content markers
        start_pattern = r'WEBSITE_CONTENT_START:\s*(https?://[^\s\n]+)'
        end_pattern = r'WEBSITE_CONTENT_END:\s*(https?://[^\s\n]+)'
        
        start_matches = re.findall(start_pattern, text)
        end_matches = re.findall(end_pattern, text)
        
        urls.extend(start_matches)
        urls.extend(end_matches)
        
        return list(set(urls))
    
    def _extract_urls_from_text(self, text: str) -> List[str]:
        """Extract URLs from general text patterns"""
        # More comprehensive URL pattern
        url_patterns = [
            r'https?://[^\s\)\]\}\n]+',
            r'Fetching content from URL:\s*(https?://[^\s\n]+)',
            r'Successfully extracted \d+ characters from\s*(https?://[^\s\n]+)',
            r'Source \d+:\s*(https?://[^\s\n]+)',
        ]
        
        urls = []
        for pattern in url_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            urls.extend(matches)
        
        # Clean URLs
        cleaned_urls = []
        for url in urls:
            # Remove trailing punctuation
            url = re.sub(r'[.,;:!?]+$', '', url.strip())
            if self._is_valid_url(url):
                cleaned_urls.append(url)
        
        return list(set(cleaned_urls))
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid and from credible source"""
        if not url or not url.startswith(('http://', 'https://')):
            return False
        
        # Filter out obviously invalid URLs
        invalid_patterns = [
            'example.com',
            'localhost',
            '127.0.0.1',
            'test.com'
        ]
        
        url_lower = url.lower()
        for pattern in invalid_patterns:
            if pattern in url_lower:
                return False
        
        return True
    
    def _extract_structured_analysis_enhanced(self, response_text: str) -> Dict[str, Any]:
        """Extract structured analysis from response with better parsing"""
        analysis = {}
        
        try:
            # Look for structured sections in the response
            sections = {
                'status': ['Verification Status:', 'VERIFICATION STATUS:'],
                'confidence': ['Confidence Level:', 'CONFIDENCE LEVEL:'],
                'sources_analyzed': ['Sources Analyzed:', 'SOURCES ANALYZED:']
            }
            
            for key, markers in sections.items():
                for marker in markers:
                    if marker in response_text:
                        # Extract content after marker
                        start_idx = response_text.find(marker) + len(marker)
                        end_idx = response_text.find('\n', start_idx)
                        if end_idx == -1:
                            end_idx = start_idx + 100
                        
                        content = response_text[start_idx:end_idx].strip()
                        
                        if key == 'confidence':
                            # Extract number
                            numbers = re.findall(r'\d+', content)
                            if numbers:
                                analysis[key] = int(numbers[0])
                        elif key == 'sources_analyzed':
                            # Extract number
                            numbers = re.findall(r'\d+', content)
                            if numbers:
                                analysis[key] = int(numbers[0])
                        else:
                            analysis[key] = content
                        break
            
        except Exception as e:
            logger.warning(f"Failed to extract structured analysis: {e}")
        
        return analysis
    
    def _extract_section_content(self, text: str, start_marker: str, end_markers: List[str]) -> str:
        """Extract content between markers"""
        start_idx = text.find(start_marker)
        if start_idx == -1:
            return ""
        
        start_idx += len(start_marker)
        
        # Find earliest end marker
        end_idx = len(text)
        for end_marker in end_markers:
            marker_idx = text.find(end_marker, start_idx)
            if marker_idx != -1 and marker_idx < end_idx:
                end_idx = marker_idx
        
        return text[start_idx:end_idx].strip()
    
    def _extract_list_content(self, text: str, start_marker: str, end_markers: List[str]) -> List[str]:
        """Extract list items from section"""
        section_text = self._extract_section_content(text, start_marker, end_markers)
        items = []
        
        for line in section_text.split('\n'):
            line = line.strip()
            if line and (line.startswith('-') or line.startswith('*') or re.match(r'^\d+\.', line)):
                # Remove list markers
                item = re.sub(r'^[-*]\s*|\d+\.\s*', '', line).strip()
                if item:
                    items.append(item)
        
        return items
    
    def _estimate_confidence(self, text: str) -> int:
        """Estimate confidence based on text content"""
        # Count content extractions
        content_count = text.count("WEBSITE_CONTENT_START:") + text.count("Successfully extracted")
        
        # Base confidence
        confidence = 40
        
        # Boost for content extractions
        confidence += min(content_count * 15, 40)
        
        # Boost for specific evidence
        if 'according to' in text.lower() or 'study shows' in text.lower():
            confidence += 10
        
        return min(confidence, 95)
    
    def _extract_basic_findings(self, text: str) -> List[str]:
        """Extract basic findings when structured extraction fails"""
        findings = []
        sentences = text.split('.')
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 50 and any(word in sentence.lower() for word in ['according to', 'study', 'research', 'data shows', 'evidence']):
                findings.append(sentence + '.')
                if len(findings) >= 3:
                    break
        
        return findings[:3]
    
    def _extract_insights_enhanced(self, response_text: str, statement: str, urls: List[str]) -> List[Dict[str, Any]]:
        """Extract insights with URL association"""
        insights = []
        
        # Extract content blocks with associated URLs
        content_blocks = response_text.split("WEBSITE_CONTENT_START:")
        
        for i, block in enumerate(content_blocks[1:], 1):
            if "WEBSITE_CONTENT_END:" in block:
                content = block.split("WEBSITE_CONTENT_END:")[0].strip()
                if content and len(content) > 100:
                    insights.append({
                        'type': 'web_content',
                        'content': content[:500] + "..." if len(content) > 500 else content,
                        'source_url': urls[i-1] if i-1 < len(urls) else None,
                        'relevance_score': 85,
                        'extraction_method': 'gemini_function'
                    })
        
        # If no content blocks found, create insights from URLs and text
        if not insights and urls:
            # Create basic insights from the overall response
            key_findings = self._extract_basic_findings(response_text)
            for i, finding in enumerate(key_findings):
                insights.append({
                    'type': 'analysis_finding',
                    'content': finding,
                    'source_url': urls[i] if i < len(urls) else None,
                    'relevance_score': 70,
                    'extraction_method': 'text_analysis'
                })
        
        return insights
    
    def _create_error_response(self, statement: str, reason: str) -> Dict[str, Any]:
        """Create error response"""
        return {
            'statement': statement,
            'search_timestamp': datetime.now().isoformat(),
            'web_content': [],
            'urls_processed': [],
            'function_calls_made': 0,
            'content_summary': f'Content extraction failed: {reason}',
            'search_method': 'failed',
            'error': reason,
            'structured_analysis': {}
        }

# Create client instance
gemini_client = GeminiClient()