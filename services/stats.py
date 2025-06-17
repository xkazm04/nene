from typing import Optional, List, Dict
from dotenv import load_dotenv
from supabase import create_client, Client
import logging
import os
from collections import defaultdict
from models.stats_models import ProfileStatsResponse, StatementSummary, StatsData, CategoryStats
from models.research_models import StatementCategory

load_dotenv()

logger = logging.getLogger(__name__)

class StatsService:
    def __init__(self):
        """Initialize Supabase client with credentials from environment."""
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment variables")
        
        try:
            self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
            logger.info("Stats service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {str(e)}")
            raise

    def get_profile_stats(self, profile_id: str) -> Optional[ProfileStatsResponse]:
        """
        Get comprehensive statistics for a profile including recent statements and breakdowns.
        
        Args:
            profile_id: Profile UUID
            
        Returns:
            ProfileStatsResponse: Complete stats data or None if profile not found
        """
        try:
            logger.info(f"Retrieving stats for profile: {profile_id}")
            
            # First verify the profile exists
            profile_check = self.supabase.table("profiles").select("id").eq("id", profile_id).limit(1).execute()
            
            if not profile_check.data:
                logger.warning(f"Profile not found: {profile_id}")
                return None
            
            # Get recent statements (last 10) from research_results table
            recent_statements = self._get_recent_statements(profile_id)
            
            # Get statistics breakdown
            stats = self._calculate_stats(profile_id)
            
            return ProfileStatsResponse(
                profile_id=profile_id,
                recent_statements=recent_statements,
                stats=stats
            )
            
        except Exception as e:
            logger.error(f"Failed to retrieve stats for profile {profile_id}: {str(e)}")
            return None

    def _get_recent_statements(self, profile_id: str) -> List[StatementSummary]:
        """
        Get recent statements for a profile from research_results table.
        
        Args:
            profile_id: Profile UUID
            
        Returns:
            List of recent statements
        """
        try:
            # Query research_results table for statements associated with this profile
            response = self.supabase.table("research_results") \
                .select("id, statement, verdict, status, correction, country, category, profile_id, created_at, processed_at, experts") \
                .eq("profile_id", profile_id) \
                .order("processed_at", desc=True) \
                .limit(10) \
                .execute()
            
            statements = []
            for stmt_data in response.data or []:
                try:
                    # Convert category string to StatementCategory enum if possible
                    category = None
                    if stmt_data.get("category"):
                        try:
                            category = StatementCategory(stmt_data["category"])
                        except ValueError:
                            category = StatementCategory.OTHER
                    
                    # Use verdict as the main text, fallback to statement if no verdict
                    verdict_text = stmt_data.get("verdict") or stmt_data.get("statement", "")
                    
                    statement = StatementSummary(
                        id=stmt_data.get("id"),
                        verdict=verdict_text,
                        status=stmt_data.get("status", "UNVERIFIABLE"),
                        correction=stmt_data.get("correction"),
                        country=stmt_data.get("country"),
                        category=category,
                        profile_id=stmt_data.get("profile_id"),
                        expert_perspectives=[],  # Could be populated from experts field if needed
                        created_at=stmt_data.get("processed_at") or stmt_data.get("created_at")
                    )
                    statements.append(statement)
                except Exception as e:
                    logger.warning(f"Failed to parse statement data: {stmt_data}, error: {str(e)}")
                    continue
            
            logger.debug(f"Retrieved {len(statements)} recent statements for profile {profile_id}")
            return statements
            
        except Exception as e:
            logger.error(f"Failed to get recent statements for profile {profile_id}: {str(e)}")
            return []

    def _calculate_stats(self, profile_id: str) -> StatsData:
        """
        Calculate comprehensive statistics for a profile from research_results table.
        
        Args:
            profile_id: Profile UUID
            
        Returns:
            StatsData: Statistical breakdown
        """
        try:
            # Query all research results for this profile to calculate stats
            response = self.supabase.table("research_results") \
                .select("category, status") \
                .eq("profile_id", profile_id) \
                .execute()
            
            data = response.data or []
            
            # Count categories and statuses
            category_counts = defaultdict(int)
            status_counts = defaultdict(int)
            
            for item in data:
                category = item.get("category", "other")
                status = item.get("status", "UNVERIFIABLE")
                
                category_counts[category] += 1
                status_counts[status] += 1
            
            # Convert to CategoryStats objects
            categories = [
                CategoryStats(category=cat, count=count)
                for cat, count in category_counts.items()
            ]
            
            # Sort categories by count (descending)
            categories.sort(key=lambda x: x.count, reverse=True)
            
            stats = StatsData(
                total_statements=len(data),
                categories=categories,
                status_breakdown=dict(status_counts)
            )
            
            logger.debug(f"Calculated stats for profile {profile_id}: {stats.total_statements} total statements")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to calculate stats for profile {profile_id}: {str(e)}")
            return StatsData()

    def get_profile_statement_count(self, profile_id: str) -> int:
        """
        Get total statement count for a profile from research_results table.
        
        Args:
            profile_id: Profile UUID
            
        Returns:
            int: Total number of statements
        """
        try:
            response = self.supabase.table("research_results") \
                .select("id", count="exact") \
                .eq("profile_id", profile_id) \
                .execute()
            return response.count or 0
            
        except Exception as e:
            logger.error(f"Failed to get statement count for profile {profile_id}: {str(e)}")
            return 0

    def get_category_breakdown(self, profile_id: str) -> Dict[str, int]:
        """
        Get category breakdown for a profile from research_results table.
        
        Args:
            profile_id: Profile UUID
            
        Returns:
            Dict mapping category names to counts
        """
        try:
            response = self.supabase.table("research_results") \
                .select("category") \
                .eq("profile_id", profile_id) \
                .execute()
            
            category_counts = defaultdict(int)
            for item in response.data or []:
                category = item.get("category", "other")
                category_counts[category] += 1
            
            return dict(category_counts)
            
        except Exception as e:
            logger.error(f"Failed to get category breakdown for profile {profile_id}: {str(e)}")
            return {}

# Create service instance
stats_service = StatsService()