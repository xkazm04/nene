import logging
from typing import Optional, Dict, Any

from services.web_research.firecrawl_base_service import firecrawl_base_service
from services.web_research.metadata.search_functions import WikipediaSearchService
from services.web_research.metadata.parsers import WikipediaParserService
from services.web_research.metadata.extractors import MetadataExtractorService
from services.web_research.metadata.normalizers import DataNormalizerService
from services.web_research.metadata.cleaners import DataCleanerService

logger = logging.getLogger(__name__)

class FirecrawlMetadataService:
    """Service for metadata research using Firecrawl Search SDK with Wikipedia infobox parsing"""
    
    def __init__(self):
        self.base_service = firecrawl_base_service
        self._service_available = self.base_service.is_available()
        
        # Initialize specialized services
        self.search_service = WikipediaSearchService(self.base_service)
        self.parser_service = WikipediaParserService()
        self.extractor_service = MetadataExtractorService()
        self.normalizer_service = DataNormalizerService()
        self.cleaner_service = DataCleanerService()
    
    async def search_wikipedia_metadata(self, name: str, category: str, subcategory: str) -> Dict[str, Any]:
        """
        Search Wikipedia for item metadata with enhanced infobox parsing
        
        Args:
            name: Item name to search for
            category: Item category (games, sports, music)
            subcategory: Item subcategory
            
        Returns:
            Dictionary with metadata and Wikipedia URL
        """
        if not self._service_available:
            return {
                'success': False,
                'error': 'Firecrawl not available',
                'metadata': {},
                'reference_url': None
            }
        
        try:
            logger.info(f"Searching Wikipedia for: {name}")
            
            # Step 1: Search and find Wikipedia URL
            wikipedia_url = await self.search_service.find_wikipedia_url(name, category, subcategory)
            
            if not wikipedia_url:
                return {
                    'success': False,
                    'error': 'No relevant Wikipedia page found',
                    'metadata': {},
                    'reference_url': None
                }
            
            # Step 2: Scrape Wikipedia content
            content = await self.search_service.scrape_wikipedia_content(wikipedia_url)
            
            if not content:
                return {
                    'success': False,
                    'error': 'Failed to scrape Wikipedia page',
                    'metadata': {},
                    'reference_url': wikipedia_url
                }
            
            # Step 3: Parse metadata from content
            metadata = await self.parser_service.parse_wikipedia_content(
                content, wikipedia_url, category, subcategory
            )
            
            # Step 4: Clean and validate metadata
            cleaned_metadata = self.cleaner_service.clean_metadata(metadata, category, subcategory)
            
            return {
                'success': True,
                'metadata': cleaned_metadata,
                'reference_url': wikipedia_url,
                'content_length': len(content),
                'parsing_method': cleaned_metadata.get('_parsing_method', 'unknown')
            }
            
        except Exception as e:
            logger.error(f"Wikipedia metadata search failed for {name}: {e}")
            return {
                'success': False,
                'error': str(e),
                'metadata': {},
                'reference_url': None
            }

# Create metadata service instance
firecrawl_metadata_service = FirecrawlMetadataService()