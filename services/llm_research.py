import os
import logging
from typing import List, Literal, Optional
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
import json
import google.generativeai as genai
from prompts.fc_prompt import factcheck_prompt

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


class ResourceReference(BaseModel):
    url: str
    title: str
    category: Literal["mainstream", "governance", "academic", "medical", "other"]
    country: str
    credibility: Literal["high", "medium", "low"]


class ResourceAnalysis(BaseModel):
    total: str  # e.g., "85%"
    count: int
    mainstream: int = 0
    governance: int = 0
    academic: int = 0
    medical: int = 0
    other: int = 0
    major_countries: List[str] = []
    references: List[ResourceReference] = []


class LLMResearchResponse(BaseModel):
    valid_sources: str  # e.g., "15 (85% agreement across 23 unique sources)"
    verdict: str
    status: Literal["TRUE", "FALSE", "MISLEADING",
                    "PARTIALLY_TRUE", "UNVERIFIABLE"]
    # Corrected statement if original is false/misleading
    correction: Optional[str] = None
    resources_agreed: ResourceAnalysis
    resources_disagreed: ResourceAnalysis
    experts: ExpertOpinion
    research_method: str  # Track which service was used


class LlmResearchService:
    def __init__(self):
        """Initialize both LLM and Gemini clients for comprehensive research."""
        # Initialize LLM (primary)
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        if not self.groq_api_key:
            raise ValueError("GROQ_API_KEY not found in environment variables")

        self.llm_client = OpenAI(
            api_key=self.groq_api_key,
            base_url="https://api.groq.com/openai/v1"
        )
        self.llm_model = "meta-llama/llama-4-scout-17b-16e-instruct"

        # Initialize Gemini (fallback)
        try:
            self.google_api_key = os.environ['GOOGLE_API_KEY']
            genai.configure(api_key=self.google_api_key)
            self.gemini_model = genai.GenerativeModel(
                'gemini-1.5-flash-latest')
            logger.info("Gemini fallback service initialized successfully")
        except KeyError:
            logger.warning(
                "GOOGLE_API_KEY not found - Gemini fallback unavailable")
            self.gemini_model = None
        except Exception as e:
            logger.warning(f"Could not initialize Gemini: {e}")
            self.gemini_model = None

        logger.info("Combined Research service initialized successfully")

    def research_statement(self, request: LLMResearchRequest) -> LLMResearchResponse:
        """
        Research a statement using LLM first, fallback to Gemini if UNVERIFIABLE.

        Args:
            request: Research request with statement, source, and context

        Returns:
            LLMResearchResponse: Fact-check result with verdict and resources

        Raises:
            Exception: If both research methods fail
        """
        try:
            logger.info(
                f"Starting research for statement: {request.statement[:100]}...")

            # Try LLM first (primary method)
            try:
                llm_result = self._research_with_llm(request)

                # If LLM gives definitive answer, return it
                if llm_result.status != "UNVERIFIABLE":
                    llm_result.research_method = "LLM (Primary)"
                    logger.info(
                        f"LLM research successful with status: {llm_result.status}")
                    return llm_result

                logger.info(
                    "LLM returned UNVERIFIABLE, attempting Gemini fallback...")

            except Exception as e:
                logger.warning(
                    f"LLM research failed: {e}, attempting Gemini fallback...")

            # Fallback to Gemini if LLM is unverifiable or fails
            if self.gemini_model:
                try:
                    gemini_result = self._research_with_gemini(request)
                    gemini_result.research_method = "Gemini (Fallback - Internet Search)"
                    logger.info(
                        f"Gemini research successful with status: {gemini_result.status}")
                    return gemini_result

                except Exception as e:
                    logger.error(f"Gemini research also failed: {e}")
            else:
                logger.error("Gemini fallback not available")

            # If both fail, return the LLM result (even if UNVERIFIABLE) or create error response
            if 'llm_result' in locals():
                llm_result.research_method = "LLM (Primary - Fallback Failed)"
                return llm_result
            else:
                # Create error response if both services failed
                return self._create_error_response(request)

        except Exception as e:
            error_msg = f"Complete research failure: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)

    def _research_with_llm(self, request: LLMResearchRequest) -> LLMResearchResponse:
        """Research using LLM (training data based)."""
        logger.debug("Starting LLM research")

        # Construct the research prompt
        system_prompt = self._get_system_prompt()
        user_prompt = self._get_user_prompt(request)

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
            raise Exception(f"Invalid JSON response from LLM: {e}")

        return self._create_response_object(parsed_response)

    def _research_with_gemini(self, request: LLMResearchRequest) -> LLMResearchResponse:
        """Research using Gemini with internet search capabilities."""
        logger.debug("Starting Gemini research")

        # Enhanced Gemini prompt with internet search capabilities
        gemini_prompt = f"""You are a professional fact-checker with access to current internet information and extensive knowledge across multiple domains.
                        Your task is to fact-check the following statement using both your knowledge base AND current internet search capabilities to find the most up-to-date information:

                        STATEMENT: "{request.statement}"
                        SOURCE: {request.source}
                        CONTEXT: {request.context}

                        """ + factcheck_prompt

        # Generate content with Gemini
        response = self.gemini_model.generate_content(gemini_prompt)

        if not response or not response.text:
            raise Exception("Empty response from Gemini")

        # Try to extract JSON from response
        response_text = response.text.strip()

        # Find JSON object in response
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1

        if start_idx == -1 or end_idx == 0:
            raise Exception("No JSON object found in Gemini response")

        json_str = response_text[start_idx:end_idx]

        try:
            parsed_response = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON response from Gemini: {e}")

        return self._create_response_object(parsed_response)

    def _create_response_object(self, parsed_response: dict) -> LLMResearchResponse:
        """Create standardized response object from parsed JSON."""
        # Extract expert opinions
        experts_data = parsed_response.get("experts", {})
        experts = ExpertOpinion(
            critic=experts_data.get("critic"),
            devil=experts_data.get("devil"),
            nerd=experts_data.get("nerd"),
            psychic=experts_data.get("psychic")
        )

        # Extract resource analysis for agreed sources
        agreed_data = parsed_response.get("resources_agreed", {})
        resources_agreed = ResourceAnalysis(
            total=agreed_data.get("total", "0%"),
            count=agreed_data.get("count", 0),
            mainstream=agreed_data.get("mainstream", 0),
            governance=agreed_data.get("governance", 0),
            academic=agreed_data.get("academic", 0),
            medical=agreed_data.get("medical", 0),
            other=agreed_data.get("other", 0),
            major_countries=agreed_data.get("major_countries", []),
            references=[
                ResourceReference(**ref) for ref in agreed_data.get("references", [])
            ]
        )

        # Extract resource analysis for disagreed sources
        disagreed_data = parsed_response.get("resources_disagreed", {})
        resources_disagreed = ResourceAnalysis(
            total=disagreed_data.get("total", "0%"),
            count=disagreed_data.get("count", 0),
            mainstream=disagreed_data.get("mainstream", 0),
            governance=disagreed_data.get("governance", 0),
            academic=disagreed_data.get("academic", 0),
            medical=disagreed_data.get("medical", 0),
            other=disagreed_data.get("other", 0),
            major_countries=disagreed_data.get("major_countries", []),
            references=[
                ResourceReference(**ref) for ref in disagreed_data.get("references", [])
            ]
        )

        # Create structured response
        return LLMResearchResponse(
            valid_sources=parsed_response.get("valid_sources", "Unknown"),
            verdict=parsed_response.get(
                "verdict", "Unable to determine verdict"),
            status=parsed_response.get("status", "UNVERIFIABLE"),
            correction=parsed_response.get("correction"),
            resources_agreed=resources_agreed,
            resources_disagreed=resources_disagreed,
            experts=experts,
            research_method=""  # Will be set by calling method
        )

    def _create_error_response(self, request: LLMResearchRequest) -> LLMResearchResponse:
        """Create error response when both services fail."""
        return LLMResearchResponse(
            valid_sources="0 (Service Error)",
            verdict="Unable to fact-check due to service errors",
            status="UNVERIFIABLE",
            correction=None,
            resources_agreed=ResourceAnalysis(),
            resources_disagreed=ResourceAnalysis(),
            experts=ExpertOpinion(),
            research_method="Error - Both Services Failed"
        )

    def _get_system_prompt(self) -> str:
        """Get the system prompt for LLM fact-checking."""
        return """You are a professional fact-checker with access to extensive knowledge across multiple domains including science, politics, economics, history, and current events.
                    Your task is to fact-check statements using your trained knowledge base. You must be thorough, accurate, and unbiased in your analysis.""" + factcheck_prompt

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
llm_research_service = LlmResearchService()
