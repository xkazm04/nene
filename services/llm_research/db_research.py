import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from models.research_models import LLMResearchResponse
from models.db_models import ResearchResultDB, ResearchResourceDB, SearchFilters
from schemas.research import ResearchRequest
from repositories.research_repository import research_repository
from utils.data_serializers import data_serializer

logger = logging.getLogger(__name__)

class ResearchService:
    """Service layer for research operations with clean separation of concerns."""
    
    def __init__(self):
        self.repository = research_repository
        self.serializer = data_serializer
        logger.info("Research service initialized successfully")
    
    def check_duplicate_statement(self, statement: str) -> Optional[str]:
        """
        Check if a statement already exists in the database.
        
        Args:
            statement: The statement to check for duplicates
            
        Returns:
            str: ID of existing record if duplicate found, None otherwise
        """
        return self.repository.find_duplicate_statement(statement)
    
    def save_research_result(self, request: ResearchRequest, result: LLMResearchResponse) -> Optional[str]:
        """
        Save research result to database with full transaction support.
        
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
            
            # Prepare research result data
            db_data = self._prepare_research_result_data(request, result)
            
            # Save main research result
            research_result_id = self.repository.create_research_result(db_data)
            
            if not research_result_id:
                raise Exception("Failed to create research result record")
            
            # Log profile association if present
            if request.profile_id:
                logger.info(f"Research result linked to profile: {request.profile_id}")
            
            # Save legacy resources for backwards compatibility
            self._save_legacy_resources(research_result_id, result)
            
            logger.info(f"Successfully saved research result to database with ID: {research_result_id}")
            return research_result_id
            
        except Exception as e:
            error_msg = f"Failed to save research result to database: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Error type: {type(e).__name__}")
            raise Exception(error_msg)
    
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
            
            # Get main result
            result = self.repository.get_research_result_by_id(result_id)
            
            if not result:
                return None
            
            # Get legacy resources for backwards compatibility
            resources = self.repository.get_research_resources(result_id)
            result["resources"] = resources
            
            logger.debug(f"Retrieved research result with {len(resources)} legacy resources")
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
        profile_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Search research results with optional filters.
        
        Args:
            search_text: Text to search in statement, source, context
            status_filter: Filter by status (TRUE, FALSE, etc.)
            country_filter: Filter by country ISO code
            category_filter: Filter by statement category
            profile_filter: Filter by profile ID
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of research results
        """
        try:
            filters = SearchFilters(
                search_text=search_text,
                status_filter=status_filter,
                country_filter=country_filter,
                category_filter=category_filter,
                profile_filter=profile_filter,
                limit=limit,
                offset=offset
            )
            
            return self.repository.search_research_results(filters)
            
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
        return self.repository.get_profile_statement_count(profile_id)
    
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
        return self.repository.get_profile_statements(profile_id, limit, offset)
    
    def get_analytics_summary(self) -> Dict[str, Any]:
        """
        Get analytics summary of research results.
        
        Returns:
            Dict containing analytics data
        """
        try:
            summary = self.repository.get_analytics_summary()
            return summary.model_dump()
        except Exception as e:
            logger.error(f"Failed to retrieve analytics summary: {str(e)}")
            return {
                "total_statements": 0,
                "recent_activity": 0,
                "countries_analyzed": 0,
                "categories_covered": 0,
                "linked_to_profiles": 0
            }
    
    def _prepare_research_result_data(self, request: ResearchRequest, result: LLMResearchResponse) -> ResearchResultDB:
        """
        Prepare research result data for database insertion.
        
        Args:
            request: Original research request
            result: LLM research response
            
        Returns:
            ResearchResultDB: Prepared data for database insertion
        """
        return ResearchResultDB(
            statement=request.statement,
            source=request.source if request.source != "Unknown" else None,
            context=request.context if request.context else None,
            request_datetime=request.datetime.isoformat(),
            statement_date=request.statement_date.isoformat() if request.statement_date else None,
            country=request.country,
            category=request.category,
            profile_id=request.profile_id,
            valid_sources=result.valid_sources,
            verdict=result.verdict,
            status=result.status,
            correction=result.correction,
            resources_agreed=self.serializer.serialize_resource_analysis(result.resources_agreed),
            resources_disagreed=self.serializer.serialize_resource_analysis(result.resources_disagreed),
            experts=self.serializer.serialize_experts(result.experts),
            processed_at=datetime.utcnow().isoformat()
        )
    
    def _save_legacy_resources(self, research_result_id: str, result: LLMResearchResponse) -> None:
        """
        Save legacy resources for backwards compatibility.
        
        Args:
            research_result_id: Research result ID
            result: LLM research response
        """
        try:
            # Extract legacy URLs from resources
            legacy_urls = self.serializer.extract_legacy_resources(
                result.resources_agreed, 
                result.resources_disagreed
            )
            
            if not legacy_urls:
                logger.debug("No legacy resources to save")
                return
            
            # Create resource records
            resources = [
                ResearchResourceDB(
                    research_result_id=research_result_id,
                    url=url,
                    order_index=index + 1
                )
                for index, url in enumerate(legacy_urls)
            ]
            
            # Save to database
            success = self.repository.create_research_resources(resources)
            
            if success:
                logger.debug(f"Successfully saved {len(resources)} legacy resources")
            else:
                logger.warning("Failed to save some legacy resources")
                
        except Exception as e:
            logger.error(f"Failed to save legacy resources: {str(e)}")
            # Don't re-raise since main result was saved successfully

# Create service instance
db_research_service = ResearchService()