import logging
from typing import Dict, Any, List
import re

logger = logging.getLogger(__name__)

class GeminiSearchUtils:
    """Enhanced utilities for parsing and processing Gemini search responses"""
    
    @staticmethod
    def parse_enhanced_response(raw_response: str, statement: str, category: str, search_method: str = 'web_search', extracted_content: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Parse the enhanced search response with content integration"""
        try:
            logger.info("Parsing enhanced search response with content integration...")
            
            # Extract structured information with better parsing
            search_results = GeminiSearchUtils._extract_section(raw_response, "SEARCH_RESULTS:", ["VERIFICATION"])
            verification_status = GeminiSearchUtils._extract_section(raw_response, "VERIFICATION:", ["KEY_DOCUMENTS"])
            key_documents = GeminiSearchUtils._extract_section(raw_response, "KEY_DOCUMENTS:", ["SUPPORTING_EVIDENCE"])
            supporting = GeminiSearchUtils._extract_section(raw_response, "SUPPORTING_EVIDENCE:", ["CONTRADICTORY_EVIDENCE"])
            contradictory = GeminiSearchUtils._extract_section(raw_response, "CONTRADICTORY_EVIDENCE:", ["EXPERT_QUOTES"])
            expert_quotes = GeminiSearchUtils._extract_section(raw_response, "EXPERT_QUOTES:", ["REFERENCE_DOCUMENTS", "WEB_SOURCES_FOUND"])
            reference_documents = GeminiSearchUtils._extract_section(raw_response, "REFERENCE_DOCUMENTS:", ["WEB_SOURCES_FOUND", "FACTCHECK_SUMMARY"])
            web_sources = GeminiSearchUtils._extract_section(raw_response, "WEB_SOURCES_FOUND:", ["FACTCHECK_SUMMARY", "KNOWLEDGE_CONTEXT"])
            knowledge_context = GeminiSearchUtils._extract_section(raw_response, "KNOWLEDGE_CONTEXT:", ["FACTCHECK_SUMMARY"])
            factcheck_summary = GeminiSearchUtils._extract_section(raw_response, "FACTCHECK_SUMMARY:", ["CONFIDENCE_ASSESSMENT"])
            confidence_assessment = GeminiSearchUtils._extract_section(raw_response, "CONFIDENCE_ASSESSMENT:", [])
            
            # Parse evidence with better extraction
            supporting_sources = GeminiSearchUtils._parse_evidence_list(supporting)
            contradictory_sources = GeminiSearchUtils._parse_evidence_list(contradictory)
            
            # Parse key documents
            key_docs = GeminiSearchUtils._parse_key_documents(key_documents)
            
            # Parse expert quotes
            expert_quotes_parsed = GeminiSearchUtils._parse_expert_quotes(expert_quotes)
            
            # Parse reference documents for reflection
            reference_docs = GeminiSearchUtils._parse_reference_documents(reference_documents)
            
            # Parse web sources found
            web_sources_parsed = GeminiSearchUtils._parse_web_sources(web_sources)
            
            # Integrate extracted content context
            content_context = GeminiSearchUtils._integrate_extracted_content(extracted_content or [])
            
            # Calculate enhanced confidence based on content availability
            confidence_score = GeminiSearchUtils._calculate_enhanced_confidence(
                verification_status, 
                len(supporting_sources), 
                len(contradictory_sources),
                len(key_docs),
                confidence_assessment,
                search_method == 'fallback_with_knowledge',
                len(extracted_content or [])
            )
            
            logger.info(f"Parsed {len(supporting_sources)} supporting and {len(contradictory_sources)} contradictory sources")
            logger.info(f"Found {len(key_docs)} key documents and {len(expert_quotes_parsed)} expert quotes")
            logger.info(f"Found {len(reference_docs)} reference documents and {len(web_sources_parsed)} web sources")
            logger.info(f"Integrated content from {len(extracted_content or [])} web pages")
            
            return {
                'statement': statement,
                'category': category,
                'search_results_summary': search_results.strip(),
                'verification_status': verification_status.strip(),
                'supporting_evidence': supporting_sources,
                'contradictory_evidence': contradictory_sources,
                'key_documents': key_docs,
                'expert_quotes': expert_quotes_parsed,
                'reference_documents': reference_docs,
                'web_sources_found': web_sources_parsed,
                'knowledge_context': knowledge_context.strip(),
                'content_context': content_context,  # New: extracted web content
                'factcheck_summary': factcheck_summary.strip(),
                'confidence_assessment': confidence_assessment.strip(),
                'confidence_score': confidence_score,
                'total_sources': len(supporting_sources) + len(contradictory_sources),
                'total_documents': len(key_docs),
                'total_references': len(reference_docs),
                'total_web_sources': len(web_sources_parsed),
                'content_sources': len(extracted_content or []),
                'search_method': search_method
            }
            
        except Exception as e:
            logger.error(f"Failed to parse enhanced response: {e}")
            logger.error(f"Response text sample: {raw_response[:500]}...")
            return GeminiSearchUtils._create_fallback_response(statement, f"Enhanced parsing error: {str(e)}")
    
    @staticmethod
    def _parse_web_sources(sources_text: str) -> List[Dict[str, Any]]:
        """Parse web sources found section"""
        sources = []
        
        lines = sources_text.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('-') and len(line) > 10:
                line = line[1:].strip()  # Remove dash
                
                # Parse format: URL: description
                if ':' in line:
                    parts = line.split(':', 1)
                    url = parts[0].strip()
                    description = parts[1].strip()
                    
                    if url.startswith('http'):
                        sources.append({
                            'url': url,
                            'description': description,
                            'credibility': GeminiSearchUtils._assess_url_credibility(url)
                        })
        
        return sources
    
    @staticmethod
    def _integrate_extracted_content(extracted_content: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Integrate extracted web content into analysis context"""
        if not extracted_content:
            return {
                'total_content_sources': 0,
                'content_summary': "No web content extracted",
                'key_insights': [],
                'credible_sources': 0
            }
        
        # Aggregate insights from all extracted content
        all_excerpts = []
        credible_sources = 0
        
        for content in extracted_content:
            domain = content.get('domain', '')
            excerpts = content.get('relevant_excerpts', [])
            
            # Count credible sources
            if GeminiSearchUtils._assess_url_credibility(f"https://{domain}") == 'high':
                credible_sources += 1
            
            # Collect all excerpts
            for excerpt in excerpts:
                all_excerpts.append({
                    'text': excerpt,
                    'source': domain,
                    'credibility': GeminiSearchUtils._assess_url_credibility(f"https://{domain}")
                })
        
        # Sort excerpts by credibility
        all_excerpts.sort(key=lambda x: {'high': 3, 'medium': 2, 'unknown': 1}.get(x['credibility'], 0), reverse=True)
        
        # Create content summary
        content_summary = f"Extracted content from {len(extracted_content)} web sources "
        content_summary += f"({credible_sources} high-credibility sources). "
        content_summary += f"Total relevant excerpts: {len(all_excerpts)}."
        
        return {
            'total_content_sources': len(extracted_content),
            'content_summary': content_summary,
            'key_insights': all_excerpts[:10],  # Top 10 insights
            'credible_sources': credible_sources
        }
    
    @staticmethod
    def _assess_url_credibility(url: str) -> str:
        """Assess URL credibility"""
        url_lower = url.lower()
        
        high_credibility = [
            'reuters.com', 'apnews.com', 'bbc.com', 'npr.org',
            'factcheck.org', 'politifact.com', 'snopes.com',
            'cdc.gov', 'who.int', 'nih.gov', 'fda.gov',
            'nasa.gov', 'noaa.gov', 'epa.gov',
            'congress.gov', 'whitehouse.gov', 'state.gov',
            'nature.com', 'science.org', 'nejm.org', 'bmj.com'
        ]
        
        medium_credibility = [
            'bloomberg.com', 'wsj.com', 'ft.com',
            'guardian.com', 'washingtonpost.com', 'nytimes.com',
            'cnn.com', 'cbsnews.com', 'abcnews.go.com'
        ]
        
        for domain in high_credibility:
            if domain in url_lower:
                return "high"
        
        for domain in medium_credibility:
            if domain in url_lower:
                return "medium"
        
        # Check for .gov, .edu domains
        if '.gov' in url_lower or '.edu' in url_lower:
            return "high"
        
        return "unknown"
    
    @staticmethod
    def _calculate_enhanced_confidence(
        verification: str, 
        supporting_count: int, 
        contradictory_count: int,
        documents_count: int,
        confidence_assessment: str,
        is_fallback: bool = False,
        content_sources_count: int = 0
    ) -> int:
        """Calculate confidence score with content extraction bonus"""
        base_score = 50
        
        # Reduce for fallback
        if is_fallback:
            base_score = 35
        
        # Adjust based on verification status
        if any(term in verification.lower() for term in ['true', 'confirmed', 'verified']):
            base_score += 25
        elif any(term in verification.lower() for term in ['false', 'debunked', 'incorrect']):
            base_score += 20
        elif 'partially true' in verification.lower():
            base_score += 15
        elif 'misleading' in verification.lower():
            base_score += 10
        elif 'unverifiable' in verification.lower():
            base_score -= 15
        
        # Boost for evidence
        evidence_score = min(supporting_count * 4, 20)
        base_score += evidence_score
        
        # Boost for key documents found
        documents_score = min(documents_count * 3, 15)
        base_score += documents_score
        
        # NEW: Boost for extracted web content
        content_score = min(content_sources_count * 5, 20)
        base_score += content_score
        
        # Penalize for contradictory evidence
        if contradictory_count > 0:
            base_score -= min(contradictory_count * 3, 12)
        
        # Adjust based on confidence assessment
        if 'high' in confidence_assessment.lower():
            base_score += 15
        elif 'medium' in confidence_assessment.lower():
            base_score += 5
        elif 'low' in confidence_assessment.lower():
            base_score -= 10
        
        return max(30, min(95, base_score))
    
    @staticmethod
    def _extract_section(text: str, start_marker: str, end_markers: List[str]) -> str:
        """Extract text between markers with better handling"""
        start_idx = text.find(start_marker)
        if start_idx == -1:
            return ""
        
        start_idx += len(start_marker)
        
        # Find the earliest end marker
        end_idx = len(text)
        for end_marker in end_markers:
            marker_idx = text.find(end_marker, start_idx)
            if marker_idx != -1 and marker_idx < end_idx:
                end_idx = marker_idx
        
        return text[start_idx:end_idx].strip()
    
    @staticmethod
    def _parse_evidence_list(evidence_text: str) -> List[Dict[str, Any]]:
        """Parse evidence list with enhanced extraction"""
        sources = []
        
        lines = evidence_text.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('-') and len(line) > 15:  # Require substantial content
                line = line[1:].strip()  # Remove dash
                
                # Try to split source and description
                if ':' in line:
                    parts = line.split(':', 1)
                    source = parts[0].strip()
                    description = parts[1].strip()
                else:
                    source = "Web Research"
                    description = line
                
                # Extract URL if present
                url = GeminiSearchUtils._extract_url(description)
                
                # Skip very short descriptions
                if len(description) < 10:
                    continue
                
                sources.append({
                    'source': source,
                    'description': description,
                    'url': url,
                    'credibility': GeminiSearchUtils._assess_source_credibility(source)
                })
        
        return sources
    
    @staticmethod
    def _parse_key_documents(documents_text: str) -> List[Dict[str, Any]]:
        """Parse key documents section"""
        documents = []
        
        lines = documents_text.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('-') and len(line) > 10:
                # Parse format: - Title - Source - URL - Key findings
                line = line[1:].strip()  # Remove dash
                
                # Try to split into components
                parts = line.split(' - ')
                if len(parts) >= 3:
                    title = parts[0].strip()
                    source = parts[1].strip()
                    
                    # Check if third part is URL or findings
                    third_part = parts[2].strip()
                    if third_part.startswith('http'):
                        url = third_part
                        findings = ' - '.join(parts[3:]).strip() if len(parts) > 3 else ""
                    else:
                        url = GeminiSearchUtils._extract_url(line)
                        findings = ' - '.join(parts[2:]).strip()
                    
                    documents.append({
                        'title': title,
                        'source': source,
                        'url': url,
                        'key_findings': findings,
                        'credibility': GeminiSearchUtils._assess_source_credibility(source)
                    })
                elif ':' in line:
                    # Fallback parsing
                    parts = line.split(':', 1)
                    title = parts[0].strip()
                    content = parts[1].strip()
                    url = GeminiSearchUtils._extract_url(content)
                    
                    documents.append({
                        'title': title,
                        'source': 'Web Search',
                        'url': url,
                        'key_findings': content,
                        'credibility': 'medium'
                    })
        
        return documents
    
    @staticmethod
    def _parse_expert_quotes(quotes_text: str) -> List[Dict[str, Any]]:
        """Parse expert quotes section"""
        quotes = []
        
        lines = quotes_text.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('-') and len(line) > 10:
                line = line[1:].strip()  # Remove dash
                
                # Parse format: Expert Name, Title: "Quote" - URL
                if ':' in line and '"' in line:
                    expert_part, quote_part = line.split(':', 1)
                    expert_info = expert_part.strip()
                    
                    # Extract quote and URL
                    quote_with_url = quote_part.strip()
                    url = GeminiSearchUtils._extract_url(quote_with_url)
                    quote = quote_with_url.replace(url, '').strip().strip('"').strip()
                    
                    quotes.append({
                        'expert': expert_info,
                        'quote': quote,
                        'url': url,
                        'credibility': 'high' if any(term in expert_info.lower() for term in ['professor', 'dr.', 'phd', 'researcher']) else 'medium'
                    })
        
        return quotes
    
    @staticmethod
    def _parse_reference_documents(reference_text: str) -> List[Dict[str, Any]]:
        """Parse reference documents for reflection"""
        references = []
        
        lines = reference_text.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('-') and len(line) > 10:
                line = line[1:].strip()  # Remove dash
                
                # Extract URL and description
                url = GeminiSearchUtils._extract_url(line)
                description = line.replace(url, '').strip().strip('-').strip()
                
                if url and description:
                    references.append({
                        'description': description,
                        'url': url,
                        'type': GeminiSearchUtils._classify_reference_type(url, description),
                        'suitable_for_reflection': GeminiSearchUtils._is_suitable_for_reflection(url, description)
                    })
        
        return references
    
    @staticmethod
    def _extract_url(text: str) -> str:
        """Extract URL from text"""
        url_pattern = r'https?://[^\s\)\]]+(?=[.\s\)\]]|$)'
        match = re.search(url_pattern, text)
        return match.group(0) if match else ""
    
    @staticmethod
    def _classify_reference_type(url: str, description: str) -> str:
        """Classify reference document type"""
        url_lower = url.lower()
        desc_lower = description.lower()
        
        if any(domain in url_lower for domain in ['.gov', '.mil', 'whitehouse', 'congress']):
            return 'government'
        elif any(domain in url_lower for domain in ['.edu', '.org']) and any(term in desc_lower for term in ['study', 'research', 'paper']):
            return 'academic'
        elif any(term in desc_lower for term in ['report', 'document', 'analysis']):
            return 'report'
        else:
            return 'other'
    
    @staticmethod
    def _is_suitable_for_reflection(url: str, description: str) -> bool:
        """Determine if reference is suitable for reflection"""
        # Government documents, academic papers, and official reports are good for reflection
        ref_type = GeminiSearchUtils._classify_reference_type(url, description)
        suitable_types = ['government', 'academic', 'report']
        
        # Must have URL and be of suitable type
        return bool(url) and ref_type in suitable_types
    
    @staticmethod
    def _assess_source_credibility(source: str) -> str:
        """Enhanced source credibility assessment"""
        source_lower = source.lower()
        
        high_credibility = [
            'reuters', 'associated press', 'ap news', 'bbc', 'factcheck.org', 
            'politifact', 'snopes', 'cdc', 'who', 'nih', 'nejm', 'nature',
            'science', 'pnas', 'government', 'federal', 'academic', 'university',
            'peer-reviewed', 'official report', 'white house', 'congress'
        ]
        
        medium_credibility = [
            'npr', 'pbs', 'bloomberg', 'wall street journal', 'financial times',
            'washington post', 'new york times', 'research', 'study', 'institute',
            'training data', 'expert', 'professor', 'analysis'
        ]
        
        for term in high_credibility:
            if term in source_lower:
                return "high"
        
        for term in medium_credibility:
            if term in source_lower:
                return "medium"
        
        return "unknown"
    
    @staticmethod
    def _create_fallback_response(statement: str, reason: str) -> Dict[str, Any]:
        """Create enhanced fallback response"""
        return {
            'statement': statement,
            'search_results_summary': f'Search unavailable: {reason}',
            'verification_status': 'Unverifiable - Search Failed',
            'supporting_evidence': [],
            'contradictory_evidence': [],
            'key_documents': [],
            'expert_quotes': [],
            'reference_documents': [],
            'web_sources_found': [],
            'knowledge_context': '',
            'content_context': {'total_content_sources': 0, 'content_summary': 'No content extracted', 'key_insights': [], 'credible_sources': 0},
            'factcheck_summary': f'Unable to verify due to search failure: {reason}',
            'confidence_assessment': 'Low confidence - search failed',
            'confidence_score': 20,
            'total_sources': 0,
            'total_documents': 0,
            'total_references': 0,
            'total_web_sources': 0,
            'content_sources': 0,
            'error': reason,
            'search_method': 'failed'
        }

# Create utils instance
gemini_search_utils = GeminiSearchUtils()