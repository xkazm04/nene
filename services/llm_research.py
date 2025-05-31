import os
import logging
from typing import List, Literal, Optional
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
import json

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)


class LLMResearchRequest(BaseModel):
    statement: str
    source: str
    context: str


class ExpertOpinion(BaseModel):
    critic: Optional[str] = None
    devil: Optional[str] = None
    nerd: Optional[str] = None
    psychic: Optional[str] = None


class LLMResearchResponse(BaseModel):
    valid_sources: str  # e.g., "15 (85% agreement across 23 unique sources)"
    verdict: str
    status: Literal["TRUE", "FALSE", "MISLEADING", "PARTIALLY_TRUE", "UNVERIFIABLE"]
    correction: Optional[str] = None  # Corrected statement if original is false/misleading
    resources: List[str]
    experts: ExpertOpinion


class LLMResearchService:
    def __init__(self):
        """Initialize OpenAI client for LLM-based research."""
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        groq_client = OpenAI(api_key=self.groq_api_key,
                             base_url="https://api.groq.com/openai/v1")
        openai_client = OpenAI(api_key=self.api_key)
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY not found in environment variables")

        self.client = groq_client
        # self.model = "gpt-4.1-mini"  
        self.model = "meta-llama/llama-4-scout-17b-16e-instruct"
        logger.info("LLM Research service initialized successfully")

    def research_statement(self, request: LLMResearchRequest) -> LLMResearchResponse:
        """
        Research a statement using LLM's trained knowledge base.

        Args:
            request: Research request with statement, source, and context

        Returns:
            LLMResearchResponse: Fact-check result with verdict and resources

        Raises:
            Exception: If research fails
        """
        try:
            logger.info(
                f"Starting LLM research for statement: {request.statement[:100]}...")
            logger.info(f"Statement source: {request.source}")
            logger.info(f"Context: {request.context}")

            # Construct the research prompt
            system_prompt = self._get_system_prompt()
            user_prompt = self._get_user_prompt(request)

            logger.debug("Sending research request to OpenAI API")

            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # Low temperature for consistent fact-checking
                max_tokens=2500,  # Increased for expanded response
                response_format={"type": "json_object"}
            )

            logger.info("Successfully received response from OpenAI API")

            # Parse the response
            response_content = response.choices[0].message.content
            logger.debug(f"Raw response: {response_content[:200]}...")

            try:
                parsed_response = json.loads(response_content)
                logger.info("Successfully parsed JSON response")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                raise Exception(f"Invalid JSON response from OpenAI: {e}")

            # Extract expert opinions
            experts_data = parsed_response.get("experts", {})
            experts = ExpertOpinion(
                critic=experts_data.get("critic"),
                devil=experts_data.get("devil"),
                nerd=experts_data.get("nerd"),
                psychic=experts_data.get("psychic")
            )

            # Create structured response
            result = LLMResearchResponse(
                valid_sources=parsed_response.get("valid_sources", "Unknown"),
                verdict=parsed_response.get("verdict", "Unable to determine verdict"),
                status=parsed_response.get("status", "UNVERIFIABLE"),
                correction=parsed_response.get("correction"),
                resources=parsed_response.get("resources", []),
                experts=experts
            )

            logger.info(f"Research completed successfully")
            logger.info(f"Status: {result.status}")
            logger.info(f"Valid sources: {result.valid_sources}")
            logger.info(f"Verdict: {result.verdict[:100]}...")
            logger.info(f"Expert perspectives included: {len([x for x in [experts.critic, experts.devil, experts.nerd, experts.psychic] if x])}")

            return result

        except Exception as e:
            error_msg = f"Failed to research statement with LLM: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Error type: {type(e).__name__}")
            raise Exception(error_msg)

    def _get_system_prompt(self) -> str:
        """Get the system prompt for LLM fact-checking."""
        return """You are a professional fact-checker with access to extensive knowledge across multiple domains including science, politics, economics, history, and current events.

Your task is to fact-check statements using your trained knowledge base. You must be thorough, accurate, and unbiased in your analysis.

FACT-CHECKING CRITERIA:
- TRUE: Statement is accurate according to reliable sources and scientific consensus
- FALSE: Statement is demonstrably incorrect or contradicted by evidence
- MISLEADING: Statement contains some truth but presents it in a way that creates false impressions
- PARTIALLY_TRUE: Statement is partially correct but missing important context or nuance
- UNVERIFIABLE: Insufficient reliable information available to make a determination

EXPERT PERSPECTIVES (each max 4 sentences):
- CRITIC: Looks for hidden truths and gaps in statements, examining underlying assumptions and potential conspiratorial elements
- DEVIL: Represents minority viewpoints and finds logical reasoning behind dissenting sources, playing devil's advocate
- NERD: Provides statistical background, numbers, and data-driven context to support the verdict
- PSYCHIC: Analyzes psychological motivations behind the statement, uncovering manipulation tactics and goals

RESPONSE FORMAT:
Return a JSON object with this exact structure:
{
    "valid_sources": "number (percentage agreement across X unique sources)",
    "verdict": "One sentence verdict explaining your fact-check conclusion",
    "status": "TRUE/FALSE/MISLEADING/PARTIALLY_TRUE/UNVERIFIABLE",
    "correction": "If statement is false/misleading, provide the accurate version in one sentence, otherwise null",
    "resources": [
        "https://reliable-source1.com/relevant-article",
        "https://reliable-source2.org/scientific-study",
        "https://reliable-source3.edu/research-paper"
    ],
    "experts": {
        "critic": "Critical perspective examining hidden truths and gaps (max 4 sentences)",
        "devil": "Devil's advocate representing minority viewpoints (max 4 sentences)",
        "nerd": "Statistical and data-driven analysis (max 4 sentences)",
        "psychic": "Psychological motivation analysis (max 4 sentences)"
    }
}

GUIDELINES:
- Base your analysis on scientific consensus, peer-reviewed research, and authoritative sources
- Consider the context and how the statement might be interpreted
- Provide 3 major URLs to reputable sources that can verify your analysis
- Be specific about the level of agreement among sources
- Expert perspectives should be distinct and offer different analytical angles
- Keep expert opinions concise but insightful (max 4 sentences each)"""

    def _get_user_prompt(self, request: LLMResearchRequest) -> str:
        """Get the user prompt with the specific research request."""
        return f"""Please fact-check the following statement using your knowledge base and provide expert perspectives:

STATEMENT: "{request.statement}"

SOURCE: {request.source}

CONTEXT: {request.context}

Analyze this statement thoroughly and provide a comprehensive fact-check result. Consider:
1. The accuracy of any numerical claims or statistics
2. The scientific consensus on the topic
3. Historical context and evolution of understanding
4. How the statement might mislead even if partially true
5. The reliability and motivation of the stated source

Provide your analysis in the specified JSON format including:
- Standard fact-check elements (sources, verdict, status, correction, resources)
- Four expert perspectives (critic, devil, nerd, psychic) offering different analytical angles

Each expert perspective should be clear, concise (max 4 sentences), and provide unique insights into the statement."""


# Create service instance
llm_research_service = LLMResearchService()