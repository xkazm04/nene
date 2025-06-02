import logging
from typing import Dict, Any, List, Optional
from models.research_models import ExpertOpinion, ResourceAnalysis

logger = logging.getLogger(__name__)

class DataSerializer:
    """Handles serialization and deserialization of complex data types."""
    
    @staticmethod
    def serialize_resource_analysis(resource_analysis: Optional[ResourceAnalysis]) -> Optional[Dict[str, Any]]:
        """
        Convert ResourceAnalysis to dictionary for JSON storage.
        
        Args:
            resource_analysis: ResourceAnalysis object
            
        Returns:
            Dict representation suitable for JSON storage
        """
        if not resource_analysis:
            return None
            
        try:
            return {
                "total": resource_analysis.total,
                "count": resource_analysis.count,
                "mainstream": resource_analysis.mainstream,
                "governance": resource_analysis.governance,
                "academic": resource_analysis.academic,
                "medical": resource_analysis.medical,
                "other": resource_analysis.other,
                "major_countries": resource_analysis.major_countries,
                "references": [
                    {
                        "url": ref.url,
                        "title": ref.title,
                        "category": ref.category,
                        "country": ref.country,
                        "credibility": ref.credibility
                    }
                    for ref in resource_analysis.references
                ]
            }
        except Exception as e:
            logger.error(f"Failed to serialize resource analysis: {e}")
            return None
    
    @staticmethod
    def serialize_experts(experts: Optional[ExpertOpinion]) -> Optional[Dict[str, Any]]:
        """Convert ExpertOpinion to dictionary for JSON storage."""
        if not experts:
            return None
            
        try:
            expert_dict = {}
            
            if experts.critic is not None:
                expert_dict["critic"] = experts.critic
            if experts.devil is not None:
                expert_dict["devil"] = experts.devil
            if experts.nerd is not None:
                expert_dict["nerd"] = experts.nerd
            if experts.psychic is not None:
                expert_dict["psychic"] = experts.psychic
                
            return expert_dict if expert_dict else None
        except Exception as e:
            logger.error(f"Failed to serialize experts: {e}")
            return None
    
    @staticmethod
    def extract_legacy_resources(
        resources_agreed: Optional[ResourceAnalysis], 
        resources_disagreed: Optional[ResourceAnalysis]
    ) -> List[str]:
        """
        Extract URLs from new resource structure for legacy compatibility.
        
        Args:
            resources_agreed: Agreed resource analysis
            resources_disagreed: Disagreed resource analysis
            
        Returns:
            List of URLs for legacy resources table
        """
        legacy_urls = []
        
        try:
            # Extract URLs from agreed resources
            if resources_agreed and resources_agreed.references:
                for ref in resources_agreed.references:
                    legacy_urls.append(ref.url)
            
            # Extract URLs from disagreed resources
            if resources_disagreed and resources_disagreed.references:
                for ref in resources_disagreed.references:
                    legacy_urls.append(ref.url)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_urls = []
            for url in legacy_urls:
                if url not in seen:
                    seen.add(url)
                    unique_urls.append(url)
            
            return unique_urls
        except Exception as e:
            logger.error(f"Failed to extract legacy resources: {e}")
            return []

# Create service instance
data_serializer = DataSerializer()