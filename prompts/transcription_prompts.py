from typing import Dict, Optional

class TranscriptionAnalysisPrompts:
    """Centralized prompts for transcription analysis."""
    
    @staticmethod
    def get_system_prompt() -> str:
        """Get the system prompt for the LLM analysis."""
        return """You are a professional fact-checking analyst specializing in identifying political statements that warrant verification.

Your task is to analyze political transcriptions and extract specific factual claims that can be objectively verified or debunked, including estimating when these statements occur in the video.

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

STATEMENT CATEGORIES:
- politics: Political processes, elections, governance, laws, regulations
- economy: Economic data, financial claims, market performance, employment
- environment: Climate change, pollution, environmental policies, sustainability
- military: Defense spending, conflicts, military actions, security issues
- healthcare: Medical claims, health statistics, healthcare policies, public health
- education: Education statistics, school policies, academic achievements
- technology: Tech innovations, digital policies, cybersecurity, AI/automation
- social: Social issues, demographics, inequality, civil rights, immigration
- international: Foreign policy, international relations, global agreements
- other: Statements that don't fit clearly into above categories

LANGUAGE CODES (ISO 639-1):
Use standard 2-letter codes: en (English), es (Spanish), fr (French), de (German), it (Italian), pt (Portuguese), ru (Russian), zh (Chinese), ja (Japanese), ar (Arabic), etc.

TIMESTAMP ESTIMATION GUIDELINES:
- Estimate when each statement appears in the video (in seconds from start)
- Consider natural speech patterns, pauses, and context
- Add buffer time for slower speakers (typically 10-20% extra time)
- Provide confidence score (0.0-1.0) for timing accuracy
- If video duration is provided, ensure timestamps don't exceed it
- For statements spanning multiple sentences, estimate the full range

RESPONSE FORMAT:
Return a JSON object with this exact structure:
{
    "overall_context": "One sentence summary of the entire transcription's main topic/context",
    "detected_language": "two-letter ISO language code of the transcription",
    "estimated_duration": 1800,
    "statements": [
        {
            "statement": "exact quote from transcription",
            "language": "two-letter ISO code if different from main language, or null",
            "context": "one sentence explaining the context of this specific statement",
            "category": "one of the predefined categories or null if unclear",
            "estimated_time_from": 120,
            "estimated_time_to": 135,
            "confidence_score": 0.85
        }
    ],
    "analysis_summary": "Brief summary of the analysis and number of fact-checkable statements found",
    "dominant_categories": ["list", "of", "most", "common", "categories"]
}

IMPORTANT:
- Extract statements as exact quotes from the original transcription
- Be selective and focus only on statements with clear factual claims
- Provide context for each statement to understand its setting
- Categorize statements based on their primary subject matter
- Estimate timestamps based on natural flow and speech patterns
- Include confidence scores for timing estimates
- If unsure about language/category/timing, use null instead of guessing"""

    @staticmethod
    def get_user_prompt(speaker: str, context: str, language_code: str, transcription: str, video_duration: Optional[int] = None) -> str:
        """Get the user prompt with the specific transcription data."""
        duration_info = f"\nVIDEO_DURATION: {video_duration} seconds" if video_duration else "\nVIDEO_DURATION: Unknown"
        
        return f"""Please analyze the following political transcription for fact-checkable statements with enhanced metadata and timestamp estimation:

SPEAKER: {speaker}
CONTEXT: {context}
EXPECTED_LANGUAGE: {language_code}{duration_info}

TRANSCRIPTION:
"{transcription}"

Extract only the most significant factual claims that warrant professional fact-checking. For each statement, provide:
1. The exact quote from the transcription
2. Language code (if different from expected or mixed languages detected)
3. Brief context explaining the setting/topic of the statement
4. Category classification based on the primary subject matter
5. Estimated timestamp range when this statement occurs in the video
6. Confidence score for the timing estimate (0.0-1.0)

TIMESTAMP ESTIMATION INSTRUCTIONS:
- Analyze the flow and structure of the transcription
- Consider natural speaking pace and pauses
- Add appropriate buffer time for slower speakers
- Estimate based on the relative position in the transcription
- Provide realistic confidence scores based on text clarity and structure
- Ensure timestamps are sequential and don't overlap inappropriately

Focus on statements that contain specific, verifiable information that can be researched and fact-checked."""

    @staticmethod
    def get_prompts() -> Dict[str, str]:
        """Get all prompts as a dictionary for easy access."""
        return {
            "system": TranscriptionAnalysisPrompts.get_system_prompt(),
            "user_template": "Use get_user_prompt() method with parameters"
        }