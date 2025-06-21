import logging
import os
import asyncio
from typing import Optional
from groq import Groq

from models.research_models import LLMResearchRequest, LLMResearchResponse
from utils.response_parser import ResponseParser

logger = logging.getLogger(__name__)

class GroqLLMClient:
    """
    Enhanced Groq LLM client with unified interface
    """
    
    def __init__(self):
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            logger.warning("GROQ_API_KEY not found - Groq client unavailable")
            self.client = None
        else:
            try:
                self.client = Groq(api_key=api_key)
                logger.info("Groq client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Groq client: {e}")
                self.client = None
    
    def is_available(self) -> bool:
        """Check if client is available"""
        return self.client is not None
    
    def get_client_name(self) -> str:
        """Get client name"""
        return "Groq LLM (Primary)"
    
    # ===== UNIFIED INTERFACE METHODS =====
    
    async def generate_response(self, prompt: str) -> str:
        """
        Generate response from prompt - unified interface method
        
        Args:
            prompt: The prompt to send to Groq
            
        Returns:
            Raw response text from Groq
        """
        if not self.client:
            raise Exception("Groq client not available")
        
        try:
            logger.info("Generating Groq response...")
            
            response = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                temperature=0.1,
                max_tokens=14000,
                top_p=0.9,
                stream=False
            )
            
            if response and response.choices and response.choices[0].message:
                content = response.choices[0].message.content
                logger.info(f"Groq response generated successfully ({len(content)} chars)")
                return content
            else:
                raise Exception("Empty response from Groq")
                
        except Exception as e:
            logger.error(f"Groq response generation failed: {e}")
            raise
    
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
        try:
            logger.info(f"Groq research for statement: {request.statement[:100]}...")
            
            if not self.client:
                raise Exception("Groq client not available")
            
            # Generate prompt
            if custom_prompt_builder:
                prompt = custom_prompt_builder.build_prompt(request)
                logger.info("Using custom prompt builder")
            else:
                # Use default prompt manager
                from prompts.fc_prompt import prompt_manager
                prompt = prompt_manager.get_enhanced_factcheck_prompt(
                    statement=request.statement,
                    source=request.source,
                    context=request.context,
                    country=request.country,
                    category=request.category
                )
                logger.info("Using default fact-check prompt")
            
            # Generate response
            loop = asyncio.get_event_loop()
            response_text = loop.run_until_complete(self.generate_response(prompt))
            
            # Parse response
            parser = ResponseParser()
            parsed_result = parser.parse_llm_response(response_text)
            
            # Set research method
            parsed_result.research_method = "groq_llm"
            
            logger.info("Groq research completed successfully")
            return parsed_result
            
        except Exception as e:
            logger.error(f"Groq research failed: {e}")
            # Create error response
            parser = ResponseParser()
            return parser.create_error_response(request, f"Groq research failed: {str(e)}")
    
    def research_metadata(
        self, 
        request: LLMResearchRequest, 
        custom_prompt_builder: Optional[object] = None
    ) -> dict:
        """
        Extract research metadata using Groq LLM.
        
        Args:
            request: LLM research request
            custom_prompt_builder: Optional custom prompt builder
            
        Returns:
            Dictionary with extracted metadata
        """
        try:
            logger.info(f"Groq metadata extraction for: {request.statement[:100]}...")
            
            if not self.client:
                raise Exception("Groq client not available")
            
            # Build metadata extraction prompt
            if custom_prompt_builder and hasattr(custom_prompt_builder, 'build_metadata_prompt'):
                prompt = custom_prompt_builder.build_metadata_prompt(request)
            else:
                prompt = f"""
                Analyze this statement and extract metadata in JSON format:
                
                Statement: "{request.statement}"
                Source: {request.source}
                Context: {request.context}
                
                Extract and return ONLY a JSON object with:
                {{
                    "confidence_score": 0-100,
                    "complexity_level": "low|medium|high",
                    "verification_difficulty": "easy|moderate|difficult",
                    "primary_topics": ["topic1", "topic2", "topic3"],
                    "requires_web_research": true/false,
                    "estimated_processing_time": "quick|normal|extended"
                }}
                
                JSON only, no explanation:
                """
            
            # Generate response
            loop = asyncio.get_event_loop()
            response_text = loop.run_until_complete(self.generate_response(prompt))
            
            # Parse JSON response
            import json
            try:
                metadata = json.loads(response_text.strip())
                logger.info("Groq metadata extraction completed successfully")
                return metadata
            except json.JSONDecodeError:
                logger.warning("Failed to parse metadata JSON, returning defaults")
                return {
                    "confidence_score": 50,
                    "complexity_level": "medium",
                    "verification_difficulty": "moderate",
                    "primary_topics": ["general"],
                    "requires_web_research": True,
                    "estimated_processing_time": "normal"
                }
                
        except Exception as e:
            logger.error(f"Groq metadata extraction failed: {e}")
            return {
                "confidence_score": 50,
                "complexity_level": "unknown",
                "verification_difficulty": "unknown",
                "primary_topics": ["error"],
                "requires_web_research": False,
                "estimated_processing_time": "error"
            }

# Create client instance
groq_client = GroqLLMClient()