import logging
import asyncio
import traceback
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
from supabase import create_client, Client
from models.research_models import LLMResearchResponse, LLMResearchRequest, ResearchMetadata
from services.llm_clients.groq_client import GroqLLMClient
from services.llm_clients.gemini_client import GeminiClient
from utils.response_parser import ResponseParser
from prompts.fc_prompt import prompt_manager
from schemas.research import ResearchRequest 
from services.llm_research.db_ops import DatabaseOperations

load_dotenv()
logger = logging.getLogger(__name__)

class DatabaseResearchService:
    """
    Unified database research service that combines:
    1. Database operations (save/retrieve research results)
    2. Enhanced LLM research with web context
    3. Grounding source analysis
    4. Expert perspectives generation
    """
    
    def __init__(self):
        # Initialize Supabase client
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment variables")
        
        try:
            self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
            logger.info("Supabase client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {str(e)}")
            raise
        
        # Initialize database operations with Supabase client
        self.db_ops = DatabaseOperations(self.supabase)
        
        # Initialize LLM clients for enhanced research
        self.groq_client = GroqLLMClient()
        self.gemini_client = GeminiClient()
        self.parser = ResponseParser()
        
        logger.info("Unified database research service initialized with LLM capabilities")
    
    # ===== MAIN RESEARCH METHODS =====

    async def research_statement(self, request: ResearchRequest) -> LLMResearchResponse:
        """
        Perform enhanced LLM research on a statement with fallback and database deduplication.
        Returns existing research if duplicate is found.
        """
        logger.info(f"Starting enhanced LLM research for statement: {request.statement[:100]}...")
        
        try:
            # Step 1: Check for existing research and return if found
            existing_id = self.db_ops.check_duplicate_statement(request.statement)
            if existing_id:
                logger.info(f"Found existing research for statement: {existing_id}")
                existing_result = self.db_ops.get_research_result_as_llm_response(existing_id)
                if existing_result:
                    logger.info("Returning existing research result")
                    # Update research method to indicate it's from database
                    existing_result.research_method = "database_retrieval"
                    return existing_result
                else:
                    logger.warning("Failed to retrieve existing result, continuing with new research")
            
            # Step 2: Perform enhanced LLM research with tri-factor approach
            llm_result = await self._enhanced_llm_research(request)
            
            # Step 3: Save to database only if we don't have existing research
            if not existing_id:
                research_id = self.save_research_result(request, llm_result)
                if research_id:
                    logger.info(f"Research completed and saved with ID: {research_id}")
                    llm_result.research_id = research_id
            
            return llm_result

        except Exception as e:
            logger.error(f"Enhanced LLM research failed: {e}")
            return self._create_error_response(request, str(e))
    
    async def research_with_web_context(self, request: ResearchRequest, web_context: str, web_sources: Optional[List[str]] = None) -> LLMResearchResponse:
        """
        Perform enhanced LLM research with web context and database deduplication.
        Returns existing research if duplicate is found.
        """
        logger.info(f"Starting web-enhanced research for statement: {request.statement[:100]}...")
        
        try:
            # Step 1: Check for existing research and return if found
            existing_id = self.db_ops.check_duplicate_statement(request.statement)
            if existing_id:
                logger.info(f"Found existing research for statement: {existing_id}")
                existing_result = self.db_ops.get_research_result_as_llm_response(existing_id)
                if existing_result:
                    logger.info("Returning existing web-enhanced research result")
                    # Update research method to indicate it's from database
                    existing_result.research_method = "database_retrieval_web_enhanced"
                    return existing_result
                else:
                    logger.warning("Failed to retrieve existing result, continuing with new research")
            
            # Step 2: Perform enhanced LLM research with web context
            llm_result = await self._enhanced_llm_research_with_web(request, web_context, web_sources)
            
            # Step 3: Save to database only if we don't have existing research
            if not existing_id:
                research_id = self.save_research_result(request, llm_result)
                if research_id:
                    logger.info(f"Web-enhanced research completed and saved with ID: {research_id}")
                    llm_result.research_id = research_id
            
            return llm_result
            
        except Exception as e:
            logger.error(f"Web-enhanced research failed: {e}")
            return self._create_error_response(request, str(e))
    
    # ===== LLM RESEARCH METHODS =====
    
    async def _enhanced_llm_research(self, request: ResearchRequest) -> LLMResearchResponse:
        """Enhanced LLM research with tri-factor approach"""
        try:
            # Convert ResearchRequest to LLMResearchRequest for LLM clients
            llm_request = self._convert_to_llm_request(request)
            
            # Try Groq first, fallback to Gemini
            try:
                logger.info("Attempting research with Groq client...")
                llm_result = self.groq_client.research_statement(llm_request)
            except Exception as groq_error:
                logger.warning(f"Groq client failed: {groq_error}, falling back to Gemini")
                llm_result = self.gemini_client.research_statement(llm_request)
            
            # Enhance the result with proper field mapping
            llm_result = self._enhance_llm_result(llm_result, request)
            
            logger.info("Enhanced LLM research completed successfully")
            return llm_result
            
        except Exception as e:
            logger.error(f"Enhanced LLM research failed: {e}")
            logger.error(traceback.format_exc())
            return self._create_error_response(request, f"LLM research failed: {str(e)}")
    
    async def _enhanced_llm_research_with_web(
        self, 
        request: ResearchRequest, 
        web_context: str,
        web_sources: list = None
    ) -> LLMResearchResponse:
        """Enhanced LLM research with web context integration"""
        try:
            # Convert ResearchRequest to LLMResearchRequest
            llm_request = self._convert_to_llm_request(request)
            
            # Get the web-enhanced factcheck prompt
            if web_sources:
                prompt = prompt_manager.get_web_enhanced_prompt(
                    statement=request.statement,
                    source=request.source,
                    context=request.context,
                    web_sources=web_sources,
                    web_findings=web_context
                )
            else:
                prompt = prompt_manager.get_enhanced_factcheck_prompt(
                    statement=request.statement,
                    source=request.source,
                    context=request.context,
                    country=request.country,
                    category=request.category,
                    web_context=web_context
                )
            
            # Generate response using LLM
            try:
                response_text = await self.groq_client.generate_response(prompt)
            except Exception as groq_error:
                logger.warning(f"Groq failed for web-enhanced research: {groq_error}, trying Gemini")
                response_text = await self.gemini_client.generate_response(prompt)
            
            # Parse the response
            llm_result = self.parser.parse_llm_response(response_text, llm_request)
            
            # Enhance the result with proper field mapping and web context
            llm_result = self._enhance_llm_result_with_web(llm_result, request, web_context)
            
            logger.info("Enhanced LLM research with web context completed successfully")
            return llm_result
            
        except Exception as e:
            logger.error(f"Enhanced LLM research with web failed: {e}")
            logger.error(traceback.format_exc())
            return self._create_error_response(request, f"Web-enhanced LLM research failed: {str(e)}")
    
    def _enhance_llm_result(self, llm_result: LLMResearchResponse, request: ResearchRequest) -> LLMResearchResponse:
        """Enhance LLM result with proper field mapping from request"""
        # Map request fields to response fields
        if not llm_result.country and request.country:
            llm_result.country = request.country
        
        if not llm_result.category and request.category:
            try:
                from models.research_models import StatementCategory
                llm_result.category = StatementCategory(request.category.lower())
            except (ValueError, AttributeError):
                logger.warning(f"Invalid category from request: {request.category}")
        
        # Set research method
        if not hasattr(llm_result, 'research_method') or not llm_result.research_method:
            llm_result.research_method = "enhanced_llm_research"
        
        # Create proper research metadata
        if not llm_result.research_metadata:
            llm_result.research_metadata = ResearchMetadata(
                research_sources=["llm_training_data"],
                research_timestamp=datetime.now().isoformat(),
                tri_factor_research=False,
                web_results_count=0,
                total_resources_analyzed=1,
                resource_quality_score=0.75
            )
        
        return llm_result
    
    def _enhance_llm_result_with_web(self, llm_result: LLMResearchResponse, request: ResearchRequest, web_context: str) -> LLMResearchResponse:
        """Enhance LLM result with web context and proper field mapping"""
        # First apply basic enhancements
        llm_result = self._enhance_llm_result(llm_result, request)
        
        # Set web-enhanced research method
        llm_result.research_method = "enhanced_llm_with_web_context"
        
        # Create web-enhanced research metadata
        llm_result.research_metadata = ResearchMetadata(
            research_sources=["llm_training_data", "web_search"],
            research_timestamp=datetime.now().isoformat(),
            tri_factor_research=True,
            web_results_count=self._count_web_sources(web_context),
            total_resources_analyzed=self._count_web_sources(web_context) + 1,
            resource_quality_score=0.85
        )
        
        # Set simplified web findings (not the full dump)
        if web_context:
            llm_result.web_findings = [self._create_web_summary(web_context)]
        
        return llm_result
    
    def _count_web_sources(self, web_context: str) -> int:
        """Count sources mentioned in web context"""
        if not web_context:
            return 0
        
        # Look for source count indicators
        if "Grounding sources found:" in web_context:
            try:
                line = [l for l in web_context.split('\n') if 'Grounding sources found:' in l][0]
                count = int(line.split(':')[1].strip())
                return count
            except (IndexError, ValueError):
                pass
        
        # Fallback: count URL patterns
        import re
        urls = re.findall(r'https?://[^\s\n]+', web_context)
        return len(set(urls))
    
    def _create_web_summary(self, web_context: str) -> str:
        """Create a simple summary of web research instead of full dump"""
        if not web_context:
            return "No web research performed"
        
        lines = web_context.split('\n')
        summary_parts = []
        
        for line in lines:
            if 'Statement:' in line:
                statement = line.split('Statement:')[1].strip()[:100]
                summary_parts.append(f"Searched: {statement}")
            elif 'Grounding sources found:' in line:
                sources = line.split('found:')[1].strip()
                summary_parts.append(f"Sources found: {sources}")
            elif 'Search performed:' in line:
                performed = line.split(':')[1].strip()
                summary_parts.append(f"Search performed: {performed}")
        
        if summary_parts:
            return " | ".join(summary_parts)
        else:
            return f"Web research completed ({len(web_context)} chars)"

    # ===== DATABASE OPERATIONS =====
    
    def save_research_result(self, request: ResearchRequest, llm_result: LLMResearchResponse) -> Optional[str]:
        """Save research result to database - wrapper method"""
        try:
            return self.db_ops.save_research_result(request, llm_result)
        except Exception as e:
            logger.error(f"Failed to save research result: {e}")
            return None
    
    # ===== HELPER METHODS =====
    
    def _convert_to_llm_request(self, request: ResearchRequest) -> LLMResearchRequest:
        """Convert ResearchRequest to LLMResearchRequest for LLM clients"""
        return LLMResearchRequest(
            statement=request.statement,
            source=request.source,
            context=request.context,
            country=request.country,
            category=request.category,
            profile_id=request.profile_id
        )
    
    def _create_error_response(self, request: Optional[ResearchRequest], error_message: str) -> LLMResearchResponse:
        """Create error response for failed research with proper metadata"""
        
        # Create proper error metadata using valid literal values
        error_metadata = ResearchMetadata(
            research_sources=["llm_training_data"],  # Use valid literal value
            research_timestamp=datetime.now().isoformat(),
            tri_factor_research=False
        )
        
        return LLMResearchResponse(
            valid_sources="0",
            verdict=f"Research failed: {error_message}",
            status="UNVERIFIABLE",
            correction=None,
            country=getattr(request, 'country', None) if request else None,
            category=getattr(request, 'category', None) if request else None,
            research_method="error",
            expert_perspectives=[],
            key_findings=[],
            research_summary="",
            confidence_score=0,
            research_metadata=error_metadata,
            additional_context=f"Error timestamp: {datetime.now().isoformat()}",
            llm_findings=[],
            web_findings=[],
            resource_findings=[]
        )

# Create unified service instance
db_research_service = DatabaseResearchService()