import os
import logging
import asyncio
from typing import List, Dict, Optional, Union
from enum import Enum
from dataclasses import dataclass, field
from urllib.parse import urlparse, urljoin
import aiohttp
import time

from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, START, END
from langchain_core.runnables import RunnableConfig
from google.genai import Client
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Validate required environment variables
if os.getenv("GOOGLE_API_KEY") is None:
    logger.error("GOOGLE_API_KEY environment variable is not set")
    raise ValueError("GOOGLE_API_KEY is not set")

try:
    genai_client = Client(api_key=os.getenv("GOOGLE_API_KEY"))
    logger.info("Google GenAI client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Google GenAI client: {e}")
    raise


class ImageType(Enum):
    """Supported image types for avatar search"""
    SPORT_PLAYER = "sport_player"
    VIDEO_GAME = "video_game"


@dataclass
class ImageResult:
    """Data class for image search results"""
    url: str
    title: str
    source: str
    is_preferred: bool = False
    content_type: str = ""
    status: str = "unknown"
    file_size: Optional[int] = None
    dimensions: Optional[tuple] = None


@dataclass
class ImageSearchState:
    """State for the image search agent"""
    query: str
    image_type: ImageType
    search_query: str = ""
    search_results: List[ImageResult] = field(default_factory=list)
    validated_images: List[ImageResult] = field(default_factory=list)
    final_image: Optional[ImageResult] = None
    error_message: Optional[str] = None
    processing_time: float = 0.0


@dataclass
class Configuration:
    """Configuration for the image search agent"""
    max_results: int = 10
    verify_timeout: int = 5
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    preferred_sources: List[str] = field(default_factory=lambda: [
        "pinterest.com", "steam", "espn.com", "nba.com", "nfl.com", 
        "wikipedia.org", "wikimedia.org", "official"
    ])
    model: str = "gemini-2.0-flash-exp"
    allowed_content_types: List[str] = field(default_factory=lambda: [
        "image/jpeg", "image/png", "image/webp", "image/gif"
    ])


def generate_search_query(state: ImageSearchState, config: RunnableConfig) -> Dict:
    """Generate optimized search queries for finding avatar images"""
    logger.info(f"Generating search query for: {state.query} (type: {state.image_type.value})")
    
    start_time = time.time()
    
    try:
        llm = ChatGoogleGenerativeAI(
            model=config.get("model", "gemini-2.0-flash-exp"),
            temperature=0.7,
            api_key=os.getenv("GOOGLE_API_KEY"),
        )
        
        # Create search query based on type
        if state.image_type == ImageType.SPORT_PLAYER:
            prompt = f"""Generate an optimized image search query to find a high-quality avatar/profile image for:
            Sport Player: {state.query}
            
            Include terms like: avatar, profile picture, headshot, official photo, portrait
            Target sources: ESPN, NBA.com, NFL.com, Pinterest sport boards, Wikipedia
            Avoid: cartoon, artwork, fan art, low resolution
            
            Return a single optimized search query (max 10 words)."""
        else:  # VIDEO_GAME
            prompt = f"""Generate an optimized image search query to find game cover art or logo for:
            Video Game: {state.query}
            
            Include terms like: cover art, game logo, steam banner, official artwork, icon
            Target sources: Steam, Pinterest gaming boards, official game sites, Wikipedia
            Avoid: screenshot, gameplay, fan art, low resolution
            
            Return a single optimized search query (max 10 words)."""
        
        result = llm.invoke(prompt)
        search_query = result.content.strip().replace('"', '').replace("'", "")
        
        processing_time = time.time() - start_time
        logger.info(f"Generated search query: '{search_query}' in {processing_time:.2f}s")
        
        return {
            "search_query": search_query,
            "processing_time": state.processing_time + processing_time
        }
        
    except Exception as e:
        logger.error(f"Error generating search query: {e}")
        return {
            "search_query": state.query,  # Fallback to original query
            "error_message": f"Query generation failed: {str(e)}",
            "processing_time": state.processing_time + (time.time() - start_time)
        }


def search_images(state: ImageSearchState, config: RunnableConfig) -> Dict:
    """Search for images using Google Search API"""
    logger.info(f"Searching for images with query: '{state.search_query}'")
    
    start_time = time.time()
    search_query = state.search_query or state.query
    
    try:
        # Add image-specific search parameters
        formatted_query = f"{search_query} high quality avatar profile picture filetype:jpg OR filetype:png OR filetype:webp"
        logger.debug(f"Formatted search query: {formatted_query}")
        
        # Use Google Search with image focus
        response = genai_client.models.generate_content(
            model=config.get("model", "gemini-2.0-flash-exp"),
            contents=f"Search for high-quality images matching: {formatted_query}. Focus on professional avatar images, profile pictures, or game cover art. Return image URLs with their sources and titles.",
            config={
                "tools": [{"google_search": {}}],
                "temperature": 0,
            },
        )
        
        # Extract image URLs from search results
        search_results = []
        results_count = 0
        
        if response.candidates and response.candidates[0].grounding_metadata:
            for chunk in response.candidates[0].grounding_metadata.grounding_chunks:
                if hasattr(chunk, 'web') and chunk.web and results_count < config.get("max_results", 10):
                    url = chunk.web.uri
                    title = chunk.web.title if hasattr(chunk.web, 'title') else "Untitled"
                    source = urlparse(url).netloc
                    
                    # Filter for image URLs and validate format
                    if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']):
                        # Security check - avoid suspicious URLs
                        if _is_safe_url(url):
                            search_results.append(ImageResult(
                                url=url,
                                title=title,
                                source=source,
                                status="found"
                            ))
                            results_count += 1
                            logger.debug(f"Found image: {url} from {source}")
                        else:
                            logger.warning(f"Skipping potentially unsafe URL: {url}")
        
        processing_time = time.time() - start_time
        logger.info(f"Found {len(search_results)} images in {processing_time:.2f}s")
        
        return {
            "search_results": search_results,
            "processing_time": state.processing_time + processing_time
        }
        
    except Exception as e:
        logger.error(f"Error during image search: {e}")
        return {
            "search_results": [],
            "error_message": f"Image search failed: {str(e)}",
            "processing_time": state.processing_time + (time.time() - start_time)
        }


async def validate_images(state: ImageSearchState, config: RunnableConfig) -> Dict:
    """Validate that images are accessible and safe"""
    logger.info(f"Validating {len(state.search_results)} images")
    
    start_time = time.time()
    validated_images = []
    timeout = config.get("verify_timeout", 5)
    max_file_size = config.get("max_file_size", 10 * 1024 * 1024)
    allowed_content_types = config.get("allowed_content_types", ["image/jpeg", "image/png", "image/webp"])
    preferred_sources = config.get("preferred_sources", [])
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
        tasks = []
        for image in state.search_results:
            tasks.append(_validate_single_image(session, image, max_file_size, allowed_content_types, preferred_sources))
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, ImageResult) and result.status == "valid":
                    validated_images.append(result)
                elif isinstance(result, Exception):
                    logger.warning(f"Image validation failed: {result}")
                    
        except Exception as e:
            logger.error(f"Error during batch image validation: {e}")
    
    # Sort by preferred sources first, then by file size (smaller first for faster loading)
    validated_images.sort(key=lambda x: (
        not x.is_preferred,  # Preferred sources first
        x.file_size or float('inf')  # Smaller files first
    ))
    
    processing_time = time.time() - start_time
    logger.info(f"Validated {len(validated_images)} out of {len(state.search_results)} images in {processing_time:.2f}s")
    
    return {
        "validated_images": validated_images,
        "processing_time": state.processing_time + processing_time
    }


async def _validate_single_image(
    session: aiohttp.ClientSession, 
    image: ImageResult, 
    max_file_size: int,
    allowed_content_types: List[str],
    preferred_sources: List[str]
) -> ImageResult:
    """Validate a single image"""
    try:
        logger.debug(f"Validating image: {image.url}")
        
        async with session.head(image.url, allow_redirects=True) as response:
            if response.status == 200:
                content_type = response.headers.get('content-type', '').lower()
                content_length = response.headers.get('content-length')
                
                # Check content type
                if not any(ct in content_type for ct in allowed_content_types):
                    logger.debug(f"Invalid content type: {content_type} for {image.url}")
                    return ImageResult(url=image.url, title=image.title, source=image.source, status="invalid_type")
                
                # Check file size
                if content_length:
                    file_size = int(content_length)
                    if file_size > max_file_size:
                        logger.debug(f"File too large: {file_size} bytes for {image.url}")
                        return ImageResult(url=image.url, title=image.title, source=image.source, status="too_large")
                    image.file_size = file_size
                
                # Check if from preferred source
                is_preferred = any(source.lower() in image.source.lower() for source in preferred_sources)
                
                image.content_type = content_type
                image.is_preferred = is_preferred
                image.status = "valid"
                
                logger.debug(f"Image validated successfully: {image.url} (preferred: {is_preferred})")
                return image
            else:
                logger.debug(f"HTTP {response.status} for {image.url}")
                return ImageResult(url=image.url, title=image.title, source=image.source, status=f"http_{response.status}")
                
    except Exception as e:
        logger.debug(f"Validation failed for {image.url}: {e}")
        return ImageResult(url=image.url, title=image.title, source=image.source, status="error")


def select_best_image(state: ImageSearchState, config: RunnableConfig) -> Dict:
    """Use AI to select the most appropriate image"""
    logger.info(f"Selecting best image from {len(state.validated_images)} candidates")
    
    start_time = time.time()
    
    if not state.validated_images:
        logger.warning("No valid images available for selection")
        return {
            "final_image": None,
            "error_message": "No valid images found",
            "processing_time": state.processing_time + (time.time() - start_time)
        }
    
    # If only one image or first is from preferred source, use it
    if len(state.validated_images) == 1:
        logger.info("Only one valid image available, selecting it")
        return {
            "final_image": state.validated_images[0],
            "processing_time": state.processing_time + (time.time() - start_time)
        }
    
    if state.validated_images[0].is_preferred:
        logger.info("First image is from preferred source, selecting it")
        return {
            "final_image": state.validated_images[0],
            "processing_time": state.processing_time + (time.time() - start_time)
        }
    
    try:
        # Use AI to select best image
        llm = ChatGoogleGenerativeAI(
            model=config.get("model", "gemini-2.0-flash-exp"),
            temperature=0,
            api_key=os.getenv("GOOGLE_API_KEY"),
        )
        
        top_images = state.validated_images[:5]  # Limit to top 5
        image_descriptions = "\n".join([
            f"{i+1}. URL: {img.url}\n   Title: {img.title}\n   Source: {img.source}\n   Preferred: {img.is_preferred}\n   Size: {img.file_size or 'unknown'} bytes"
            for i, img in enumerate(top_images)
        ])
        
        prompt = f"""Select the best avatar/profile image for "{state.query}" (type: {state.image_type.value}) from these options:

{image_descriptions}

Criteria for {state.image_type.value}:
- High quality and professional appearance
- Clear view of subject (person's face for players, game logo/art for games)
- From reputable source (preferred sources are better)
- Appropriate size (not too large for web use)
- Relevant to the query

Return only the number (1-{len(top_images)}) of the best option."""
        
        result = llm.invoke(prompt)
        
        try:
            selected_index = int(result.content.strip()) - 1
            if 0 <= selected_index < len(top_images):
                selected_image = top_images[selected_index]
                logger.info(f"AI selected image {selected_index + 1}: {selected_image.url}")
                return {
                    "final_image": selected_image,
                    "processing_time": state.processing_time + (time.time() - start_time)
                }
        except ValueError as e:
            logger.warning(f"Could not parse AI selection: {result.content}. Error: {e}")
    
    except Exception as e:
        logger.error(f"Error during AI image selection: {e}")
    
    # Fallback to first image
    logger.info("Falling back to first validated image")
    return {
        "final_image": state.validated_images[0],
        "processing_time": state.processing_time + (time.time() - start_time)
    }


def format_response(state: ImageSearchState, config: RunnableConfig) -> Dict:
    """Format the final response"""
    logger.info("Formatting final response")
    
    if state.error_message:
        logger.error(f"Image search completed with error: {state.error_message}")
        return {
            "messages": [AIMessage(content=f"Error: {state.error_message}")],
            "image_result": None,
            "processing_time": state.processing_time
        }
    
    if not state.final_image:
        logger.warning("Image search completed but no suitable image found")
        return {
            "messages": [AIMessage(content="No suitable image found for the query.")],
            "image_result": None,
            "processing_time": state.processing_time
        }
    
    image = state.final_image
    
    message_content = f"""Found avatar image for "{state.query}":

**Image URL:** {image.url}
**Source:** {image.source}
**Title:** {image.title}
**Content Type:** {image.content_type}
**File Size:** {image.file_size or 'Unknown'} bytes
**Preferred Source:** {'Yes' if image.is_preferred else 'No'}

This image has been validated as accessible and appropriate for use as an avatar."""
    
    result = {
        "messages": [AIMessage(content=message_content)],
        "image_result": {
            "url": image.url,
            "source": image.source,
            "title": image.title,
            "content_type": image.content_type,
            "file_size": image.file_size,
            "is_preferred": image.is_preferred,
            "query": state.query,
            "type": state.image_type.value
        },
        "processing_time": state.processing_time
    }
    
    logger.info(f"Image search completed successfully in {state.processing_time:.2f}s. Found: {image.url}")
    return result


def _is_safe_url(url: str) -> bool:
    """Basic URL safety check"""
    try:
        parsed = urlparse(url)
        
        # Check for basic URL structure
        if not parsed.scheme in ['http', 'https']:
            return False
            
        if not parsed.netloc:
            return False
            
        # Avoid suspicious domains
        suspicious_patterns = ['bit.ly', 'tinyurl', 'localhost', '127.0.0.1']
        if any(pattern in parsed.netloc.lower() for pattern in suspicious_patterns):
            return False
            
        return True
        
    except Exception:
        return False


# Create the Agent Graph
builder = StateGraph(ImageSearchState, config_schema=Configuration)

# Add nodes
builder.add_node("generate_query", generate_search_query)
builder.add_node("search_images", search_images)
builder.add_node("validate_images", validate_images)
builder.add_node("select_best", select_best_image)
builder.add_node("format_response", format_response)

# Define flow
builder.add_edge(START, "generate_query")
builder.add_edge("generate_query", "search_images")
builder.add_edge("search_images", "validate_images")
builder.add_edge("validate_images", "select_best")
builder.add_edge("select_best", "format_response")
builder.add_edge("format_response", END)

# Compile graph
graph = builder.compile(name="image-search-agent")


# Helper function to use the agent
async def find_avatar(query: str, image_type: str = "sport_player") -> Optional[Dict]:
    """
    Find an avatar image for a sport player or video game.
    
    Args:
        query: Name of sport player or video game title
        image_type: Either "sport_player" or "video_game"
    
    Returns:
        Dict with image URL and metadata, or None if failed
    """
    logger.info(f"Starting avatar search for: '{query}' (type: {image_type})")
    
    try:
        # Validate inputs
        if not query or not query.strip():
            logger.error("Empty query provided")
            return None
            
        if image_type not in ["sport_player", "video_game"]:
            logger.error(f"Invalid image_type: {image_type}")
            return None
        
        initial_state = ImageSearchState(
            query=query.strip(),
            image_type=ImageType.SPORT_PLAYER if image_type == "sport_player" else ImageType.VIDEO_GAME
        )
        
        config = {
            "model": "gemini-2.0-flash-exp",
            "max_results": 10,
            "verify_timeout": 5,
            "max_file_size": 10 * 1024 * 1024,  # 10MB
            "preferred_sources": ["pinterest.com", "steam", "espn.com", "nba.com", "nfl.com", "wikipedia.org"],
            "allowed_content_types": ["image/jpeg", "image/png", "image/webp", "image/gif"]
        }
        
        result = await graph.ainvoke(initial_state, config)
        
        if result.get("image_result"):
            logger.info(f"Avatar search successful for '{query}'")
        else:
            logger.warning(f"Avatar search failed for '{query}'")
            
        return result.get("image_result")
        
    except Exception as e:
        logger.error(f"Unexpected error during avatar search for '{query}': {e}")
        return None


async def main():
    """Main function for testing"""
    try:
        # Example usage
        result = await find_avatar("LeBron James", "sport_player")
        if result:
            print(f"Success: {result}")
        else:
            print("No result found")
    except Exception as e:
        logger.error(f"Error during image search: {e}")
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())