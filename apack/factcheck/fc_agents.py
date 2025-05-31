import json
import logging
from typing import List

from helpers.model_management import get_llm_model
from helpers.response_parser import extract_json_from_text
from schemas.fc_schemas import AgentAnalysis, ResearchData, FactCheckConfig
from prompts.fc_prompts import get_agent_prompts

logger = logging.getLogger(__name__)


class FactCheckAgent:
    """Individual fact-checking agent"""
    
    def __init__(self, agent_name: str, prompt: str, llm):
        self.agent_name = agent_name
        self.prompt = prompt
        self.llm = llm
    
    def analyze(self, research_data: ResearchData) -> AgentAnalysis:
        """Run this agent's analysis on the research data"""
        try:
            formatted_prompt = self.prompt.format(
                statement=research_data.statement,
                speaker=research_data.speaker,
                context=json.dumps(research_data.context),
                research_summary=research_data.summary
            )
            
            logger.info(f"Running {self.agent_name} analysis")
            response = self.llm.invoke(formatted_prompt)
            
            # Extract content if it's a response object
            if hasattr(response, 'content'):
                response_text = response.content
            else:
                response_text = str(response)
            
            # Try to parse JSON response
            analysis_dict = self._parse_agent_response(response_text)
            
            # Validate required fields
            analysis_dict = self._validate_and_fix_response(analysis_dict)
            
            return AgentAnalysis(**analysis_dict)
            
        except Exception as e:
            logger.error(f"Error in {self.agent_name} analysis: {e}")
            return self._create_error_analysis(str(e))
    
    def _parse_agent_response(self, response_text: str) -> dict:
        """Parse agent response, trying multiple methods"""
        
        # Try direct JSON parsing first
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass
        
        # Try extracting JSON from text
        extracted_json = extract_json_from_text(response_text)
        if extracted_json and len(extracted_json) > 0:
            return extracted_json[0]
        
        # Try finding JSON in the response
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # If all else fails, create a structured response from the text
        return self._create_fallback_response(response_text)
    
    def _create_fallback_response(self, response_text: str) -> dict:
        """Create a structured response when JSON parsing fails"""
        return {
            "agent_name": self.agent_name,
            "perspective": f"{self.agent_name.title()} perspective",
            "analysis": response_text,
            "confidence_score": 0.5,
            "key_findings": ["Unable to parse structured response"],
            "supporting_evidence": [],
            "verdict": "UNVERIFIABLE",
            "reasoning": "Response could not be parsed into structured format"
        }
    
    def _validate_and_fix_response(self, analysis_dict: dict) -> dict:
        """Validate and fix common issues in agent responses"""
        
        # Ensure required fields exist
        required_fields = {
            "agent_name": self.agent_name,
            "perspective": f"{self.agent_name.title()} perspective",
            "analysis": "No analysis provided",
            "confidence_score": 0.5,
            "key_findings": [],
            "supporting_evidence": [],
            "verdict": "UNVERIFIABLE",
            "reasoning": "No reasoning provided"
        }
        
        for field, default_value in required_fields.items():
            if field not in analysis_dict:
                analysis_dict[field] = default_value
        
        # Validate confidence score
        try:
            confidence = float(analysis_dict["confidence_score"])
            analysis_dict["confidence_score"] = max(0.0, min(1.0, confidence))
        except (ValueError, TypeError):
            analysis_dict["confidence_score"] = 0.5
        
        # Validate verdict
        valid_verdicts = ["TRUE", "FALSE", "MISLEADING", "PARTIALLY_TRUE", "UNVERIFIABLE"]
        if analysis_dict["verdict"] not in valid_verdicts:
            analysis_dict["verdict"] = "UNVERIFIABLE"
        
        # Ensure lists are actually lists
        if not isinstance(analysis_dict["key_findings"], list):
            analysis_dict["key_findings"] = []
        
        if not isinstance(analysis_dict["supporting_evidence"], list):
            analysis_dict["supporting_evidence"] = []
        
        return analysis_dict
    
    def _create_error_analysis(self, error_message: str) -> AgentAnalysis:
        """Create an error analysis when the agent fails"""
        return AgentAnalysis(
            agent_name=self.agent_name,
            perspective=f"Error in {self.agent_name} analysis",
            analysis=f"Analysis failed due to error: {error_message}",
            confidence_score=0.0,
            key_findings=[f"Agent {self.agent_name} encountered an error"],
            supporting_evidence=[],
            verdict="UNVERIFIABLE",
            reasoning=f"Error occurred during analysis: {error_message}"
        )


class FactCheckAgentManager:
    """Manages multiple fact-checking agents"""
    
    def __init__(self, config: FactCheckConfig):
        self.config = config
        self.llm = get_llm_model(config.model_name)
        self.agents = self._create_agents()
    
    def _create_agents(self) -> List[FactCheckAgent]:
        """Create all fact-checking agents"""
        agent_prompts = get_agent_prompts()
        agents = []
        
        for agent_name, prompt in agent_prompts.items():
            agent = FactCheckAgent(agent_name, prompt, self.llm)
            agents.append(agent)
        
        logger.info(f"Created {len(agents)} fact-checking agents")
        return agents
    
    def run_all_analyses(self, research_data: ResearchData) -> List[AgentAnalysis]:
        """Run all agent analyses on the research data"""
        analyses = []
        
        for agent in self.agents:
            try:
                analysis = agent.analyze(research_data)
                analyses.append(analysis)
                logger.info(f"{agent.agent_name} analysis completed")
            except Exception as e:
                logger.error(f"Failed to run {agent.agent_name} analysis: {e}")
                # Add error analysis
                error_analysis = agent._create_error_analysis(str(e))
                analyses.append(error_analysis)
        
        logger.info(f"Completed {len(analyses)} agent analyses")
        return analyses
    
    def add_custom_agent(self, agent_name: str, prompt: str):
        """Add a custom agent with a specific prompt"""
        agent = FactCheckAgent(agent_name, prompt, self.llm)
        self.agents.append(agent)
        logger.info(f"Added custom agent: {agent_name}")


def create_agent_manager(config: FactCheckConfig = None) -> FactCheckAgentManager:
    """Factory function to create an agent manager"""
    if config is None:
        config = FactCheckConfig()
    
    return FactCheckAgentManager(config)