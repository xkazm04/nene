import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import json
import hashlib
import asyncio
from time import sleep

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from google.api_core.exceptions import ResourceExhausted, DeadlineExceeded, ServiceUnavailable

from models.research_models import LLMResearchRequest
from utils.duplicate_detector import DuplicateDetector

logger = logging.getLogger(__name__)

class GeminiWebService:
    """Service for performing real-time web research using Gemini's search capabilities"""
    
    def __init__(self):
        self.api_key = os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            logger.warning("Key not found - web search will be unavailable")
            self.model = None
        else:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(
                    'gemini-1.5-pro',
                    tools='google_search_retrieval'
                )
            except Exception as e:
                logger.error(f"Failed to initialize Gemini model: {e}")
                self.model = None
        
        self.duplicate_detector = DuplicateDetector()
        self._cache = {}  # Simple in-memory cache
        self._cache_ttl = 3600  # 1 hour cache TTL
        self.max_retries = 2
        self.base_delay = 5  # Base delay for exponential backoff
    
    async def search_statement(self, statement: str) -> Dict[str, Any]:
        """
        Search for information about a statement using Gemini's web search
        """
        if not self.model:
            return self._create_fallback_response(statement, "Gemini API not available")
        
        try:
            # Check cache first
            cache_key = self._generate_cache_key(statement)
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                logger.info("Returning cached web search result")
                return cached_result
            
            # Generate search queries (reduced number for rate limiting)
            search_queries = self._generate_search_queries(statement)[:3]  # Limit to 3 queries
            
            # Perform searches with rate limiting
            search_results = []
            for i, query in enumerate(search_queries):
                try:
                    # Add delay between requests to avoid rate limiting
                    if i > 0:
                        await asyncio.sleep(2)  # 2 second delay between requests
                    
                    result = await self._perform_single_search_with_retry(query, statement)
                    if result:
                        search_results.extend(result)
                except Exception as e:
                    logger.warning(f"Search query '{query}' failed: {e}")
                    continue
            
            # If no results, return fallback
            if not search_results:
                return self._create_fallback_response(statement, "All search queries failed")
            
            # Remove duplicates and structure response
            unique_results = self.duplicate_detector.remove_duplicate_web_results(search_results)
            
            # Analyze and structure findings
            web_response = self._structure_web_response(statement, unique_results)
            
            # Cache the result
            self._cache_result(cache_key, web_response)
            
            return web_response
            
        except Exception as e:
            logger.error(f"Gemini web search failed: {e}")
            return self._create_fallback_response(statement, f"Search failed: {str(e)}")
    
    async def _perform_single_search_with_retry(self, query: str, original_statement: str) -> List[Dict[str, Any]]:
        """Perform a single search query with retry logic"""
        
        for attempt in range(self.max_retries + 1):
            try:
                return await self._perform_single_search(query, original_statement)
                
            except ResourceExhausted as e:
                # Handle quota exceeded (429)
                retry_delay = getattr(e, 'retry_delay', None)
                if retry_delay and hasattr(retry_delay, 'seconds'):
                    delay = retry_delay.seconds
                else:
                    delay = self.base_delay * (2 ** attempt)  # Exponential backoff
                
                logger.warning(f"Rate limit exceeded for query '{query}'. Attempt {attempt + 1}/{self.max_retries + 1}")
                
                if attempt < self.max_retries:
                    logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(min(delay, 60))  # Cap delay at 60 seconds
                else:
                    logger.error(f"Max retries exceeded for query '{query}'")
                    raise
                    
            except (DeadlineExceeded, ServiceUnavailable) as e:
                delay = self.base_delay * (2 ** attempt)
                logger.warning(f"Service unavailable for query '{query}'. Attempt {attempt + 1}/{self.max_retries + 1}")
                
                if attempt < self.max_retries:
                    logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Max retries exceeded for query '{query}'")
                    raise
                    
            except Exception as e:
                logger.error(f"Unexpected error for query '{query}': {e}")
                raise
        
        return []
    
    def _create_fallback_response(self, statement: str, reason: str) -> Dict[str, Any]:
        """Create a fallback response when web search is unavailable"""
        return {
            'statement': statement,
            'search_timestamp': datetime.now().isoformat(),
            'total_results': 0,
            'supporting_evidence': [],
            'contradicting_evidence': [],
            'neutral_information': [],
            'recency_score': 0,
            'confidence_score': 30,  # Low confidence for fallback
            'source': 'gemini_web_search_fallback',
            'error': reason,
            'fallback': True
        }
    
    async def _perform_single_search(self, query: str, original_statement: str) -> List[Dict[str, Any]]:
        """Perform a single search query using Gemini"""
        try:
            # Create search prompt
            search_prompt = f"""
            Search for information about this query: "{query}"
            
            Focus on finding:
            1. Factual information and evidence
            2. Recent news and developments
            3. Scientific studies or research
            4. Expert opinions and analysis
            5. Contradictory information or debunking
            
            Original statement being researched: "{original_statement}"
            
            Please provide search results with:
            - Source URLs
            - Publication dates
            - Brief summaries
            - Credibility indicators
            """
            
            # Generate response with search
            response = self.model.generate_content(
                search_prompt,
                safety_settings={
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                }
            )
            
            # Parse search results from response
            return self._parse_search_response(response.text, query)
            
        except Exception as e:
            logger.warning(f"Single search failed for query '{query}': {e}")
            return []
    
    def _parse_search_response(self, response_text: str, query: str) -> List[Dict[str, Any]]:
        """Parse Gemini's search response into structured data"""
        try:
            # Extract structured information from the response
            # This is a simplified parser - you might want to enhance this
            results = []
            
            # Look for URLs, dates, and summaries in the response
            lines = response_text.split('\n')
            current_result = {}
            
            for line in lines:
                line = line.strip()
                if not line:
                    if current_result:
                        results.append(current_result)
                        current_result = {}
                    continue
                
                # Extract URLs
                if 'http' in line:
                    current_result['url'] = self._extract_url(line)
                
                # Extract dates
                if any(year in line for year in ['2023', '2024', '2025']):
                    current_result['date'] = self._extract_date(line)
                
                # Store summary
                if len(line) > 50 and 'url' not in line.lower():
                    current_result['summary'] = line
                    current_result['query'] = query
                    current_result['relevance_score'] = self._calculate_relevance(line, query)
            
            # Add final result if exists
            if current_result:
                results.append(current_result)
            
            return results
            
        except Exception as e:
            logger.warning(f"Failed to parse search response: {e}")
            return []
    
    def _extract_url(self, text: str) -> str:
        """Extract URL from text"""
        import re
        url_pattern = r'https?://[^\s]+'
        match = re.search(url_pattern, text)
        return match.group(0) if match else ""
    
    def _extract_date(self, text: str) -> str:
        """Extract date from text"""
        import re
        # Simple date extraction - enhance as needed
        date_pattern = r'\b\d{4}\b'
        match = re.search(date_pattern, text)
        return match.group(0) if match else ""
    
    def _calculate_relevance(self, text: str, query: str) -> float:
        """Calculate relevance score between text and query"""
        query_words = set(query.lower().split())
        text_words = set(text.lower().split())
        
        if not query_words:
            return 0.0
        
        intersection = query_words.intersection(text_words)
        return len(intersection) / len(query_words)
    
    def _structure_web_response(self, statement: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Structure the web search results into a comprehensive response"""
        # Sort by relevance and recency
        sorted_results = sorted(
            results,
            key=lambda x: (x.get('relevance_score', 0), x.get('date', '0')),
            reverse=True
        )
        
        # Categorize results
        supporting_evidence = []
        contradicting_evidence = []
        neutral_information = []
        
        for result in sorted_results[:20]:  # Limit to top 20 results
            summary = result.get('summary', '').lower()
            
            # Simple categorization logic - enhance as needed
            if any(word in summary for word in ['false', 'debunked', 'myth', 'incorrect']):
                contradicting_evidence.append(result)
            elif any(word in summary for word in ['true', 'confirmed', 'proven', 'evidence']):
                supporting_evidence.append(result)
            else:
                neutral_information.append(result)
        
        return {
            'statement': statement,
            'search_timestamp': datetime.now().isoformat(),
            'total_results': len(results),
            'supporting_evidence': supporting_evidence,
            'contradicting_evidence': contradicting_evidence,
            'neutral_information': neutral_information,
            'recency_score': self._calculate_recency_score(sorted_results),
            'confidence_score': min(85 + len(supporting_evidence) * 2, 95),
            'source': 'gemini_web_search'
        }
    
    def _calculate_recency_score(self, results: List[Dict[str, Any]]) -> float:
        """Calculate how recent the information is"""
        current_year = datetime.now().year
        recent_count = 0
        
        for result in results:
            date_str = result.get('date', '')
            if str(current_year) in date_str or str(current_year - 1) in date_str:
                recent_count += 1
        
        return min((recent_count / len(results)) * 100, 100) if results else 0
    
    def _generate_cache_key(self, statement: str) -> str:
        """Generate cache key for statement"""
        return hashlib.md5(statement.encode()).hexdigest()
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached result if still valid"""
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            if datetime.now().timestamp() - timestamp < self._cache_ttl:
                return cached_data
            else:
                del self._cache[cache_key]
        return None
    
    def _cache_result(self, cache_key: str, result: Dict[str, Any]) -> None:
        """Cache search result"""
        self._cache[cache_key] = (result, datetime.now().timestamp())
    
    def _generate_search_queries(self, statement: str) -> List[str]:
        """Generate multiple search queries to comprehensively research the statement"""
        base_queries = [
            f'"{statement}" fact check',
            f'"{statement}" evidence research',
            f'"{statement}" scientific study',
            f'"{statement}" news recent',
            f'"{statement}" debunked myth',
            f'"{statement}" expert opinion'
        ]
        
        # Add date-specific queries for recent information
        current_year = datetime.now().year
        recent_queries = [
            f'"{statement}" {current_year}',
            f'"{statement}" latest research {current_year}',
            f'"{statement}" news {current_year-1} {current_year}'
        ]
        
        return base_queries + recent_queries