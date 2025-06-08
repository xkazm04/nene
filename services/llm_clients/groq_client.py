import os
import json
import logging
from typing import Optional
from openai import OpenAI
from models.research_models import LLMResearchRequest, LLMResearchResponse
from services.llm_clients.base_client import BaseLLMClient
from utils.response_parser import ResponseParser
from utils.prompt_builder import PromptBuilder

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
    
    def research_statement(
        self, 
        request: LLMResearchRequest, 
        custom_prompt_builder: Optional[object] = None
    ) -> LLMResearchResponse:
        """
        Research using Groq LLM with configurable prompt builder.
        
        Args:
            request: LLM research request
            custom_prompt_builder: Optional custom prompt builder for specialized use cases
            
        Returns:
            LLM research response
        """
        if not self.is_available():
            raise Exception("Groq LLM client not available")
        
        logger.debug("Starting Groq LLM research")
        
        # Use custom prompt builder if provided, otherwise use default
        if custom_prompt_builder:
            system_prompt = getattr(custom_prompt_builder, 'get_system_prompt', lambda: "You are a helpful AI assistant.")()
            user_prompt = getattr(custom_prompt_builder, 'get_user_prompt', lambda x: request.context or request.statement)(request)
        else:
            # Default fact-checking prompt builder
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
        
        # Create response object - handle both fact-checking and metadata responses
        if custom_prompt_builder:
            # For custom use cases (like metadata), return raw parsed response
            # wrapped in a basic LLMResearchResponse structure
            result = LLMResearchResponse(
                valid_sources="Custom research completed",
                verdict=json.dumps(parsed_response),  # Store JSON in verdict for parsing
                status="VERIFIED",
                research_method=f"{self.get_client_name()} (Custom)",
                profile_id=request.profile_id
            )
        else:
            # Default fact-checking response parsing
            parser = ResponseParser()
            result = parser.create_response_object(parsed_response, request)
            result.research_method = self.get_client_name()
        
        return result
    
    def research_metadata(
        self, 
        name: str, 
        category: str, 
        subcategory: str, 
        custom_prompt: str
    ) -> dict:
        """
        Specialized method for metadata research with direct JSON response.
        
        Args:
            name: Item name
            category: Item category  
            subcategory: Item subcategory
            custom_prompt: Custom prompt for metadata extraction
            
        Returns:
            Parsed JSON response directly
        """
        if not self.is_available():
            raise Exception("Groq LLM client not available")
        
        logger.debug(f"Starting Groq metadata research for: {name}")
        
        system_prompt = """You are a metadata research assistant. 
        Provide ONLY factual information in valid JSON format. 
        Use null for uncertain data. Be accurate and concise."""
        
        # Call LLM API
        response = self.llm_client.chat.completions.create(
            model=self.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": custom_prompt}
            ],
            temperature=0.1,
            max_tokens=1500,
            response_format={"type": "json_object"}
        )
        
        # Parse and return JSON directly
        response_content = response.choices[0].message.content
        try:
            return json.loads(response_content)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from Groq LLM for metadata: {e}")
            return {}