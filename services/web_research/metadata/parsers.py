import logging
from typing import Dict, Any
from bs4 import BeautifulSoup

from .extractors import MetadataExtractorService
from .infobox_config import INFOBOX_CLASSES

logger = logging.getLogger(__name__)

class WikipediaParserService:
    """Service for parsing Wikipedia content and extracting metadata"""
    
    def __init__(self):
        self.extractor = MetadataExtractorService()
        self.infobox_classes = INFOBOX_CLASSES
    
    async def parse_wikipedia_content(
        self, 
        content: str, 
        url: str, 
        category: str, 
        subcategory: str
    ) -> Dict[str, Any]:
        """Parse Wikipedia content with focus on infobox data"""
        metadata = {}
        
        try:
            # First attempt: Parse HTML content for infobox if available
            if '<table' in content and 'infobox' in content.lower():
                logger.info("Attempting HTML infobox parsing")
                html_metadata = await self._parse_html_infobox(content, category, subcategory)
                if html_metadata:
                    metadata.update(html_metadata)
                    metadata['_parsing_method'] = 'html_infobox'
            
            # Second attempt: Enhanced markdown parsing if HTML failed or unavailable
            if not metadata or len(metadata) <= 1:  # Only _parsing_method
                logger.info("Falling back to enhanced markdown parsing")
                markdown_metadata = self._parse_enhanced_markdown(content, category, subcategory)
                metadata.update(markdown_metadata)
                if not metadata.get('_parsing_method'):
                    metadata['_parsing_method'] = 'enhanced_markdown'
            
            # Always try to extract image URL
            image_url = self.extractor.extract_wikipedia_image(content, url)
            if image_url:
                metadata['image_url'] = image_url
            
            logger.info(f"Extracted metadata: {list(metadata.keys())} using {metadata.get('_parsing_method')}")
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to parse Wikipedia content: {e}")
            return {'_parsing_method': 'failed', 'error': str(e)}
    
    async def _parse_html_infobox(self, content: str, category: str, subcategory: str) -> Dict[str, Any]:
        """Parse HTML content to extract infobox data"""
        metadata = {}
        
        try:
            # Extract HTML portion if content contains both markdown and HTML
            html_content = self._extract_html_from_content(content)
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find infobox table
            infobox = self._find_infobox(soup, category)
            
            if not infobox:
                logger.warning("No infobox found in HTML content")
                return {}
            
            logger.info(f"Found infobox with class: {infobox.get('class', [])}")
            
            # Parse infobox based on category
            if category == 'games':
                metadata = self.extractor.extract_game_metadata(infobox)
            elif category == 'sports':
                metadata = self.extractor.extract_sports_metadata(infobox)
            elif category == 'music':
                metadata = self.extractor.extract_music_metadata(infobox)
            
            return metadata
            
        except Exception as e:
            logger.warning(f"HTML infobox parsing failed: {e}")
            return {}
    
    def _parse_enhanced_markdown(self, content: str, category: str, subcategory: str) -> Dict[str, Any]:
        """Enhanced markdown parsing with better pattern recognition"""
        metadata = {}
        
        if category == 'games' and subcategory == 'video_games':
            metadata.update(self.extractor.extract_game_metadata_from_markdown(content))
        elif category == 'sports':
            metadata.update(self.extractor.extract_sports_metadata_from_markdown(content))
        elif category == 'music':
            metadata.update(self.extractor.extract_music_metadata_from_markdown(content))
        
        return metadata
    
    def _extract_html_from_content(self, content: str) -> str:
        """Extract HTML portion from mixed content"""
        if '```html' in content:
            # Extract HTML block from markdown
            html_start = content.find('```html')
            if html_start != -1:
                html_start = content.find('\n', html_start) + 1
                html_end = content.find('```', html_start)
                if html_end != -1:
                    return content[html_start:html_end]
        return content
    
    def _find_infobox(self, soup: BeautifulSoup, category: str):
        """Find the infobox table element based on category"""
        possible_classes = self.infobox_classes.get(category, [])
        
        # Try to find by specific infobox classes
        for class_name in possible_classes:
            # Try exact class match
            infobox = soup.find('table', class_=class_name)
            if infobox:
                return infobox
            
            # Try partial class match
            infobox = soup.find('table', class_=lambda x: x and class_name in ' '.join(x))
            if infobox:
                return infobox
        
        # Fallback: any table with "infobox" in class
        infobox = soup.find('table', class_=lambda x: x and 'infobox' in ' '.join(x))
        if infobox:
            return infobox
        
        # Last resort: look for table with infobox in any attribute
        tables = soup.find_all('table')
        for table in tables:
            if 'infobox' in str(table.get('class', [])).lower():
                return table
        
        return None