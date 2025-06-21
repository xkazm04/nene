import logging
import json
import traceback
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
    """Enhanced parser for LLM responses with flexible resource categorization"""
    
    def parse_llm_response(self, response: str, request: Optional[LLMResearchRequest] = None) -> LLMResearchResponse:
        """
        Parse raw LLM response text and return LLMResearchResponse object.
        
        Args:
            response: Raw response text from LLM
            request: Optional original research request
            
        Returns:
            LLMResearchResponse object
        """
        try:
            logger.info(f"Parsing LLM response ({len(response)} chars)")
            
            # Try to extract JSON from the response
            parsed_json = self._extract_json_from_response(response)
            
            if not parsed_json:
                logger.warning("No valid JSON found in LLM response, creating fallback response")
                return self._create_fallback_response(response, request)
            
            # Create response object using existing method
            if request:
                return self.create_response_object(parsed_json, request)
            else:
                # Create dummy request for compatibility
                dummy_request = LLMResearchRequest(
                    statement="Unknown statement",
                    source="Unknown source",
                    context="Unknown context"
                )
                return self.create_response_object(parsed_json, dummy_request)
                
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.error(f"Response preview: {response[:200]}...")
            return self._create_error_response_from_text(response, str(e), request)
    
    def _extract_json_from_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Extract JSON object from LLM response text"""
        try:
            # First, try to parse the entire response as JSON
            try:
                return json.loads(response.strip())
            except json.JSONDecodeError:
                pass
            
            # Try to find JSON within the response text
            json_patterns = [
                # Look for JSON between triple backticks
                r'```json\s*(\{.*?\})\s*```',
                r'```\s*(\{.*?\})\s*```',
                # Look for JSON blocks
                r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
                # Look for the response format section
                r'RESPONSE FORMAT:.*?(\{.*?\})',
            ]
            
            import re
            
            for pattern in json_patterns:
                matches = re.findall(pattern, response, re.DOTALL | re.IGNORECASE)
                for match in matches:
                    try:
                        # Clean the match
                        json_text = match.strip()
                        if json_text.startswith('{') and json_text.endswith('}'):
                            parsed = json.loads(json_text)
                            if isinstance(parsed, dict) and len(parsed) > 3:  # Should have multiple fields
                                logger.info("Successfully extracted JSON from response")
                                return parsed
                    except json.JSONDecodeError:
                        continue
            
            # Try to extract key-value pairs manually
            return self._extract_key_value_pairs(response)
            
        except Exception as e:
            logger.warning(f"Failed to extract JSON from response: {e}")
            return None
    
    def _extract_key_value_pairs(self, response: str) -> Optional[Dict[str, Any]]:
        """Extract key-value pairs from unstructured response text"""
        try:
            import re
            
            # Common patterns for key-value extraction
            patterns = {
                'valid_sources': r'valid_sources["\']?\s*:\s*["\']?([^"\n,}]+)',
                'verdict': r'verdict["\']?\s*:\s*["\']?([^"\n}]+)',
                'status': r'status["\']?\s*:\s*["\']?(TRUE|FALSE|FACTUAL_ERROR|DECEPTIVE_LIE|MANIPULATIVE|PARTIALLY_TRUE|OUT_OF_CONTEXT|UNVERIFIABLE)',
                'correction': r'correction["\']?\s*:\s*["\']?([^"\n}]+)',
                'country': r'country["\']?\s*:\s*["\']?([a-z]{2})',
                'category': r'category["\']?\s*:\s*["\']?(politics|economy|environment|military|healthcare|education|technology|social|international|legal|history|other)',
                'research_metadata': r'research_metadata["\']?\s*:\s*["\']?([^"\n}]+)',
            }
            
            extracted = {}
            
            for key, pattern in patterns.items():
                matches = re.findall(pattern, response, re.IGNORECASE | re.MULTILINE)
                if matches:
                    extracted[key] = matches[0].strip().strip('"\'')
            
            if len(extracted) >= 3:  # At least some basic fields
                logger.info(f"Extracted {len(extracted)} key-value pairs from response")
                return extracted
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to extract key-value pairs: {e}")
            return None
    
    def _create_fallback_response(self, response: str, request: Optional[LLMResearchRequest]) -> LLMResearchResponse:
        """Create fallback response when JSON parsing fails"""
        
        # Try to extract basic information from text
        import re
        
        # Look for status keywords
        status = "UNVERIFIABLE"
        if re.search(r'\b(true|accurate|correct)\b', response, re.IGNORECASE):
            status = "TRUE"
        elif re.search(r'\b(false|incorrect|wrong|misleading)\b', response, re.IGNORECASE):
            status = "FACTUAL_ERROR"
        elif re.search(r'\b(manipulative|deceptive)\b', response, re.IGNORECASE):
            status = "MANIPULATIVE"
        elif re.search(r'\b(partially|somewhat|mixed)\b', response, re.IGNORECASE):
            status = "PARTIALLY_TRUE"
        
        # Extract a verdict from the response
        sentences = response.split('.')
        verdict = "Analysis completed with limited structured data."
        
        for sentence in sentences:
            if len(sentence.strip()) > 50 and any(word in sentence.lower() for word in ['statement', 'claim', 'evidence', 'analysis']):
                verdict = sentence.strip()[:200] + "..." if len(sentence) > 200 else sentence.strip()
                break
        
        return LLMResearchResponse(
            valid_sources="Unknown (parsed from text)",
            verdict=verdict,
            status=status,
            correction=None,
            country=getattr(request, 'country', None) if request else None,
            category=getattr(request, 'category', None) if request else None,
            research_method="text_parsing_fallback",
            profile_id=getattr(request, 'profile_id', None) if request else None,
            expert_perspectives=[],
            key_findings=[],
            research_summary=response[:300] + "..." if len(response) > 300 else response,
            confidence_score=40,  # Lower confidence for fallback parsing
            research_metadata=None,
            additional_context="Response parsed using fallback text analysis"
        )
    
    def _create_error_response_from_text(self, response: str, error_message: str, request: Optional[LLMResearchRequest]) -> LLMResearchResponse:
        """Create error response when parsing completely fails"""
        return LLMResearchResponse(
            valid_sources="0 (parsing error)",
            verdict=f"Failed to parse LLM response: {error_message}",
            status="UNVERIFIABLE",
            correction=None,
            country=getattr(request, 'country', None) if request else None,
            category=getattr(request, 'category', None) if request else None,
            research_method="error_recovery",
            profile_id=getattr(request, 'profile_id', None) if request else None,
            expert_perspectives=[],
            key_findings=[],
            research_summary="",
            confidence_score=20,
            research_metadata=None,
            additional_context=f"Parse error: {error_message}. Response length: {len(response)} chars"
        )
    
    def create_response_object(self, parsed_response: Dict[str, Any], request: LLMResearchRequest) -> LLMResearchResponse:
        """
        Create LLMResearchResponse object from parsed JSON response.
        Enhanced to handle flexible resource categories.
        
        Args:
            parsed_response: Parsed JSON response from LLM
            request: Original research request
            
        Returns:
            LLMResearchResponse object
        """
        try:
            logger.debug("Creating response object with enhanced resource categorization")
            
            # Parse basic fields
            valid_sources = parsed_response.get("valid_sources", "")
            verdict = parsed_response.get("verdict", "")
            status = parsed_response.get("status", "UNVERIFIABLE")
            correction = parsed_response.get("correction")
            country = parsed_response.get("country", request.country)
            category = parsed_response.get("category", request.category)
            
            # Parse legacy expert opinions
            experts = self._parse_expert_opinions(parsed_response.get("experts", {}))
            
            # Parse expert perspectives from LLM response
            expert_perspectives = self._parse_expert_perspectives(parsed_response.get("expert_perspectives", []))
            
            # Parse resource analysis with enhanced error handling
            resources_agreed = self._parse_resource_analysis_enhanced(parsed_response.get("resources_agreed", {}))
            resources_disagreed = self._parse_resource_analysis_enhanced(parsed_response.get("resources_disagreed", {}))
            
            # Parse category
            if category and isinstance(category, str):
                try:
                    category = StatementCategory(category.lower())
                except ValueError:
                    logger.warning(f"Invalid category '{category}', using OTHER")
                    category = StatementCategory.OTHER
            
            # Parse research metadata
            research_metadata_raw = parsed_response.get("research_metadata")
            research_metadata = None
            if research_metadata_raw and isinstance(research_metadata_raw, str):
                # For string metadata, just store as additional context
                research_metadata = research_metadata_raw
            
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
                expert_perspectives=expert_perspectives,
                research_method="LLM Research",
                profile_id=request.profile_id,
                research_summary=verdict,
                confidence_score=self._calculate_confidence_score(parsed_response, expert_perspectives),
                research_metadata=None,  # Will be set by calling service
                additional_context=research_metadata_raw if isinstance(research_metadata_raw, str) else ""
            )
            
            logger.info(f"Created response object with {len(expert_perspectives)} expert perspectives")
            if resources_agreed:
                logger.info(f"Resources agreed: {resources_agreed.count} sources")
            if resources_disagreed:
                logger.info(f"Resources disagreed: {resources_disagreed.count} sources")
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to create response object: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            logger.error(f"Parsed response keys: {list(parsed_response.keys())}")
            
            # Create minimal fallback response
            return LLMResearchResponse(
                valid_sources="Error parsing response",
                verdict=f"Response parsing failed: {str(e)}",
                status="UNVERIFIABLE",
                research_method="LLM Research (Error)",
                profile_id=request.profile_id,
                expert_perspectives=[],
                confidence_score=30
            )
    
    def _parse_resource_analysis_enhanced(self, resource_data: Dict[str, Any]) -> Optional[ResourceAnalysis]:
        """Enhanced resource analysis parsing with flexible category handling"""
        if not resource_data:
            return None
        
        try:
            # Parse references with enhanced error handling
            references = []
            for i, ref_data in enumerate(resource_data.get("references", [])):
                try:
                    if isinstance(ref_data, dict):
                        # Create reference with flexible validation
                        reference = ResourceReference(
                            url=ref_data.get("url", ""),
                            title=ref_data.get("title", ""),
                            category=ref_data.get("category", "other"),  # Will be normalized by validator
                            country=ref_data.get("country", "unknown"),  # Will be normalized by validator
                            credibility=ref_data.get("credibility", "medium"),
                            key_finding=ref_data.get("key_finding")
                        )
                        references.append(reference)
                        logger.debug(f"Successfully parsed reference: {reference.title} ({reference.category})")
                        
                except Exception as ref_error:
                    logger.warning(f"Failed to parse reference {i}: {ref_error}")
                    logger.debug(f"Reference data: {ref_data}")
                    continue
            
            # Count categories dynamically from references
            category_counts = self._count_categories_from_references(references)
            
            # Create resource analysis with dynamic counts
            resource_analysis = ResourceAnalysis(
                total=resource_data.get("total", "0%"),
                count=resource_data.get("count", len(references)),
                
                # Traditional categories
                mainstream=category_counts.get("mainstream", 0),
                governance=category_counts.get("governance", 0),
                academic=category_counts.get("academic", 0),
                medical=category_counts.get("medical", 0),
                other=category_counts.get("other", 0),
                
                # Extended categories
                economic=category_counts.get("economic", 0),
                legal=category_counts.get("legal", 0),
                technology=category_counts.get("technology", 0),
                international=category_counts.get("international", 0),
                policy=category_counts.get("policy", 0),
                fact_checking=category_counts.get("fact_checking", 0),
                
                major_countries=self._extract_major_countries(references),
                references=references
            )
            
            logger.info(f"Successfully parsed resource analysis with {len(references)} references")
            logger.debug(f"Category breakdown: {category_counts}")
            
            return resource_analysis
            
        except Exception as e:
            logger.error(f"Failed to parse resource analysis: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def _count_categories_from_references(self, references: List[ResourceReference]) -> Dict[str, int]:
        """Count categories dynamically from parsed references"""
        category_counts = {}
        
        for ref in references:
            category = ref.category
            category_counts[category] = category_counts.get(category, 0) + 1
        
        return category_counts
    
    def _extract_major_countries(self, references: List[ResourceReference]) -> List[str]:
        """Extract major countries from references"""
        countries = {}
        
        for ref in references:
            if ref.country and ref.country != "unknown":
                countries[ref.country] = countries.get(ref.country, 0) + 1
        
        # Return countries with 2+ sources, sorted by count
        major_countries = [country for country, count in countries.items() if count >= 2]
        return sorted(major_countries, key=lambda x: countries[x], reverse=True)
    
    def _parse_expert_perspectives(self, perspectives_data: List[Dict[str, Any]]) -> List[ExpertPerspective]:
        """Parse expert perspectives from LLM response"""
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
                logger.debug(f"Successfully parsed expert perspective: {expert_name} ({stance})")
                
            except Exception as e:
                logger.warning(f"Failed to parse expert perspective {i}: {e}")
                logger.debug(f"Perspective data: {perspective_data}")
                continue
        
        logger.info(f"Successfully parsed {len(perspectives)} expert perspectives")
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
    
    def _calculate_confidence_score(self, parsed_response: Dict[str, Any], expert_perspectives: List[ExpertPerspective]) -> int:
        """Calculate confidence score based on response data and expert perspectives"""
        
        # Start with base confidence
        base_confidence = 50
        
        # Boost based on status
        status = parsed_response.get("status", "UNVERIFIABLE")
        if status in ["TRUE", "FALSE"]:
            base_confidence += 20
        elif status in ["PARTIALLY_TRUE", "MANIPULATIVE"]:
            base_confidence += 10
        
        # Boost based on number of expert perspectives
        perspective_boost = min(len(expert_perspectives) * 5, 25)
        base_confidence += perspective_boost
        
        # Boost based on average expert confidence
        if expert_perspectives:
            avg_expert_confidence = sum(p.confidence_level for p in expert_perspectives) / len(expert_perspectives)
            confidence_boost = (avg_expert_confidence - 50) * 0.2
            base_confidence += int(confidence_boost)
        
        # Boost based on resource count
        resources_agreed = parsed_response.get("resources_agreed", {})
        resources_disagreed = parsed_response.get("resources_disagreed", {})
        
        total_resources = (resources_agreed.get("count", 0) + resources_disagreed.get("count", 0))
        resource_boost = min(total_resources * 2, 15)
        base_confidence += resource_boost
        
        return max(30, min(95, base_confidence))

    def create_error_response(self, request: LLMResearchRequest, error_message: str) -> LLMResearchResponse:
        """Create error response when processing fails"""
        return LLMResearchResponse(
            valid_sources="0 (Error occurred during processing)",
            verdict=f"Processing failed: {error_message}",
            status="UNVERIFIABLE",
            research_method="Error Recovery",
            profile_id=request.profile_id,
            expert_perspectives=[],
            confidence_score=20
        )

response_parser = ResponseParser()