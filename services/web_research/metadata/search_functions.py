import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class WikipediaSearchService:
    """Service for searching and scraping Wikipedia content"""
    
    def __init__(self, base_service):
        self.base_service = base_service
    
    async def find_wikipedia_url(self, name: str, category: str, subcategory: str) -> Optional[str]:
        """Find the best Wikipedia URL for an item"""
        try:
            # Create Wikipedia-specific search query
            wikipedia_query = f'site:wikipedia.org "{name}" {subcategory}'
            
            # Search for Wikipedia page
            search_result = await self.base_service.search(wikipedia_query, limit=5)
            
            if not search_result.get('success', False):
                logger.warning(f"Wikipedia search failed: {search_result.get('error', 'Unknown error')}")
                return None
            
            # Find the best Wikipedia URL from results
            return self._find_best_wikipedia_url(search_result['results'], name)
            
        except Exception as e:
            logger.error(f"Wikipedia URL search failed for {name}: {e}")
            return None
    
    async def scrape_wikipedia_content(self, url: str) -> Optional[str]:
        """Scrape Wikipedia page content with both HTML and markdown"""
        try:
            scrape_result = await self.base_service.scrape_url(
                url, 
                formats=['html', 'markdown']
            )
            
            if scrape_result.get('success', False):
                return scrape_result.get('content', '')
            else:
                logger.warning(f"Failed to scrape {url}: {scrape_result.get('error', 'Unknown error')}")
                return None
                
        except Exception as e:
            logger.error(f"Wikipedia scraping failed for {url}: {e}")
            return None
    
    def _find_best_wikipedia_url(self, results: List[Dict[str, Any]], name: str) -> Optional[str]:
        """Find the best Wikipedia URL from search results"""
        wikipedia_urls = []
        name_lower = name.lower()
        
        for result in results:
            url = result.get('url', '')
            title = result.get('title', '').lower()
            
            if 'wikipedia.org' in url and '/wiki/' in url:
                # Score based on title similarity and URL quality
                score = 0
                
                # Title similarity
                if name_lower in title:
                    score += 10
                if name_lower in url.lower():
                    score += 8
                
                # Prefer main articles over disambiguation pages
                if 'disambiguation' not in title and 'disambiguation' not in url:
                    score += 5
                
                # Prefer English Wikipedia
                if url.startswith('https://en.wikipedia.org'):
                    score += 3
                
                wikipedia_urls.append((url, score))
        
        # Return the highest scoring URL
        if wikipedia_urls:
            wikipedia_urls.sort(key=lambda x: x[1], reverse=True)
            return wikipedia_urls[0][0]
        
        return None