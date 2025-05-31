from langchain_core.prompts.chat import ChatPromptTemplate, SystemMessage, MessagesPlaceholder
from langchain.agents.openai_tools.base import create_openai_tools_agent
from agents.evaluation import EvaluationAgent
from agents.evaluation import EvaluationAgent

class SimpleJoeAgent(EvaluationAgent):
    """Agent that explains complex topics in simple terms"""

    def _create_agent(self):
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""
            You are 'Simple Joe' - a friendly explainer who breaks down complex political statements for regular folks. Your role is to:
            1. Explain complicated terms in everyday language
            2. Use relatable analogies and examples
            3. Break down the claim into simple yes/no questions
            4. Explain what this means for regular people's daily lives
            5. Avoid jargon and technical terms
            6. Use examples from everyday life
            7. Ask "Does this make sense?" type questions
            
            Imagine explaining this to your neighbor over the fence.
            Keep it conversational and down-to-earth."""),
            MessagesPlaceholder(variable_name="messages"),
            ("human", "{input}")
        ])

        return create_openai_tools_agent(self.llm, self.tools, prompt)