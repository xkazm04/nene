import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client, Client
from models.db_models import ResearchResultDB, ResearchResourceDB, SearchFilters, AnalyticsSummary

load_dotenv()
logger = logging.getLogger(__name__)

class ResearchRepository:
    """Repository for database operations related to research results."""
    
    def __init__(self):
        """Initialize Supabase client with credentials from environment."""
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment variables")
        
        try:
            self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
            logger.info("Research repository initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {str(e)}")
            raise
    
    def find_duplicate_statement(self, statement: str) -> Optional[str]:
        """
        Find existing record with the same statement.
        
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
            return None
    
    def create_research_result(self, data: ResearchResultDB) -> Optional[str]:
        """
        Create a new research result record.
        
        Args:
            data: Research result data
            
        Returns:
            str: ID of created record, None if failed
        """
        try:
            logger.info(f"Creating research result for statement: {data.statement[:100]}...")
            
            # Convert to dict for database insertion
            db_data = data.model_dump(exclude={'id'})
            
            logger.debug(f"Database payload prepared: {list(db_data.keys())}")
            
            response = self.supabase.table("research_results").insert(db_data).execute()
            
            if not response.data:
                raise Exception("No data returned from database insert")
            
            research_result_id = response.data[0]["id"]
            logger.info(f"New research result saved with ID: {research_result_id}")
            
            return research_result_id
            
        except Exception as e:
            logger.error(f"Failed to create research result: {str(e)}")
            raise
    
    def get_research_result_by_id(self, result_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a research result by ID.
        
        Args:
            result_id: Database ID of the research result
            
        Returns:
            Dict containing the research result or None if not found
        """
        try:
            logger.debug(f"Retrieving research result: {result_id}")
            
            response = self.supabase.table("research_results").select("*").eq("id", result_id).execute()
            
            if not response.data:
                logger.warning(f"Research result not found: {result_id}")
                return None
            
            result = response.data[0]
            logger.debug(f"Retrieved research result: {result_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to retrieve research result {result_id}: {str(e)}")
            return None
    
    def search_research_results(self, filters: SearchFilters) -> List[Dict[str, Any]]:
        """
        Search research results with filters.
        
        Args:
            filters: Search filters
            
        Returns:
            List of research results
        """
        try:
            logger.debug(f"Searching research results with filters: {filters}")
            
            query = self.supabase.table("research_results").select(
                "id, statement, source, status, statement_date, country, category, processed_at, profile_id"
            )
            
            # Apply filters
            if filters.status_filter:
                query = query.eq("status", filters.status_filter)
                
            if filters.country_filter:
                query = query.eq("country", filters.country_filter)
                
            if filters.category_filter:
                query = query.eq("category", filters.category_filter)

            if filters.profile_filter:
                query = query.eq("profile_id", filters.profile_filter)
            
            if filters.search_text:
                query = query.or_(f"statement.ilike.%{filters.search_text}%,source.ilike.%{filters.search_text}%,context.ilike.%{filters.search_text}%")
            
            response = query.order("processed_at", desc=True).range(filters.offset, filters.offset + filters.limit - 1).execute()
            
            results = response.data or []
            logger.debug(f"Found {len(results)} research results")
            return results
            
        except Exception as e:
            logger.error(f"Failed to search research results: {str(e)}")
            return []
    
    def get_profile_statement_count(self, profile_id: str) -> int:
        """
        Get total count of research results for a specific profile.
        
        Args:
            profile_id: Profile UUID
            
        Returns:
            int: Total count of statements for the profile
        """
        try:
            logger.debug(f"Getting statement count for profile: {profile_id}")
            
            response = self.supabase.table("research_results").select("id", count="exact").eq("profile_id", profile_id).execute()
            
            count = response.count or 0
            logger.debug(f"Profile {profile_id} has {count} statements")
            return count
            
        except Exception as e:
            logger.error(f"Failed to get statement count for profile {profile_id}: {str(e)}")
            return 0
    
    def get_profile_statements(self, profile_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get research results for a specific profile.
        
        Args:
            profile_id: Profile UUID
            limit: Maximum results to return
            offset: Number of results to skip
            
        Returns:
            List of research results for the profile
        """
        try:
            logger.debug(f"Getting statements for profile: {profile_id}")
            
            query = self.supabase.table("research_results").select(
                "id, statement, source, status, statement_date, country, category, processed_at, verdict"
            ).eq("profile_id", profile_id)
            
            response = query.order("processed_at", desc=True).range(offset, offset + limit - 1).execute()
            
            statements = response.data or []
            logger.debug(f"Found {len(statements)} statements for profile {profile_id}")
            return statements
            
        except Exception as e:
            logger.error(f"Failed to get statements for profile {profile_id}: {str(e)}")
            return []
    
    def create_research_resources(self, resources: List[ResearchResourceDB]) -> bool:
        """
        Create research resource records.
        
        Args:
            resources: List of research resources
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not resources:
                logger.debug("No resources to save")
                return True
            
            logger.debug(f"Saving {len(resources)} research resources")
            
            resources_data = [resource.model_dump() for resource in resources]
            
            response = self.supabase.table("research_resources").insert(resources_data).execute()
            
            if not response.data:
                raise Exception("No data returned from resources insert")
            
            logger.debug(f"Successfully saved {len(response.data)} research resources")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save research resources: {str(e)}")
            return False
    
    def get_research_resources(self, research_result_id: str) -> List[str]:
        """
        Get research resources for a research result.
        
        Args:
            research_result_id: Research result ID
            
        Returns:
            List of resource URLs
        """
        try:
            logger.debug(f"Getting resources for research result: {research_result_id}")
            
            response = self.supabase.table("research_resources").select("url").eq("research_result_id", research_result_id).order("order_index").execute()
            
            urls = [r["url"] for r in response.data] if response.data else []
            logger.debug(f"Found {len(urls)} resources")
            return urls
            
        except Exception as e:
            logger.error(f"Failed to get research resources: {str(e)}")
            return []
    
    def get_analytics_summary(self) -> AnalyticsSummary:
        """
        Get analytics summary of research results.
        
        Returns:
            AnalyticsSummary: Analytics data
        """
        try:
            logger.debug("Retrieving analytics summary")
            
            # Get overall count
            total_response = self.supabase.table("research_results").select("id", count="exact").execute()
            
            # Get recent activity (last 7 days)
            seven_days_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
            recent_response = self.supabase.table("research_results").select("id", count="exact").gte("processed_at", seven_days_ago).execute()
            
            # Get country count
            country_response = self.supabase.table("research_results").select("country", count="exact").not_.is_("country", "null").execute()
            
            # Get category count
            category_response = self.supabase.table("research_results").select("category", count="exact").not_.is_("category", "null").execute()
            
            # Get profile linking stats
            linked_response = self.supabase.table("research_results").select("profile_id", count="exact").not_.is_("profile_id", "null").execute()
            
            return AnalyticsSummary(
                total_statements=total_response.count or 0,
                recent_activity=recent_response.count or 0,
                countries_analyzed=country_response.count or 0,
                categories_covered=category_response.count or 0,
                linked_to_profiles=linked_response.count or 0
            )
            
        except Exception as e:
            logger.error(f"Failed to retrieve analytics summary: {str(e)}")
            return AnalyticsSummary(
                total_statements=0,
                recent_activity=0,
                countries_analyzed=0,
                categories_covered=0,
                linked_to_profiles=0
            )

# Create repository instance
research_repository = ResearchRepository()