import os
import logging
from typing import List, Optional
from dotenv import load_dotenv
from openai import OpenAI
import json
import asyncio
from typing import Optional
from datetime import datetime

from models.transcription_models import (
    TranscriptionAnalysisInput,
    EnhancedTranscriptionAnalysisResult
)
from models.video_models import EnhancedFactCheckStatementWithTimestamp, TimestampEstimate
from models.statement_categories import StatementCategory
from prompts.transcription_prompts import TranscriptionAnalysisPrompts
from services.media.video_service import video_service
from models.processing_models import ProcessingUpdate, ProcessingStatus
from services.sse_service import sse_service

load_dotenv()
logger = logging.getLogger(__name__)

class LLMTranscriptionAnalysisService:
    def __init__(self):
        """Initialize OpenAI client with API key from environment."""
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        
        if not self.api_key and not self.groq_api_key:
            raise ValueError("Either OPENAI_API_KEY or GROQ_API_KEY must be set in environment variables")
        
        # Prefer Groq if available, fallback to OpenAI
        if self.groq_api_key:
            self.client = OpenAI(api_key=self.groq_api_key, base_url="https://api.groq.com/openai/v1")
            self.model = "meta-llama/llama-4-scout-17b-16e-instruct"
            self.provider = "Groq"
        else:
            self.client = OpenAI(api_key=self.api_key)
            self.model = "gpt-4o-mini"
            self.provider = "OpenAI"
        
        self.prompts = TranscriptionAnalysisPrompts()
        logger.info(f"LLM Transcription Analysis service initialized with {self.provider} ({self.model})")
    
    def analyze_transcription(
        self, 
        input_data: TranscriptionAnalysisInput, 
        video_id: str = None,
        frontend_mode: bool = False,
        job_id: Optional[str] = None
    ) -> EnhancedTranscriptionAnalysisResult:
        """
        Analyze transcription for political statements worthy of fact-checking with enhanced metadata and timestamps.
        
        Args:
            input_data: Transcription analysis input containing speaker, context, and transcription
            video_id: Optional video ID for database linking
            frontend_mode: Whether called from frontend (enables SSE)
            job_id: Processing job ID for SSE updates
            
        Returns:
            EnhancedTranscriptionAnalysisResult: List of statements with metadata and timestamps
            
        Raises:
            Exception: If analysis fails
        """
        try:
            logger.info(f"Starting enhanced transcription analysis for speaker: {input_data.speaker}")
            
            # Send SSE update if in frontend mode
            if frontend_mode and job_id:
                update = ProcessingUpdate(
                    job_id=job_id,
                    video_id=video_id,
                    status=ProcessingStatus.ANALYZING,
                    step="Starting LLM analysis",
                    progress=86,
                    message=f"Analyzing transcription for fact-checkable statements",
                    timestamp=datetime.utcnow()
                )
                asyncio.create_task(sse_service.broadcast_update(job_id, update))
            
            # Get prompts
            system_prompt = self.prompts.get_system_prompt()
            user_prompt = self.prompts.get_user_prompt(
                input_data.speaker,
                input_data.context,
                input_data.language_code,
                input_data.transcription,
                input_data.video_duration_seconds
            )
            
            logger.debug(f"Sending request to {self.provider} API")
            
            # Send SSE update for LLM processing
            if frontend_mode and job_id:
                update = ProcessingUpdate(
                    job_id=job_id,
                    video_id=video_id,
                    status=ProcessingStatus.ANALYZING,
                    step="Processing with LLM",
                    progress=90,
                    message=f"AI is analyzing the transcription using {self.provider}",
                    timestamp=datetime.utcnow()
                )
                asyncio.create_task(sse_service.broadcast_update(job_id, update))
            
            # Call LLM API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=4000,
                response_format={"type": "json_object"}
            )
            
            logger.info(f"Successfully received response from {self.provider} API")
            
            # Parse response
            response_content = response.choices[0].message.content
            try:
                parsed_response = json.loads(response_content)
            except json.JSONDecodeError as e:
                raise Exception(f"Invalid JSON response from {self.provider}: {e}")
            
            # Process statements
            statements_data = parsed_response.get("statements", [])
            statements = []
            timestamp_estimates = []
            
            for stmt_data in statements_data:
                try:
                    # Validate category
                    category = None
                    if stmt_data.get("category"):
                        try:
                            category = StatementCategory(stmt_data["category"])
                        except ValueError:
                            category = None
                    
                    # Create enhanced statement with timestamp
                    statement = EnhancedFactCheckStatementWithTimestamp(
                        statement=stmt_data["statement"],
                        language=stmt_data.get("language"),
                        context=stmt_data.get("context"),
                        category=category,
                        estimated_time_from=stmt_data.get("estimated_time_from"),
                        estimated_time_to=stmt_data.get("estimated_time_to"),
                        confidence_score=stmt_data.get("confidence_score")
                    )
                    statements.append(statement)
                    
                    # Create timestamp estimate for database storage
                    if (stmt_data.get("estimated_time_from") is not None and 
                        stmt_data.get("estimated_time_to") is not None):
                        
                        timestamp_estimate = TimestampEstimate(
                            statement=stmt_data["statement"],
                            time_from_seconds=stmt_data["estimated_time_from"],
                            time_to_seconds=stmt_data["estimated_time_to"],
                            context=stmt_data.get("context"),
                            category=category,
                            confidence_score=stmt_data.get("confidence_score")
                        )
                        timestamp_estimates.append(timestamp_estimate)
                    
                except Exception as stmt_error:
                    logger.warning(f"Failed to parse statement: {stmt_error}. Skipping: {stmt_data}")
                    continue
            
            # Send SSE update with analysis results
            if frontend_mode and job_id:
                update = ProcessingUpdate(
                    job_id=job_id,
                    video_id=video_id,
                    status=ProcessingStatus.ANALYZING,
                    step="Analysis completed",
                    progress=95,
                    message=f"Found {len(statements)} fact-checkable statements",
                    data={
                        "statements_found": len(statements),
                        "detected_language": parsed_response.get("detected_language"),
                        "dominant_categories": parsed_response.get("dominant_categories", [])
                    },
                    timestamp=datetime.utcnow()
                )
                asyncio.create_task(sse_service.broadcast_update(job_id, update))
            
            # Validate and convert dominant categories
            dominant_categories = []
            if parsed_response.get("dominant_categories"):
                for cat_str in parsed_response["dominant_categories"]:
                    try:
                        category = StatementCategory(cat_str)
                        dominant_categories.append(category)
                    except ValueError:
                        continue
            
            # Create enhanced result
            result = EnhancedTranscriptionAnalysisResult(
                statements=statements,
                total_statements=len(statements),
                analysis_summary=parsed_response.get("analysis_summary", "Enhanced analysis completed"),
                overall_context=parsed_response.get("overall_context"),
                detected_language=parsed_response.get("detected_language"),
                dominant_categories=dominant_categories if dominant_categories else None,
                estimated_duration=parsed_response.get("estimated_duration")
            )
            
            # Save timestamps to database if video_id is provided
            if video_id and timestamp_estimates:
                self._save_timestamps_to_database(
                    video_id, 
                    timestamp_estimates,
                    frontend_mode=frontend_mode,
                    job_id=job_id
                )
            
            logger.info("Enhanced transcription analysis completed successfully")
            
            return result
            
        except Exception as e:
            error_msg = f"Failed to analyze transcription with {self.provider}: {str(e)}"
            logger.error(error_msg)
            
            # Send SSE error if in frontend mode
            if frontend_mode and job_id:
                update = ProcessingUpdate(
                    job_id=job_id,
                    video_id=video_id,
                    status=ProcessingStatus.FAILED,
                    step="Analysis failed",
                    progress=90,
                    message="LLM analysis failed",
                    error=str(e),
                    timestamp=datetime.utcnow()
                )
                asyncio.create_task(sse_service.broadcast_update(job_id, update))
            
            raise Exception(error_msg)
    
    def _save_timestamps_to_database(
        self, 
        video_id: str, 
        timestamp_estimates: List[TimestampEstimate],
        frontend_mode: bool = False,
        job_id: Optional[str] = None
    ):
        """Save timestamp estimates to database with SSE updates."""
        try:
            success = video_service.create_timestamps(
                video_id, 
                timestamp_estimates,
                frontend_mode=frontend_mode,
                job_id=job_id
            )
            
            if success:
                # Update video status
                video_service.update_video_status(
                    video_id, 
                    transcribed=True, 
                    analyzed=True,
                    frontend_mode=frontend_mode,
                    job_id=job_id,
                    progress=98,
                    step_message="Analysis phase completed"
                )
        except Exception as e:
            logger.error(f"Failed to save timestamps to database: {str(e)}")

    def get_available_categories(self) -> List[str]:
        """Get list of available statement categories."""
        return [category.value for category in StatementCategory]
    
    def validate_category(self, category_str: str) -> Optional[StatementCategory]:
        """Validate and convert category string to enum."""
        try:
            return StatementCategory(category_str)
        except ValueError:
            return None

# Create service instance
llm_analysis_service = LLMTranscriptionAnalysisService()