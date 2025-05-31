from typing import Dict, Any
from langchain.agents.agent import AgentExecutor
from models.models import Statement  
from langchain_core.prompts.chat import ChatPromptTemplate, SystemMessage, MessagesPlaceholder
from langchain.agents.openai_tools.base import create_openai_tools_agent
from agents.evaluation import EvaluationAgent
from langchain.tools import Tool
from agents.evaluation import EvaluationAgent
class FactCheckDatabaseAgent(EvaluationAgent):
    """Agent with access to fact-checking databases"""
    
    def __init__(self, llm):
        # Initialize fact-checking API tools
        tools = [
            Tool(
                name="politifact_search",
                description="Search PolitiFact database for fact-checks",
                func=self._search_politifact
            ),
            Tool(
                name="snopes_search",
                description="Search Snopes for fact-checks",
                func=self._search_snopes
            ),
            Tool(
                name="factcheckorg_search",
                description="Search FactCheck.org database",
                func=self._search_factcheckorg
            )
        ]
        super().__init__(llm, tools)
    
    def _create_agent(self):
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are a fact-checking database specialist. Your role is to:
            1. Search established fact-checking databases (PolitiFact, Snopes, FactCheck.org)
            2. Find previous fact-checks of similar claims
            3. Identify patterns in political rhetoric
            4. Cross-reference multiple fact-checking sources
            5. Report findings from authoritative fact-checkers
            
            Always cite which fact-checking organization provided the information.
            If no direct match is found, look for similar claims or patterns."""),
            MessagesPlaceholder(variable_name="messages"),
            ("human", "{input}")
        ])
        
        return create_openai_tools_agent(self.llm, self.tools, prompt)
    
    def _search_politifact(self, query: str) -> str:
        """Search PolitiFact API (simulated)"""
        # In production, use actual PolitiFact API
        # This is a simulation of what the API might return
        
        try:
            # Simulated API call
            base_url = "https://www.politifact.com/api/v2/statement/"
            
            # In reality, you'd make an actual API request here
            # response = requests.get(base_url, params={"q": query})
            
            # Simulated response
            return f"""PolitiFact search results for "{query}":
            - Found 3 similar claims previously fact-checked
            - 2 rated as "Mostly False" due to missing context
            - 1 rated as "Half True" with important caveats
            - Common pattern: This type of claim often cherry-picks data"""
            
        except Exception as e:
            return f"PolitiFact search error: {str(e)}"
    
    def _search_snopes(self, query: str) -> str:
        """Search Snopes (web scraping or API if available)"""
        # Simulated Snopes search
        return f"""Snopes search results for "{query}":
        - Found related fact-check from 2023
        - Rating: "Mixture" - contains elements of truth but misleading overall
        - Key context: The timeframe and methodology matter significantly"""
    
    def _search_factcheckorg(self, query: str) -> str:
        """Search FactCheck.org"""
        # Simulated search
        return f"""FactCheck.org results for "{query}":
        - Previous analysis found this claim lacks important context
        - Statistical manipulation detected in similar claims
        - Recommended checking original data sources"""
    
    def evaluate(self, statement: Statement, context: str = "") -> Dict[str, Any]:
        executor = AgentExecutor(agent=self.agent, tools=self.tools, verbose=True)
        
        input_text = f"""
        Statement: "{statement.text}"
        Speaker: {statement.speaker.name} ({statement.speaker.role})
        Context: {context}
        
        Search fact-checking databases for this claim or similar ones.
        Provide findings from established fact-checkers.
        """
        
        result = executor.invoke({"input": input_text})
        
        return {
            "agent": "FactCheckDatabase",
            "perspective": "Established Fact-Checker Findings",
            "analysis": result["output"],
            "confidence": 0.9,  # High confidence when found in databases
            "sources": ["PolitiFact", "Snopes", "FactCheck.org"]
        }
