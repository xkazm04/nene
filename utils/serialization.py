import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from models.research_models import ExpertPerspective

logger = logging.getLogger(__name__)

class SerializationUtils:
    """Utility class for serializing research data"""
    
    @staticmethod
    def serialize_expert_perspectives(perspectives: List[ExpertPerspective]) -> Optional[str]:
        """Serialize expert perspectives to JSON string"""
        if not perspectives:
            return None
        
        try:
            data = []
            for perspective in perspectives:
                if isinstance(perspective, ExpertPerspective):
                    data.append({
                        'expert_name': perspective.expert_name,
                        'stance': perspective.stance,
                        'reasoning': perspective.reasoning,
                        'confidence_level': perspective.confidence_level,  # Fix: use correct field name
                        'summary': perspective.summary,
                        'source_type': perspective.source_type,
                        'expertise_area': perspective.expertise_area,
                        'publication_date': perspective.publication_date,
                    })
                else:
                    # Handle dict format
                    data.append(perspective)
            
            return json.dumps(data, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to serialize expert perspectives: {e}")
            return None
    
    @staticmethod
    def deserialize_expert_perspectives(json_str: str) -> List[ExpertPerspective]:
        """Deserialize expert perspectives from JSON string"""
        if not json_str:
            return []
        
        try:
            data = json.loads(json_str) if isinstance(json_str, str) else json_str
            perspectives = []
            
            for item in data:
                if isinstance(item, dict):
                    # Map old field names to new ones if needed
                    if 'credibility_score' in item:
                        item['confidence_level'] = item.pop('credibility_score')
                    
                    perspective = ExpertPerspective(**item)
                    perspectives.append(perspective)
            
            return perspectives
        except Exception as e:
            logger.error(f"Failed to deserialize expert perspectives: {e}")
            return []
    
    @staticmethod
    def serialize_resource_analysis(resource_analysis) -> Optional[Dict[str, Any]]:
        """Serialize ResourceAnalysis to dict for JSONB storage"""
        if not resource_analysis:
            return None
        
        try:
            if hasattr(resource_analysis, 'dict'):
                return resource_analysis.dict()
            elif hasattr(resource_analysis, 'model_dump'):
                return resource_analysis.model_dump()
            elif isinstance(resource_analysis, dict):
                return resource_analysis
            else:
                logger.warning(f"Unknown resource analysis type: {type(resource_analysis)}")
                return None
        except Exception as e:
            logger.error(f"Failed to serialize resource analysis: {e}")
            return None

    @staticmethod
    def serialize_expert_opinion(expert_opinion) -> Optional[Dict[str, Any]]:
        """Serialize ExpertOpinion to dict for JSONB storage"""
        if not expert_opinion:
            return None
        
        try:
            if hasattr(expert_opinion, 'dict'):
                return expert_opinion.dict()
            elif hasattr(expert_opinion, 'model_dump'):
                return expert_opinion.model_dump()
            elif isinstance(expert_opinion, dict):
                return expert_opinion
            else:
                logger.warning(f"Unknown expert opinion type: {type(expert_opinion)}")
                return None
        except Exception as e:
            logger.error(f"Failed to serialize expert opinion: {e}")
            return None

    @staticmethod
    def serialize_research_metadata(metadata) -> Optional[str]:
        """Serialize research metadata to JSON string"""
        if not metadata:
            return None
        
        try:
            # Handle both dict and ResearchMetadata objects
            if hasattr(metadata, 'dict'):
                metadata_dict = metadata.dict()
            elif hasattr(metadata, 'model_dump'):
                metadata_dict = metadata.model_dump()
            else:
                metadata_dict = metadata
            
            return SerializationUtils.serialize_to_json(metadata_dict)
        except Exception as e:
            logger.error(f"Failed to serialize research metadata: {e}")
            return None
    
    @staticmethod
    def serialize_to_json(data: Any) -> Optional[str]:
        """Serialize any data to JSON string"""
        if data is None:
            return None
        
        try:
            return json.dumps(data, default=SerializationUtils._json_serializer, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to serialize to JSON: {e}")
            return None
    
    @staticmethod
    def deserialize_from_json(json_str: str) -> Optional[Dict[str, Any]]:
        """Deserialize data from JSON string"""
        if not json_str:
            return None
        
        try:
            return json.loads(json_str) if isinstance(json_str, str) else json_str
        except Exception as e:
            logger.error(f"Failed to deserialize from JSON: {e}")
            return None
    
    @staticmethod
    def clean_dates_in_dict(data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert any datetime objects to ISO format strings"""
        cleaned = {}
        
        for key, value in data.items():
            if isinstance(value, (datetime, date)):
                cleaned[key] = value.isoformat()
            elif isinstance(value, dict):
                cleaned[key] = SerializationUtils.clean_dates_in_dict(value)
            elif isinstance(value, list):
                cleaned[key] = [
                    SerializationUtils.clean_dates_in_dict(item) if isinstance(item, dict)
                    else item.isoformat() if isinstance(item, (datetime, date))
                    else item
                    for item in value
                ]
            else:
                cleaned[key] = value
        
        return cleaned
    
    @staticmethod
    def _json_serializer(obj):
        """JSON serializer for objects not serializable by default json code"""
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif hasattr(obj, 'dict'):
            return obj.dict()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

# Create instance for easy importing
serialization_utils = SerializationUtils()