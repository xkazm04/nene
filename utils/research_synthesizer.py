import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from models.research_models import (
    LLMResearchResponse, 
    ExpertPerspective, 
    ResearchMetadata,
    convert_expert_opinion_to_perspectives,
    create_research_metadata
)
from utils.duplicate_detector import DuplicateDetector

logger = logging.getLogger(__name__)

class ResearchSynthesizer:
    """Synthesizes research results from multiple sources into a comprehensive response"""
    
    def __init__(self):
        self.duplicate_detector = DuplicateDetector()
    
    async def synthesize_research(
        self,
        llm_response: LLMResearchResponse,
        web_response: Optional[Dict[str, Any]],
        resource_analysis: Optional[Dict[str, Any]],
        original_request: Any,
        processing_start_time: Optional[float] = None
    ) -> LLMResearchResponse:
        """
        Synthesize research from all sources into an enhanced response
        """
        try:
            logger.info("Synthesizing tri-factor research results...")
            
            # Start with original LLM response
            enhanced_response = llm_response.model_copy(deep=True)
            
            # Convert legacy expert opinions to perspectives if needed
            if enhanced_response.experts and not enhanced_response.expert_perspectives:
                legacy_perspectives = convert_expert_opinion_to_perspectives(enhanced_response.experts)
                enhanced_response.expert_perspectives.extend(legacy_perspectives)
            
            # Enhance with web search findings
            if web_response:
                enhanced_response = self._integrate_web_findings(enhanced_response, web_response)
            
            # Enhance with resource analysis
            if resource_analysis:
                enhanced_response = self._integrate_resource_analysis(enhanced_response, resource_analysis)
            
            # Remove duplicates across all sources
            enhanced_response = self._remove_cross_source_duplicates(enhanced_response)
            
            # Calculate final confidence score
            enhanced_response.confidence_score = self._calculate_final_confidence(
                llm_response, web_response, resource_analysis
            )
            
            # Add research metadata
            enhanced_response.research_metadata = self._create_research_metadata(
                web_response, resource_analysis, processing_start_time
            )
            
            # Update research summary
            enhanced_response.research_summary = self._create_comprehensive_summary(
                enhanced_response, web_response, resource_analysis
            )
            
            # Update research method to reflect tri-factor approach
            sources_used = enhanced_response.research_metadata.research_sources
            enhanced_response.research_method = f"Tri-factor research: {', '.join(sources_used)}"
            
            logger.info("Research synthesis completed successfully")
            return enhanced_response
            
        except Exception as e:
            logger.error(f"Research synthesis failed: {e}")
            return llm_response  # Return original on error
    
    def _integrate_web_findings(
        self, 
        response: LLMResearchResponse, 
        web_response: Dict[str, Any]
    ) -> LLMResearchResponse:
        """Integrate web search findings into the response"""
        
        # Add web-sourced expert perspectives
        web_experts = self._extract_web_expert_perspectives(web_response)
        if web_experts:
            response.expert_perspectives.extend(web_experts)
        
        # Update key findings with web information
        web_findings = self._extract_web_key_findings(web_response)
        if web_findings:
            response.key_findings.extend(web_findings)
            response.web_findings = web_findings  # Store separately
        
        # Add recent information indicator
        if web_response.get('recency_score', 0) > 70:
            response.additional_context += f"\n\nRecent Information: This analysis includes recent web findings with {web_response['recency_score']:.0f}% recency score."
        
        return response
    
    def _integrate_resource_analysis(
        self, 
        response: LLMResearchResponse, 
        resource_analysis: Dict[str, Any]
    ) -> LLMResearchResponse:
        """Integrate resource analysis into the response"""
        
        total_resources = resource_analysis.get('total_resources_found', 0)
        supporting = resource_analysis.get('supporting_resources', 0)
        contradicting = resource_analysis.get('contradicting_resources', 0)
        quality_score = resource_analysis.get('resource_quality_score', 0)
        
        # Add resource analysis to additional context
        resource_context = f"""

Resource Analysis Summary:
- Total Resources Found: {total_resources}
- Supporting Evidence: {supporting} sources
- Contradicting Evidence: {contradicting} sources
- Academic Sources: {resource_analysis.get('academic_resources', 0)}
- Resource Quality Score: {quality_score:.1f}/100
- Source Diversity: {resource_analysis.get('source_diversity', 0):.1f}%
"""
        
        response.additional_context += resource_context
        
        # Add top sources to key findings
        top_sources = resource_analysis.get('top_sources', [])
        if top_sources:
            source_findings = []
            for source in top_sources[:3]:  # Top 3 sources
                finding = f"High-quality source: {source.get('title', 'Untitled')} (Quality: {source.get('quality_score', 0)}/100)"
                source_findings.append(finding)
            
            response.key_findings.extend(source_findings)
            response.resource_findings = source_findings  # Store separately
        
        return response
    
    def _remove_cross_source_duplicates(self, response: LLMResearchResponse) -> LLMResearchResponse:
        """Remove duplicates across all research sources"""
        
        # Remove duplicate expert perspectives
        response.expert_perspectives = self.duplicate_detector.merge_similar_expert_perspectives(
            response.expert_perspectives
        )
        
        # Remove duplicate key findings
        response.key_findings = self.duplicate_detector.deduplicate_key_findings(
            response.key_findings
        )
        
        # Remove duplicates across source-specific findings
        deduplicated = self.duplicate_detector.remove_content_duplicates_across_sources(
            response.llm_findings,
            response.web_findings,
            response.resource_findings
        )
        
        response.llm_findings = deduplicated['llm']
        response.web_findings = deduplicated['web']
        response.resource_findings = deduplicated['resource']
        
        return response
    
    def _extract_web_expert_perspectives(self, web_response: Dict[str, Any]) -> List[ExpertPerspective]:
        """Extract expert perspectives from web search results"""
        perspectives = []
        
        # Process supporting evidence
        for evidence in web_response.get('supporting_evidence', []):
            summary = evidence.get('summary', '')
            if len(summary) > 50:  # Substantial content
                perspective = ExpertPerspective(
                    expert_name="Web Research Finding",
                    credentials="Online Source",
                    stance="SUPPORTING",
                    reasoning=summary[:100],  # Limit length
                    confidence_level=min(evidence.get('relevance_score', 0.5) * 100, 90),
                    source_type="web",
                    expertise_area="Web Research",
                    publication_date=evidence.get('date')
                )
                perspectives.append(perspective)
        
        # Process contradicting evidence
        for evidence in web_response.get('contradicting_evidence', []):
            summary = evidence.get('summary', '')
            if len(summary) > 50:
                perspective = ExpertPerspective(
                    expert_name="Web Research Finding",
                    credentials="Online Source",
                    stance="OPPOSING",
                    reasoning=summary[:100],
                    confidence_level=min(evidence.get('relevance_score', 0.5) * 100, 90),
                    source_type="web",
                    expertise_area="Web Research",
                    publication_date=evidence.get('date')
                )
                perspectives.append(perspective)
        
        return perspectives[:5]  # Limit to 5 web perspectives
    
    def _extract_web_key_findings(self, web_response: Dict[str, Any]) -> List[str]:
        """Extract key findings from web search results"""
        findings = []
        
        total_results = web_response.get('total_results', 0)
        supporting = len(web_response.get('supporting_evidence', []))
        contradicting = len(web_response.get('contradicting_evidence', []))
        
        if total_results > 0:
            findings.append(f"Web research found {total_results} relevant sources")
            
            if supporting > contradicting:
                findings.append(f"Web evidence leans supporting: {supporting} supporting vs {contradicting} contradicting sources")
            elif contradicting > supporting:
                findings.append(f"Web evidence leans contradicting: {contradicting} contradicting vs {supporting} supporting sources")
            else:
                findings.append(f"Web evidence is mixed: {supporting} supporting and {contradicting} contradicting sources")
        
        return findings
    
    def _calculate_final_confidence(
        self,
        llm_response: LLMResearchResponse,
        web_response: Optional[Dict[str, Any]],
        resource_analysis: Optional[Dict[str, Any]]
    ) -> int:
        """Calculate final confidence score based on all research sources"""
        
        # Start with LLM confidence
        base_confidence = getattr(llm_response, 'confidence_score', 70)
        
        # Calculate weighted confidence
        # LLM: 50%, Web: 30%, Resources: 20%
        if web_response and resource_analysis:
            final_confidence = (
                base_confidence * 0.5 +
                web_response.get('confidence_score', 70) * 0.3 +
                resource_analysis.get('confidence_score', 50) * 0.2
            )
        elif web_response:
            final_confidence = (
                base_confidence * 0.7 +
                web_response.get('confidence_score', 70) * 0.3
            )
        elif resource_analysis:
            final_confidence = (
                base_confidence * 0.8 +
                resource_analysis.get('confidence_score', 50) * 0.2
            )
        else:
            final_confidence = base_confidence
        
        return min(int(final_confidence), 95)  # Cap at 95%
    
    # Alternative approach - return dict instead of ResearchMetadata object

    def _create_research_metadata(
        self,
        web_response: Optional[Dict[str, Any]],
        resource_analysis: Optional[Dict[str, Any]],
        processing_start_time: Optional[float]
    ) -> Dict[str, Any]:
        """Create research metadata as dictionary for better compatibility"""
        
        sources_used = ['llm_training_data']
        
        if web_response:
            sources_used.append('web_search')
        
        if resource_analysis:
            sources_used.append('resource_analysis')
        
        processing_time = None
        if processing_start_time:
            processing_time = datetime.now().timestamp() - processing_start_time
        
        # Return as dictionary instead of Pydantic model
        return {
            'research_sources': sources_used,
            'research_timestamp': datetime.now().isoformat(),
            'tri_factor_research': len(sources_used) > 1,
            'web_results_count': web_response.get('total_results') if web_response else None,
            'web_recency_score': web_response.get('recency_score') if web_response else None,
            'total_resources_analyzed': resource_analysis.get('total_resources_found') if resource_analysis else None,
            'resource_quality_score': resource_analysis.get('resource_quality_score') if resource_analysis else None,
            'processing_time_seconds': processing_time
        }
    
    def _create_comprehensive_summary(
        self,
        response: LLMResearchResponse,
        web_response: Optional[Dict[str, Any]],
        resource_analysis: Optional[Dict[str, Any]]
    ) -> str:
        """Create a comprehensive research summary"""
        
        summary_parts = [response.research_summary] if response.research_summary else [response.verdict]
        
        if web_response:
            web_summary = f"Web research analysis of {web_response.get('total_results', 0)} sources shows "
            supporting = len(web_response.get('supporting_evidence', []))
            contradicting = len(web_response.get('contradicting_evidence', []))
            
            if supporting > contradicting:
                web_summary += f"predominantly supporting evidence ({supporting} vs {contradicting} sources)."
            elif contradicting > supporting:
                web_summary += f"predominantly contradicting evidence ({contradicting} vs {supporting} sources)."
            else:
                web_summary += f"mixed evidence ({supporting} supporting, {contradicting} contradicting sources)."
            
            summary_parts.append(web_summary)
        
        if resource_analysis:
            total_resources = resource_analysis.get('total_resources_found', 0)
            quality_score = resource_analysis.get('resource_quality_score', 0)
            
            resource_summary = f"Resource analysis identified {total_resources} relevant sources with an average quality score of {quality_score:.1f}/100."
            summary_parts.append(resource_summary)
        
        return " ".join(summary_parts)