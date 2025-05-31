from pydantic import BaseModel, Field
from typing import Dict, List
class StatementInput(BaseModel):
    """Input model for fact-checking"""
    statement: str
    speaker: str
    background: Dict[str, str]  # {"where": "location", "when": "date/time"}


class AgentAnalysis(BaseModel):
    """Unified output format for all agents"""
    agent_name: str
    perspective: str
    analysis: str
    confidence_score: float = Field(ge=0, le=1)
    key_findings: List[str]
    supporting_evidence: List[Dict[str, str]]  # [{"source": "url", "excerpt": "text"}]
    verdict: str  # "TRUE", "FALSE", "MISLEADING", "PARTIALLY_TRUE", "UNVERIFIABLE"
    reasoning: str


class ResearchData(BaseModel):
    """Research data structure"""
    statement: str
    speaker: str
    context: Dict[str, str]
    search_results: str
    context_results: str
    speaker_info: str
    sources: List[Dict[str, str]]
    summary: str


class FactCheckResult(BaseModel):
    """Main result model"""
    statement: str
    speaker: str
    context: Dict[str, str]
    timestamp: str
    web_research_summary: str
    sources: List[Dict[str, str]]
    agent_analyses: List[AgentAnalysis]
    overall_verdict: str
    confidence: float
    
    
class FactCheckConfig(BaseModel):
    """Configuration for fact checking"""
    model_name: str = "openai"
    search_provider: str = "duckduckgo"
    temperature: float = 0.3
    max_search_results: int = 1500
    enable_wikipedia: bool = True
    search_delay: float = 1.0