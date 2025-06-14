import json
import logging
from datetime import datetime, date
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

from config.database_top import supabase
from models.research_models import LLMResearchResponse, ExpertPerspective, ExpertOpinion

logger = logging.getLogger(__name__)

class ResearchRequest(BaseModel):
    """Research request model for database operations"""
    statement: str
    source: str
    context: str
    datetime: datetime
    statement_date: Optional[datetime] = None
    country: Optional[str] = None
    category: Optional[str] = None
    profile_id: Optional[str] = None

class DatabaseResearchService:
    """Enhanced database service that uses web context for better LLM analysis"""
    
    def __init__(self):
        self.supabase = supabase
        logger.info("Enhanced database research service initialized")
    
    def save_research_result(self, request: ResearchRequest, llm_result: LLMResearchResponse) -> Optional[str]:
        """
        Save research result to database with expert perspectives support.
        Enhanced to properly handle expert_perspectives field and date serialization.
        
        Args:
            request: Research request data
            llm_result: LLM research result with expert perspectives
            
        Returns:
            Database ID if successful, None otherwise
        """
        try:
            logger.info("Saving research result with expert perspectives to database...")
            
            # Prepare expert perspectives for database storage
            expert_perspectives_json = self._serialize_expert_perspectives(llm_result.expert_perspectives)
            
            # Properly serialize statement_date
            statement_date_str = None
            if request.statement_date:
                if isinstance(request.statement_date, datetime):
                    statement_date_str = request.statement_date.date().isoformat()
                elif isinstance(request.statement_date, date):
                    statement_date_str = request.statement_date.isoformat()
                else:
                    # Try to convert string to date
                    try:
                        if isinstance(request.statement_date, str):
                            parsed_date = datetime.fromisoformat(request.statement_date.replace('Z', '+00:00'))
                            statement_date_str = parsed_date.date().isoformat()
                    except Exception as date_error:
                        logger.warning(f"Failed to parse statement_date: {request.statement_date}, error: {date_error}")
                        statement_date_str = None
            
            # Prepare data for database insertion
            data = {
                'statement': request.statement,
                'source': request.source,
                'context': request.context,
                'request_datetime': request.datetime.isoformat(),
                'statement_date': statement_date_str,  # Properly serialized date
                'country': request.country,
                'category': request.category,
                'valid_sources': llm_result.valid_sources,
                'verdict': llm_result.verdict,
                'status': llm_result.status,
                'correction': llm_result.correction,
                'resources_agreed': self._serialize_resource_analysis(llm_result.resources_agreed),
                'resources_disagreed': self._serialize_resource_analysis(llm_result.resources_disagreed),
                'experts': self._serialize_expert_opinions(llm_result.experts),
                'expert_perspectives': expert_perspectives_json, 
                'processed_at': datetime.utcnow().isoformat(),
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            # Remove None values to avoid database issues
            data = {k: v for k, v in data.items() if v is not None}
            
            logger.debug(f"Prepared data with {len(llm_result.expert_perspectives)} expert perspectives")
            logger.debug(f"Statement date serialized as: {statement_date_str}")
            
            # Insert into database
            result = self.supabase.table('research_results').insert(data).execute()
            
            if result.data and len(result.data) > 0:
                record_id = result.data[0]['id']
                logger.info(f"Successfully saved research result with ID: {record_id}")
                logger.info(f"Expert perspectives saved: {len(llm_result.expert_perspectives)}")
                return record_id
            else:
                logger.error("No data returned from database insert")
                return None
                
        except Exception as e:
            logger.error(f"Failed to save research result: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Log the problematic data for debugging
            logger.error(f"Request statement_date type: {type(request.statement_date)}")
            logger.error(f"Request statement_date value: {request.statement_date}")
            
            return None
    
    def _serialize_expert_perspectives(self, perspectives: List[ExpertPerspective]) -> Optional[str]:
        """
        Serialize expert perspectives to JSON string for database storage.
        Enhanced with better error handling and date serialization.
        
        Args:
            perspectives: List of ExpertPerspective objects
            
        Returns:
            JSON string or None
        """
        if not perspectives:
            return None
        
        try:
            # Convert Pydantic models to dictionaries
            perspectives_data = []
            for perspective in perspectives:
                if hasattr(perspective, 'model_dump'):
                    # Pydantic v2
                    perspective_dict = perspective.model_dump()
                elif hasattr(perspective, 'dict'):
                    # Pydantic v1
                    perspective_dict = perspective.dict()
                else:
                    # Fallback manual extraction
                    perspective_dict = {
                        'expert_name': perspective.expert_name,
                        'stance': perspective.stance,
                        'reasoning': perspective.reasoning,
                        'confidence_level': perspective.confidence_level,
                        'source_type': perspective.source_type,
                        'expertise_area': perspective.expertise_area,
                        'publication_date': perspective.publication_date
                    }
                
                # Handle publication_date serialization
                if perspective_dict.get('publication_date'):
                    pub_date = perspective_dict['publication_date']
                    if isinstance(pub_date, (datetime, date)):
                        perspective_dict['publication_date'] = pub_date.isoformat()
                    elif not isinstance(pub_date, str):
                        perspective_dict['publication_date'] = None
                
                perspectives_data.append(perspective_dict)
            
            # Convert to JSON string with proper serialization
            json_str = json.dumps(perspectives_data, ensure_ascii=False, default=self._json_serialize_helper)
            logger.debug(f"Serialized {len(perspectives_data)} expert perspectives to JSON")
            return json_str
            
        except Exception as e:
            logger.error(f"Failed to serialize expert perspectives: {e}")
            logger.error(f"Perspectives data: {perspectives}")
            return None
    
    def _json_serialize_helper(self, obj):
        """Helper function for JSON serialization of complex objects"""
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        else:
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    def _serialize_resource_analysis(self, resource_analysis) -> Optional[Dict[str, Any]]:
        """Serialize resource analysis to dictionary with proper date handling"""
        if not resource_analysis:
            return None
        
        try:
            if hasattr(resource_analysis, 'model_dump'):
                data = resource_analysis.model_dump()
            elif hasattr(resource_analysis, 'dict'):
                data = resource_analysis.dict()
            else:
                return None
            
            # Handle any date objects in the data
            return self._clean_dates_in_dict(data)
            
        except Exception as e:
            logger.warning(f"Failed to serialize resource analysis: {e}")
            return None
    
    def _serialize_expert_opinions(self, expert_opinions) -> Optional[Dict[str, Any]]:
        """Serialize legacy expert opinions to dictionary with proper date handling"""
        if not expert_opinions:
            return None
        
        try:
            if hasattr(expert_opinions, 'model_dump'):
                data = expert_opinions.model_dump()
            elif hasattr(expert_opinions, 'dict'):
                data = expert_opinions.dict()
            else:
                return None
            
            # Handle any date objects in the data
            return self._clean_dates_in_dict(data)
            
        except Exception as e:
            logger.warning(f"Failed to serialize expert opinions: {e}")
            return None
    
    def _clean_dates_in_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively clean date objects in dictionary to make them JSON serializable"""
        if not isinstance(data, dict):
            return data
        
        cleaned = {}
        for key, value in data.items():
            if isinstance(value, (datetime, date)):
                cleaned[key] = value.isoformat()
            elif isinstance(value, dict):
                cleaned[key] = self._clean_dates_in_dict(value)
            elif isinstance(value, list):
                cleaned[key] = [
                    self._clean_dates_in_dict(item) if isinstance(item, dict)
                    else item.isoformat() if isinstance(item, (datetime, date))
                    else item
                    for item in value
                ]
            else:
                cleaned[key] = value
        
        return cleaned
    
    def get_research_result(self, research_id: str) -> Optional[Dict[str, Any]]:
        """
        Get research result by ID with expert perspectives support.
        Enhanced to properly deserialize expert_perspectives field.
        
        Args:
            research_id: Database ID of research result
            
        Returns:
            Research result data with expert perspectives or None
        """
        try:
            result = self.supabase.table('research_results').select('*').eq('id', research_id).execute()
            
            if result.data and len(result.data) > 0:
                record = result.data[0]
                
                # Deserialize expert perspectives
                expert_perspectives = self._deserialize_expert_perspectives(record.get('expert_perspectives'))
                if expert_perspectives:
                    record['expert_perspectives'] = expert_perspectives
                
                logger.info(f"Retrieved research result {research_id} with {len(expert_perspectives) if expert_perspectives else 0} expert perspectives")
                return record
            else:
                logger.warning(f"No research result found with ID: {research_id}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to get research result {research_id}: {e}")
            return None
    
    def _deserialize_expert_perspectives(self, perspectives_json: Optional[str]) -> List[Dict[str, Any]]:
        """
        Deserialize expert perspectives from JSON string.
        
        Args:
            perspectives_json: JSON string from database
            
        Returns:
            List of expert perspective dictionaries
        """
        if not perspectives_json:
            return []
        
        try:
            if isinstance(perspectives_json, str):
                perspectives_data = json.loads(perspectives_json)
            elif isinstance(perspectives_json, list):
                perspectives_data = perspectives_json
            else:
                logger.warning(f"Unexpected expert perspectives format: {type(perspectives_json)}")
                return []
            
            logger.debug(f"Deserialized {len(perspectives_data)} expert perspectives")
            return perspectives_data
            
        except Exception as e:
            logger.error(f"Failed to deserialize expert perspectives: {e}")
            return []
    
    def check_duplicate_statement(self, statement: str) -> Optional[str]:
        """Check if statement already exists in database"""
        try:
            result = self.supabase.table('research_results').select('id').eq('statement', statement).limit(1).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]['id']
            else:
                return None
                
        except Exception as e:
            logger.error(f"Failed to check duplicate statement: {e}")
            return None
    
    def search_research_results(self, **kwargs) -> List[Dict[str, Any]]:
        """Search research results with filters"""
        try:
            query = self.supabase.table('research_results').select('*')
            
            # Apply filters
            if kwargs.get('status'):
                query = query.eq('status', kwargs['status'])
            if kwargs.get('country'):
                query = query.eq('country', kwargs['country'])
            if kwargs.get('category'):
                query = query.eq('category', kwargs['category'])
            
            # Apply limit
            limit = kwargs.get('limit', 50)
            query = query.limit(limit)
            
            # Execute query
            result = query.execute()
            
            if result.data:
                # Deserialize expert perspectives for each result
                for record in result.data:
                    expert_perspectives = self._deserialize_expert_perspectives(record.get('expert_perspectives'))
                    record['expert_perspectives'] = expert_perspectives
                
                return result.data
            else:
                return []
                
        except Exception as e:
            logger.error(f"Failed to search research results: {e}")
            return []
    
    def get_research_with_web_context(self, request: ResearchRequest, web_context: str) -> Optional[LLMResearchResponse]:
        """
        Perform database research enhanced with web context
        This method uses the web context to provide better analysis
        """
        try:
            logger.info("Performing database research with web context enhancement")
            
            # Check for duplicates first
            existing_id = self.check_duplicate_statement(request.statement)
            if existing_id:
                logger.info(f"Found existing research result: {existing_id}")
                existing_result = self.get_research_result(existing_id)
                if existing_result:
                    # Convert existing result to response format
                    return self._convert_to_response_with_context(existing_result, web_context)
            
            # If no existing result, create enhanced analysis using web context
            enhanced_response = self._create_enhanced_analysis_with_context(request, web_context)
            
            # Save the enhanced result
            if enhanced_response:
                saved_id = self.save_research_result(request, enhanced_response)
                if saved_id:
                    logger.info(f"Saved enhanced research result with ID: {saved_id}")
                    enhanced_response.database_id = saved_id
            
            return enhanced_response
            
        except Exception as e:
            logger.error(f"Database research with web context failed: {e}")
            return None
    
    def _create_enhanced_analysis_with_context(self, request: ResearchRequest, web_context: str) -> Optional[LLMResearchResponse]:
        """Create enhanced analysis using web context as additional information"""
        try:
            # Extract key information from web context
            context_insights = self._extract_context_insights(web_context)
            
            # Create response with web-enhanced information
            response = LLMResearchResponse(
                valid_sources=f"Database analysis enhanced with web context from {context_insights.get('urls_found', 0)} sources",
                verdict=f"Analysis based on training data and web context: {context_insights.get('preliminary_verification', 'Requires verification')}",
                status="REQUIRES_VERIFICATION",  # Since this is database-only analysis
                research_method="Database Research + Web Context",
                profile_id=request.profile_id,
                expert_perspectives=[],
                confidence_score=60,  # Moderate confidence for database + context
                additional_context=web_context,
                research_summary=f"Database analysis enhanced with web context from {context_insights.get('web_sources', 0)} web sources",
                key_findings=context_insights.get('key_facts', [])
            )
            
            logger.info("Created enhanced analysis with web context")
            return response
            
        except Exception as e:
            logger.error(f"Failed to create enhanced analysis with context: {e}")
            return None
    
    def _extract_context_insights(self, web_context: str) -> Dict[str, Any]:
        """Extract structured insights from web context"""
        insights = {
            'preliminary_verification': 'Unknown',
            'key_facts': [],
            'urls_found': 0,
            'web_sources': 0
        }
        
        try:
            # Extract preliminary verification
            if 'PRELIMINARY_VERIFICATION:' in web_context:
                verification_line = web_context.split('PRELIMINARY_VERIFICATION:')[1].split('\n')[0].strip()
                insights['preliminary_verification'] = verification_line
            
            # Extract key facts
            if 'KEY_FACTS_FOUND:' in web_context:
                facts_section = web_context.split('KEY_FACTS_FOUND:')[1].split('SUPPORTING_EVIDENCE:')[0] if 'SUPPORTING_EVIDENCE:' in web_context else web_context.split('KEY_FACTS_FOUND:')[1]
                facts = []
                for line in facts_section.split('\n'):
                    line = line.strip()
                    if line.startswith(('1.', '2.', '3.')) and len(line) > 10:
                        facts.append(line[2:].strip())
                insights['key_facts'] = facts
            
            # Extract metadata
            if 'URLs found:' in web_context:
                try:
                    urls_line = [line for line in web_context.split('\n') if 'URLs found:' in line][0]
                    insights['urls_found'] = int(urls_line.split('URLs found:')[1].split()[0])
                except:
                    pass
            
            if 'Content sources:' in web_context:
                try:
                    sources_line = [line for line in web_context.split('\n') if 'Content sources:' in line][0]
                    insights['web_sources'] = int(sources_line.split('Content sources:')[1].split()[0])
                except:
                    pass
            
        except Exception as e:
            logger.warning(f"Failed to extract context insights: {e}")
        
        return insights
    
    def _convert_to_response_with_context(self, existing_result: dict, web_context: str) -> LLMResearchResponse:
        """Convert existing database result to response format, enhanced with web context"""
        try:
            # Parse expert perspectives from database
            expert_perspectives = []
            perspectives_data = existing_result.get("expert_perspectives", [])
            
            if perspectives_data:
                for perspective_dict in perspectives_data:
                    try:
                        perspective = ExpertPerspective(**perspective_dict)
                        expert_perspectives.append(perspective)
                    except Exception as e:
                        logger.warning(f"Failed to parse expert perspective: {e}")
                        continue
            
            # Extract context insights
            context_insights = self._extract_context_insights(web_context)
            
            # Enhance existing context with web context
            existing_context = existing_result.get("additional_context", "")
            enhanced_context = f"{existing_context}\n\nWEB_CONTEXT_ENHANCEMENT:\n{web_context}" if existing_context else f"WEB_CONTEXT_ENHANCEMENT:\n{web_context}"
            
            # Enhance research method
            existing_method = existing_result.get("research_method", "Database Retrieval")
            enhanced_method = f"{existing_method} + Web Context Enhancement"
            
            # Create enhanced response
            response = LLMResearchResponse(
                valid_sources=existing_result.get("valid_sources", ""),
                verdict=existing_result.get("verdict", ""),
                status=existing_result.get("status", "UNVERIFIABLE"),
                correction=existing_result.get("correction"),
                country=existing_result.get("country"),
                category=existing_result.get("category"),
                resources_agreed=existing_result.get("resources_agreed", {}),
                resources_disagreed=existing_result.get("resources_disagreed", {}),
                experts=ExpertOpinion(**existing_result.get("experts", {})) if existing_result.get("experts") else None,
                research_method=enhanced_method,
                profile_id=existing_result.get("profile_id"),
                expert_perspectives=expert_perspectives,
                key_findings=existing_result.get("key_findings", []) + context_insights.get('key_facts', []),
                research_summary=existing_result.get("research_summary", existing_result.get("verdict", "")),
                additional_context=enhanced_context,
                confidence_score=min(existing_result.get("confidence_score", 70) + 10, 95),  # Boost confidence with web context
                research_metadata=existing_result.get("research_metadata"),
                llm_findings=existing_result.get("llm_findings", []),
                web_findings=existing_result.get("web_findings", []),
                resource_findings=existing_result.get("resource_findings", []),
                processed_at=existing_result.get("processed_at", datetime.utcnow().isoformat()),
                database_id=existing_result.get("id"),
                is_duplicate=True
            )
            
            logger.info("Successfully enhanced existing result with web context")
            return response
            
        except Exception as e:
            logger.error(f"Failed to convert existing result with context: {e}")
            # Return basic conversion without enhancement
            return self._basic_convert_existing_result(existing_result)

# Create service instance
db_research_service = DatabaseResearchService()