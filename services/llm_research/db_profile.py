import json
import logging
import re
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class ProfileService:
    """Service for enhanced speaker profile processing with LLM-based metadata extraction"""
    
    def __init__(self, profile_service=None):
        self.profile_service = profile_service
    
    async def process_enhanced_speaker_profile(self, source: str) -> Optional[str]:
        """
        Enhanced speaker profile processing with LLM-based metadata extraction
        
        Args:
            source: Speaker name or source
            
        Returns:
            Profile ID if successful, None otherwise
        """
        try:
            if not source or len(source.strip()) < 2:
                logger.info("No source provided or source too short for profile creation")
                return None
            
            # Extract clean speaker name
            from utils.research_extractions import research_extraction_utils
            speaker_name = research_extraction_utils.extract_speaker_name(source)
            
            if not speaker_name:
                logger.warning(f"Could not extract speaker name from: {source}")
                return None
            
            # Try to get existing profile first
            if self.profile_service:
                existing_profile_id = self.profile_service.get_or_create_profile(speaker_name)
                if existing_profile_id:
                    return existing_profile_id
            
            # Extract metadata using LLM
            metadata = await self._extract_speaker_metadata_with_llm(speaker_name)
            
            # Create enhanced profile
            profile_id = self._create_enhanced_profile(speaker_name, metadata)
            
            if profile_id:
                logger.info(f"Created enhanced profile for {speaker_name}: {profile_id}")
            
            return profile_id
            
        except Exception as e:
            logger.error(f"Enhanced speaker profile processing failed: {e}")
            return None
    
    async def _extract_speaker_metadata_with_llm(self, speaker_name: str) -> Dict:
        """
        Use LLM to extract speaker metadata from training data
        
        Args:
            speaker_name: Clean speaker name
            
        Returns:
            Dictionary with extracted metadata
        """
        try:
            prompt = f"""
Extract available information about this person from your training data: {speaker_name}

Return ONLY a JSON object with available information:
{{
    "country": "ISO country code (e.g., 'us', 'gb', 'de') or null",
    "party": "Political party name or null",
    "position": "Current or most recent position/title or null",
    "type": "person|media|organization",
    "score": "Credibility score 0-100 based on public trust and fact-checking history"
}}

If you don't have reliable information about this person, return:
{{
    "country": null,
    "party": null,
    "position": null,
    "type": "person",
    "score": 50
}}

JSON only, no explanation:
"""
            
            # Use the unified LLM research service for metadata extraction
            from services.llm_clients.groq_client import GroqLLMClient
            from services.llm_clients.gemini_client import GeminiClient
            
            groq_client = GroqLLMClient()
            gemini_client = GeminiClient()
            
            response = None
            if groq_client.is_available():
                response = await groq_client.generate_response(prompt)
            elif gemini_client.is_available():
                response = await gemini_client.generate_response(prompt)
            
            if response:
                try:
                    # Try to extract JSON from response
                    response = response.strip()
                    if response.startswith('```json'):
                        response = response.replace('```json', '').replace('```', '')
                    elif response.startswith('```'):
                        response = response.replace('```', '')
                    
                    return json.loads(response)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse LLM JSON response for {speaker_name}")
            
        except Exception as e:
            logger.error(f"LLM metadata extraction failed for {speaker_name}: {e}")
        
        # Return default metadata
        return {
            "country": None,
            "party": None,
            "position": None,
            "type": "person",
            "score": 50
        }
    
    def _create_enhanced_profile(self, speaker_name: str, metadata: Dict) -> Optional[str]:
        """
        Create profile with enhanced metadata
        
        Args:
            speaker_name: Speaker name
            metadata: Extracted metadata from LLM
            
        Returns:
            Profile ID if successful
        """
        try:
            if not self.profile_service:
                logger.warning("Profile service not available, cannot create enhanced profile")
                return None
            
            from services.profile import ProfileCreate
            
            profile_data = ProfileCreate(
                name=speaker_name,
                country=metadata.get('country'),
                party=metadata.get('party'),
                position=metadata.get('position'),
                type=metadata.get('type', 'person'),
                score=float(metadata.get('score', 50))
            )
            
            # Use profile service to create enhanced profile
            return self.profile_service.get_or_create_profile(speaker_name)
            
        except Exception as e:
            logger.error(f"Failed to create enhanced profile for {speaker_name}: {e}")
            return None

# Create service instance
profile_service = ProfileService()