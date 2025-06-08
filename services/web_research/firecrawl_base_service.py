import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class FirecrawlBaseService:
    """Base Firecrawl service for generic web search and scraping functionality"""
    
    def __init__(self):
        self.api_key = os.getenv('FIRECRAWL_API_KEY')
        self._service_available = True
        
        if not self.api_key:
            logger.warning("FIRECRAWL_API_KEY not found - Firecrawl services will be unavailable")
            self._service_available = False
            self.app = None
        else:
            try:
                from firecrawl import FirecrawlApp
                self.app = FirecrawlApp(api_key=self.api_key)
                logger.info("Firecrawl SDK initialized successfully")
            except ImportError:
                logger.error("Firecrawl SDK not installed. Install with: pip install firecrawl-py")
                self._service_available = False
                self.app = None
            except Exception as e:
                logger.error(f"Failed to initialize Firecrawl SDK: {e}")
                self._service_available = False
                self.app = None
    
    def is_available(self) -> bool:
        """Check if Firecrawl service is available"""
        return self._service_available and self.app is not None
    
    async def search(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """
        Generic search method using Firecrawl
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            Search results with success status
        """
        if not self.is_available():
            return {
                'success': False,
                'error': 'Firecrawl service not available',
                'results': []
            }
        
        try:
            logger.info(f"Performing Firecrawl search: {query[:100]}...")
            
            # Use Firecrawl's search functionality
            search_result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.app.search(query, limit=limit)
            )
            
            # Process search results
            if self._check_search_success(search_result):
                results = self._extract_search_results(search_result)
                
                return {
                    'success': True,
                    'results': results,
                    'search_method': 'firecrawl_search',
                    'query': query,
                    'timestamp': datetime.now().isoformat()
                }
            else:
                error_msg = self._extract_search_error(search_result)
                logger.warning(f"Firecrawl search failed: {error_msg}")
                
                return {
                    'success': False,
                    'error': error_msg,
                    'results': [],
                    'query': query,
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Firecrawl search error: {error_msg}")
            
            return {
                'success': False,
                'error': error_msg,
                'results': [],
                'query': query,
                'timestamp': datetime.now().isoformat()
            }
    
    async def scrape_url(self, url: str, formats: List[str] = None) -> Dict[str, Any]:
        """
        Generic URL scraping method
        
        Args:
            url: URL to scrape
            formats: List of formats to extract (e.g., ['markdown', 'html'])
            
        Returns:
            Scraped content with success status
        """
        if not self.is_available():
            return {
                'success': False,
                'error': 'Firecrawl service not available',
                'content': None
            }
        
        if formats is None:
            formats = ['markdown']
        
        try:
            logger.info(f"Scraping URL: {url}")
            
            scrape_result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.app.scrape_url(url, formats=formats)
            )
            
            if self._check_scrape_success(scrape_result):
                content = self._extract_content_from_scrape_response(scrape_result)
                
                return {
                    'success': True,
                    'content': content,
                    'url': url,
                    'formats': formats,
                    'timestamp': datetime.now().isoformat()
                }
            else:
                error_msg = self._extract_scrape_error(scrape_result)
                logger.warning(f"URL scraping failed: {error_msg}")
                
                return {
                    'success': False,
                    'error': error_msg,
                    'content': None,
                    'url': url
                }
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"URL scraping error: {error_msg}")
            
            return {
                'success': False,
                'error': error_msg,
                'content': None,
                'url': url
            }
    
    def _check_search_success(self, search_result) -> bool:
        """Check if Firecrawl search was successful"""
        try:
            if not search_result:
                return False
            
            # Check success attribute
            if hasattr(search_result, 'success'):
                return bool(search_result.success)
            
            # Check if we have data
            if hasattr(search_result, 'data') and search_result.data:
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Failed to check search success: {e}")
            return False
    
    def _check_scrape_success(self, scrape_result) -> bool:
        """Check if Firecrawl scrape was successful"""
        try:
            if not scrape_result:
                return False
            
            # Check success attribute
            if hasattr(scrape_result, 'success'):
                return bool(scrape_result.success)
            
            # Check if we have data
            if hasattr(scrape_result, 'data') and scrape_result.data:
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Failed to check scrape success: {e}")
            return False
    
    def _extract_search_results(self, search_result) -> List[Dict[str, Any]]:
        """Extract and process search results from Firecrawl response"""
        try:
            results = []
            
            if hasattr(search_result, 'data') and search_result.data:
                for item in search_result.data[:10]:  # Limit to 10 items
                    result_item = {
                        'url': getattr(item, 'url', '') or getattr(item, 'sourceURL', ''),
                        'title': getattr(item, 'title', ''),
                        'description': getattr(item, 'description', ''),
                        'markdown': getattr(item, 'markdown', ''),
                        'domain': self._extract_domain(getattr(item, 'url', '') or getattr(item, 'sourceURL', '')),
                        'summary': (getattr(item, 'description', '') or getattr(item, 'markdown', ''))[:300]
                    }
                    results.append(result_item)
            
            return results
            
        except Exception as e:
            logger.warning(f"Failed to extract search results: {e}")
            return []
    
    def _extract_content_from_scrape_response(self, scrape_result) -> Optional[str]:
        """Extract content from scrape response"""
        try:
            if hasattr(scrape_result, 'data') and scrape_result.data:
                # Try to get markdown content first
                if hasattr(scrape_result.data, 'markdown'):
                    return scrape_result.data.markdown
                # Fallback to description
                elif hasattr(scrape_result.data, 'description'):
                    return scrape_result.data.description
                # Fallback to any text content
                elif hasattr(scrape_result.data, 'content'):
                    return scrape_result.data.content
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to extract scrape content: {e}")
            return None
    
    def _extract_search_error(self, search_result) -> str:
        """Extract error message from Firecrawl search response"""
        try:
            if hasattr(search_result, 'error'):
                return str(search_result.error)
            elif hasattr(search_result, 'message'):
                return str(search_result.message)
            else:
                return "Unknown search error"
        except:
            return "Failed to extract error message"
    
    def _extract_scrape_error(self, scrape_result) -> str:
        """Extract error message from Firecrawl scrape response"""
        try:
            if hasattr(scrape_result, 'error'):
                return str(scrape_result.error)
            elif hasattr(scrape_result, 'message'):
                return str(scrape_result.message)
            else:
                return "Unknown scrape error"
        except:
            return "Failed to extract error message"
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc
        except:
            return ""

# Create base service instance
firecrawl_base_service = FirecrawlBaseService()