from models.research_models import LLMResearchRequest
from prompts.fc_prompt import factcheck_prompt

class PromptBuilder:
    """Builder for creating prompts for different LLM clients."""
    
    def get_system_prompt(self) -> str:
        """Get the system prompt for LLM fact-checking."""
        return f"""You are a professional fact-checker with access to extensive knowledge across multiple domains including science, politics, economics, history, and current events.

Your task is to fact-check statements using your trained knowledge base. You must be thorough, accurate, and unbiased in your analysis.

{factcheck_prompt}"""

    def get_user_prompt(self, request: LLMResearchRequest) -> str:
        """Get the user prompt with the specific research request."""
        return f"""Please fact-check the following statement using your knowledge base and provide expert perspectives:

STATEMENT: "{request.statement}"
SOURCE: {request.source}
CONTEXT: {request.context}
SPEAKER_COUNTRY: {request.country or 'Unknown'}
STATEMENT_CATEGORY: {request.category or 'Unknown'}

ANALYSIS REQUIREMENTS:
- Consider the political and cultural context of the speaker's country if provided
- Focus on domain-specific expertise relevant to the statement category
- Include country and category fields in your response
- Provide comprehensive fact-checking as per the specified JSON format

Analyze this statement thoroughly and provide a comprehensive fact-check result. Consider:
1. The accuracy of any numerical claims or statistics
2. The scientific consensus on the topic
3. Historical context and evolution of understanding
4. How the statement might mislead even if partially true
5. The reliability and motivation of the stated source
6. Country-specific context and political landscape if applicable
7. Category-specific expertise and domain knowledge

Provide your analysis in the specified JSON format including:
- Standard fact-check elements (sources, verdict, status, correction, country, category, resources)
- Four expert perspectives (critic, devil, nerd, psychic) offering different analytical angles

Each expert perspective should be clear, concise (max 3 sentences), and provide unique insights into the statement."""

    def get_gemini_prompt(self, request: LLMResearchRequest) -> str:
        """Get enhanced prompt for Gemini with internet search capabilities."""
        return f"""You are a professional fact-checker with access to current internet information and extensive knowledge across multiple domains.

Your task is to fact-check the following statement using both your knowledge base AND current internet search capabilities to find the most up-to-date information:

STATEMENT: "{request.statement}"
SOURCE: {request.source}
CONTEXT: {request.context}
SPEAKER_COUNTRY: {request.country or 'Unknown'}
STATEMENT_CATEGORY: {request.category or 'Unknown'}

{factcheck_prompt}

ADDITIONAL REQUIREMENTS:
- If country is provided, consider local context and political landscape of that country
- If category is provided, focus on domain-specific expertise and sources relevant to that category
- Include the country and category in your response using the provided values
- Use your internet search capabilities to find the most current information available
"""