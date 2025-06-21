import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from supabase import Client
from schemas.research import ResearchRequest  
from models.research_models import LLMResearchResponse
from utils.serialization import SerializationUtils
from utils.research_extractions import ResearchExtractionUtils

logger = logging.getLogger(__name__)

class DatabaseOperations:
    """Service for database operations related to research results"""
    
    def __init__(self, supabase: Client):
        self.supabase = supabase
        self.serialization = SerializationUtils()
        self.extraction = ResearchExtractionUtils()

    def check_duplicate_statement(self, statement: str) -> Optional[str]:
        """Check if a statement has already been researched and return its ID if found"""
        try:
            # Simple exact match - remove overly complex similarity checking
            response = self.supabase.table('research_results').select('id').eq('statement', statement).limit(1).execute()
            
            if response.data:
                research_id = response.data[0]['id']
                logger.info(f"Found duplicate statement with ID: {research_id}")
                return research_id
            
            logger.debug("No duplicate statement found")
            return None
            
        except Exception as e:
            logger.error(f"Failed to check for duplicate statement: {e}")
            return None
        
    def get_research_result_as_llm_response(self, research_id: str) -> Optional['LLMResearchResponse']:
        """Retrieve research result from database and convert to LLMResearchResponse"""
        try:
            from models.research_models import LLMResearchResponse
            
            response = self.supabase.table('research_results').select('*').eq('id', research_id).execute()
            
            if not response.data:
                return None
                
            result = response.data[0]
            
            # Convert database result back to LLMResearchResponse
            llm_response = LLMResearchResponse(
                valid_sources=result.get('valid_sources', '0'),
                verdict=result.get('verdict', 'Analysis completed'),
                status=result.get('status', 'UNVERIFIABLE'),
                correction=result.get('correction', ''),
                country=result.get('country', ''),
                category=result.get('category', 'other'),
                resources_agreed=self.serialization.deserialize_from_json(result.get('resources_agreed', [])),
                resources_disagreed=self.serialization.deserialize_from_json(result.get('resources_disagreed', [])),
                experts=self.serialization.deserialize_from_json(result.get('experts', [])),
                research_method=result.get('research_method', 'database_retrieval'),
                confidence_score=result.get('confidence_score', 50),
                research_summary=result.get('research_summary', ''),
                additional_context=result.get('additional_context', ''),
                key_findings=result.get('key_findings', []),
                web_findings=result.get('web_findings', []),
                expert_perspectives=self.serialization.deserialize_expert_perspectives(
                    result.get('expert_perspectives', [])
                ),
                research_metadata=self.serialization.deserialize_from_json(
                    result.get('research_metadata', {})
                ),
                created_at=result.get('created_at'),
                research_id=result.get('id')
            )
            
            logger.info(f"Successfully converted DB result {research_id} to LLMResearchResponse")
            return llm_response
            
        except Exception as e:
            logger.error(f"Failed to convert DB result to LLMResearchResponse: {e}")
            return None

    def save_research_result(self, request: ResearchRequest, llm_result: LLMResearchResponse) -> Optional[str]:
        """Save research result to database with proper field mapping and fallback to LLM output"""
        try:
            # Use LLM output as fallback for missing request fields
            country = request.country or getattr(llm_result, 'country', None)
            category = request.category or getattr(llm_result, 'category', None)
            statement_date = request.statement_date
            
            # If statement_date is missing, try to extract from LLM result metadata
            if not statement_date and hasattr(llm_result, 'research_metadata'):
                metadata = llm_result.research_metadata
                if isinstance(metadata, dict):
                    statement_date = metadata.get('statement_date') or metadata.get('date')

            # Prepare the data for database storage
            research_data = {
                # Request fields (with LLM fallbacks)
                'statement': request.statement,
                'source': request.source,
                'context': request.context,
                'request_datetime': request.datetime.isoformat(),
                'statement_date': statement_date.isoformat() if statement_date else None,
                'country': country,
                'category': category,
                'profile_id': request.profile_id,
                
                # Core LLM response fields
                'valid_sources': llm_result.valid_sources,
                'verdict': llm_result.verdict,
                'status': llm_result.status,
                'correction': llm_result.correction,
                
                # Legacy JSONB fields
                'resources_agreed': self.serialization.serialize_resource_analysis(llm_result.resources_agreed),
                'resources_disagreed': self.serialization.serialize_resource_analysis(llm_result.resources_disagreed),
                'experts': self.serialization.serialize_expert_opinion(llm_result.experts),
                
                # New unified LLM fields
                'research_method': llm_result.research_method,
                'confidence_score': llm_result.confidence_score,
                'research_summary': llm_result.research_summary,
                'additional_context': llm_result.additional_context,
                
                # Store findings as PostgreSQL arrays
                'key_findings': self.extraction.extract_simple_findings(llm_result.key_findings),
                'web_findings': self.extraction.extract_simple_web_findings(llm_result.web_findings),
                
                # Expert perspectives as JSONB
                'expert_perspectives': self.serialization.serialize_expert_perspectives(llm_result.expert_perspectives),
                
                # Research metadata as JSONB
                'research_metadata': self.serialization.serialize_research_metadata(llm_result.research_metadata)
            }

            # Insert research result
            response = self.supabase.table('research_results').insert(research_data).execute()
            
            if response.data:
                research_id = response.data[0]['id']
                logger.info(f"Research result saved successfully with ID: {research_id}")
                return research_id
            else:
                logger.error("Failed to save research result: No data returned from insert")
                return None

        except Exception as e:
            logger.error(f"Failed to save research result: {e}")
            logger.error(f"Request data: statement={request.statement[:50]}...")
            return None

    def get_research_result(self, research_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve research result from database"""
        try:
            response = self.supabase.table('research_results').select('*').eq('id', research_id).execute()
            
            if response.data:
                result = response.data[0]
                # Deserialize JSONB fields
                if result.get('expert_perspectives'):
                    result['expert_perspectives'] = self.serialization.deserialize_expert_perspectives(
                        result['expert_perspectives']
                    )
                if result.get('research_metadata'):
                    result['research_metadata'] = self.serialization.deserialize_from_json(
                        result['research_metadata']
                    )
                return result
            
            return None
        except Exception as e:
            logger.error(f"Failed to get research result: {e}")
            return None

    def search_research_results(self, query: str, status: Optional[str] = None, 
                              limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """Search research results in database"""
        try:
            # Build the query
            db_query = self.supabase.table('research_results').select('*')
            
            # Add text search if query provided
            if query:
                db_query = db_query.text_search('statement', query)
            
            # Add status filter if provided
            if status:
                db_query = db_query.eq('status', status)
            
            # Add pagination
            db_query = db_query.range(offset, offset + limit - 1)
            
            # Order by most recent
            db_query = db_query.order('created_at', desc=True)
            
            response = db_query.execute()
            
            results = []
            for result in response.data:
                # Deserialize JSONB fields
                if result.get('expert_perspectives'):
                    result['expert_perspectives'] = self.serialization.deserialize_expert_perspectives(
                        result['expert_perspectives']
                    )
                if result.get('research_metadata'):
                    result['research_metadata'] = self.serialization.deserialize_from_json(
                        result['research_metadata']
                    )
                results.append(result)
            
            return results
        except Exception as e:
            logger.error(f"Failed to search research results: {e}")
            return []