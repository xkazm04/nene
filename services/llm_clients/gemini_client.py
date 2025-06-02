import os
import json
import logging
import google.generativeai as genai
from models.research_models import LLMResearchRequest, LLMResearchResponse
from services.llm_clients.base_client import BaseLLMClient
from utils.response_parser import ResponseParser
from utils.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)

class GeminiClient(BaseLLMClient):
    """Gemini client for fact-checking research with internet search capabilities."""
    
    def __init__(self):
        try:
            self.google_api_key = os.environ['GOOGLE_API_KEY']
            genai.configure(api_key=self.google_api_key)
            self.gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest')
            logger.info("Gemini client initialized successfully")
        except KeyError:
            logger.warning("GOOGLE_API_KEY not found - Gemini client unavailable")
            self.gemini_model = None
        except Exception as e:
            logger.warning(f"Could not initialize Gemini: {e}")
            self.gemini_model = None
    
    def is_available(self) -> bool:
        """Check if Gemini client is available."""
        return self.gemini_model is not None
    
    def get_client_name(self) -> str:
        """Get client name."""
        return "Gemini (Fallback - Internet Search)"
    
    def research_statement(self, request: LLMResearchRequest) -> LLMResearchResponse:
        """Research using Gemini with internet search capabilities."""
        if not self.is_available():
            raise Exception("Gemini client not available")
        
        logger.debug("Starting Gemini research")
        
        # Build enhanced prompt for Gemini
        prompt_builder = PromptBuilder()
        gemini_prompt = prompt_builder.get_gemini_prompt(request)
        
        # Generate content with Gemini
        response = self.gemini_model.generate_content(gemini_prompt)
        
        if not response or not response.text:
            raise Exception("Empty response from Gemini")
        
        # Extract JSON from response
        json_str = self._extract_json_from_response(response.text)
        
        try:
            parsed_response = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON response from Gemini: {e}")
        
        # Create response object
        parser = ResponseParser()
        result = parser.create_response_object(parsed_response, request)
        result.research_method = self.get_client_name()
        
        return result
    
    def _extract_json_from_response(self, response_text: str) -> str:
        """Extract JSON object from Gemini response text."""
        response_text = response_text.strip()
        
        # Find JSON object in response
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1
        
        if start_idx == -1 or end_idx == 0:
            raise Exception("No JSON object found in Gemini response")
        
        return response_text[start_idx:end_idx]