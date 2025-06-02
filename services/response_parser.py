import logging
from typing import Dict, Any, Optional
from models.research_models import (
    LLMResearchRequest, 
    LLMResearchResponse, 
    ExpertOpinion, 
    ResourceAnalysis, 
    ResourceReference
)

logger = logging.getLogger(__name__)

class ResponseParser:
    """Parser for LLM responses to create structured response objects."""
    
    def create_response_object(self, parsed_response: Dict[str, Any], request: LLMResearchRequest) -> LLMResearchResponse:
        """Create standardized response object from parsed JSON."""
        
        # Extract expert opinions with defaults
        experts = self._parse_experts(parsed_response.get("experts", {}))
        
        # Extract resource analysis with safe defaults
        resources_agreed = self._parse_resource_analysis(parsed_response.get("resources_agreed", {}))
        resources_disagreed = self._parse_resource_analysis(parsed_response.get("resources_disagreed", {}))
        
        # Create structured response
        return LLMResearchResponse(
            valid_sources=parsed_response.get("valid_sources", "Unknown"),
            verdict=parsed_response.get("verdict", "Unable to determine verdict"),
            status=parsed_response.get("status", "UNVERIFIABLE"),
            correction=parsed_response.get("correction"),
            country=parsed_response.get("country") or request.country,
            category=parsed_response.get("category") or request.category,
            resources_agreed=resources_agreed,
            resources_disagreed=resources_disagreed,
            experts=experts,
            research_method=""  # Will be set by calling client
        )
    
    def _parse_experts(self, experts_data: Dict[str, Any]) -> ExpertOpinion:
        """Parse expert opinions from response data."""
        return ExpertOpinion(
            critic=experts_data.get("critic"),
            devil=experts_data.get("devil"),
            nerd=experts_data.get("nerd"),
            psychic=experts_data.get("psychic")
        )
    
    def _parse_resource_analysis(self, resource_data: Dict[str, Any]) -> Optional[ResourceAnalysis]:
        """Parse resource analysis from response data with error handling."""
        if not resource_data:
            return ResourceAnalysis(total="0%", count=0)
        
        try:
            return ResourceAnalysis(
                total=resource_data.get("total", "0%"),
                count=resource_data.get("count", 0),
                mainstream=resource_data.get("mainstream", 0),
                governance=resource_data.get("governance", 0),
                academic=resource_data.get("academic", 0),
                medical=resource_data.get("medical", 0),
                other=resource_data.get("other", 0),
                major_countries=resource_data.get("major_countries", []),
                references=self._parse_references(resource_data.get("references", []))
            )
        except Exception as e:
            logger.warning(f"Failed to parse resource analysis: {e}")
            return ResourceAnalysis(total="0%", count=0)
    
    def _parse_references(self, references_data: list) -> list[ResourceReference]:
        """Parse reference list with error handling."""
        references = []
        
        for ref_data in references_data:
            try:
                references.append(ResourceReference(**ref_data))
            except Exception as e:
                logger.warning(f"Failed to parse reference: {e}")
                continue
        
        return references
    
    def create_error_response(self, request: LLMResearchRequest, error_message: str = "Service Error") -> LLMResearchResponse:
        """Create error response when research fails."""
        return LLMResearchResponse(
            valid_sources=f"0 ({error_message})",
            verdict=f"Unable to fact-check due to {error_message.lower()}",
            status="UNVERIFIABLE",
            correction=None,
            country=request.country,
            category=request.category,
            resources_agreed=ResourceAnalysis(total="0%", count=0),
            resources_disagreed=ResourceAnalysis(total="0%", count=0),
            experts=ExpertOpinion(),
            research_method=f"Error - {error_message}"
        )