class ExtendedFactCheckingService:
    """Enhanced service with multi-perspective evaluation"""

    def __init__(self, llm):
        self.evaluator = MultiPerspectiveEvaluator(llm)

    def process_statement_extended(self, statement: Statement,
                                   context: str = "",
                                   enable_all_agents: bool = True,
                                   specific_agents: Optional[List[str]] = None) -> Dict[str, Any]:
        """Process statement with extended multi-agent evaluation"""

        # Determine which agents to use
        if specific_agents:
            agents_to_use = specific_agents
        elif enable_all_agents:
            agents_to_use = None  # Use all
        else:
            agents_to_use = ["fact_checker", "nerd"]  # Default subset

        # Get multi-perspective evaluation
        evaluation = self.evaluator.evaluate_statement(
            statement,
            context,
            agents_to_use
        )

        # Format for response
        return {
            "statement": statement.text,
            "speaker": statement.speaker.dict(),
            "timestamp": {
                "start": statement.start_time,
                "end": statement.end_time
            },
            "extended_evaluation": evaluation,
            "quick_summary": self._generate_quick_summary(evaluation),
            "visualization_data": self._prepare_visualization_data(evaluation)
        }

    def _generate_quick_summary(self, evaluation: Dict[str, Any]) -> str:
        """Generate a quick summary of the evaluation"""
        consensus = evaluation["consensus_level"]
        verdict = evaluation["synthesis"]["verdict"]

        if consensus > 0.8:
            consensus_text = "Strong agreement"
        elif consensus > 0.5:
            consensus_text = "Moderate agreement"
        else:
            consensus_text = "Significant disagreement"

        perspectives_summary = []
        for agent, data in evaluation["perspectives"].items():
            if "error" not in data:
                perspectives_summary.append(f"{agent}: {data['perspective']}")

        return f"""
        Verdict: {verdict.value}
        Consensus: {consensus_text} ({consensus:.0%})
        
        Agent Perspectives:
        {chr(10).join('• ' + p for p in perspectives_summary)}
        
        Key Finding: {evaluation['synthesis']['summary'][:200]}...
        """

    def _prepare_visualization_data(self, evaluation: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare data for visualization"""

        # Extract confidence scores for radar chart
        agent_confidences = {}
        for agent, data in evaluation["perspectives"].items():
            if "error" not in data:
                agent_confidences[agent] = data.get("confidence", 0.5)

        # Prepare sentiment distribution
        sentiments = {
            "positive": 0,
            "negative": 0,
            "neutral": 0
        }

        for agent, data in evaluation["perspectives"].items():
            if "error" not in data:
                analysis = data.get("analysis", "").lower()
                if any(word in analysis for word in ["true", "accurate", "correct"]):
                    sentiments["positive"] += 1
                elif any(word in analysis for word in ["false", "incorrect", "lie"]):
                    sentiments["negative"] += 1
                else:
                    sentiments["neutral"] += 1

        return {
            "agent_confidences": agent_confidences,
            "sentiment_distribution": sentiments,
            "consensus_score": evaluation["consensus_level"],
            "verdict": evaluation["synthesis"]["verdict"].value
        }
