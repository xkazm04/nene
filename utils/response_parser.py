import logging
import json
from typing import Dict, Any, List, Optional
from models.research_models import (
    LLMResearchResponse, 
    LLMResearchRequest,
    ExpertOpinion, 
    ExpertPerspective,
    ResourceAnalysis, 
    ResourceReference,
    StatementCategory
)

logger = logging.getLogger(__name__)

class ResponseParser:
    """Enhanced parser for LLM responses with expert perspectives support"""
    
    def create_response_object(self, parsed_response: Dict[str, Any], request: LLMResearchRequest) -> LLMResearchResponse:
        """
        Create LLMResearchResponse object from parsed JSON response.
        Enhanced to properly handle expert_perspectives from LLM output.
        
        Args:
            parsed_response: Parsed JSON response from LLM
            request: Original research request
            
        Returns:
            LLMResearchResponse object
        """
        try:
            logger.debug("Creating response object with expert perspectives support")
            
            # Parse basic fields
            valid_sources = parsed_response.get("valid_sources", "")
            verdict = parsed_response.get("verdict", "")
            status = parsed_response.get("status", "UNVERIFIABLE")
            correction = parsed_response.get("correction")
            country = parsed_response.get("country", request.country)
            category = parsed_response.get("category", request.category)
            
            # Parse legacy expert opinions
            experts = self._parse_expert_opinions(parsed_response.get("experts", {}))
            
            # Parse NEW expert perspectives from LLM response
            expert_perspectives = self._parse_expert_perspectives(parsed_response.get("expert_perspectives", []))
            
            # If no expert_perspectives but we have legacy experts, convert them
            if not expert_perspectives and experts:
                expert_perspectives = self._convert_legacy_experts_to_perspectives(experts)
                logger.info(f"Converted {len(expert_perspectives)} legacy expert opinions to perspectives")
            
            # Parse resource analysis
            resources_agreed = self._parse_resource_analysis(parsed_response.get("resources_agreed", {}))
            resources_disagreed = self._parse_resource_analysis(parsed_response.get("resources_disagreed", {}))
            
            # Parse category
            if category and isinstance(category, str):
                try:
                    category = StatementCategory(category.lower())
                except ValueError:
                    logger.warning(f"Invalid category '{category}', using OTHER")
                    category = StatementCategory.OTHER
            
            response = LLMResearchResponse(
                valid_sources=valid_sources,
                verdict=verdict,
                status=status,
                correction=correction,
                country=country,
                category=category,
                resources_agreed=resources_agreed,
                resources_disagreed=resources_disagreed,
                experts=experts,
                expert_perspectives=expert_perspectives,  # Properly set expert perspectives
                research_method="LLM Research",
                profile_id=request.profile_id,
                research_summary=verdict,  # Use verdict as initial summary
                confidence_score=self._calculate_confidence_score(parsed_response, expert_perspectives)
            )
            
            logger.info(f"Created response object with {len(expert_perspectives)} expert perspectives")
            return response
            
        except Exception as e:
            logger.error(f"Failed to create response object: {e}")
            logger.error(f"Parsed response keys: {list(parsed_response.keys())}")
            
            # Create minimal fallback response
            return LLMResearchResponse(
                valid_sources="Error parsing response",
                verdict=f"Response parsing failed: {str(e)}",
                status="UNVERIFIABLE",
                research_method="LLM Research (Error)",
                profile_id=request.profile_id,
                expert_perspectives=[],  # Empty list for failed parsing
                confidence_score=30
            )
    
    def _parse_expert_perspectives(self, perspectives_data: List[Dict[str, Any]]) -> List[ExpertPerspective]:
        """
        Parse expert perspectives from LLM response.
        
        Args:
            perspectives_data: List of expert perspective dictionaries from LLM
            
        Returns:
            List of ExpertPerspective objects
        """
        perspectives = []
        
        if not perspectives_data or not isinstance(perspectives_data, list):
            logger.debug("No expert perspectives data found or invalid format")
            return perspectives
        
        for i, perspective_data in enumerate(perspectives_data):
            try:
                if not isinstance(perspective_data, dict):
                    logger.warning(f"Invalid perspective data format at index {i}: {type(perspective_data)}")
                    continue
                
                # Extract required fields with validation
                expert_name = perspective_data.get("expert_name", f"Expert {i+1}")
                stance = perspective_data.get("stance", "NEUTRAL")
                reasoning = perspective_data.get("reasoning", "")
                confidence_level = float(perspective_data.get("confidence_level", 50.0))
                summary = perspective_data.get("summary", "")
                
                # Validate stance
                if stance not in ["SUPPORTING", "OPPOSING", "NEUTRAL"]:
                    logger.warning(f"Invalid stance '{stance}' for expert {expert_name}, using NEUTRAL")
                    stance = "NEUTRAL"
                
                # Validate confidence level
                confidence_level = max(0.0, min(100.0, confidence_level))
                
                # Extract optional fields
                source_type = perspective_data.get("source_type", "llm")
                expertise_area = perspective_data.get("expertise_area", "General Analysis")
                publication_date = perspective_data.get("publication_date")
                
                perspective = ExpertPerspective(
                    expert_name=expert_name,
                    stance=stance,
                    reasoning=reasoning,
                    confidence_level=confidence_level,
                    summary=summary,
                    source_type=source_type,
                    expertise_area=expertise_area,
                    publication_date=publication_date
                )
                
                perspectives.append(perspective)
                logger.debug(f"Parsed expert perspective: {expert_name} ({stance})")
                
            except Exception as e:
                logger.warning(f"Failed to parse expert perspective at index {i}: {e}")
                logger.warning(f"Perspective data: {perspective_data}")
                continue
        
        logger.info(f"Successfully parsed {len(perspectives)} expert perspectives")
        return perspectives
    
    def _convert_legacy_experts_to_perspectives(self, experts: ExpertOpinion) -> List[ExpertPerspective]:
        """
        Convert legacy ExpertOpinion to ExpertPerspective objects.
        
        Args:
            experts: Legacy ExpertOpinion object
            
        Returns:
            List of ExpertPerspective objects
        """
        perspectives = []
        
        # Convert CRITIC
        if experts.critic:
            perspectives.append(ExpertPerspective(
                expert_name="Critical Analyst",
                stance="NEUTRAL",
                reasoning=experts.critic,
                confidence_level=75.0,
                summary="Critical analysis of the statement",
                source_type="llm",
                expertise_area="Critical Analysis",
                publication_date=None
            ))
        
        # Convert DEVIL
        if experts.devil:
            perspectives.append(ExpertPerspective(
                expert_name="Devil's Advocate",
                stance="OPPOSING",
                reasoning=experts.devil,
                confidence_level=70.0,
                summary="Counter-arguments to the statement",
                source_type="llm",
                expertise_area="Counter-Analysis",
                publication_date=None
            ))
        
        # Convert NERD
        if experts.nerd:
            perspectives.append(ExpertPerspective(
                expert_name="Technical Expert",
                stance="SUPPORTING",  # Usually data-driven, tends to support if evidence exists
                reasoning=experts.nerd,
                confidence_level=85.0,
                summary="Technical/statistical analysis of the statement",
                source_type="llm",
                expertise_area="Technical/Statistical Analysis",
                publication_date=None
            ))
        
        # Convert PSYCHIC
        if experts.psychic:
            perspectives.append(ExpertPerspective(
                expert_name="Predictive Analyst",
                stance="NEUTRAL",
                reasoning=experts.psychic,
                confidence_level=60.0,
                summary="Future implications and predictions based on the statement",
                source_type="llm",
                expertise_area="Psychological/Motivational Analysis",
                publication_date=None
            ))
        
        return perspectives
    
    def _parse_expert_opinions(self, experts_data: Dict[str, Any]) -> Optional[ExpertOpinion]:
        """Parse legacy expert opinions format"""
        if not experts_data:
            return None
        
        try:
            return ExpertOpinion(
                critic=experts_data.get("critic"),
                devil=experts_data.get("devil"),
                nerd=experts_data.get("nerd"),
                psychic=experts_data.get("psychic")
            )
        except Exception as e:
            logger.warning(f"Failed to parse expert opinions: {e}")
            return None
    
    def _parse_resource_analysis(self, resource_data: Dict[str, Any]) -> Optional[ResourceAnalysis]:
        """Parse resource analysis data"""
        if not resource_data:
            return None
        
        try:
            # Parse references
            references = []
            for ref_data in resource_data.get("references", []):
                if isinstance(ref_data, dict):
                    reference = ResourceReference(
                        url=ref_data.get("url", ""),
                        title=ref_data.get("title", ""),
                        category=ref_data.get("category", "other"),
                        country=ref_data.get("country", "unknown"),
                        credibility=ref_data.get("credibility", "medium")
                    )
                    references.append(reference)
            
            return ResourceAnalysis(
                total=resource_data.get("total", "0%"),
                count=resource_data.get("count", 0),
                mainstream=resource_data.get("mainstream", 0),
                governance=resource_data.get("governance", 0),
                academic=resource_data.get("academic", 0),
                medical=resource_data.get("medical", 0),
                other=resource_data.get("other", 0),
                major_countries=resource_data.get("major_countries", []),
                references=references
            )
        except Exception as e:
            logger.warning(f"Failed to parse resource analysis: {e}")
            return None
    
    def _calculate_confidence_score(self, parsed_response: Dict[str, Any], expert_perspectives: List[ExpertPerspective]) -> int:
        """Calculate confidence score based on response data and expert perspectives"""
        
        # Start with base confidence
        base_confidence = 50
        
        # Boost based on status
        status = parsed_response.get("status", "UNVERIFIABLE")
        if status in ["TRUE", "FALSE"]:
            base_confidence += 20
        elif status in ["PARTIALLY_TRUE", "MISLEADING"]:
            base_confidence += 10
        
        # Boost based on number of expert perspectives
        perspective_boost = min(len(expert_perspectives) * 5, 25)
        base_confidence += perspective_boost
        
        # Boost based on average expert confidence
        if expert_perspectives:
            avg_expert_confidence = sum(p.confidence_level for p in expert_perspectives) / len(expert_perspectives)
            confidence_boost = (avg_expert_confidence - 50) * 0.2  # Scale to reasonable range
            base_confidence += int(confidence_boost)
        
        # Boost based on resource count
        resources_agreed = parsed_response.get("resources_agreed", {})
        resources_disagreed = parsed_response.get("resources_disagreed", {})
        
        total_resources = (resources_agreed.get("count", 0) + resources_disagreed.get("count", 0))
        resource_boost = min(total_resources * 2, 15)
        base_confidence += resource_boost
        
        return max(30, min(95, base_confidence))

# Create parser instance
response_parser = ResponseParser()