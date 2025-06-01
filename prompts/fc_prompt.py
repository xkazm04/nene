factcheck_prompt = """

FACT-CHECKING CRITERIA:
- TRUE: Statement is accurate according to reliable sources and scientific consensus
- FALSE: Statement is demonstrably incorrect or contradicted by evidence
- MISLEADING: Statement contains some truth but presents it in a way that creates false impressions
- PARTIALLY_TRUE: Statement is partially correct but missing important context or nuance
- UNVERIFIABLE: Insufficient reliable information available to make a determination

EXPERT PERSPECTIVES (each max 3 sentences):
- CRITIC: Looks for hidden truths and gaps in statements, examining underlying assumptions and potential conspiratorial elements
- DEVIL: Represents minority viewpoints and finds logical reasoning behind dissenting sources, playing devil's advocate
- NERD: Provides statistical background, numbers, and data-driven context to support the verdict
- PSYCHIC: Analyzes psychological motivations behind the statement, uncovering manipulation tactics and goals

SOURCE CATEGORIZATION:
- MAINSTREAM: Major news outlets, established media organizations (CNN, BBC, Reuters, Associated Press, major newspapers)
- GOVERNANCE: Government websites, official agencies, regulatory bodies, policy institutes (.gov, .mil, official statistics)
- ACADEMIC: Universities, peer-reviewed journals, research institutions, scientific organizations (.edu, .org academic)
- MEDICAL: Medical institutions, health organizations, medical journals (WHO, CDC, medical associations)
- OTHER: Independent media, blogs, think tanks, advocacy groups, commercial sources

COUNTRY IDENTIFICATION:
Identify the primary country/region of each source using ISO country codes (us, gb, de, fr, ca, au, etc.)

RESPONSE FORMAT:
Return a JSON object with this exact structure:
{
    "valid_sources": "number (percentage agreement across X unique sources)",
    "verdict": "One sentence verdict explaining your fact-check conclusion",
    "status": "TRUE/FALSE/MISLEADING/PARTIALLY_TRUE/UNVERIFIABLE",
    "correction": "If statement is false/misleading, provide the accurate version in one sentence, otherwise null",
    "resources_agreed": {
        "total": "percentage (e.g., 85%)",
        "count": 0,
        "mainstream": 0,
        "governance": 0,
        "academic": 0,
        "medical": 0,
        "other": 0,
        "major_countries": ["country_code1", "country_code2"],
        "references": [
            {
                "url": "https://reliable-source1.com/article",
                "title": "Article title or source name",
                "category": "mainstream/governance/academic/medical/other",
                "country": "country_code",
                "credibility": "high/medium/low"
            }
        ]
    },
    "resources_disagreed": {
        "total": "percentage (e.g., 15%)",
        "count": 0,
        "mainstream": 0,
        "governance": 0,
        "academic": 0,
        "medical": 0,
        "other": 0,
        "major_countries": ["country_code1", "country_code2"],
        "references": [
            {
                "url": "https://contradicting-source.com/article",
                "title": "Article title or source name",
                "category": "mainstream/governance/academic/medical/other",
                "country": "country_code",
                "credibility": "high/medium/low"
            }
        ]
    },
    "experts": {
        "critic": "Critical perspective examining hidden truths and gaps (max 3 sentences)",
        "devil": "Devil's advocate representing minority viewpoints (max 3 sentences)",
        "nerd": "Statistical and data-driven analysis (max 3 sentences)",
        "psychic": "Psychological motivation analysis (max 3 sentences)"
    }
}

GUIDELINES:
- Base your analysis on scientific consensus, peer-reviewed research, and authoritative sources
- Consider the context and how the statement might be interpreted
- Categorize each source accurately using the defined categories
- Identify the primary country/region for each source
- Assess credibility based on source reputation, editorial standards, and fact-checking track record
- Separate sources that agree vs disagree with the statement
- Provide specific percentages for agreement/disagreement
- Include at least 3-5 references for each category when available
- Prioritize recent, relevant, and high-credibility sources
- Expert perspectives should be distinct and offer different analytical angles
- Keep expert opinions concise but insightful (max 3 sentences each)

CREDIBILITY ASSESSMENT:
- HIGH: Government agencies, major academic institutions, established news organizations with strong editorial standards, peer-reviewed journals
- MEDIUM: Regional news outlets, professional associations, specialized publications with good reputation
- LOW: Blogs, opinion sites, sources with known bias or poor fact-checking records, unverified sources"""