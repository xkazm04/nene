import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class FirecrawlService:
    """Service for analyzing resource quantity and quality using Firecrawl Search SDK"""
    
    def __init__(self):
        self.api_key = os.getenv('FIRECRAWL_API_KEY')
        self._service_available = True
        
        if not self.api_key:
            logger.warning("FIRECRAWL_API_KEY not found - resource analysis will be unavailable")
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
    
    async def analyze_statement_resources(self, statement: str) -> Dict[str, Any]:
        """
        Analyze resources using Firecrawl Search with fast-fail strategy
        """
        try:
            if not self._service_available or not self.app:
                return self._create_fallback_analysis(statement, "Firecrawl SDK not available")
            
            logger.info(f"Starting Firecrawl search analysis for: {statement[:100]}...")
            
            # Generate search strategies
            search_strategies = self._create_search_strategies(statement)
            
            # Perform searches with fast-fail strategy
            search_results = []
            successful_searches = 0
            server_error_encountered = False
            
            for i, strategy in enumerate(search_strategies):
                # Skip remaining strategies if server error encountered
                if server_error_encountered:
                    logger.warning("Skipping remaining strategies due to server error")
                    break
                
                try:
                    # Add delay between requests to avoid rate limiting
                    if i > 0:
                        await asyncio.sleep(2)
                    
                    result = await self._perform_firecrawl_search(strategy)
                    logger.info(f"Search strategy '{strategy['type']}' completed with {len(result.get('results', []))} results")
                    search_results.append(result)
                    
                    if result.get('success', False):
                        successful_searches += 1
                    elif result.get('server_error', False):
                        server_error_encountered = True
                        logger.warning("Server error encountered - stopping further searches")
                        break
                        
                except Exception as e:
                    logger.warning(f"Search strategy '{strategy['type']}' failed: {e}")
                    # Check if it's a server error
                    if any(indicator in str(e).lower() for indicator in ['server', '500', 'undefined']):
                        server_error_encountered = True
                        logger.warning("Server error detected - stopping further attempts")
                        break
                    
                    search_results.append({
                        'strategy': strategy,
                        'results': [],
                        'success': False,
                        'error': str(e)
                    })
            
            # If server error encountered, return quick fallback
            if server_error_encountered:
                return self._create_fallback_analysis(
                    statement, 
                    "Firecrawl service temporarily unavailable (server error)"
                )
            
            # If no successful searches, return fallback
            if successful_searches == 0:
                return self._create_fallback_analysis(statement, "All search strategies failed")
            
            # Analyze results
            analysis = self._analyze_search_results(statement, search_results, search_strategies)
            analysis['successful_searches'] = successful_searches
            analysis['total_searches'] = len(search_strategies)
            analysis['server_error_encountered'] = server_error_encountered
            
            logger.info(f"Firecrawl analysis completed: {successful_searches}/{len(search_strategies)} strategies successful")
            return analysis
            
        except Exception as e:
            logger.error(f"Resource analysis failed: {e}")
            return self._create_fallback_analysis(statement, f"Analysis failed: {str(e)}")
    
    async def _perform_firecrawl_search(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform search using Firecrawl Search API
        """
        try:
            logger.info(f"Performing Firecrawl search for strategy: {strategy['type']}")
            
            query = strategy['query']
            
            # Use Firecrawl's search functionality
            search_result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.app.search(query, limit=10)
            )
            
            # Process search results
            if self._check_search_success(search_result):
                results = self._extract_search_results(search_result, strategy)
                
                return {
                    'strategy': strategy,
                    'results': results,
                    'success': True,
                    'search_method': 'firecrawl_search'
                }
            else:
                error_msg = self._extract_search_error(search_result)
                server_error = any(indicator in error_msg.lower() for indicator in [
                    'server', '500', 'undefined', 'internal error'
                ])
                
                return {
                    'strategy': strategy,
                    'results': [],
                    'success': False,
                    'error': error_msg,
                    'server_error': server_error
                }
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Firecrawl search error for strategy {strategy['type']}: {error_msg}")
            
            server_error = any(indicator in error_msg.lower() for indicator in [
                'server', '500', 'undefined', 'internal error', 'timeout', 'connection'
            ])
            
            return {
                'strategy': strategy,
                'results': [],
                'success': False,
                'error': error_msg,
                'server_error': server_error
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
    
    def _extract_search_results(self, search_result, strategy: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract and process search results from Firecrawl response"""
        try:
            results = []
            
            if hasattr(search_result, 'data') and search_result.data:
                for item in search_result.data[:10]:  # Limit to 10 items
                    result_item = {
                        'url': getattr(item, 'url', '') or getattr(item, 'sourceURL', ''),
                        'title': getattr(item, 'title', ''),
                        'summary': (getattr(item, 'description', '') or getattr(item, 'markdown', ''))[:300],
                        'domain': self._extract_domain(getattr(item, 'url', '') or getattr(item, 'sourceURL', '')),
                        'strategy_type': strategy['type'],
                        'relevance_score': self._calculate_relevance(
                            getattr(item, 'title', '') + ' ' + getattr(item, 'description', ''),
                            strategy['query']
                        )
                    }
                    results.append(result_item)
            
            return results
            
        except Exception as e:
            logger.warning(f"Failed to extract search results: {e}")
            return []
    
    def _extract_search_error(self, search_result) -> str:
        """Extract error message from Firecrawl search response"""
        try:
            if not search_result:
                return 'No response from Firecrawl'
            
            if hasattr(search_result, 'error') and search_result.error:
                return str(search_result.error)
            
            if hasattr(search_result, 'success') and not search_result.success:
                return 'Search was not successful (no error details provided)'
            
            return 'Unknown error occurred'
            
        except Exception as e:
            logger.warning(f"Failed to extract error from search result: {e}")
            return f'Error extraction failed: {str(e)}'
    
    def _create_search_strategies(self, statement: str) -> List[Dict[str, Any]]:
        """Create search strategies optimized for Firecrawl Search"""
        return [
            {
                'type': 'supporting',
                'query': f'"{statement}" evidence proof research study verified',
                'expected_sentiment': 'positive'
            },
            {
                'type': 'contradicting',
                'query': f'"{statement}" false debunked incorrect myth disproven',
                'expected_sentiment': 'negative'
            },
            {
                'type': 'academic',
                'query': f'"{statement}" scientific journal academic paper peer reviewed',
                'expected_sentiment': 'authoritative'
            }
        ]
    
    def _analyze_search_results(
        self, 
        statement: str, 
        search_results: List[Dict[str, Any]], 
        strategies: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze search results to determine resource quantity and quality"""
        
        analysis = {
            'statement': statement,
            'analysis_timestamp': datetime.now().isoformat(),
            'total_resources_found': 0,
            'supporting_resources': 0,
            'contradicting_resources': 0,
            'academic_resources': 0,
            'resource_quality_score': 0,
            'source_diversity': 0,
            'confidence_score': 0,
            'detailed_breakdown': {},
            'top_sources': [],
            'source': 'firecrawl_search_analysis'
        }
        
        all_sources = []
        strategy_results = {}
        
        # Process each search result
        for i, result in enumerate(search_results):
            if not result.get('success', False):
                continue
            
            strategy = strategies[i] if i < len(strategies) else {'type': 'unknown'}
            strategy_type = strategy['type']
            resources = result.get('results', [])
            
            strategy_results[strategy_type] = len(resources)
            
            # Analyze each resource
            for resource in resources:
                resource_analysis = self._analyze_single_resource(resource, strategy)
                all_sources.append(resource_analysis)
                
                # Count by type
                if strategy_type == 'supporting':
                    analysis['supporting_resources'] += 1
                elif strategy_type == 'contradicting':
                    analysis['contradicting_resources'] += 1
                elif strategy_type == 'academic':
                    analysis['academic_resources'] += 1
        
        # Calculate totals and scores
        analysis['total_resources_found'] = len(all_sources)
        analysis['detailed_breakdown'] = strategy_results
        
        if all_sources:
            # Calculate quality score
            quality_scores = [s.get('quality_score', 0) for s in all_sources]
            analysis['resource_quality_score'] = sum(quality_scores) / len(quality_scores)
            
            # Calculate source diversity
            unique_domains = set(s.get('domain', '') for s in all_sources if s.get('domain'))
            analysis['source_diversity'] = min(len(unique_domains) / len(all_sources) * 100, 100) if all_sources else 0
            
            # Calculate confidence based on quantity and quality
            quantity_factor = min(len(all_sources) / 15, 1)  # Normalize to 15 sources
            quality_factor = analysis['resource_quality_score'] / 100
            diversity_factor = analysis['source_diversity'] / 100
            
            analysis['confidence_score'] = int((quantity_factor * 0.5 + quality_factor * 0.3 + diversity_factor * 0.2) * 100)
            
            # Get top sources
            sorted_sources = sorted(all_sources, key=lambda x: x.get('quality_score', 0), reverse=True)
            analysis['top_sources'] = sorted_sources[:5]  # Top 5 sources
        
        return analysis
    
    def _analyze_single_resource(self, resource: Dict[str, Any], strategy: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a single resource for quality and relevance"""
        url = resource.get('url', '')
        title = resource.get('title', '')
        summary = resource.get('summary', '')
        domain = resource.get('domain', '')
        
        # Calculate quality score
        quality_score = self._calculate_resource_quality(url, title, summary, domain)
        
        return {
            'url': url,
            'title': title,
            'domain': domain,
            'summary_length': len(summary),
            'quality_score': quality_score,
            'strategy_type': strategy['type'],
            'relevance_score': resource.get('relevance_score', 0)
        }
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc if url else 'unknown'
        except:
            return 'unknown'
    
    def _calculate_relevance(self, text: str, query: str) -> float:
        """Calculate relevance score between text and query"""
        if not text or not query:
            return 0.0
        
        query_words = set(query.lower().replace('"', '').split())
        text_words = set(text.lower().split())
        
        if not query_words:
            return 0.0
        
        intersection = query_words.intersection(text_words)
        return min(len(intersection) / len(query_words), 1.0)
    
    def _calculate_resource_quality(self, url: str, title: str, summary: str, domain: str) -> int:
        """Calculate quality score for a resource (0-100)"""
        score = 50  # Base score for Firecrawl search results
        
        # Domain authority indicators
        authoritative_domains = [
            'edu', 'gov', 'org', 'wikipedia', 'britannica',
            'reuters.com', 'bbc.com', 'npr.org', 'cnn.com', 'nature.com',
            'science.org', 'pubmed.ncbi.nlm.nih.gov'
        ]
        
        if any(auth_domain in domain for auth_domain in authoritative_domains):
            score += 25
        
        # Content quality indicators
        if len(summary) > 100:
            score += 10
        
        if any(indicator in summary.lower() for indicator in ['study', 'research', 'analysis', 'peer reviewed']):
            score += 10
        
        # Title quality
        if len(title) > 20 and title:
            score += 5
        
        return min(score, 100)
    
    def _create_fallback_analysis(self, statement: str, reason: str) -> Dict[str, Any]:
        """Create fallback analysis when Firecrawl is unavailable"""
        return {
            'statement': statement,
            'analysis_timestamp': datetime.now().isoformat(),
            'total_resources_found': 0,
            'supporting_resources': 0,
            'contradicting_resources': 0,
            'academic_resources': 0,
            'resource_quality_score': 0,
            'source_diversity': 0,
            'confidence_score': 20,  # Low confidence for fallback
            'detailed_breakdown': {},
            'top_sources': [],
            'source': 'firecrawl_search_fallback',
            'error': reason,
            'fallback': True,
            'successful_searches': 0,
            'total_searches': 0,
            'server_error_encountered': False
        }