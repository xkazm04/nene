import logging
from typing import List, Dict, Any, Set
import hashlib
from urllib.parse import urlparse
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

class DuplicateDetector:
    """Detects and removes duplicate content from research results"""
    
    def __init__(self):
        self.similarity_threshold = 0.8  # 80% similarity threshold
        self.url_similarity_threshold = 0.9  # 90% URL similarity threshold
    
    def remove_duplicate_web_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate web search results based on URL and content similarity
        """
        if not results:
            return results
        
        unique_results = []
        seen_urls = set()
        seen_content_hashes = set()
        
        for result in results:
            # Check URL duplicates (normalized)
            url = result.get('url', '')
            normalized_url = self._normalize_url(url)
            
            if normalized_url in seen_urls:
                logger.debug(f"Skipping duplicate URL: {url}")
                continue
            
            # Check content duplicates
            content = result.get('summary', '') + result.get('title', '')
            content_hash = self._generate_content_hash(content)
            
            if content_hash in seen_content_hashes:
                logger.debug(f"Skipping duplicate content from: {url}")
                continue
            
            # Check similarity with existing results
            if self._is_similar_to_existing(result, unique_results):
                logger.debug(f"Skipping similar content from: {url}")
                continue
            
            # Add to unique results
            unique_results.append(result)
            seen_urls.add(normalized_url)
            seen_content_hashes.add(content_hash)
        
        logger.info(f"Filtered {len(results)} results down to {len(unique_results)} unique results")
        return unique_results
    
    def remove_duplicate_resource_sources(self, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate resource sources from Firecrawl analysis
        """
        if not sources:
            return sources
        
        unique_sources = []
        seen_domains = set()
        seen_titles = set()
        
        for source in sources:
            domain = source.get('domain', '')
            title = source.get('title', '').lower().strip()
            url = source.get('url', '')
            
            # Skip if we've seen this domain with very similar content
            domain_key = f"{domain}_{self._generate_content_hash(title)}"
            
            # Check for exact title duplicates
            if title and title in seen_titles:
                logger.debug(f"Skipping duplicate title: {title}")
                continue
            
            # Check for domain + content duplicates
            if domain_key in seen_domains:
                logger.debug(f"Skipping duplicate domain content: {domain}")
                continue
            
            # Check URL similarity (handle URL parameters, etc.)
            if self._is_duplicate_url(url, [s.get('url', '') for s in unique_sources]):
                logger.debug(f"Skipping similar URL: {url}")
                continue
            
            unique_sources.append(source)
            if title:
                seen_titles.add(title)
            if domain:
                seen_domains.add(domain_key)
        
        logger.info(f"Filtered {len(sources)} sources down to {len(unique_sources)} unique sources")
        return unique_sources
    
    def merge_similar_expert_perspectives(self, perspectives: List[Any]) -> List[Any]:
        """
        Merge similar expert perspectives to avoid redundancy
        """
        if not perspectives:
            return perspectives
        
        unique_perspectives = []
        
        for perspective in perspectives:
            reasoning = getattr(perspective, 'reasoning', '')
            stance = getattr(perspective, 'stance', '')
            
            # Check if similar perspective already exists
            is_duplicate = False
            for existing in unique_perspectives:
                existing_reasoning = getattr(existing, 'reasoning', '')
                existing_stance = getattr(existing, 'stance', '')
                
                # Same stance and similar reasoning
                if (stance == existing_stance and 
                    self._calculate_text_similarity(reasoning, existing_reasoning) > self.similarity_threshold):
                    
                    logger.debug(f"Merging similar {stance} perspective")
                    # Keep the one with higher confidence
                    if getattr(perspective, 'confidence_level', 0) > getattr(existing, 'confidence_level', 0):
                        unique_perspectives.remove(existing)
                        unique_perspectives.append(perspective)
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_perspectives.append(perspective)
        
        logger.info(f"Merged {len(perspectives)} perspectives down to {len(unique_perspectives)} unique perspectives")
        return unique_perspectives
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison"""
        try:
            parsed = urlparse(url.lower())
            # Remove common tracking parameters
            normalized = f"{parsed.netloc}{parsed.path}"
            # Remove trailing slashes and common suffixes
            normalized = normalized.rstrip('/').rstrip('.html').rstrip('.htm')
            return normalized
        except:
            return url.lower()
    
    def _generate_content_hash(self, content: str) -> str:
        """Generate hash for content comparison"""
        # Normalize content: lowercase, remove extra whitespace
        normalized = ' '.join(content.lower().split())
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def _is_similar_to_existing(self, new_result: Dict[str, Any], existing_results: List[Dict[str, Any]]) -> bool:
        """Check if new result is similar to any existing result"""
        new_content = new_result.get('summary', '') + ' ' + new_result.get('title', '')
        
        for existing in existing_results:
            existing_content = existing.get('summary', '') + ' ' + existing.get('title', '')
            
            similarity = self._calculate_text_similarity(new_content, existing_content)
            if similarity > self.similarity_threshold:
                return True
        
        return False
    
    def _is_duplicate_url(self, url: str, existing_urls: List[str]) -> bool:
        """Check if URL is duplicate of existing URLs"""
        normalized_url = self._normalize_url(url)
        
        for existing_url in existing_urls:
            normalized_existing = self._normalize_url(existing_url)
            
            # Check exact match
            if normalized_url == normalized_existing:
                return True
            
            # Check high similarity (for URLs with different parameters)
            similarity = self._calculate_text_similarity(normalized_url, normalized_existing)
            if similarity > self.url_similarity_threshold:
                return True
        
        return False
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts"""
        if not text1 or not text2:
            return 0.0
        
        # Use SequenceMatcher for similarity calculation
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def deduplicate_key_findings(self, findings: List[str]) -> List[str]:
        """Remove duplicate or very similar key findings"""
        if not findings:
            return findings
        
        unique_findings = []
        
        for finding in findings:
            is_duplicate = False
            for existing in unique_findings:
                similarity = self._calculate_text_similarity(finding, existing)
                if similarity > 0.7:  # Lower threshold for findings
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_findings.append(finding)
        
        return unique_findings
    
    def remove_content_duplicates_across_sources(
        self, 
        llm_content: List[str], 
        web_content: List[str], 
        resource_content: List[str]
    ) -> Dict[str, List[str]]:
        """
        Remove duplicates across different research sources
        """
        all_content = []
        source_mapping = []
        
        # Collect all content with source mapping
        for content in llm_content:
            all_content.append(content)
            source_mapping.append('llm')
        
        for content in web_content:
            all_content.append(content)
            source_mapping.append('web')
        
        for content in resource_content:
            all_content.append(content)
            source_mapping.append('resource')
        
        # Remove duplicates
        unique_indices = []
        seen_hashes = set()
        
        for i, content in enumerate(all_content):
            content_hash = self._generate_content_hash(content)
            if content_hash not in seen_hashes:
                unique_indices.append(i)
                seen_hashes.add(content_hash)
        
        # Rebuild source-specific lists
        result = {
            'llm': [],
            'web': [],
            'resource': []
        }
        
        for i in unique_indices:
            source = source_mapping[i]
            result[source].append(all_content[i])
        
        return result