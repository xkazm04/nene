import os
import logging
import requests
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
from pydantic import BaseModel
import json
import argparse

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

class SearchResult(BaseModel):
    url: str
    name: str
    snippet: str
    metadata: str

class YouAPIResponse(BaseModel):
    answer: str
    search_results: List[SearchResult]

class YouAPIService:
    def __init__(self):
        """Initialize You.com API service with API key from environment."""
        self.api_key = os.getenv("YOU_API_KEY")
        if not self.api_key:
            raise ValueError("YOU_API_KEY not found in environment variables")
        
        self.base_url = "https://api.ydc-index.io/search"
        self.headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }
        logger.info("You.com API service initialized successfully")
    
    def search_query(self, query: str) -> YouAPIResponse:
        """
        Search using You.com API and return structured response.
        
        Args:
            query: Search query string
            
        Returns:
            YouAPIResponse: Structured response with answer and search results
            
        Raises:
            Exception: If API call fails
        """
        try:
            logger.info(f"Starting You.com API search for query: {query[:100]}...")
            
            payload = {
                "query": query
            }
            
            logger.debug("Sending request to You.com API")
            response = requests.post(
                self.base_url,
                json=payload,
                headers=self.headers,
                timeout=30
            )
            
            logger.info(f"You.com API response status: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f"You.com API returned status {response.status_code}: {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            # Parse the response
            response_data = response.json()
            logger.debug(f"Raw response keys: {list(response_data.keys())}")
            
            # Extract answer (assuming it's in 'answer' field or similar)
            answer = self._extract_answer(response_data)
            
            # Extract search results
            search_results = self._extract_search_results(response_data)
            
            result = YouAPIResponse(
                answer=answer,
                search_results=search_results
            )
            
            logger.info(f"Successfully processed You.com API response")
            logger.info(f"Answer length: {len(answer)} characters")
            logger.info(f"Found {len(search_results)} search results")
            
            return result
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error calling You.com API: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Failed to search with You.com API: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def _extract_answer(self, response_data: Dict[str, Any]) -> str:
        """Extract the main answer from You.com API response."""
        # Try different possible fields for the answer
        possible_fields = ['answer', 'response', 'text', 'message', 'content']
        
        for field in possible_fields:
            if field in response_data and response_data[field]:
                return str(response_data[field])
        
        # If no direct answer field, try to construct from other data
        if 'choices' in response_data and response_data['choices']:
            first_choice = response_data['choices'][0]
            if 'message' in first_choice and 'content' in first_choice['message']:
                return first_choice['message']['content']
        
        # Fallback: return raw response as string
        logger.warning("Could not find answer field in response, using raw response")
        return json.dumps(response_data, indent=2)
    
    def _extract_search_results(self, response_data: Dict[str, Any]) -> List[SearchResult]:
        """Extract search results from You.com API response."""
        search_results = []
        
        # Try different possible fields for search results
        possible_fields = ['search_results', 'results', 'sources', 'citations', 'web_results']
        
        for field in possible_fields:
            if field in response_data and isinstance(response_data[field], list):
                for result in response_data[field]:
                    try:
                        search_result = SearchResult(
                            url=result.get('url', ''),
                            name=result.get('name', result.get('title', 'Unknown')),
                            snippet=result.get('snippet', result.get('description', '')),
                            metadata=json.dumps(result.get('metadata', {}))
                        )
                        search_results.append(search_result)
                    except Exception as e:
                        logger.warning(f"Failed to parse search result: {e}")
                        continue
                break
        
        if not search_results:
            logger.info("No search results found in response")
        
        return search_results

# Create service instance
you_service = YouAPIService()

def main():
    """Main function for console testing."""
    parser = argparse.ArgumentParser(description='Test You.com API service')
    parser.add_argument('query', help='Search query to test')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        print(f"Testing You.com API with query: {args.query}")
        print("-" * 50)
        
        # Perform search
        result = you_service.search_query(args.query)
        
        # Display results
        print(f"ANSWER:")
        print(f"{result.answer}")
        print()
        
        print(f"SEARCH RESULTS ({len(result.search_results)} found):")
        for i, search_result in enumerate(result.search_results, 1):
            print(f"{i}. {search_result.name}")
            print(f"   URL: {search_result.url}")
            print(f"   Snippet: {search_result.snippet[:200]}...")
            print(f"   Metadata: {search_result.metadata}")
            print()
        
        print("Test completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
    
    
# python -m services.you_service "Who won the Nobel Prize in Physics in 2024? Please answer in one sentence."