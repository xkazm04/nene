factcheck_prompt = """
FACT-CHECKING CRITERIA:
- TRUE: Statement is accurate and aligns with the consensus of reliable, authoritative sources.
- FALSE: Statement is demonstrably incorrect or contradicted by verifiable evidence.
- MISLEADING: Statement uses factual elements to create a false narrative or impression by omitting critical context or manipulating data.
- PARTIALLY_TRUE: Statement is a mix of correct and incorrect claims, or is broadly true but requires significant clarification.
- UNVERIFIABLE: Insufficient reliable, independent information is available to make a determination.

VERDICT & CORRECTION GUIDELINES:
- verdict: A single, concise sentence that synthesizes the core reason for the rating. It should identify the primary point of accuracy, inaccuracy, or misrepresentation. Example: "The statement is misleading because it correctly cites job growth numbers but omits that this growth was primarily in low-wage sectors."
- correction: If the verdict is not TRUE, provide a direct, quantifiable, and accurate version that corrects the primary flaw identified in the verdict. Otherwise, this should be null.

EXPERT PERSPECTIVES ANALYSIS:
Create 5 detailed and distinct expert perspectives. Each must provide a unique analytical angle on the statement, grounded in a specific methodology.

EXPERT PERSPECTIVES (each 2-3 sentences with a specific stance):
- CRITICAL_ANALYST: Examines the statement's logical structure, the quality of its evidence, and potential rhetorical fallacies. Stance: NEUTRAL - focuses on the integrity of the argument itself.
- DEVILS_ADVOCATE: Actively challenges the prevailing interpretation by presenting the strongest plausible counter-argument or an alternative narrative. Stance: OPPOSING - seeks to find legitimate alternative viewpoints, even if they are minority ones.  
- QUANTITATIVE_ANALYST: Provides data-driven analysis, contextualizing statistics with trends, per-capita rates, or comparisons. Stance: SUPPORTING/OPPOSING based on what the data reveals.
- STRATEGIC_ANALYST: Analyzes the potential motivations behind the statement and its likely strategic impact on different groups or future events. Stance: NEUTRAL - focuses on motivations and consequences.
- CONTEXTUAL_SPECIALIST: Provides specialized knowledge from a specific academic or professional domain relevant to the statement. The expertise area for this specialist MUST be chosen from the list in DYNAMIC_DOMAIN_SPECIALIST_SELECTION. Stance: SUPPORTING/OPPOSING based on domain expertise.

DYNAMIC_DOMAIN_SPECIALIST_SELECTION:
Based on the statement's primary `category`, select the MOST RELEVANT expertise area for the 'CONTEXTUAL_SPECIALIST' from the following list. Frame the analysis from this specific perspective.
- For 'economy', 'politics', 'international': Economist (analyzing market impact, incentives, cost-benefit) or Legal Scholar (analyzing legal frameworks, rights, precedents).
- For 'social', 'history', 'education': Historian (analyzing historical context, precedents, long-term trends) or Social Psychologist (analyzing group behavior, cognitive biases, public perception).
- For 'military', 'international': Geopolitical Analyst (analyzing strategic interests, state relations, power dynamics).
- For 'healthcare': Public Health Specialist (analyzing epidemiological data, policy impact, health outcomes).
- For 'technology', 'environment': Policy Analyst (analyzing policy effectiveness, regulatory impact, technical feasibility).

Each expert should have:
- A clear stance (SUPPORTING, OPPOSING, or NEUTRAL)
- Specific reasoning (2-3 sentences)
- A confidence level (0-100), reflecting the certainty of the analysis (e.g., data-driven analysis may be higher confidence than strategic analysis).
- Identified expertise area (e.g., for Contextual Specialist, it should be 'Historian' or 'Economist', not a generic domain).

SOURCE CATEGORIZATION:
- MAINSTREAM: Major news outlets, established media organizations (CNN, BBC, Reuters, Associated Press, major newspapers)
- GOVERNANCE: Government websites, official agencies, regulatory bodies, policy institutes (.gov, .mil, official statistics)
- ACADEMIC: Universities, peer-reviewed journals, research institutions, scientific organizations (.edu, .org academic)
- MEDICAL: Medical institutions, health organizations, medical journals (WHO, CDC, medical associations)
- OTHER: Independent media, blogs, think tanks, advocacy groups, commercial sources

COUNTRY IDENTIFICATION:
Identify the primary country/region of each source using ISO country codes (us, gb, de, fr, ca, au, etc.)

STATEMENT CATEGORIES:
- politics: Political statements, governance, elections, policy announcements
- economy: Economic data, financial claims, market statements, trade information
- environment: Climate change, environmental policies, sustainability claims
- military: Defense spending, military capabilities, security matters
- healthcare: Medical claims, health policy, pandemic information
- education: Educational statistics, policy, institutional claims
- technology: Tech innovations, digital policy, cybersecurity
- social: Social issues, demographics, cultural statements
- international: Foreign relations, international agreements, global affairs
- other: Statements that don't fit the above categories

RESPONSE FORMAT:
Return a JSON object with this exact structure:
{
    "valid_sources": "number (percentage agreement across X unique sources)",
    "verdict": "One sentence verdict explaining your fact-check conclusion",
    "status": "TRUE/FALSE/MISLEADING/PARTIALLY_TRUE/UNVERIFIABLE",
    "correction": "If statement is false/misleading, provide the accurate version in one sentence, otherwise null",
    "country": "ISO country code of statement origin/speaker (e.g., 'us', 'gb', 'de')",
    "category": "politics/economy/environment/military/healthcare/education/technology/social/international/other",
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
    "expert_perspectives": [
        {
            "expert_name": "Critical Analyst",
            "stance": "NEUTRAL",
            "reasoning": "Detailed analytical perspective examining assumptions and logical structure (2-3 sentences)",
            "confidence_level": 75.0,
            "summary": "One short sentence summary of the analysis fitting as a headline",
            "source_type": "llm",
            "expertise_area": "Argument Analysis",
            "publication_date": null
        },
        {
            "expert_name": "Devil's Advocate",
            "stance": "OPPOSING",
            "reasoning": "Counter-argument perspective challenging the statement (2-3 sentences)",
            "confidence_level": 70.0,
            "summary": "One short sentence summary of the analysis fitting as a headline",
            "source_type": "llm",
            "expertise_area": "Alternative Interpretation",
            "publication_date": null
        },
        {
            "expert_name": "Quantitative Analyst",
            "stance": "SUPPORTING/OPPOSING",
            "reasoning": "Data-driven analysis with specific numbers and technical context (2-3 sentences)",
            "confidence_level": 85.0,
            "summary": "One short sentence summary of the analysis fitting as a headline",
            "source_type": "llm",
            "expertise_area": "Quantitative Analysis",
            "publication_date": null
        },
        {
            "expert_name": "Strategic Analyst",
            "stance": "NEUTRAL",
            "reasoning": "Analysis of motivations, implications, and future consequences (2-3 sentences)",
            "confidence_level": 65.0,
            "summary": "One short sentence summary of the analysis fitting as a headline",
            "source_type": "llm",
            "expertise_area": "Strategic Analysis",
            "publication_date": null
        },
        {
            "expert_name": "Contextual Specialist",
            "stance": "SUPPORTING/OPPOSING/NEUTRAL",
            "reasoning": "Specialized domain knowledge relevant to the statement's field (2-3 sentences)",
            "confidence_level": 80.0,
            "summary": "One short sentence summary of the analysis fitting as a headline",
            "source_type": "llm",
            "expertise_area": "[Specific domain from Dynamic Selection, e.g., 'Historian', 'Economist', 'Legal Scholar']",
            "publication_date": null
        }
    ],
        "experts": {
        "critic": "Summarize the key insights from the Critical Analyst and Devil's Advocate (max 3 sentences) - LEGACY FIELD",
        "devil": "Provide the single most compelling counter-argument from the Devil's Advocate perspective (max 3 sentences) - LEGACY FIELD",
        "nerd": "Distill the most important statistic or data point from the Quantitative Analyst's reasoning (max 3 sentences) - LEGACY FIELD",
        "psychic": "Synthesize the core motivation and impact from the Strategic Analyst's perspective (max 3 sentences) - LEGACY FIELD"
    }
}
"""