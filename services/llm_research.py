import os
import logging
from typing import List, Literal, Optional
from enum import Enum
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
import json
import google.generativeai as genai
from prompts.fc_prompt import factcheck_prompt
from models.research_models import LLMResearchRequest, LLMResearchResponse
from services.llm_clients.groq_client import GroqLLMClient
from services.llm_clients.gemini_client import GeminiClient
from services.response_parser import ResponseParser

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

class StatementCategory(str, Enum):
    """Categories for statement classification."""
    POLITICS = "politics"
    ECONOMY = "economy"
    ENVIRONMENT = "environment"
    MILITARY = "military"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    TECHNOLOGY = "technology"
    SOCIAL = "social"
    INTERNATIONAL = "international"
    OTHER = "other"

class ExpertOpinion(BaseModel):
    critic: Optional[str] = None
    devil: Optional[str] = None
    nerd: Optional[str] = None
    psychic: Optional[str] = None

class ResourceReference(BaseModel):
    url: str
    title: str
    category: Literal["mainstream", "governance", "academic", "medical", "other"]
    country: str
    credibility: Literal["high", "medium", "low"]

class ResourceAnalysis(BaseModel):
    total: str  # e.g., "85%"
    count: int
    mainstream: int = 0
    governance: int = 0
    academic: int = 0
    medical: int = 0
    other: int = 0
    major_countries: List[str] = []
    references: List[ResourceReference] = []

class LlmResearchService:
    """Main research service that coordinates multiple LLM clients."""
    
    def __init__(self):
        """Initialize all available LLM clients."""
        self.clients = [
            GroqLLMClient(),
            GeminiClient()
        ]
        
        # Filter to only available clients
        self.available_clients = [client for client in self.clients if client.is_available()]
        
        if not self.available_clients:
            raise ValueError("No LLM clients are available. Please check your API keys.")
        
        self.response_parser = ResponseParser()
        
        client_names = [client.get_client_name() for client in self.available_clients]
        logger.info(f"Research service initialized with clients: {', '.join(client_names)}")
    
    def research_statement(self, request: LLMResearchRequest) -> LLMResearchResponse:
        """
        Research a statement using available LLM clients with fallback strategy.

        Args:
            request: Research request with statement, source, context, country, and category

        Returns:
            LLMResearchResponse: Fact-check result with verdict and resources

        Raises:
            Exception: If all research methods fail
        """
        try:
            logger.info(f"Starting research for statement: {request.statement[:100]}...")
            logger.info(f"Country: {request.country}, Category: {request.category}")
            
            last_exception = None
            
            # Try each client in order
            for i, client in enumerate(self.available_clients):
                try:
                    logger.debug(f"Attempting research with {client.get_client_name()}")
                    result = client.research_statement(request)
                    
                    # If primary client gives definitive answer, return it
                    # If fallback client, return any result
                    if i == 0 and result.status != "UNVERIFIABLE":
                        logger.info(f"Primary client successful with status: {result.status}")
                        return result
                    elif i > 0:
                        logger.info(f"Fallback client successful with status: {result.status}")
                        return result
                    else:
                        logger.info(f"Primary client returned UNVERIFIABLE, trying fallback...")
                        last_result = result
                        continue
                        
                except Exception as e:
                    last_exception = e
                    logger.warning(f"{client.get_client_name()} failed: {e}")
                    continue
            
            # If we get here, all clients failed or returned UNVERIFIABLE
            if 'last_result' in locals():
                last_result.research_method += " (All Fallbacks Failed)"
                return last_result
            else:
                # Create error response
                error_message = f"All research methods failed. Last error: {last_exception}"
                logger.error(error_message)
                return self.response_parser.create_error_response(request, "All Services Failed")
                
        except Exception as e:
            error_msg = f"Complete research failure: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)

# Create service instance
llm_research_service = LlmResearchService()
