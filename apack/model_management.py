from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from dotenv import load_dotenv
import os
from typing import Optional, List

load_dotenv()

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


def get_llm_model(model: str, api_key: Optional[str] = None):
    """
    Initialize and return the specified LLM model.
    
    Args:
        model: Model name ("openai", "groq", "google")
        api_key: Optional API key override
    
    Returns:
        Initialized LLM model instance
        
    Raises:
        ValueError: If model is unsupported or API key is missing
    """
    
    if model == "openai":
        effective_key = api_key or OPENAI_API_KEY
        if not effective_key:
            raise ValueError("OpenAI API key not found")
        return ChatOpenAI(
            api_key=effective_key,
            model="gpt-4o-mini",
            temperature=0.3
        )
    elif model == "groq":
        effective_key = api_key or GROQ_API_KEY
        if not effective_key:
            raise ValueError("Groq API key not found")
        return ChatGroq(
            api_key=effective_key,
            model="llama-3.3-70b-versatile",
            temperature=0.3
        )
    elif model == "google":
        effective_key = api_key or GOOGLE_API_KEY
        if not effective_key:
            raise ValueError("Google API key not found")
        return ChatGoogleGenerativeAI(
            api_key=effective_key,
            model="gemini-2.0-flash-exp",
            temperature=0.3
        )
    else:
        raise ValueError(f"Unsupported model: {model}")


def get_available_models() -> List[str]:
    """Get list of available models based on API key availability."""
    available = []
    
    if OPENAI_API_KEY:
        available.append("openai")
    if GROQ_API_KEY:
        available.append("groq")
    if GOOGLE_API_KEY:
        available.append("google")
    
    return available


def validate_model_availability(model: str) -> bool:
    """Check if a model is available based on API key presence."""
    return model in get_available_models()