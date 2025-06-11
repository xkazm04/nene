import logging
import asyncio
from typing import Dict, Any, List, Optional
import re
import requests
from datetime import datetime

import google.generativeai as genai

logger = logging.getLogger(__name__)

class GeminiReflectionService:
    """Reflection service for iterating on search results and analyzing referenced documents"""
    
    def __init__(self, gemini_model=None):
        self.model = gemini_model
        self.max_reflection_attempts = 1  # Start with one iteration
        self.max_document_size = 50000  # Max characters to extract from document
        
    def is_available(self) -> bool:
        """Check if reflection service is available"""
        return self.model is not None
    
    async def perform_reflection(self, search_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform reflection on search results by analyzing referenced documents
        
        Args:
            search_result: Initial search result from GeminiSearchCore
            
        Returns:
            Enhanced search result with reflection findings
        """
        if not self.is_available():
            logger.warning("Reflection service not available - skipping reflection")
            return search_result
        
        try:
            logger.info("Starting reflection analysis on search results...")
            
            # Extract suitable reference documents
            reference_docs = search_result.get('reference_documents', [])
            suitable_refs = [ref for ref in reference_docs if ref.get('suitable_for_reflection', False)]
            
            if not suitable_refs:
                logger.info("No suitable reference documents found for reflection")
                return self._add_reflection_metadata(search_result, [], "No suitable references")
            
            logger.info(f"Found {len(suitable_refs)} suitable documents for reflection")
            
            # Analyze each suitable reference
            reflection_findings = []
            for ref in suitable_refs[:3]:  # Limit to top 3 to avoid rate limits
                try:
                    finding = await self._analyze_reference_document(ref, search_result['statement'])
                    if finding:
                        reflection_findings.append(finding)
                    
                    # Add delay between requests
                    await asyncio.sleep(2)
                    
                except Exception as ref_error:
                    logger.warning(f"Failed to analyze reference {ref.get('url', 'unknown')}: {ref_error}")
                    continue
            
            # Synthesize reflection findings
            if reflection_findings:
                synthesis = await self._synthesize_reflection_findings(
                    search_result['statement'], 
                    search_result, 
                    reflection_findings
                )
                return self._add_reflection_metadata(search_result, reflection_findings, "Completed", synthesis)
            else:
                return self._add_reflection_metadata(search_result, [], "No successful document analysis")
                
        except Exception as e:
            logger.error(f"Reflection analysis failed: {e}")
            return self._add_reflection_metadata(search_result, [], f"Reflection error: {str(e)}")
    
    async def _analyze_reference_document(self, reference: Dict[str, Any], statement: str) -> Optional[Dict[str, Any]]:
        """Analyze a specific reference document"""
        try:
            url = reference.get('url', '')
            description = reference.get('description', '')
            
            if not url:
                return None
            
            logger.info(f"Analyzing reference document: {description[:50]}...")
            
            # Attempt to extract text content from URL
            document_content = await self._extract_document_content(url)
            
            if not document_content:
                logger.warning(f"Could not extract content from {url}")
                return None
            
            # Analyze document content with LLM
            analysis = await self._analyze_document_content(document_content, statement, description, url)
            
            return {
                'url': url,
                'description': description,
                'type': reference.get('type', 'unknown'),
                'content_length': len(document_content),
                'analysis': analysis,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze reference document: {e}")
            return None
    
    async def _extract_document_content(self, url: str) -> Optional[str]:
        """Extract text content from a document URL"""
        try:
            # Simple text extraction - could be enhanced with specialized parsers
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; FactChecker/1.0; +research)'
            }
            
            # Check if URL looks like a downloadable document
            if any(ext in url.lower() for ext in ['.pdf', '.doc', '.docx']):
                logger.info(f"Skipping document extraction for binary file: {url}")
                return None
            
            response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            response.raise_for_status()
            
            # Basic HTML/text extraction
            content = response.text
            
            # Simple text cleaning (remove HTML tags, excess whitespace)
            content = re.sub(r'<[^>]+>', ' ', content)
            content = re.sub(r'\s+', ' ', content)
            content = content.strip()
            
            # Limit content size
            if len(content) > self.max_document_size:
                content = content[:self.max_document_size] + "... [truncated]"
            
            # Must have substantial content
            if len(content) < 500:
                logger.warning(f"Document content too short: {len(content)} characters")
                return None
            
            logger.info(f"Extracted {len(content)} characters from document")
            return content
            
        except Exception as e:
            logger.warning(f"Failed to extract content from {url}: {e}")
            return None
    
    async def _analyze_document_content(self, content: str, statement: str, description: str, url: str) -> Dict[str, Any]:
        """Analyze document content using LLM"""
        try:
            analysis_prompt = f"""
            Analyze this document content in relation to the fact-checking statement: "{statement}"
            
            Document Description: {description}
            Document URL: {url}
            
            Document Content:
            {content[:5000]}  # Limit prompt size
            
            Please provide analysis in this format:
            
            RELEVANCE: [High/Medium/Low] - How relevant is this document to the statement?
            
            KEY_FINDINGS:
            - [Specific finding from the document that relates to the statement]
            - [Another specific finding]
            
            SUPPORTING_POINTS:
            - [Points from the document that support the statement]
            
            CONTRADICTING_POINTS:
            - [Points from the document that contradict the statement]
            
            ADDITIONAL_CONTEXT:
            [Important context or background information from the document]
            
            DOCUMENT_CREDIBILITY:
            [Assessment of document's credibility and authority]
            
            SUMMARY:
            [2-3 sentence summary of what this document contributes to fact-checking the statement]
            """
            
            response = self.model.generate_content(analysis_prompt)
            
            if not response or not response.text:
                return {'error': 'Empty response from document analysis'}
            
            # Parse the response
            analysis_text = response.text
            
            return {
                'relevance': self._extract_analysis_field(analysis_text, 'RELEVANCE'),
                'key_findings': self._extract_analysis_list(analysis_text, 'KEY_FINDINGS'),
                'supporting_points': self._extract_analysis_list(analysis_text, 'SUPPORTING_POINTS'),
                'contradicting_points': self._extract_analysis_list(analysis_text, 'CONTRADICTING_POINTS'),
                'additional_context': self._extract_analysis_field(analysis_text, 'ADDITIONAL_CONTEXT'),
                'document_credibility': self._extract_analysis_field(analysis_text, 'DOCUMENT_CREDIBILITY'),
                'summary': self._extract_analysis_field(analysis_text, 'SUMMARY'),
                'raw_analysis': analysis_text
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze document content: {e}")
            return {'error': f'Analysis failed: {str(e)}'}
    
    async def _synthesize_reflection_findings(self, statement: str, original_result: Dict[str, Any], reflection_findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Synthesize all reflection findings into enhanced conclusion"""
        try:
            synthesis_prompt = f"""
            Based on the original fact-checking and detailed document analysis, provide an enhanced assessment:
            
            ORIGINAL STATEMENT: "{statement}"
            ORIGINAL VERIFICATION: {original_result.get('verification_status', 'Unknown')}
            ORIGINAL SUMMARY: {original_result.get('factcheck_summary', 'No summary')}
            
            DOCUMENT ANALYSIS RESULTS:
            """
            
            for i, finding in enumerate(reflection_findings, 1):
                analysis = finding.get('analysis', {})
                synthesis_prompt += f"""
            
            Document {i}: {finding.get('description', 'Unknown')}
            URL: {finding.get('url', 'No URL')}
            Relevance: {analysis.get('relevance', 'Unknown')}
            Key Findings: {'; '.join(analysis.get('key_findings', []))}
            Supporting: {'; '.join(analysis.get('supporting_points', []))}
            Contradicting: {'; '.join(analysis.get('contradicting_points', []))}
            Summary: {analysis.get('summary', 'No summary')}
            """
            
            synthesis_prompt += f"""
            
            SYNTHESIS TASK:
            Provide an enhanced fact-check assessment considering both original search and document analysis:
            
            ENHANCED_VERIFICATION: [True/False/Partially True/Misleading/Unverifiable]
            
            CONFIDENCE_LEVEL: [High/Medium/Low] - Based on document evidence quality
            
            KEY_DOCUMENT_EVIDENCE:
            - [Most important evidence from document analysis]
            - [Second most important evidence]
            
            ENHANCED_SUMMARY:
            [3-4 sentence enhanced summary incorporating document findings]
            
            REFLECTION_IMPACT:
            [How did the document analysis change or strengthen the original assessment?]
            """
            
            response = self.model.generate_content(synthesis_prompt)
            
            if response and response.text:
                synthesis_text = response.text
                return {
                    'enhanced_verification': self._extract_analysis_field(synthesis_text, 'ENHANCED_VERIFICATION'),
                    'confidence_level': self._extract_analysis_field(synthesis_text, 'CONFIDENCE_LEVEL'),
                    'key_document_evidence': self._extract_analysis_list(synthesis_text, 'KEY_DOCUMENT_EVIDENCE'),
                    'enhanced_summary': self._extract_analysis_field(synthesis_text, 'ENHANCED_SUMMARY'),
                    'reflection_impact': self._extract_analysis_field(synthesis_text, 'REFLECTION_IMPACT'),
                    'raw_synthesis': synthesis_text
                }
            else:
                return {'error': 'Failed to generate synthesis'}
                
        except Exception as e:
            logger.error(f"Failed to synthesize reflection findings: {e}")
            return {'error': f'Synthesis failed: {str(e)}'}
    
    def _extract_analysis_field(self, text: str, field_name: str) -> str:
        """Extract a single field from analysis text"""
        pattern = f"{field_name}:(.+?)(?=\n[A-Z_]+:|$)"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""
    
    def _extract_analysis_list(self, text: str, field_name: str) -> List[str]:
        """Extract a list field from analysis text"""
        field_text = self._extract_analysis_field(text, field_name)
        if not field_text:
            return []
        
        # Extract bullet points
        lines = field_text.split('\n')
        items = []
        for line in lines:
            line = line.strip()
            if line.startswith('-') and len(line) > 3:
                items.append(line[1:].strip())
        
        return items
    
    def _add_reflection_metadata(self, search_result: Dict[str, Any], findings: List[Dict[str, Any]], status: str, synthesis: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add reflection metadata to search result"""
        search_result['reflection'] = {
            'status': status,
            'documents_analyzed': len(findings),
            'findings': findings,
            'synthesis': synthesis,
            'timestamp': datetime.now().isoformat()
        }
        
        # Update confidence score if synthesis available
        if synthesis and not synthesis.get('error'):
            confidence_level = synthesis.get('confidence_level', '').lower()
            if 'high' in confidence_level:
                search_result['confidence_score'] = min(search_result.get('confidence_score', 50) + 15, 95)
            elif 'medium' in confidence_level:
                search_result['confidence_score'] = min(search_result.get('confidence_score', 50) + 8, 90)
            
            # Update summary if enhanced summary available
            enhanced_summary = synthesis.get('enhanced_summary', '')
            if enhanced_summary:
                search_result['factcheck_summary'] = enhanced_summary
        
        return search_result

# Create reflection service instance (will be initialized with model from main service)
gemini_reflection_service = GeminiReflectionService()