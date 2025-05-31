from typing import Dict, Any
from langchain.agents.agent import AgentExecutor
from models.models import Statement  
from langchain_core.prompts.chat import ChatPromptTemplate, SystemMessage, MessagesPlaceholder
from langchain.agents.openai_tools.base import create_openai_tools_agent
from agents.evaluation import EvaluationAgent
class ConspiratorAgent(EvaluationAgent):
    """Critical agent that looks for manipulation and gaps"""
    
    def _create_agent(self):
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are a critical analyst who uncovers manipulation tactics and hidden agendas. Your role is to:
            1. Identify emotional manipulation techniques
            2. Find what's NOT being said (lies by omission)
            3. Detect cherry-picked data or timeframes
            4. Uncover potential conflicts of interest
            5. Analyze who benefits from this narrative
            6. Look for gaslighting or misdirection tactics
            7. Question the timing of statements
            8. Identify strawman arguments or false dichotomies
            
            Be highly skeptical but base your analysis on logical reasoning.
            Point out manipulation tactics by name when you spot them."""),
            MessagesPlaceholder(variable_name="messages"),
            ("human", "{input}")
        ])
        
        return create_openai_tools_agent(self.llm, self.tools, prompt)
    
    def evaluate(self, statement: Statement, context: str = "") -> Dict[str, Any]:
        executor = AgentExecutor(agent=self.agent, tools=self.tools, verbose=True)
        
        input_text = f"""
        Statement: "{statement.text}"
        Speaker: {statement.speaker.name} ({statement.speaker.role})
        Context: {context}
        
        Analyze this critically. What manipulation tactics might be at play?
        What's being hidden or distorted? Who benefits from this narrative?
        """
        
        result = executor.invoke({"input": input_text})
        
        return {
            "agent": "Conspirator",
            "perspective": "Critical/Skeptical Analysis",
            "analysis": result["output"],
            "confidence": 0.7,
            "warnings": ["High skepticism applied", "Look for hidden agendas"]
        }