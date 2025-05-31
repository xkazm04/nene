import os
import logging
from typing import List, Optional
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
import json
load_dotenv()

logger = logging.getLogger(__name__)

class TranscriptionAnalysisInput(BaseModel):
    language_code: str = "eng"
    speaker: str
    context: str
    transcription: str

class FactCheckStatement(BaseModel):
    statement: str

class TranscriptionAnalysisResult(BaseModel):
    statements: List[FactCheckStatement]
    total_statements: int
    analysis_summary: str

class LLMTranscriptionAnalysisService:
    def __init__(self):
        """Initialize OpenAI client with API key from environment."""
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        groq_client = OpenAI(api_key=self.groq_api_key, base_url="https://api.groq.com/openai/v1")
        openai_client = OpenAI(api_key=self.api_key)
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        self.client = groq_client
        # self.model = "gpt-4.1-mini"  
        self.model = "meta-llama/llama-4-scout-17b-16e-instruct"
        logger.info("LLM Transcription Analysis service initialized successfully")
    
    def analyze_transcription(self, input_data: TranscriptionAnalysisInput) -> TranscriptionAnalysisResult:
        """
        Analyze transcription for political statements worthy of fact-checking.
        
        Args:
            input_data: Transcription analysis input containing speaker, context, and transcription
            
        Returns:
            TranscriptionAnalysisResult: List of statements identified for fact-checking
            
        Raises:
            Exception: If analysis fails
        """
        try:
            logger.info(f"Starting transcription analysis for speaker: {input_data.speaker}")
            logger.info(f"Context: {input_data.context}")
            logger.info(f"Transcription length: {len(input_data.transcription)} characters")
            
            # Construct the analysis prompt
            system_prompt = self._get_system_prompt()
            user_prompt = self._get_user_prompt(input_data)
            
            logger.debug("Sending request to OpenAI API")
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # Low temperature for more consistent results
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            
            logger.info("Successfully received response from OpenAI API")
            
            # Parse the response
            response_content = response.choices[0].message.content
            logger.debug(f"Raw response: {response_content[:200]}...")
            
            try:
                parsed_response = json.loads(response_content)
                logger.info(f"Successfully parsed JSON response")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                raise Exception(f"Invalid JSON response from OpenAI: {e}")
            
            # Extract statements and create result
            statements_data = parsed_response.get("statements", [])
            statements = [FactCheckStatement(statement=stmt["statement"]) for stmt in statements_data]
            
            analysis_summary = parsed_response.get("analysis_summary", "Analysis completed")
            
            result = TranscriptionAnalysisResult(
                statements=statements,
                total_statements=len(statements),
                analysis_summary=analysis_summary
            )
            
            logger.info(f"Analysis completed successfully")
            logger.info(f"Identified {len(statements)} statements for fact-checking")
            logger.info(f"Analysis summary: {analysis_summary}")
            
            return result
            
        except Exception as e:
            error_msg = f"Failed to analyze transcription with OpenAI: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Error type: {type(e).__name__}")
            raise Exception(error_msg)
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for the LLM analysis."""
        return """You are a professional fact-checking analyst specializing in identifying political statements that warrant verification.

Your task is to analyze political transcriptions and extract specific factual claims that can be objectively verified or debunked.

CRITERIA for statements worthy of fact-checking:
- Specific numerical claims (statistics, percentages, dates, amounts)
- Historical facts or events
- Policy claims with measurable outcomes
- Comparative statements about economic/social indicators
- Claims about other people's actions or statements
- Verifiable cause-and-effect relationships

DO NOT include:
- Personal opinions or subjective statements
- Future predictions or promises
- Rhetorical questions
- General political rhetoric without specific claims
- Statements that are purely emotional or motivational
- Vague statements without specific details

RESPONSE FORMAT:
Return a JSON object with this exact structure:
{
    "statements": [
        {"statement": "exact quote from transcription"},
        {"statement": "another exact quote from transcription"}
    ],
    "analysis_summary": "Brief summary of the analysis and number of fact-checkable statements found"
}

Extract statements as exact quotes from the original transcription. Be selective and focus only on statements with clear factual claims that can be researched and verified."""

    def _get_user_prompt(self, input_data: TranscriptionAnalysisInput) -> str:
        """Get the user prompt with the specific transcription data."""
        return f"""Please analyze the following political transcription for fact-checkable statements:

SPEAKER: {input_data.speaker}
CONTEXT: {input_data.context}
LANGUAGE: {input_data.language_code}

TRANSCRIPTION:
"{input_data.transcription}"

Extract only the most significant factual claims that warrant professional fact-checking. Focus on statements that contain specific, verifiable information."""

# Create service instance
llm_analysis_service = LLMTranscriptionAnalysisService()