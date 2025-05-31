from langchain.agents import initialize_agent, AgentType
from langchain_community.tools import DuckDuckGoSearchRun
from typing import Any

def create_search_agent(llm: Any, verbose: bool = False):
    """
    Create a search agent with DuckDuckGo search capability.
    
    Args:
        llm: Language model instance
        verbose: Whether to enable verbose output
    
    Returns:
        Initialized agent with search tools
    """
    
    tools = [DuckDuckGoSearchRun()]
    
    agent = initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=verbose
    )
    
    return agent


def create_custom_agent(llm: Any, tools: list, agent_type: str = "zero_shot", verbose: bool = False):
    """
    Create a custom agent with specified tools.
    
    Args:
        llm: Language model instance
        tools: List of tools to provide to the agent
        agent_type: Type of agent to create
        verbose: Whether to enable verbose output
    
    Returns:
        Initialized agent
    """
    
    agent_types = {
        "zero_shot": AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        "conversational": AgentType.CONVERSATIONAL_REACT_DESCRIPTION,
        "structured": AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION
    }
    
    selected_type = agent_types.get(agent_type, AgentType.ZERO_SHOT_REACT_DESCRIPTION)
    
    return initialize_agent(
        tools=tools,
        llm=llm,
        agent=selected_type,
        verbose=verbose
    )