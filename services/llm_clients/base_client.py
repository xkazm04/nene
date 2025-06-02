import os
import logging
from abc import ABC, abstractmethod
from typing import Optional
from dotenv import load_dotenv
from models.research_models import LLMResearchRequest, LLMResearchResponse

load_dotenv()
logger = logging.getLogger(__name__)

class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""
    
    @abstractmethod
    def research_statement(self, request: LLMResearchRequest) -> LLMResearchResponse:
        """Research a statement and return fact-check results."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the client is properly configured and available."""
        pass
    
    @abstractmethod
    def get_client_name(self) -> str:
        """Get a human-readable name for this client."""
        pass