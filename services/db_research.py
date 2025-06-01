import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
from services.llm_research import LLMResearchResponse, ExpertOpinion
from schemas.research import ResearchRequest

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)



class SupabaseResearchService:
    def __init__(self):
        """Initialize Supabase client with credentials from environment."""
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment variables")
        
        try:
            self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
            logger.info("Supabase research service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {str(e)}")
            raise
    
    def check_duplicate_statement(self, statement: str) -> Optional[str]:
        """
        Check if a statement already exists in the database.
        
        Args:
            statement: The statement to check for duplicates
            
        Returns:
            str: ID of existing record if duplicate found, None otherwise
        """
        try:
            logger.debug(f"Checking for duplicate statement: {statement[:50]}...")
            
            response = self.supabase.table("research_results").select("id, processed_at").eq("statement", statement).limit(1).execute()
            
            if response.data:
                existing_id = response.data[0]["id"]
                existing_date = response.data[0]["processed_at"]
                logger.info(f"Duplicate statement found - existing record ID: {existing_id}, processed: {existing_date}")
                return existing_id
            
            logger.debug("No duplicate statement found")
            return None
            
        except Exception as e:
            logger.error(f"Error checking for duplicate statement: {str(e)}")
            # Return None to allow save attempt rather than blocking on error
            return None
    
    def save_research_result(
        self, 
        request: ResearchRequest, 
        result: LLMResearchResponse
    ) -> Optional[str]:
        """
        Save research result to Supabase database.
        
        Args:
            request: Original research request
            result: LLM research response
            
        Returns:
            str: ID of saved record or existing record ID if duplicate found
            
        Raises:
            Exception: If database save fails
        """
        try:
            logger.info(f"Saving research result to database for statement: {request.statement[:100]}...")
            
            # Check for duplicates first
            existing_id = self.check_duplicate_statement(request.statement)
            if existing_id:
                logger.warning(f"Duplicate statement detected - not saving. Existing record ID: {existing_id}")
                return existing_id
            
            # Prepare data for database insertion
            db_data = {
                "statement": request.statement,
                "source": request.source if request.source != "Unknown" else None,
                "context": request.context if request.context else None,
                "request_datetime": request.datetime.isoformat(),
                "statement_date": request.statement_date.isoformat() if request.statement_date else None,
                "valid_sources": result.valid_sources,
                "verdict": result.verdict,
                "status": result.status,
                "correction": result.correction,
                "experts": self._serialize_experts(result.experts),
                "processed_at": datetime.utcnow().isoformat()
            }
            
            logger.debug(f"Database payload prepared: {list(db_data.keys())}")
            
            # Insert research result
            response = self.supabase.table("research_results").insert(db_data).execute()
            
            if not response.data:
                raise Exception("No data returned from database insert")
            
            research_result_id = response.data[0]["id"]
            logger.info(f"New research result saved with ID: {research_result_id}")
            
            # Save resources separately
            if result.resources:
                self._save_resources(research_result_id, result.resources)
            
            logger.info(f"Successfully saved research result and {len(result.resources)} resources to database")
            return research_result_id
            
        except Exception as e:
            error_msg = f"Failed to save research result to database: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Error type: {type(e).__name__}")
            raise Exception(error_msg)
    
    def _save_resources(self, research_result_id: str, resources: list[str]) -> None:
        """Save research resources to database."""
        try:
            logger.debug(f"Saving {len(resources)} resources for research result {research_result_id}")
            
            resources_data = [
                {
                    "research_result_id": research_result_id,
                    "url": resource,
                    "order_index": index + 1
                }
                for index, resource in enumerate(resources)
            ]
            
            response = self.supabase.table("research_resources").insert(resources_data).execute()
            
            if not response.data:
                raise Exception("No data returned from resources insert")
            
            logger.debug(f"Successfully saved {len(response.data)} resources")
            
        except Exception as e:
            logger.error(f"Failed to save resources: {str(e)}")
            # Don't re-raise since main result was saved successfully
    
    def _serialize_experts(self, experts: ExpertOpinion) -> Dict[str, Any]:
        """Convert ExpertOpinion to dictionary for JSON storage."""
        expert_dict = {}
        
        if experts.critic is not None:
            expert_dict["critic"] = experts.critic
        if experts.devil is not None:
            expert_dict["devil"] = experts.devil
        if experts.nerd is not None:
            expert_dict["nerd"] = experts.nerd
        if experts.psychic is not None:
            expert_dict["psychic"] = experts.psychic
            
        return expert_dict
    
    def get_research_result(self, result_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a research result by ID.
        
        Args:
            result_id: Database ID of the research result
            
        Returns:
            Dict containing the research result with resources, or None if not found
        """
        try:
            logger.debug(f"Retrieving research result: {result_id}")
            
            # Get main result
            response = self.supabase.table("research_results").select("*").eq("id", result_id).execute()
            
            if not response.data:
                logger.warning(f"Research result not found: {result_id}")
                return None
            
            result = response.data[0]
            
            # Get resources
            resources_response = self.supabase.table("research_resources").select("url").eq("research_result_id", result_id).order("order_index").execute()
            
            result["resources"] = [r["url"] for r in resources_response.data] if resources_response.data else []
            
            logger.debug(f"Retrieved research result with {len(result['resources'])} resources")
            return result
            
        except Exception as e:
            logger.error(f"Failed to retrieve research result {result_id}: {str(e)}")
            return None
    
    def search_research_results(
        self,
        search_text: Optional[str] = None,
        status_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> list[Dict[str, Any]]:
        """
        Search research results with optional filters.
        
        Args:
            search_text: Text to search in statement, source, context
            status_filter: Filter by status (TRUE, FALSE, etc.)
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of research results
        """
        try:
            logger.debug(f"Searching research results: text='{search_text}', status='{status_filter}'")
            
            query = self.supabase.table("research_results").select("id, statement, source, status, statement_date, processed_at")
            
            if status_filter:
                query = query.eq("status", status_filter)
            
            if search_text:
                # Simple text search - Supabase will handle more complex search if needed
                query = query.or_(f"statement.ilike.%{search_text}%,source.ilike.%{search_text}%,context.ilike.%{search_text}%")
            
            response = query.order("processed_at", desc=True).range(offset, offset + limit - 1).execute()
            
            logger.debug(f"Found {len(response.data) if response.data else 0} research results")
            return response.data or []
            
        except Exception as e:
            logger.error(f"Failed to search research results: {str(e)}")
            return []

# Create service instance
db_research_service = SupabaseResearchService()