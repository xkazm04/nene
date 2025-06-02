import logging
from services.llm_clients.groq_client import GroqLLMClient
from services.llm_clients.gemini_client import GeminiClient
from utils.response_parser import ResponseParser
from models.research_models import LLMResearchRequest, LLMResearchResponse

logger = logging.getLogger(__name__)

class UnifiedLLMResearchService:
    def __init__(self):
        self.groq_client = GroqLLMClient()
        self.gemini_client = GeminiClient()
        self.parser = ResponseParser() # Used for creating standardized error responses
        logger.info("UnifiedLLMResearchService initialized.")
        if not self.groq_client.is_available() and not self.gemini_client.is_available():
            logger.warning("No LLM clients (Groq or Gemini) are available.")

    def research_statement(self, request: LLMResearchRequest) -> LLMResearchResponse:
        try:
            if self.groq_client.is_available():
                logger.info("Using Groq LLM client for research.")
                return self.groq_client.research_statement(request)
            elif self.gemini_client.is_available():
                logger.info("Groq client unavailable, falling back to Gemini client for research.")
                return self.gemini_client.research_statement(request)
            else:
                logger.error("No LLM clients are available to handle the research request.")
                # Ensure research_method is set in error responses if your models expect it
                error_response = self.parser.create_error_response(request, "No LLM clients available")
                error_response.research_method = "N/A - No Client"
                return error_response
        except Exception as e:
            logger.error(f"Error during LLM research: {e}", exc_info=True)
            error_response = self.parser.create_error_response(request, f"LLM research failed: {str(e)}")
            error_response.research_method = "N/A - Exception"
            return error_response

# Instantiate the service
# This instance will be imported by other modules.
llm_research_service = UnifiedLLMResearchService()