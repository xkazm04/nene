import asyncio
import logging
from typing import Optional, List
from datetime import datetime

from models.processing_models import ProcessingUpdate, ProcessingStatus
from models.transcription_models import TranscriptionAnalysisInput
from services.sse_service import sse_service
from services.media.video_service import video_service
from services.media.yt_download import youtube_service
from services.media.eleven_transcription import transcription_service
from services.media.llm_transcription_analysis import llm_analysis_service
from services.core import fact_checking_core_service
from schemas.research import ResearchRequestAPI

# Configure logger specifically for this module
logger = logging.getLogger(__name__)

async def process_video_pipeline(
    job_id: str,
    video_url: str,
    speaker_name: Optional[str] = None,
    context: str = "Political speech or interview",
    language_code: str = "en",
    model_id: str = "scribe_v1",
    cleanup_audio: bool = True,
    research_statements: bool = True
):
    """
    Complete video processing pipeline with SSE updates.
    
    Args:
        job_id: Processing job ID
        video_url: YouTube URL to process
        speaker_name: Optional speaker name
        context: Context description
        language_code: Expected language code
        model_id: ElevenLabs model ID
        cleanup_audio: Whether to cleanup audio files
        research_statements: Whether to research statements
    """
    video_id = None
    audio_filepath = None
    
    try:
        logger.info("=" * 60)
        logger.info(f"STARTING VIDEO PROCESSING PIPELINE")
        logger.info(f"Job ID: {job_id}")
        logger.info(f"Video URL: {video_url}")
        logger.info(f"Speaker: {speaker_name}")
        logger.info(f"Context: {context}")
        logger.info(f"Language: {language_code}")
        logger.info(f"Model: {model_id}")
        logger.info("=" * 60)
        
        # Phase 1: Download Audio
        logger.info("🎬 PHASE 1: AUDIO DOWNLOAD")
        logger.info("-" * 40)
        
        update = ProcessingUpdate(
            job_id=job_id,
            status=ProcessingStatus.DOWNLOADING,
            step="Starting download phase",
            progress=0,
            message="Beginning video processing pipeline",
            timestamp=datetime.utcnow()
        )
        await sse_service.broadcast_update(job_id, update)
        
        try:
            logger.info("Starting YouTube audio download...")
            audio_filepath, video_id = youtube_service.download_audio(
                video_url,
                speaker_name=speaker_name,
                frontend_mode=True,
                job_id=job_id
            )
            logger.info(f"✅ Phase 1 COMPLETED")
            logger.info(f"   Audio file: {audio_filepath}")
            logger.info(f"   Video ID: {video_id}")
            logger.info("-" * 40)
        except Exception as download_error:
            logger.error(f"❌ Phase 1 FAILED: {str(download_error)}")
            logger.error(f"   Error type: {type(download_error).__name__}")
            raise
        
        # Phase 2: Transcribe Audio
        logger.info("🎤 PHASE 2: AUDIO TRANSCRIPTION")
        logger.info("-" * 40)
        
        try:
            logger.info("Starting ElevenLabs transcription...")
            transcription_result = transcription_service.transcribe_audio(
                audio_file_path=audio_filepath,
                model_id=model_id,
                frontend_mode=True,
                job_id=job_id,
                video_id=video_id
            )
            logger.info(f"✅ Phase 2 COMPLETED")
            logger.info(f"   Transcription length: {len(transcription_result.text)} characters")
            logger.info(f"   Preview: {transcription_result.text[:150]}...")
            logger.info("-" * 40)
        except Exception as transcription_error:
            logger.error(f"❌ Phase 2 FAILED: {str(transcription_error)}")
            logger.error(f"   Error type: {type(transcription_error).__name__}")
            raise
        
        # Phase 3: LLM Analysis
        logger.info("🧠 PHASE 3: LLM ANALYSIS")
        logger.info("-" * 40)
        
        try:
            logger.info("Preparing transcription analysis...")
            
            # Get video info for duration
            video_info = video_service.get_video_by_id(video_id) if video_id else None
            video_duration = video_info.get('duration_seconds') if video_info else None
            logger.info(f"   Video duration: {video_duration}s")
            
            analysis_input = TranscriptionAnalysisInput(
                language_code=language_code,
                speaker=speaker_name or "Unknown Speaker",
                context=context,
                transcription=transcription_result.text,
                video_duration_seconds=video_duration
            )
            
            logger.info("Starting LLM analysis...")
            analysis_result = llm_analysis_service.analyze_transcription(
                analysis_input,
                video_id=video_id,
                frontend_mode=True,
                job_id=job_id
            )
            logger.info(f"✅ Phase 3 COMPLETED")
            logger.info(f"   Found {len(analysis_result.statements)} fact-checkable statements")
            logger.info(f"   Detected language: {analysis_result.detected_language}")
            logger.info("-" * 40)
        except Exception as analysis_error:
            logger.error(f"❌ Phase 3 FAILED: {str(analysis_error)}")
            logger.error(f"   Error type: {type(analysis_error).__name__}")
            raise
        
        # Phase 4: Research Statements (if enabled)
        if research_statements and analysis_result.statements:
            logger.info("🔍 PHASE 4: STATEMENT RESEARCH")
            logger.info("-" * 40)
            try:
                logger.info(f"Starting research for {len(analysis_result.statements)} statements...")
                await research_statements_pipeline(
                    job_id=job_id,
                    video_id=video_id,
                    statements=analysis_result.statements,
                    speaker_name=speaker_name,
                    context=context
                )
                logger.info(f"✅ Phase 4 COMPLETED")
                logger.info("-" * 40)
            except Exception as research_error:
                logger.error(f"⚠️ Phase 4 FAILED: {str(research_error)}")
                logger.error(f"   Error type: {type(research_error).__name__}")
                logger.warning("   Continuing despite research failure...")
                logger.info("-" * 40)
        else:
            logger.info("🔍 PHASE 4: STATEMENT RESEARCH - SKIPPED")
            logger.info(f"   Research enabled: {research_statements}")
            logger.info(f"   Statements found: {len(analysis_result.statements) if analysis_result.statements else 0}")
            logger.info("-" * 40)
        
        # Phase 5: Completion
        logger.info("🎉 PHASE 5: COMPLETION")
        logger.info("-" * 40)
        
        # Update job as completed
        sse_service.update_job(
            job_id,
            status=ProcessingStatus.COMPLETED,
            progress_percentage=100,
            completed_at=datetime.utcnow()
        )
        
        completion_update = ProcessingUpdate(
            job_id=job_id,
            video_id=video_id,
            status=ProcessingStatus.COMPLETED,
            step="Processing completed",
            progress=100,
            message="Video processing pipeline completed successfully",
            data={
                "total_statements": len(analysis_result.statements),
                "video_id": video_id,
                "detected_language": analysis_result.detected_language,
                "processing_summary": analysis_result.analysis_summary
            },
            timestamp=datetime.utcnow()
        )
        await sse_service.broadcast_update(job_id, completion_update)
        
        logger.info("✅ Phase 5 COMPLETED")
        logger.info("=" * 60)
        logger.info(f"🎊 PIPELINE SUCCESSFULLY COMPLETED FOR JOB {job_id}")
        logger.info(f"   Total statements: {len(analysis_result.statements)}")
        logger.info(f"   Video ID: {video_id}")
        logger.info(f"   Language: {analysis_result.detected_language}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"💥 PIPELINE FAILED FOR JOB {job_id}")
        logger.error(f"   Error: {str(e)}")
        logger.error(f"   Error type: {type(e).__name__}")
        logger.error(f"   Video URL: {video_url}")
        logger.error(f"   Phase reached: {locals().get('current_phase', 'Unknown')}")
        logger.error("=" * 60)
        
        # Update job as failed
        sse_service.update_job(
            job_id,
            status=ProcessingStatus.FAILED,
            error_message=str(e)
        )
        
        error_update = ProcessingUpdate(
            job_id=job_id,
            video_id=video_id,
            status=ProcessingStatus.FAILED,
            step="Processing failed",
            progress=0,
            message="Video processing pipeline failed",
            error=str(e),
            timestamp=datetime.utcnow()
        )
        await sse_service.broadcast_update(job_id, error_update)
        
    finally:
        # Cleanup on completion or error
        logger.info("🧹 CLEANUP PHASE")
        logger.info("-" * 40)
        
        if cleanup_audio and audio_filepath:
            try:
                logger.info(f"Cleaning up audio file: {audio_filepath}")
                transcription_service.cleanup_audio_file(audio_filepath)
                logger.info("✅ Audio file cleanup completed")
            except Exception as cleanup_error:
                logger.warning(f"⚠️ Failed to cleanup audio file: {cleanup_error}")
        else:
            logger.info("Skipping audio cleanup (disabled or no file)")
        
        logger.info("-" * 40)

async def research_statements_pipeline(
    job_id: str,
    video_id: str,
    statements: List,
    speaker_name: Optional[str] = None,
    context: str = "Political speech or interview"
):
    """
    Research individual statements with SSE updates.
    
    Args:
        job_id: Processing job ID
        video_id: Video database ID
        statements: List of statements to research
        speaker_name: Speaker name
        context: Context description
    """
    try:
        logger.info(f"Starting statement research pipeline")
        logger.info(f"   Statements to research: {len(statements)}")
        logger.info(f"   Speaker: {speaker_name}")
        logger.info(f"   Context: {context}")
        
        # Update job with statement totals
        sse_service.update_job(
            job_id,
            status=ProcessingStatus.RESEARCHING,
            statements_total=len(statements),
            statements_completed=0
        )
        
        research_start_update = ProcessingUpdate(
            job_id=job_id,
            video_id=video_id,
            status=ProcessingStatus.RESEARCHING,
            step="Starting statement research",
            progress=99,
            message=f"Beginning fact-check research for {len(statements)} statements",
            data={"statements_total": len(statements)},
            timestamp=datetime.utcnow()
        )
        await sse_service.broadcast_update(job_id, research_start_update)
        
        completed_count = 0
        failed_count = 0
        
        for i, statement in enumerate(statements, 1):
            try:
                logger.info(f"📊 Researching statement {i}/{len(statements)}")
                logger.info(f"   Statement: {statement.statement[:100]}...")
                logger.info(f"   Category: {statement.category.value if statement.category else 'None'}")
                
                # Send research start update
                research_update = ProcessingUpdate(
                    job_id=job_id,
                    video_id=video_id,
                    status=ProcessingStatus.RESEARCHING,
                    step=f"Researching statement {i}/{len(statements)}",
                    progress=99,
                    message=f"Fact-checking: {statement.statement[:100]}...",
                    data={
                        "current_statement": i,
                        "total_statements": len(statements),
                        "statement_text": statement.statement,
                        "statement_category": statement.category.value if statement.category else None
                    },
                    timestamp=datetime.utcnow()
                )
                await sse_service.broadcast_update(job_id, research_update)
                
                # Create research request
                research_request = ResearchRequestAPI(
                    statement=statement.statement,
                    source=speaker_name or "Unknown Speaker",
                    context=statement.context or context,
                    datetime=datetime.utcnow(),
                    statement_date=None,
                    country="US",  # Default, could be configurable
                    category=statement.category
                )
                
                # Perform research
                logger.info(f"   Sending to fact-checking service...")
                research_result = fact_checking_core_service.process_research_request(research_request)
                
                completed_count += 1
                logger.info(f"   ✅ Research completed: {research_result.verdict}")
                logger.info(f"   Status: {research_result.status}")
                
                # Update job progress
                sse_service.update_job(job_id, statements_completed=completed_count)
                
                # Send research completion update
                completion_update = ProcessingUpdate(
                    job_id=job_id,
                    video_id=video_id,
                    status=ProcessingStatus.RESEARCHING,
                    step=f"Statement {i}/{len(statements)} researched",
                    progress=99,
                    message=f"Research completed: {research_result.verdict}",
                    data={
                        "statement_index": i,
                        "statement_text": statement.statement,
                        "research_result": {
                            "verdict": research_result.verdict,
                            "status": research_result.status,
                            "correction": research_result.correction,
                            "database_id": research_result.database_id
                        },
                        "completed_count": completed_count,
                        "total_statements": len(statements)
                    },
                    timestamp=datetime.utcnow()
                )
                await sse_service.broadcast_update(job_id, completion_update)
                
                # Small delay to prevent overwhelming the API
                await asyncio.sleep(1)
                
            except Exception as stmt_error:
                failed_count += 1
                logger.error(f"   ❌ Failed to research statement {i}: {str(stmt_error)}")
                logger.error(f"   Error type: {type(stmt_error).__name__}")
                
                # Send statement research error
                error_update = ProcessingUpdate(
                    job_id=job_id,
                    video_id=video_id,
                    status=ProcessingStatus.RESEARCHING,
                    step=f"Statement {i}/{len(statements)} failed",
                    progress=99,
                    message=f"Research failed for statement {i}",
                    data={
                        "statement_index": i,
                        "statement_text": statement.statement,
                        "error": str(stmt_error)
                    },
                    error=str(stmt_error),
                    timestamp=datetime.utcnow()
                )
                await sse_service.broadcast_update(job_id, error_update)
                
                continue  # Continue with next statement
        
        logger.info(f"Statement research pipeline completed")
        logger.info(f"   ✅ Successfully researched: {completed_count}")
        logger.info(f"   ❌ Failed: {failed_count}")
        logger.info(f"   📊 Success rate: {(completed_count / len(statements) * 100):.1f}%")
        
    except Exception as e:
        logger.error(f"Statement research pipeline failed: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        raise