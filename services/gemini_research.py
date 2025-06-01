import google.generativeai as genai
import os
from dotenv import load_dotenv
load_dotenv()

# TBD na sports

try:
    api_key = os.environ['GOOGLE_API_KEY']
    genai.configure(api_key=api_key)
except KeyError:
    print("🔴 ERROR: GOOGLE_API_KEY environment variable not set.")
    print("Please set this environment variable with your Gemini API key.")
    exit()
except Exception as e:
    print(f"🔴 ERROR: Could not configure Gemini API: {e}")
    exit()

# --- Model Configuration ---
# For complex reasoning and research-like tasks, "gemini-1.5-flash-latest" or "gemini-1.5-pro-latest"
# are good choices. "Flash" is faster and more cost-effective for many tasks,
# while "Pro" might offer more advanced reasoning for highly complex queries.
# Check the official documentation for the latest model names and capabilities.
try:
    model = genai.GenerativeModel('gemini-1.5-flash-latest') # Or 'gemini-1.5-pro-latest'
except Exception as e:
    print(f"🔴 ERROR: Could not initialize the model: {e}")
    exit()

# --- Define a Research-Oriented Prompt ---
research_prompt = (
"""You are a professional fact-checker with access to extensive knowledge across multiple domains including science, politics, economics, history, and current events.

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
)


print(f"🔍 Sending prompt to Gemini: \"{research_prompt[:100]}...\"") # Print a snippet of the prompt

# --- Generate Content ---
try:
    # For simple text-in, text-out, use generate_content
    response = model.generate_content(research_prompt)

    # --- Process and Display the Response ---
    if response and response.text:
        print("\n✅ Gemini's Response:")
        print("--------------------------------------------------")
        print(response.text)
        print("--------------------------------------------------")
    else:
        # Handle cases where the response might be blocked or empty
        print("\n⚠️ Gemini's Response was empty or blocked.")
        if response:
            print(f"Prompt Feedback: {response.prompt_feedback}")
            if response.candidates and response.candidates[0].finish_reason:
                 print(f"Finish Reason: {response.candidates[0].finish_reason.name}")
            if response.candidates and response.candidates[0].safety_ratings:
                print("Safety Ratings:")
                for rating in response.candidates[0].safety_ratings:
                    print(f"  - Category: {rating.category.name}, Probability: {rating.probability.name}")


except Exception as e:
    print(f"\n🔴 ERROR: An error occurred during content generation: {e}")

print("\n✨ Snippet execution complete.")

