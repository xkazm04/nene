import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from models.research_models import LLMResearchRequest, LLMResearchResponse
from services.web_research.gemini_web_service import GeminiWebService
from services.web_research.firecrawl_service import FirecrawlService
from utils.research_synthesizer import ResearchSynthesizer
from utils.duplicate_detector import DuplicateDetector

logger = logging.getLogger(__name__)

class ResearchOrchestrator:
    """Orchestrates tri-factor research: LLM + Web Search + Resource Analysis"""
    
    def __init__(self):
        self.gemini_web_service = GeminiWebService()
        self.firecrawl_service = FirecrawlService()
        self.synthesizer = ResearchSynthesizer()
        self.duplicate_detector = DuplicateDetector()
    
    async def perform_tri_factor_research(
        self,
        request: LLMResearchRequest,
        llm_response: LLMResearchResponse
    ) -> LLMResearchResponse:
        """
        Performs comprehensive research using three factors
        """
        try:
            logger.info(f"Starting tri-factor research for statement: {request.statement[:100]}...")
            
            # Prepare concurrent tasks
            tasks = []
            
            # Task 1: Web search (mandatory)
            # web_task = asyncio.create_task(
            #     self._perform_web_search(request),
            #     name="web_search"
            # )
            # tasks.append(web_task)
            
            # Task 2: Resource analysis using Firecrawl Search (optional, with timeout)
            resource_task = asyncio.create_task(
                self._perform_resource_analysis(request),
                name="resource_analysis"
            )
            tasks.append(resource_task)
            
            # Execute tasks with timeouts
            web_result, resource_result = await asyncio.gather(
                *tasks, return_exceptions=True
            )
            
            # Process results
            web_response = web_result if not isinstance(web_result, Exception) else None
            resource_analysis = resource_result if not isinstance(resource_result, Exception) else None
            
            # Log any exceptions
            if isinstance(web_result, Exception):
                logger.error(f"Web search failed: {web_result}")
            if isinstance(resource_result, Exception):
                logger.warning(f"Resource analysis failed: {resource_result}")
            
            # Synthesize all research results
            enhanced_response = await self.synthesizer.synthesize_research(
                llm_response=llm_response,
                web_response=web_response,
                resource_analysis=resource_analysis,
                original_request=request
            )
            
            logger.info("Tri-factor research completed successfully")
            return enhanced_response
            
        except Exception as e:
            logger.error(f"Tri-factor research failed: {e}")
            # Return original LLM response as fallback
            return llm_response
    
    async def _perform_web_search(self, request: LLMResearchRequest) -> Optional[Dict[str, Any]]:
        """Perform web search using Gemini"""
        try:
            logger.info("Starting Gemini web search...")
            
            # Create web search with timeout
            web_response = await asyncio.wait_for(
                self.gemini_web_service.search_statement(request.statement),
                timeout=30.0  # 30 second timeout
            )
            
            logger.info("Gemini web search completed successfully")
            return web_response
            
        except asyncio.TimeoutError:
            logger.warning("Web search timed out")
            return None
        except Exception as e:
            logger.error(f"Web search error: {e}")
            raise
    
    async def _perform_resource_analysis(self, request: LLMResearchRequest) -> Optional[Dict[str, Any]]:
        """Perform resource analysis using Firecrawl Search"""
        try:
            logger.info("Starting Firecrawl search resource analysis...")
            
            # Create resource analysis with timeout
            resource_response = await asyncio.wait_for(
                self.firecrawl_service.analyze_statement_resources(request.statement),
                timeout=60.0  # 60 second timeout for search operations
            )
            
            logger.info("Firecrawl search resource analysis completed successfully")
            return resource_response
            
        except asyncio.TimeoutError:
            logger.warning("Resource analysis timed out")
            return None
        except Exception as e:
            logger.error(f"Resource analysis error: {e}")
            raise