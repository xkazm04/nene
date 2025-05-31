import logging
from datetime import datetime
from typing import Dict

from schemas.fc_schemas import StatementInput, FactCheckResult, FactCheckConfig
from StoryTeller.nene.services.lllm_research import create_researcher
from agents.fc_agents import create_agent_manager

logger = logging.getLogger(__name__)


class FactChecker:
    """Main fact-checking orchestrator"""
    
    def __init__(self, config: FactCheckConfig = None):
        self.config = config or FactCheckConfig()
        self.researcher = create_researcher(self.config)
        self.agent_manager = create_agent_manager(self.config)
    
    def fact_check_statement(
        self,
        statement: str,
        speaker: str,
        background: Dict[str, str]
    ) -> FactCheckResult:
        """
        Main function to fact-check a political statement
        
        Args:
            statement: The statement to fact-check
            speaker: Who made the statement
            background: Context like where and when
            
        Returns:
            Complete fact-check result
        """
        
        logger.info(f"Starting fact-check for statement by {speaker}")
        
        try:
            # Step 1: Create input
            statement_input = StatementInput(
                statement=statement,
                speaker=speaker,
                background=background
            )
            
            # Step 2: Research the statement
            research_data = self.researcher.research_statement(statement_input)
            
            # Step 3: Run all agent analyses
            agent_analyses = self.agent_manager.run_all_analyses(research_data)
            
            # Step 4: Calculate overall verdict and confidence
            overall_verdict, confidence = self._calculate_overall_assessment(agent_analyses)
            
            # Step 5: Create final result
            result = FactCheckResult(
                statement=statement,
                speaker=speaker,
                context=background,
                timestamp=datetime.now().isoformat(),
                web_research_summary=research_data.summary,
                sources=[{
                    "type": source["type"], 
                    "excerpt": source["content"][:200] + "..." if len(source["content"]) > 200 else source["content"]
                } for source in research_data.sources],
                agent_analyses=agent_analyses,
                overall_verdict=overall_verdict,
                confidence=confidence
            )
            
            logger.info(f"Fact-check completed. Verdict: {overall_verdict} (confidence: {confidence:.2f})")
            return result
            
        except Exception as e:
            logger.error(f"Fact-check failed: {e}")
            return self._create_error_result(statement, speaker, background, str(e))
    
    def _calculate_overall_assessment(self, agent_analyses) -> tuple[str, float]:
        """Calculate overall verdict and confidence from agent analyses"""
        
        # Verdict scoring system
        verdict_scores = {
            "TRUE": 1.0,
            "PARTIALLY_TRUE": 0.6,
            "MISLEADING": 0.3,
            "FALSE": 0.0,
            "UNVERIFIABLE": None  # Excluded from scoring
        }
        
        # Calculate weighted average of verdicts
        valid_scores = []
        total_confidence = 0
        
        for analysis in agent_analyses:
            if analysis.verdict in verdict_scores and verdict_scores[analysis.verdict] is not None:
                # Weight the verdict score by the agent's confidence
                weighted_score = verdict_scores[analysis.verdict] * analysis.confidence_score
                valid_scores.append(weighted_score)
            
            total_confidence += analysis.confidence_score
        
        # Calculate overall verdict
        if valid_scores:
            avg_score = sum(valid_scores) / len(valid_scores)
            
            if avg_score >= 0.8:
                overall_verdict = "TRUE"
            elif avg_score >= 0.5:
                overall_verdict = "PARTIALLY_TRUE"
            elif avg_score >= 0.2:
                overall_verdict = "MISLEADING"
            else:
                overall_verdict = "FALSE"
        else:
            overall_verdict = "UNVERIFIABLE"
        
        # Calculate overall confidence
        confidence = total_confidence / len(agent_analyses) if agent_analyses else 0.0
        
        return overall_verdict, confidence
    
    def _create_error_result(self, statement: str, speaker: str, background: Dict[str, str], error: str) -> FactCheckResult:
        """Create an error result when fact-checking fails"""
        return FactCheckResult(
            statement=statement,
            speaker=speaker,
            context=background,
            timestamp=datetime.now().isoformat(),
            web_research_summary=f"Fact-checking failed due to error: {error}",
            sources=[],
            agent_analyses=[],
            overall_verdict="UNVERIFIABLE",
            confidence=0.0
        )


# Convenience functions
def fact_check_statement(
    statement: str,
    speaker: str,
    background: Dict[str, str],
    config: FactCheckConfig = None
) -> FactCheckResult:
    """
    Convenience function for one-off fact-checking
    
    Args:
        statement: The statement to fact-check
        speaker: Who made the statement
        background: Context information
        config: Optional configuration
        
    Returns:
        Fact-check result
    """
    
    fact_checker = FactChecker(config)
    return fact_checker.fact_check_statement(statement, speaker, background)


def create_fact_checker(
    model_name: str = "openai",
    search_provider: str = "duckduckgo",
    enable_wikipedia: bool = True
) -> FactChecker:
    """
    Factory function to create a fact checker with custom settings
    
    Args:
        model_name: LLM model to use
        search_provider: Search provider for web research
        enable_wikipedia: Whether to use Wikipedia for speaker research
        
    Returns:
        Configured FactChecker instance
    """
    
    config = FactCheckConfig(
        model_name=model_name,
        search_provider=search_provider,
        enable_wikipedia=enable_wikipedia
    )
    
    return FactChecker(config)