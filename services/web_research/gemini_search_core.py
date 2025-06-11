import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio
import re
import requests
from urllib.parse import urlparse

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

logger = logging.getLogger(__name__)

class GeminiSearchCore:
    """Simplified core search functionality with reliable content extraction"""
    
    def __init__(self):
        self.api_key = os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            logger.warning("GOOGLE_API_KEY not found - web search will be unavailable")
            self.model = None
        else:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(
                    'gemini-2.0-flash-lite',
                    tools=[{'google_search': {}}]
                )
                logger.info("Gemini search core initialized with google_search tool")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini model: {e}")
                self.model = None
    
    def is_available(self) -> bool:
        """Check if search core is available"""
        return self.model is not None
    
    async def perform_search_with_context(self, statement: str, category: str) -> Dict[str, Any]:
        """
        Simplified search that focuses on extracting usable context for database research
        """
        if not self.model:
            return self._create_fallback_context(statement, "Gemini API not available")
        
        try:
            # Step 1: Perform focused search
            search_prompt = self._build_focused_search_prompt(statement, category)
            
            response = self.model.generate_content(
                search_prompt,
                safety_settings={
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                }
            )
            
            if not response or not response.text:
                return self._create_fallback_context(statement, "Empty search response")
            
            logger.info("Received search response from Gemini")
            
            # Step 2: Extract key information for context
            context_data = self._extract_context_information(response.text)
            
            # Step 3: Try to fetch additional content from URLs (simplified)
            urls = self._extract_urls(response.text)
            web_content = await self._fetch_key_content(urls[:2], statement)  # Limit to 2 URLs
            
            # Step 4: Create structured context for database research
            structured_context = self._create_structured_context(
                statement, category, context_data, web_content
            )
            
            return {
                'success': True,
                'context_for_db': structured_context,
                'raw_search_response': response.text,
                'urls_found': urls,
                'web_content_extracted': len(web_content),
                'search_timestamp': datetime.now().isoformat(),
                'search_method': 'gemini_with_context'
            }
            
        except Exception as e:
            logger.error(f"Search with context failed: {e}")
            return self._create_fallback_context(statement, f"Search failed: {str(e)}")
    
    def _build_focused_search_prompt(self, statement: str, category: str) -> str:
        """Build a focused search prompt that prioritizes finding factual context"""
        return f"""
        Fact-check this statement: "{statement}"
        Category: {category}
        
        Find credible sources and provide analysis in this format:
        
        VERIFICATION_STATUS: [True/False/Partially True/Misleading/Unverifiable]
        
        KEY_FACTS:
        - Fact 1: [Specific verifiable fact from credible sources]
        - Fact 2: [Specific verifiable fact from credible sources]
        - Fact 3: [Specific verifiable fact from credible sources]
        
        SUPPORTING_SOURCES:
        - Source 1: [Name] - [Key finding/quote] - [URL if available]
        - Source 2: [Name] - [Key finding/quote] - [URL if available]
        
        CONTRADICTING_SOURCES:
        - Source 1: [Name] - [Key finding/quote] - [URL if available]
        - Source 2: [Name] - [Key finding/quote] - [URL if available]
        
        EXPERT_INSIGHTS:
        - Expert 1: [Name/Title] - [Key insight] - [Source]
        - Expert 2: [Name/Title] - [Key insight] - [Source]
        
        CREDIBLE_URLS:
        - [URL 1] - [Description of content]
        - [URL 2] - [Description of content]
        
        CONTEXT_SUMMARY:
        [2-3 sentences providing essential background context for this statement]
        
        Focus on finding specific, verifiable facts and credible sources.
        """
    
    def _extract_context_information(self, response_text: str) -> Dict[str, Any]:
        """Extract structured context information from search response"""
        context = {
            'verification_status': self._extract_section(response_text, 'VERIFICATION_STATUS:', ['KEY_FACTS']),
            'key_facts': self._extract_list_items(response_text, 'KEY_FACTS:', ['SUPPORTING_SOURCES']),
            'supporting_sources': self._extract_list_items(response_text, 'SUPPORTING_SOURCES:', ['CONTRADICTING_SOURCES']),
            'contradicting_sources': self._extract_list_items(response_text, 'CONTRADICTING_SOURCES:', ['EXPERT_INSIGHTS']),
            'expert_insights': self._extract_list_items(response_text, 'EXPERT_INSIGHTS:', ['CREDIBLE_URLS']),
            'context_summary': self._extract_section(response_text, 'CONTEXT_SUMMARY:', [])
        }
        
        return context
    
    def _extract_section(self, text: str, start_marker: str, end_markers: List[str]) -> str:
        """Extract text between markers"""
        start_idx = text.find(start_marker)
        if start_idx == -1:
            return ""
        
        start_idx += len(start_marker)
        
        end_idx = len(text)
        for end_marker in end_markers:
            marker_idx = text.find(end_marker, start_idx)
            if marker_idx != -1 and marker_idx < end_idx:
                end_idx = marker_idx
        
        return text[start_idx:end_idx].strip()
    
    def _extract_list_items(self, text: str, start_marker: str, end_markers: List[str]) -> List[str]:
        """Extract list items from a section"""
        section_text = self._extract_section(text, start_marker, end_markers)
        items = []
        
        for line in section_text.split('\n'):
            line = line.strip()
            if line.startswith('-') and len(line) > 5:
                items.append(line[1:].strip())
        
        return items
    
    def _extract_urls(self, text: str) -> List[str]:
        """Extract URLs from text"""
        url_pattern = r'https?://[^\s\)\]\}]+'
        urls = re.findall(url_pattern, text)
        
        # Filter for credible domains
        credible_urls = []
        for url in urls:
            if self._is_credible_url(url):
                credible_urls.append(url.rstrip('.,;)'))
        
        return list(set(credible_urls))  # Remove duplicates
    
    def _is_credible_url(self, url: str) -> bool:
        """Check if URL is from a credible domain"""
        try:
            domain = urlparse(url).netloc.lower()
            credible_domains = [
                'reuters.com', 'apnews.com', 'bbc.com', 'cnn.com', 'npr.org',
                'factcheck.org', 'politifact.com', 'snopes.com',
                'cdc.gov', 'who.int', 'nih.gov', 'nasa.gov', 'gov',
                'nature.com', 'science.org', 'bmj.com', 'nejm.org'
            ]
            
            return any(credible in domain for credible in credible_domains)
        except:
            return False
    
    async def _fetch_key_content(self, urls: List[str], statement: str) -> List[Dict[str, str]]:
        """Fetch key content from top URLs"""
        content_list = []
        
        for url in urls:
            try:
                logger.info(f"Fetching content from: {url}")
                content = await self._fetch_url_content(url)
                
                if content:
                    # Extract most relevant sentences
                    relevant_text = self._extract_relevant_text(content, statement)
                    
                    if relevant_text:
                        content_list.append({
                            'url': url,
                            'domain': urlparse(url).netloc,
                            'relevant_text': relevant_text
                        })
                
                await asyncio.sleep(1)  # Rate limiting
                
            except Exception as e:
                logger.warning(f"Failed to fetch content from {url}: {e}")
                continue
        
        return content_list
    
    async def _fetch_url_content(self, url: str) -> Optional[str]:
        """Fetch content from URL with basic cleaning"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; FactChecker/1.0)',
                'Accept': 'text/html,application/xhtml+xml',
            }
            
            response = requests.get(url, headers=headers, timeout=8, allow_redirects=True)
            response.raise_for_status()
            
            # Basic HTML cleaning
            content = response.text
            content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
            content = re.sub(r'<[^>]+>', ' ', content)
            content = re.sub(r'\s+', ' ', content).strip()
            
            return content[:5000] if len(content) > 200 else None  # Limit size
            
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return None
    
    def _extract_relevant_text(self, content: str, statement: str) -> str:
        """Extract most relevant sentences from content"""
        # Split into sentences
        sentences = re.split(r'[.!?]+', content)
        
        # Get keywords from statement
        keywords = set(re.findall(r'\b\w{4,}\b', statement.lower()))
        
        # Score sentences by keyword relevance
        relevant_sentences = []
        for sentence in sentences:
            if len(sentence.strip()) < 20:
                continue
            
            sentence_lower = sentence.lower()
            matches = sum(1 for keyword in keywords if keyword in sentence_lower)
            
            # Bonus for numbers and factual indicators
            if re.search(r'\b\d+\.?\d*%?\b', sentence):
                matches += 1
            if any(indicator in sentence_lower for indicator in ['according to', 'study', 'research', 'data']):
                matches += 1
            
            if matches >= 2:  # Minimum relevance threshold
                relevant_sentences.append(sentence.strip())
        
        # Return top 3 most relevant sentences
        return ' '.join(relevant_sentences[:3])
    
    def _create_structured_context(
        self, 
        statement: str, 
        category: str, 
        context_data: Dict[str, Any], 
        web_content: List[Dict[str, str]]
    ) -> str:
        """Create structured context string for database research"""
        
        context_parts = [
            f"STATEMENT: {statement}",
            f"CATEGORY: {category}",
            f"SEARCH_TIMESTAMP: {datetime.now().isoformat()}"
        ]
        
        # Add verification status
        if context_data.get('verification_status'):
            context_parts.append(f"PRELIMINARY_VERIFICATION: {context_data['verification_status']}")
        
        # Add key facts
        key_facts = context_data.get('key_facts', [])
        if key_facts:
            context_parts.append("KEY_FACTS_FOUND:")
            for i, fact in enumerate(key_facts[:3], 1):
                context_parts.append(f"  {i}. {fact}")
        
        # Add supporting evidence
        supporting = context_data.get('supporting_sources', [])
        if supporting:
            context_parts.append("SUPPORTING_EVIDENCE:")
            for i, source in enumerate(supporting[:2], 1):
                context_parts.append(f"  {i}. {source}")
        
        # Add contradicting evidence
        contradicting = context_data.get('contradicting_sources', [])
        if contradicting:
            context_parts.append("CONTRADICTING_EVIDENCE:")
            for i, source in enumerate(contradicting[:2], 1):
                context_parts.append(f"  {i}. {source}")
        
        # Add web content
        if web_content:
            context_parts.append("WEB_CONTENT_EXCERPTS:")
            for i, content in enumerate(web_content, 1):
                context_parts.append(f"  {i}. From {content['domain']}: {content['relevant_text'][:200]}...")
        
        # Add context summary
        if context_data.get('context_summary'):
            context_parts.append(f"BACKGROUND_CONTEXT: {context_data['context_summary']}")
        
        return '\n'.join(context_parts)
    
    def _create_fallback_context(self, statement: str, reason: str) -> Dict[str, Any]:
        """Create fallback context when search fails"""
        fallback_context = f"""
STATEMENT: {statement}
SEARCH_STATUS: Failed - {reason}
SEARCH_TIMESTAMP: {datetime.now().isoformat()}
CONTEXT_AVAILABLE: Limited - using training data only
FALLBACK_NOTE: Web search unavailable, relying on LLM training data for analysis
"""
        
        return {
            'success': False,
            'context_for_db': fallback_context,
            'raw_search_response': f"Search failed: {reason}",
            'urls_found': [],
            'web_content_extracted': 0,
            'search_timestamp': datetime.now().isoformat(),
            'search_method': 'fallback'
        }

# Create core instance
gemini_search_core = GeminiSearchCore()