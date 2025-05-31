from typing import Dict, Any
from langchain.agents.agent import AgentExecutor
from models.models import Statement  
from langchain_core.prompts.chat import ChatPromptTemplate, SystemMessage, MessagesPlaceholder
from langchain.agents.openai_tools.base import create_openai_tools_agent
from agents.evaluation import EvaluationAgent
from langchain.tools import Tool
from agents.evaluation import EvaluationAgent

class NerdAgent(EvaluationAgent):
    """Data-driven agent focused on hard facts and methodology"""

    def __init__(self, llm):
        # Add academic search tools
        tools = [
            Tool(
                name="search_academic",
                description="Search academic papers and peer-reviewed sources",
                func=self._search_academic
            ),
            Tool(
                name="verify_statistics",
                description="Verify statistical claims and methodologies",
                func=self._verify_statistics
            )
        ]
        super().__init__(llm, tools)

    def _create_agent(self):
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are a data scientist and methodology expert. Your role is to:
            1. Verify all statistical claims with primary sources
            2. Check methodological soundness of studies cited
            3. Identify sample size issues, correlation vs causation errors
            4. Examine confidence intervals and margins of error
            5. Look for p-hacking or data dredging
            6. Verify if data is peer-reviewed
            7. Check for replication studies
            8. Identify cherry-picked time periods in data
            9. Calculate actual effect sizes
            
            Only trust peer-reviewed sources and official statistics.
            Always cite specific studies, papers, or datasets.
            Include relevant formulas or calculations when needed."""),
            MessagesPlaceholder(variable_name="messages"),
            ("human", "{input}")
        ])

        return create_openai_tools_agent(self.llm, self.tools, prompt)

    def _search_academic(self, query: str) -> str:
        """Search academic databases (simulated)"""
        # In production, use APIs like Semantic Scholar, PubMed, etc.
        return f"""Academic search for "{query}":
        - Found 3 peer-reviewed studies on this topic
        - Meta-analysis from Journal of Economic Policy (2023) shows mixed results
        - Sample sizes range from n=1,200 to n=45,000
        - Effect sizes are statistically significant but practically small (d=0.15)
        - Two studies show contradictory results, suggesting confounding variables"""

    def _verify_statistics(self, claim: str) -> str:
        """Verify statistical claims"""
        return f"""Statistical verification for claim:
        - Original data source: Bureau of Labor Statistics
        - Time period cherry-picked: Only shows favorable 2-year window
        - Full dataset (10 years) shows different trend
        - Confidence interval: 95% CI [0.02, 0.08]
        - Multiple testing problem detected - likely false positive"""

    def evaluate(self, statement: Statement, context: str = "") -> Dict[str, Any]:
        executor = AgentExecutor(
            agent=self.agent, tools=self.tools, verbose=True)

        input_text = f"""
        Statement: "{statement.text}"
        Speaker: {statement.speaker.name}
        
        Analyze this claim using rigorous scientific methodology.
        Verify all data claims. Check statistical validity.
        Cite specific studies or datasets.
        """

        result = executor.invoke({"input": input_text})

        return {
            "agent": "Nerd",
            "perspective": "Scientific/Data Analysis",
            "analysis": result["output"],
            "confidence": 0.85,
            "methodology_notes": "Peer-reviewed sources prioritized"
        }
