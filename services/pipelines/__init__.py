"""
Video processing pipelines module.

This module contains the main video processing pipelines for:
- Complete video processing (download, transcribe, analyze, research)
- Statement research pipeline
"""

from .video_processing_pipeline import process_video_pipeline, research_statements_pipeline

__all__ = [
    "process_video_pipeline",
    "research_statements_pipeline"
]