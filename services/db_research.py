import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
from models.research_models import LLMResearchResponse, ExpertOpinion, ResourceAnalysis
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
            
            # Prepare data for database insertion with safe handling of optional fields
            db_data = {
                "statement": request.statement,
                "source": request.source if request.source != "Unknown" else None,
                "context": request.context if request.context else None,
                "request_datetime": request.datetime.isoformat(),
                "statement_date": request.statement_date.isoformat() if request.statement_date else None,
                "country": request.country,
                "category": request.category,
                "valid_sources": result.valid_sources,
                "verdict": result.verdict,
                "status": result.status,
                "correction": result.correction,
                "resources_agreed": self._serialize_resource_analysis(result.resources_agreed) if result.resources_agreed else None,
                "resources_disagreed": self._serialize_resource_analysis(result.resources_disagreed) if result.resources_disagreed else None,
                "experts": self._serialize_experts(result.experts) if result.experts else None,
                "processed_at": datetime.utcnow().isoformat()
            }
            
            logger.debug(f"Database payload prepared: {list(db_data.keys())}")
            
            # Insert research result
            response = self.supabase.table("research_results").insert(db_data).execute()
            
            if not response.data:
                raise Exception("No data returned from database insert")
            
            research_result_id = response.data[0]["id"]
            logger.info(f"New research result saved with ID: {research_result_id}")
            
            # Save legacy resources for backwards compatibility (handle None case)
            legacy_resources = []
            if result.resources_agreed and result.resources_disagreed:
                legacy_resources = self._extract_legacy_resources(result.resources_agreed, result.resources_disagreed)
            elif result.resources_agreed:
                legacy_resources = self._extract_legacy_resources(result.resources_agreed, ResourceAnalysis(total="0%", count=0))
            elif result.resources_disagreed:
                legacy_resources = self._extract_legacy_resources(ResourceAnalysis(total="0%", count=0), result.resources_disagreed)
        
            if legacy_resources:
                self._save_resources(research_result_id, legacy_resources)
            
            logger.info(f"Successfully saved research result and {len(legacy_resources)} legacy resources to database")
            return research_result_id
            
        except Exception as e:
            error_msg = f"Failed to save research result to database: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Error type: {type(e).__name__}")
            raise Exception(error_msg)
    
    def _extract_legacy_resources(self, resources_agreed: ResourceAnalysis, resources_disagreed: ResourceAnalysis) -> List[str]:
        """
        Extract URLs from new resource structure for legacy compatibility.
        
        Args:
            resources_agreed: Agreed resource analysis
            resources_disagreed: Disagreed resource analysis
            
        Returns:
            List of URLs for legacy resources table
        """
        legacy_urls = []
        
        # Extract URLs from agreed resources
        for ref in resources_agreed.references:
            legacy_urls.append(ref.url)
        
        # Extract URLs from disagreed resources
        for ref in resources_disagreed.references:
            legacy_urls.append(ref.url)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in legacy_urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        return unique_urls
    
    def _save_resources(self, research_result_id: str, resources: List[str]) -> None:
        """Save research resources to database for legacy compatibility."""
        try:
            logger.debug(f"Saving {len(resources)} legacy resources for research result {research_result_id}")
            
            resources_data = [
                {
                    "research_result_id": research_result_id,
                    "url": resource,
                    "order_index": index + 1
                }
                for index, resource in enumerate(resources)
            ]
            
            if not resources_data:
                logger.debug("No resources to save")
                return
            
            response = self.supabase.table("research_resources").insert(resources_data).execute()
            
            if not response.data:
                raise Exception("No data returned from resources insert")
            
            logger.debug(f"Successfully saved {len(response.data)} legacy resources")
            
        except Exception as e:
            logger.error(f"Failed to save legacy resources: {str(e)}")
            # Don't re-raise since main result was saved successfully
    
    def _serialize_resource_analysis(self, resource_analysis: ResourceAnalysis) -> Dict[str, Any]:
        """
        Convert ResourceAnalysis to dictionary for JSON storage.
        
        Args:
            resource_analysis: ResourceAnalysis object
            
        Returns:
            Dict representation suitable for JSON storage
        """
        return {
            "total": resource_analysis.total,
            "count": resource_analysis.count,
            "mainstream": resource_analysis.mainstream,
            "governance": resource_analysis.governance,
            "academic": resource_analysis.academic,
            "medical": resource_analysis.medical,
            "other": resource_analysis.other,
            "major_countries": resource_analysis.major_countries,
            "references": [
                {
                    "url": ref.url,
                    "title": ref.title,
                    "category": ref.category,
                    "country": ref.country,
                    "credibility": ref.credibility
                }
                for ref in resource_analysis.references
            ]
        }
    
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
        Retrieve a research result by ID with enhanced data structure.
        
        Args:
            result_id: Database ID of the research result
            
        Returns:
            Dict containing the research result with all fields, or None if not found
        """
        try:
            logger.debug(f"Retrieving research result: {result_id}")
            
            # Get main result with all new fields
            response = self.supabase.table("research_results").select("*").eq("id", result_id).execute()
            
            if not response.data:
                logger.warning(f"Research result not found: {result_id}")
                return None
            
            result = response.data[0]
            
            # Get legacy resources for backwards compatibility
            resources_response = self.supabase.table("research_resources").select("url").eq("research_result_id", result_id).order("order_index").execute()
            
            # Add legacy resources field for backwards compatibility
            result["resources"] = [r["url"] for r in resources_response.data] if resources_response.data else []
            
            logger.debug(f"Retrieved research result with {len(result['resources'])} legacy resources")
            return result
            
        except Exception as e:
            logger.error(f"Failed to retrieve research result {result_id}: {str(e)}")
            return None
    
    def search_research_results(
        self,
        search_text: Optional[str] = None,
        status_filter: Optional[str] = None,
        country_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Search research results with optional filters including new fields.
        
        Args:
            search_text: Text to search in statement, source, context
            status_filter: Filter by status (TRUE, FALSE, etc.)
            country_filter: Filter by country ISO code
            category_filter: Filter by statement category
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of research results
        """
        try:
            logger.debug(f"Searching research results: text='{search_text}', status='{status_filter}', country='{country_filter}', category='{category_filter}'")
            
            query = self.supabase.table("research_results").select(
                "id, statement, source, status, statement_date, country, category, processed_at"
            )
            
            if status_filter:
                query = query.eq("status", status_filter)
                
            if country_filter:
                query = query.eq("country", country_filter)
                
            if category_filter:
                query = query.eq("category", category_filter)
            
            if search_text:
                # Simple text search - Supabase will handle more complex search if needed
                query = query.or_(f"statement.ilike.%{search_text}%,source.ilike.%{search_text}%,context.ilike.%{search_text}%")
            
            response = query.order("processed_at", desc=True).range(offset, offset + limit - 1).execute()
            
            logger.debug(f"Found {len(response.data) if response.data else 0} research results")
            return response.data or []
            
        except Exception as e:
            logger.error(f"Failed to search research results: {str(e)}")
            return []
    
    def get_analytics_summary(self) -> Dict[str, Any]:
        """
        Get analytics summary of research results.
        
        Returns:
            Dict containing analytics data
        """
        try:
            logger.debug("Retrieving analytics summary")
            
            # Get overall counts by status
            status_response = self.supabase.table("research_results").select("status", count="exact").execute()
            
            # Get counts by country
            country_response = self.supabase.table("research_results").select("country", count="exact").not_.is_("country", "null").execute()
            
            # Get counts by category
            category_response = self.supabase.table("research_results").select("category", count="exact").not_.is_("category", "null").execute()
            
            # Get recent activity (last 7 days)
            recent_response = self.supabase.table("research_results").select("processed_at", count="exact").gte("processed_at", (datetime.utcnow() - datetime.timedelta(days=7)).isoformat()).execute()
            
            return {
                "total_statements": status_response.count or 0,
                "recent_activity": recent_response.count or 0,
                "countries_analyzed": country_response.count or 0,
                "categories_covered": category_response.count or 0
            }
            
        except Exception as e:
            logger.error(f"Failed to retrieve analytics summary: {str(e)}")
            return {
                "total_statements": 0,
                "recent_activity": 0,
                "countries_analyzed": 0,
                "categories_covered": 0
            }

# Create service instance
db_research_service = SupabaseResearchService()