import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio

from services.web_research.firecrawl_base_service import firecrawl_base_service

logger = logging.getLogger(__name__)

class FirecrawlService:
    """Service for analyzing resource quantity and quality using Firecrawl Search SDK"""
    
    def __init__(self):
        self.base_service = firecrawl_base_service
        self._service_available = self.base_service.is_available()
        self.app = self.base_service.app if self._service_available else None
    
    async def analyze_statement_resources(self, statement: str) -> Dict[str, Any]:
        """
        Analyze resources using Firecrawl Search with fast-fail strategy
        """
        try:
            if not self._service_available:
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
            search_result = await self.base_service.search(query, limit=10)
            
            if search_result.get('success', False):
                # Process results for fact-checking analysis
                results = self._process_results_for_fact_checking(search_result['results'], strategy)
                
                return {
                    'strategy': strategy,
                    'results': results,
                    'success': True,
                    'search_method': 'firecrawl_search'
                }
            else:
                error_msg = search_result.get('error', 'Unknown error')
                logger.warning(f"Firecrawl search failed for strategy {strategy['type']}: {error_msg}")
                
                # Check for server errors
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
    
    def _process_results_for_fact_checking(self, results: List[Dict[str, Any]], strategy: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process search results specifically for fact-checking analysis"""
        processed_results = []
        
        for result in results:
            processed_result = {
                'url': result.get('url', ''),
                'title': result.get('title', ''),
                'summary': result.get('summary', ''),
                'domain': result.get('domain', ''),
                'strategy_type': strategy['type'],
                'relevance_score': self._calculate_relevance(
                    result.get('title', '') + ' ' + result.get('description', ''),
                    strategy['query']
                )
            }
            processed_results.append(processed_result)
        
        return processed_results
    
    def _create_search_strategies(self, statement: str) -> List[Dict[str, Any]]:
        """Create search strategies optimized for fact-checking"""
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
            parsed = urlparse(url)
            return parsed.netloc
        except:
            return ""
    
    def _calculate_relevance(self, text: str, query: str) -> float:
        """Calculate relevance score between text and query"""
        if not text or not query:
            return 0.0
        
        text_lower = text.lower()
        query_lower = query.lower()
        
        # Simple keyword matching
        query_words = query_lower.split()
        matches = sum(1 for word in query_words if word in text_lower)
        
        return min(matches / len(query_words), 1.0) if query_words else 0.0
    
    def _calculate_resource_quality(self, url: str, title: str, summary: str, domain: str) -> int:
        """Calculate quality score for a resource (0-100)"""
        score = 50  # Base score
        
        # Domain reputation
        if any(trusted in domain.lower() for trusted in ['edu', 'gov', 'org']):
            score += 20
        elif any(reputable in domain.lower() for reputable in ['bbc', 'reuters', 'nature', 'science']):
            score += 15
        
        # Content quality indicators
        if len(title) > 10:
            score += 10
        if len(summary) > 100:
            score += 15
        
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