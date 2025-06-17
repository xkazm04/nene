from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from .research_models import StatementCategory, ExpertOpinion, ExpertPerspective

class StatementSummary(BaseModel):
    """Summary of a statement for stats purposes"""
    id: Optional[str] = None
    verdict: str = Field(..., description="Final statement with 1-2 sentence summary")
    status: str = Field(..., description="TRUE, FALSE, MISLEADING, PARTIALLY_TRUE, or UNVERIFIABLE")
    correction: Optional[str] = Field(default=None, description="Corrected statement if original is false/misleading")
    country: Optional[str] = Field(default=None, description="ISO country code of speaker/statement origin")
    category: Optional[StatementCategory] = Field(default=None, description="Statement category")
    experts: Optional[ExpertOpinion] = Field(default=None, description="Expert opinions")
    profile_id: Optional[str] = Field(default=None, description="Profile ID")
    expert_perspectives: List[ExpertPerspective] = Field(default_factory=list, description="Detailed expert perspectives")
    created_at: Optional[str] = Field(default=None, description="Statement creation timestamp")

class CategoryStats(BaseModel):
    """Statistics for a specific category"""
    category: str = Field(..., description="Category name")
    count: int = Field(..., description="Number of statements in this category")
    
class StatsData(BaseModel):
    """Statistics data for statements"""
    total_statements: int = Field(default=0, description="Total number of statements")
    categories: List[CategoryStats] = Field(default_factory=list, description="Breakdown by category")
    status_breakdown: Dict[str, int] = Field(default_factory=dict, description="Breakdown by status (TRUE, FALSE, etc.)")

class ProfileStatsResponse(BaseModel):
    """Response model for profile statistics"""
    profile_id: str = Field(..., description="Profile UUID")
    recent_statements: List[StatementSummary] = Field(default_factory=list, description="Last 10 statements")
    stats: StatsData = Field(..., description="Statistical breakdown of statements")