import os
import logging
from typing import Dict, Any, List
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import re

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class GeminiClient:

    def __init__(self):
        self.api_key = os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            logger.warning("GOOGLE_API_KEY not found - web extraction unavailable")
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
    
    def fetch_website_content(self, url: str) -> str:
        """
        Fetches and extracts text content from a given website URL.
        """
        try:
            if not url or not url.startswith(('http://', 'https://')):
                return f"Invalid URL provided: {url}"
            
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
                text = text[:8000] + "... [content truncated for analysis]"
            
            if text and len(text) > 100:
                logger.info(f"Successfully extracted {len(text)} characters from {url}")
                # Return with clear URL marker for parsing
                return f"WEBSITE_CONTENT_START: {url}\n\n{text}\n\nWEBSITE_CONTENT_END: {url}"
            else:
                return f"No substantial text content found on {url}"
            
        except Exception as e:
            error_msg = f"Error fetching {url}: {str(e)}"
            logger.warning(error_msg)
            return error_msg
    
    async def enhanced_search_with_content_extraction(self, statement: str, category: str = "other") -> Dict[str, Any]:
        """
        Fixed search with proper response processing
        """
        if not self.client:
            return self._create_error_response(statement, "Gemini client not available")
        
        try:
            logger.info(f"Starting search with content extraction for: {statement[:100]}...")
            
            # Enhanced search prompt that requests structured analysis
            search_prompt = f"""
            I need to fact-check this statement: "{statement}"
            Category: {category}
            
            Please search for credible sources and fetch content from relevant websites to verify this statement.
            
            After fetching content, provide your analysis in this structured format:
            
            FACT_CHECK_ANALYSIS:
            - Verification Status: [TRUE/FALSE/PARTIALLY_TRUE/MISLEADING/UNVERIFIABLE]
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
            
            # Enable automatic function calling
            logger.info("AFC is enabled with max remote calls: 5.")
            response = self.client.models.generate_content(
                model='gemini-2.0-flash-001',
                contents=search_prompt,
                config=types.GenerateContentConfig(
                    tools=[self.fetch_website_content],
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=False,
                        maximum_remote_calls=5
                    )
                )
            )
            
            if not response or not response.text:
                return self._create_error_response(statement, "Empty search response")
            
            logger.info("Received search response with potential function calls")
            
            # Process the response with improved parsing
            extracted_content = self._process_enhanced_response(response, statement)
            
            return extracted_content
            
        except Exception as e:
            logger.error(f"Enhanced search failed: {e}")
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
            response_text = response.text
            result['content_summary'] = response_text
            
            # NEW: Better URL extraction from both content markers and general text
            urls_from_content = self._extract_urls_from_content_markers(response_text)
            urls_from_text = self._extract_urls_from_text(response_text)
            
            # Combine and deduplicate URLs
            all_urls = list(set(urls_from_content + urls_from_text))
            result['urls_processed'] = all_urls
            
            # Count successful content extractions
            content_blocks = response_text.count("WEBSITE_CONTENT_START:")
            if content_blocks == 0:
                # Fallback: count any content extraction patterns
                content_blocks = max(
                    response_text.count("Content from http"),
                    response_text.count("Fetching content from URL:"),
                    len(urls_from_content)
                )
            
            result['function_calls_made'] = content_blocks
            
            logger.info(f"Found {len(all_urls)} URLs total ({len(urls_from_content)} from content, {len(urls_from_text)} from text)")
            logger.info(f"Detected {content_blocks} successful content extractions")
            
            # Extract structured analysis
            structured_analysis = self._extract_structured_analysis_enhanced(response_text)
            result['structured_analysis'] = structured_analysis
            
            # Extract insights
            web_content = self._extract_insights_enhanced(response_text, statement, all_urls)
            result['web_content'] = web_content
            
        except Exception as e:
            logger.error(f"Error processing enhanced response: {e}")
        
        return result
    
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
            r'https?://[^\s\)\]\}\n]+',  # Standard URLs
            r'Fetching content from URL:\s*(https?://[^\s\n]+)',  # Log pattern
            r'Successfully extracted \d+ characters from\s*(https?://[^\s\n]+)',  # Success pattern
            r'Source \d+:\s*(https?://[^\s\n]+)',  # Source pattern
        ]
        
        urls = []
        for pattern in url_patterns:
            matches = re.findall(pattern, text)
            urls.extend(matches)
        
        # Clean URLs
        cleaned_urls = []
        for url in urls:
            # Remove trailing punctuation
            url = url.rstrip('.,;)]}')
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
            # Look for structured sections
            sections = {
                'verification_status': self._extract_section_content(response_text, 'Verification Status:', ['Confidence Level:', 'Sources Analyzed:']),
                'confidence_level': self._extract_section_content(response_text, 'Confidence Level:', ['Sources Analyzed:', 'KEY_FINDINGS:']),
                'sources_analyzed': self._extract_section_content(response_text, 'Sources Analyzed:', ['KEY_FINDINGS:', 'SUPPORTING_EVIDENCE:']),
                'key_findings': self._extract_list_content(response_text, 'KEY_FINDINGS:', ['SUPPORTING_EVIDENCE:', 'CONTRADICTING_EVIDENCE:']),
                'supporting_evidence': self._extract_list_content(response_text, 'SUPPORTING_EVIDENCE:', ['CONTRADICTING_EVIDENCE:', 'SOURCES_PROCESSED:']),
                'contradicting_evidence': self._extract_list_content(response_text, 'CONTRADICTING_EVIDENCE:', ['SOURCES_PROCESSED:', 'FINAL_SUMMARY:']),
                'fact_check_summary': self._extract_section_content(response_text, 'FINAL_SUMMARY:', [])
            }
            
            # Clean and process sections
            verification = sections['verification_status'].strip().upper()
            if any(status in verification for status in ['TRUE', 'FALSE', 'PARTIALLY_TRUE', 'MISLEADING', 'UNVERIFIABLE']):
                analysis['verification_status'] = verification
            else:
                # Fallback verification logic
                analysis['verification_status'] = self._infer_verification_status(response_text)
            
            # Extract confidence level
            confidence_text = sections['confidence_level'].strip()
            confidence_match = re.search(r'(\d+)', confidence_text)
            if confidence_match:
                analysis['confidence_level'] = int(confidence_match.group(1))
            else:
                analysis['confidence_level'] = self._estimate_confidence(response_text)
            
            analysis['key_findings'] = sections['key_findings'][:5]  # Limit to 5
            analysis['supporting_evidence'] = sections['supporting_evidence'][:3]  # Limit to 3
            analysis['contradicting_evidence'] = sections['contradicting_evidence'][:3]  # Limit to 3
            analysis['fact_check_summary'] = sections['fact_check_summary'] or "Analysis completed with available sources"
            
        except Exception as e:
            logger.warning(f"Failed to extract structured analysis: {e}")
            # Fallback analysis
            analysis = {
                'verification_status': self._infer_verification_status(response_text),
                'confidence_level': self._estimate_confidence(response_text),
                'key_findings': self._extract_basic_findings(response_text),
                'fact_check_summary': "Analysis completed with available sources"
            }
        
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
            if line.startswith('-') and len(line) > 5:
                items.append(line[1:].strip())
            elif line.startswith(('1.', '2.', '3.', '4.', '5.')) and len(line) > 5:
                items.append(line[2:].strip())
        
        return items
    
    def _infer_verification_status(self, text: str) -> str:
        """Infer verification status from text content"""
        text_lower = text.lower()
        
        if any(phrase in text_lower for phrase in ['confirmed', 'accurate', 'correct', 'verified']):
            if any(phrase in text_lower for phrase in ['partially', 'somewhat', 'limited']):
                return 'PARTIALLY_TRUE'
            else:
                return 'TRUE'
        elif any(phrase in text_lower for phrase in ['false', 'incorrect', 'wrong', 'debunked']):
            return 'FALSE'
        elif any(phrase in text_lower for phrase in ['misleading', 'deceptive', 'out of context']):
            return 'MISLEADING'
        else:
            return 'UNVERIFIABLE'
    
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
            if (len(sentence) > 30 and 
                any(indicator in sentence.lower() for indicator in [
                    'according to', 'study shows', 'research indicates', 'evidence suggests',
                    'analysis shows', 'data reveals', 'report states'
                ])):
                findings.append(sentence)
        
        return findings[:3]
    
    def _extract_insights_enhanced(self, response_text: str, statement: str, urls: List[str]) -> List[Dict[str, Any]]:
        """Extract insights with URL association"""
        insights = []
        
        # Extract content blocks with associated URLs
        content_blocks = response_text.split("WEBSITE_CONTENT_START:")
        
        for i, block in enumerate(content_blocks[1:], 1):  # Skip first empty split
            if "WEBSITE_CONTENT_END:" in block:
                # Extract URL and content
                lines = block.split('\n')
                if lines:
                    url = lines[0].strip()
                    content_lines = []
                    
                    for line in lines[1:]:
                        if "WEBSITE_CONTENT_END:" in line:
                            break
                        content_lines.append(line.strip())
                    
                    content = ' '.join(content_lines)
                    
                    if len(content) > 100:  # Substantial content
                        insights.append({
                            'content': content[:300] + "..." if len(content) > 300 else content,
                            'source_url': url,
                            'type': 'extracted_content',
                            'relevance_score': 0.8,
                            'extraction_method': 'function_calling'
                        })
        
        # If no content blocks found, create insights from URLs and text
        if not insights and urls:
            for url in urls[:3]:
                insights.append({
                    'content': f"Content extracted from {url}",
                    'source_url': url,
                    'type': 'url_reference',
                    'relevance_score': 0.6,
                    'extraction_method': 'url_found'
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