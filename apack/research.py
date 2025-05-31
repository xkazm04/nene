import logging
from typing import Dict, List
from langchain_community.utilities import WikipediaAPIWrapper
from helpers.model_management import get_llm_model
from search.search_tools import set_search_delay, get_search_tool
from schemas.fc_schemas import StatementInput, ResearchData, FactCheckConfig
from prompts.fc_prompts import get_research_summary_prompt

logger = logging.getLogger(__name__)


class FactCheckResearcher:
    """Handles web research for fact-checking"""
    
    def __init__(self, config: FactCheckConfig):
        self.config = config
        self.llm = get_llm_model(config.model_name)
        self.search_tool = get_search_tool(config.search_provider)
        self.wikipedia = WikipediaAPIWrapper() if config.enable_wikipedia else None
        
        # Set search delay for rate limiting
        set_search_delay(config.search_delay)
        
    def research_statement(self, statement_input: StatementInput) -> ResearchData:
        """
        Comprehensive web research function for fact-checking
        
        Args:
            statement_input: Input containing statement, speaker, and context
            
        Returns:
            ResearchData object with all research findings
        """
        
        try:
            logger.info(f"Starting research for statement by {statement_input.speaker}")
            
            # Perform different types of searches
            search_results = self._search_statement(statement_input)
            context_results = self._search_context(statement_input)
            speaker_info = self._research_speaker(statement_input.speaker)
            
            # Compile sources
            sources = self._compile_sources(search_results, context_results, speaker_info)
            
            # Generate summary using LLM
            summary = self._generate_summary(statement_input, search_results, context_results, speaker_info)
            
            research_data = ResearchData(
                statement=statement_input.statement,
                speaker=statement_input.speaker,
                context=statement_input.background,
                search_results=search_results,
                context_results=context_results,
                speaker_info=speaker_info,
                sources=sources,
                summary=summary
            )
            
            logger.info("Research completed successfully")
            return research_data
            
        except Exception as e:
            logger.error(f"Error during research: {e}")
            # Return minimal research data on error
            return ResearchData(
                statement=statement_input.statement,
                speaker=statement_input.speaker,
                context=statement_input.background,
                search_results="Research failed",
                context_results="Research failed",
                speaker_info="Research failed",
                sources=[],
                summary=f"Research failed due to error: {str(e)}"
            )
    
    def _search_statement(self, statement_input: StatementInput) -> str:
        """Search for information about the specific statement"""
        try:
            search_query = f'"{statement_input.statement}" {statement_input.speaker} fact check verification'
            logger.info(f"Searching for statement: {search_query}")
            
            results = self.search_tool.run(search_query)
            return results[:self.config.max_search_results]
            
        except Exception as e:
            logger.error(f"Statement search failed: {e}")
            return f"Statement search failed: {str(e)}"
    
    def _search_context(self, statement_input: StatementInput) -> str:
        """Search for contextual information"""
        try:
            # Build context-aware query
            context_parts = []
            if statement_input.background.get('when'):
                context_parts.append(statement_input.background['when'])
            if statement_input.background.get('where'):
                context_parts.append(statement_input.background['where'])
            
            context_query = f"{statement_input.statement} {' '.join(context_parts)} background context"
            logger.info(f"Searching for context: {context_query}")
            
            results = self.search_tool.run(context_query)
            return results[:self.config.max_search_results]
            
        except Exception as e:
            logger.error(f"Context search failed: {e}")
            return f"Context search failed: {str(e)}"
    
    def _research_speaker(self, speaker: str) -> str:
        """Research the speaker's background and credibility"""
        try:
            if self.wikipedia:
                logger.info(f"Researching speaker: {speaker}")
                wiki_results = self.wikipedia.run(speaker)
                return wiki_results[:500] if wiki_results else "No Wikipedia information found"
            else:
                # Fallback to web search
                search_query = f'"{speaker}" biography background political history'
                results = self.search_tool.run(search_query)
                return results[:500]
                
        except Exception as e:
            logger.error(f"Speaker research failed: {e}")
            return f"Speaker research failed: {str(e)}"
    
    def _compile_sources(self, search_results: str, context_results: str, speaker_info: str) -> List[Dict[str, str]]:
        """Compile all sources into a structured format"""
        sources = []
        
        if search_results and "failed" not in search_results.lower():
            sources.append({
                "type": "statement_search",
                "content": search_results[:1000],
                "description": "Web search results for the statement and fact-checking"
            })
        
        if context_results and "failed" not in context_results.lower():
            sources.append({
                "type": "context_search", 
                "content": context_results[:1000],
                "description": "Background and contextual information"
            })
        
        if speaker_info and "failed" not in speaker_info.lower():
            sources.append({
                "type": "speaker_research",
                "content": speaker_info,
                "description": "Information about the speaker's background and credibility"
            })
        
        return sources
    
    def _generate_summary(self, statement_input: StatementInput, search_results: str, 
                         context_results: str, speaker_info: str) -> str:
        """Generate an AI summary of all research findings"""
        try:
            prompt_template = get_research_summary_prompt()
            
            formatted_prompt = prompt_template.format(
                statement=statement_input.statement,
                speaker=statement_input.speaker,
                context=statement_input.background,
                search_results=search_results[:1000],
                context_results=context_results[:1000],
                speaker_info=speaker_info
            )
            
            logger.info("Generating research summary using LLM")
            summary = self.llm.invoke(formatted_prompt)
            
            # Extract content if it's a response object
            if hasattr(summary, 'content'):
                return summary.content
            else:
                return str(summary)
                
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return f"Failed to generate summary: {str(e)}"


def create_researcher(config: FactCheckConfig = None) -> FactCheckResearcher:
    """Factory function to create a researcher with default config"""
    if config is None:
        config = FactCheckConfig()
    
    return FactCheckResearcher(config)