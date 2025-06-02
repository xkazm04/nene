import os
import json
import logging
from typing import Optional
from openai import OpenAI
from models.research_models import LLMResearchRequest, LLMResearchResponse
from services.llm_clients.base_client import BaseLLMClient
from services.response_parser import ResponseParser
from services.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)

class GroqLLMClient(BaseLLMClient):
    """Groq LLM client for fact-checking research."""
    
    def __init__(self):
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.llm_model = "meta-llama/llama-4-scout-17b-16e-instruct"
        
        if self.groq_api_key:
            self.llm_client = OpenAI(
                api_key=self.groq_api_key,
                base_url="https://api.groq.com/openai/v1"
            )
            logger.info("Groq LLM client initialized successfully")
        else:
            logger.warning("GROQ_API_KEY not found - Groq client unavailable")
            self.llm_client = None
    
    def is_available(self) -> bool:
        """Check if Groq client is available."""
        return self.llm_client is not None
    
    def get_client_name(self) -> str:
        """Get client name."""
        return "Groq LLM (Primary)"
    
    def research_statement(self, request: LLMResearchRequest) -> LLMResearchResponse:
        """Research using Groq LLM (training data based)."""
        if not self.is_available():
            raise Exception("Groq LLM client not available")
        
        logger.debug("Starting Groq LLM research")
        
        # Build prompts
        prompt_builder = PromptBuilder()
        system_prompt = prompt_builder.get_system_prompt()
        user_prompt = prompt_builder.get_user_prompt(request)
        
        # Call LLM API
        response = self.llm_client.chat.completions.create(
            model=self.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=2500,
            response_format={"type": "json_object"}
        )
        
        # Parse the response
        response_content = response.choices[0].message.content
        try:
            parsed_response = json.loads(response_content)
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON response from Groq LLM: {e}")
        
        # Create response object
        parser = ResponseParser()
        result = parser.create_response_object(parsed_response, request)
        result.research_method = self.get_client_name()
        
        return result