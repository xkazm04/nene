import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class ResearchExtractionUtils:
    """Utility class for extracting and processing research data"""
    
    @staticmethod
    def extract_simple_findings(findings) -> List[str]:
        """Extract simple text findings from various input types"""
        if not findings:
            return []
        
        if isinstance(findings, list):
            # Extract text content only
            simple_findings = []
            for finding in findings:
                if isinstance(finding, str):
                    # If it's already text, clean it up
                    clean_finding = finding.strip()
                    if len(clean_finding) > 200:  # Truncate very long findings
                        clean_finding = clean_finding[:200] + "..."
                    simple_findings.append(clean_finding)
                elif isinstance(finding, dict):
                    # Extract summary or text field from dict
                    text = finding.get('summary') or finding.get('text') or finding.get('finding') or str(finding)
                    if len(text) > 200:
                        text = text[:200] + "..."
                    simple_findings.append(text)
                else:
                    simple_findings.append(str(finding)[:200])
            return simple_findings
        elif isinstance(findings, str):
            return [findings[:200]]
        else:
            return [str(findings)[:200]]

    @staticmethod
    def extract_simple_web_findings(web_findings) -> List[str]:
        """Extract simple web research summary instead of full dump"""
        if not web_findings:
            return []
        
        if isinstance(web_findings, list):
            summaries = []
            for finding in web_findings:
                if isinstance(finding, str):
                    # Look for summary sections in the web finding
                    if "=== GOOGLE SEARCH WITH GROUNDING RESULTS ===" in finding:
                        # Extract key info from the web search result
                        lines = finding.split('\n')
                        summary_parts = []
                        
                        for line in lines:
                            if 'Statement:' in line:
                                statement = line.split('Statement:')[1].strip()[:100]
                                summary_parts.append(f"Searched: {statement}")
                            elif 'Grounding sources found:' in line:
                                sources = line.split('found:')[1].strip()
                                summary_parts.append(f"Sources found: {sources}")
                            elif 'Total sources discovered:' in line:
                                total = line.split('discovered:')[1].strip()
                                summary_parts.append(f"Total sources: {total}")
                        
                        if summary_parts:
                            summaries.append(" | ".join(summary_parts))
                        else:
                            summaries.append("Web search completed")
                    else:
                        # Regular finding, truncate
                        summaries.append(finding[:200] + "..." if len(finding) > 200 else finding)
                else:
                    summaries.append(str(finding)[:200])
            return summaries
        elif isinstance(web_findings, str):
            return ResearchExtractionUtils.extract_simple_web_findings([web_findings])
        else:
            return [str(web_findings)[:200]]

    @staticmethod
    def extract_urls_from_web_context(web_context: str) -> List[str]:
        """Extract URLs from web research context"""
        urls = []
        
        # Look for the credible sources section
        if "=== CREDIBLE SOURCES FOUND ===" in web_context:
            sources_section = web_context.split("=== CREDIBLE SOURCES FOUND ===")[1]
            next_section = sources_section.find("===")
            if next_section != -1:
                sources_section = sources_section[:next_section]
            
            # Extract URLs using regex
            url_pattern = r'https?://[^\s\n]+'
            urls = re.findall(url_pattern, sources_section)
        
        logger.info(f"Extracted {len(urls)} URLs from web context")
        return urls

    @staticmethod
    def create_fallback_web_context(statement: str, reason: str) -> str:
        """Create fallback context when web research fails"""
        return f"""
=== WEB RESEARCH FALLBACK ===
Statement: {statement}
Reason: {reason}
Note: Fact-checking based on LLM training data only.
Timestamp: {datetime.now().isoformat()}
"""

    @staticmethod
    def extract_speaker_name(source: str) -> Optional[str]:
        """Extract clean speaker name from source string"""
        if not source:
            return None
        
        # Remove common prefixes and suffixes
        name = source.strip()
        
        # Remove titles and prefixes
        prefixes_to_remove = [
            r'^(President|Prime Minister|PM|Senator|Rep\.?|Mr\.?|Mrs\.?|Ms\.?|Dr\.?)\s+',
            r'^(The\s+)?(Honorable|Hon\.?)\s+',
            r'^(Secretary|Minister)\s+',
        ]
        
        for prefix_pattern in prefixes_to_remove:
            name = re.sub(prefix_pattern, '', name, flags=re.IGNORECASE)
        
        # Remove suffixes like (D-CA), (R-TX), etc.
        name = re.sub(r'\s*\([^)]*\)\s*$', '', name)
        
        # Remove extra whitespace
        name = re.sub(r'\s+', ' ', name).strip()
        
        return name if len(name) > 1 else None

# Create instance for easy importing
research_extraction_utils = ResearchExtractionUtils()