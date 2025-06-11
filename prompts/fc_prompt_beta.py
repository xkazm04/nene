factcheck_prompt = """
FACT-CHECKING CRITERIA:
- TRUE: Statement is accurate and aligns with the consensus of reliable, authoritative sources.
- FALSE: Statement is demonstrably incorrect or contradicted by verifiable evidence.
- MISLEADING: Statement uses factual elements to create a false narrative or impression by omitting critical context or manipulating data.
- PARTIALLY_TRUE: Statement is a mix of correct and incorrect claims, or is broadly true but requires significant clarification.
- UNVERIFIABLE: Insufficient reliable, independent information is available to make a determination.

VERDICT & CORRECTION GUIDELINES:
- verdict: A single, powerful sentence that identifies the core truth or falsehood with specific evidence. Must include: (1) the rating rationale, (2) the key evidence or missing context, and (3) why this matters. Example: "The statement is misleading because while it correctly cites a 15% GDP growth, it fails to mention this followed a 20% contraction the previous year, creating a net decline."
- correction: Provide a precise, fact-based correction that directly addresses the flaw. Include specific numbers, dates, and authoritative sources. Must be actionable and quotable. Example: "According to IMF data, the economy experienced a net 5% contraction over the two-year period (2023-2024), not the implied growth."

EXPERT PERSPECTIVES ANALYSIS:
Create 5 detailed and distinct expert perspectives. Each must provide unique, substantive analysis grounded in their specific methodology and expertise.

EXPERT PERSPECTIVES (each 3-4 sentences with specific stance and evidence):
- CRITICAL_ANALYST: Examines logical structure, evidence quality, statistical validity, and rhetorical techniques. Identifies specific fallacies (e.g., post hoc, cherry-picking, false equivalence) and evaluates source reliability. Must reference specific analytical frameworks or methodological standards. Stance: NEUTRAL - focuses on argumentative integrity.
  
- DEVILS_ADVOCATE: Constructs the strongest possible counter-narrative using legitimate evidence and alternative interpretations. Must present specific data points, credible minority viewpoints, or contextual factors that challenge the mainstream interpretation. Should acknowledge the strength of their alternative view. Stance: OPPOSING - presents legitimate dissent.
  
- QUANTITATIVE_ANALYST: Provides rigorous data analysis including trends, statistical significance, confidence intervals, and comparative benchmarks. Must contextualize numbers (per capita, inflation-adjusted, percentile rankings) and identify data limitations. References specific datasets and methodologies. Stance: SUPPORTING/OPPOSING based on empirical evidence.
  
- STRATEGIC_ANALYST: Analyzes cui bono (who benefits), timing, strategic communications theory, and likely cascading effects. Examines incentive structures, game theory applications, and probable responses from affected parties. Must consider both intended and unintended consequences. Stance: NEUTRAL - focuses on strategic dynamics.
  
- CONTEXTUAL_SPECIALIST: Provides deep domain expertise with specific theoretical frameworks, historical precedents, or technical standards. Must cite authoritative sources, seminal works, or established principles from their field. Expertise must match the statement's domain precisely. Stance: SUPPORTING/OPPOSING based on domain consensus.

DYNAMIC_DOMAIN_SPECIALIST_SELECTION:
Based on the statement's primary category and content, select the MOST RELEVANT expertise for the 'CONTEXTUAL_SPECIALIST':

- For 'economy': 
  - Economist: Analyze using economic theory (Keynesian, Austrian, etc.), cite specific models, reference historical economic parallels
  - Financial Analyst: Focus on market mechanics, valuation methods, systemic risk factors
  
- For 'politics', 'international':
  - Political Scientist: Apply theories of governance, power dynamics, institutional analysis
  - Legal Scholar: Examine constitutional law, international law, regulatory frameworks, precedents
  
- For 'social', 'education':
  - Sociologist: Apply social theory, demographic analysis, cultural frameworks
  - Historian: Provide historical parallels with specific dates/events, long-term pattern analysis
  
- For 'military', 'international':
  - Geopolitical Analyst: Analyze balance of power, deterrence theory, alliance dynamics
  - Security Expert: Focus on operational capabilities, strategic doctrine, threat assessment
  
- For 'healthcare':
  - Public Health Specialist: Analyze epidemiological data, health policy effectiveness, population health metrics
  - Medical Researcher: Focus on clinical evidence, biological mechanisms, treatment efficacy
  
- For 'technology':
  - Technology Policy Expert: Analyze innovation cycles, regulatory impact, adoption patterns
  - Computer Scientist: Focus on technical feasibility, algorithmic implications, security considerations
  
- For 'environment':
  - Climate Scientist: Analyze using climate models, IPCC frameworks, atmospheric data
  - Environmental Economist: Focus on cost-benefit of environmental policies, market mechanisms

Each expert should have:
- A clear stance (SUPPORTING, OPPOSING, or NEUTRAL)
- Specific reasoning (3-4 sentences) with concrete examples, data, or theoretical frameworks
- A confidence level (0-100) calculated as: Base confidence (60%) + Evidence quality (0-20%) + Source consensus (0-20%)
- Identified expertise area with specific subdiscipline

ENHANCED SOURCE EVALUATION:
When evaluating sources, consider:
1. Temporal relevance (how recent is the data?)
2. Geographic scope (local vs. global data)
3. Methodological transparency (are methods disclosed?)
4. Conflict of interest (funding sources, affiliations)
5. Peer review status (for academic sources)
6. Track record (historical accuracy of source)

SOURCE CATEGORIZATION:
- MAINSTREAM: Major news outlets, established media organizations (CNN, BBC, Reuters, Associated Press, major newspapers)
- GOVERNANCE: Government websites, official agencies, regulatory bodies, policy institutes (.gov, .mil, official statistics)
- ACADEMIC: Universities, peer-reviewed journals, research institutions, scientific organizations (.edu, .org academic)
- MEDICAL: Medical institutions, health organizations, medical journals (WHO, CDC, medical associations)
- LEGAL: Court records, law reviews, bar associations, legal databases
- ECONOMIC: Central banks, economic research institutes, financial regulatory bodies
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
- legal: Legal claims, judicial decisions, regulatory matters
- history: Historical claims, interpretations of past events
- other: Statements that don't fit the above categories

RESPONSE FORMAT:
Return a JSON object with this exact structure:
{
    "valid_sources": "number (percentage agreement across X unique sources)",
    "verdict": "One comprehensive sentence explaining the fact-check conclusion with specific evidence",
    "status": "TRUE/FALSE/MISLEADING/PARTIALLY_TRUE/UNVERIFIABLE",
    "correction": "If false/misleading, provide precise correction with source citation, otherwise null",
    "country": "ISO country code of statement origin/speaker (e.g., 'us', 'gb', 'de')",
    "category": "politics/economy/environment/military/healthcare/education/technology/social/international/legal/history/other",
    "resources_agreed": {
        "total": "percentage (e.g., 85%)",
        "count": 0,
        "mainstream": 0,
        "governance": 0,
        "academic": 0,
        "medical": 0,
        "legal": 0,
        "economic": 0,
        "other": 0,
        "major_countries": ["country_code1", "country_code2"],
        "references": [
            {
                "url": "https://reliable-source1.com/article",
                "title": "Article title or source name",
                "category": "mainstream/governance/academic/medical/legal/economic/other",
                "country": "country_code",
                "credibility": "high/medium/low",
                "publication_date": "YYYY-MM-DD",
                "key_finding": "Specific data point or conclusion that supports the statement"
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
        "legal": 0,
        "economic": 0,
        "other": 0,
        "major_countries": ["country_code1", "country_code2"],
        "references": [
            {
                "url": "https://contradicting-source.com/article",
                "title": "Article title or source name",
                "category": "mainstream/governance/academic/medical/legal/economic/other",
                "country": "country_code",
                "credibility": "high/medium/low",
                "publication_date": "YYYY-MM-DD",
                "key_finding": "Specific data point or conclusion that contradicts the statement"
            }
        ]
    },
    "expert_perspectives": [
        {
            "expert_name": "Critical Analyst",
            "stance": "NEUTRAL",
            "reasoning": "Rigorous examination of logical structure and evidence quality with specific analytical frameworks (3-4 sentences)",
            "confidence_level": 75.0,
            "summary": "Core analytical finding in headline form",
            "source_type": "llm",
            "expertise_area": "Argument Analysis",
            "publication_date": null
        },
        {
            "expert_name": "Devil's Advocate",
            "stance": "OPPOSING",
            "reasoning": "Strongest counter-argument with specific evidence and alternative interpretation (3-4 sentences)",
            "confidence_level": 70.0,
            "summary": "Key dissenting view in headline form",
            "source_type": "llm",
            "expertise_area": "Alternative Interpretation",
            "publication_date": null
        },
        {
            "expert_name": "Quantitative Analyst",
            "stance": "SUPPORTING/OPPOSING",
            "reasoning": "Data-driven analysis with specific statistics, trends, and methodological notes (3-4 sentences)",
            "confidence_level": 85.0,
            "summary": "Primary quantitative finding in headline form",
            "source_type": "llm",
            "expertise_area": "Quantitative Analysis",
            "publication_date": null
        },
        {
            "expert_name": "Strategic Analyst",
            "stance": "NEUTRAL",
            "reasoning": "Strategic analysis of motivations, stakeholders, and cascading effects (3-4 sentences)",
            "confidence_level": 65.0,
            "summary": "Key strategic insight in headline form",
            "source_type": "llm",
            "expertise_area": "Strategic Analysis",
            "publication_date": null
        },
        {
            "expert_name": "Contextual Specialist",
            "stance": "SUPPORTING/OPPOSING/NEUTRAL",
            "reasoning": "Deep domain expertise with specific frameworks, precedents, or technical standards (3-4 sentences)",
            "confidence_level": 80.0,
            "summary": "Domain-specific conclusion in headline form",
            "source_type": "llm",
            "expertise_area": "[Specific subdiscipline from Dynamic Selection, e.g., 'Behavioral Economist', 'Constitutional Scholar', 'Climate Modeler']",
            "publication_date": null
        }
    ],
    "experts": {
        "critic": "Synthesize key logical flaws or strengths from Critical Analyst and Devil's Advocate perspectives (max 3 sentences) - LEGACY FIELD",
        "devil": "Present the single most compelling counter-argument with supporting evidence (max 3 sentences) - LEGACY FIELD",
        "nerd": "Highlight the most significant quantitative finding with context (max 3 sentences) - LEGACY FIELD",
        "psychic": "Identify the primary strategic motivation and its likely impact (max 3 sentences) - LEGACY FIELD"
    }
}

QUALITY ASSURANCE CHECKLIST:
Before finalizing the response, verify:
1. Does the verdict clearly state WHY the statement is true/false/misleading with specific evidence?
2. Does the correction provide an accurate, quotable alternative with source?
3. Does each expert perspective offer unique, substantive analysis (not generic observations)?
4. Are confidence levels justified by the quality and consensus of available evidence?
5. Do expert perspectives reference specific theories, data, or frameworks from their domain?
6. Are sources properly categorized and evaluated for credibility?
7. Is the selected domain specialist truly the most relevant for this statement?

EXPERT PERSPECTIVE EXAMPLES:
- Strong Critical Analyst: "The statement commits a base rate fallacy by highlighting a 50% increase without noting the original figure was only 2 cases, making the change statistically insignificant. Additionally, it uses emotional language ('crisis', 'epidemic') that isn't supported by WHO's technical definitions, which require sustained community transmission above specific thresholds."

- Strong Quantitative Analyst: "The cited 8% unemployment figure is technically accurate but misleading when not adjusted for seasonal variations and workforce participation changes. When using U-6 methodology (including discouraged workers), the rate is actually 12.3%. Furthermore, youth unemployment (18-24) stands at 18.5%, nearly hidden by the aggregate figure."

- Strong Contextual Specialist (Historian): "This claim mirrors similar rhetoric from the 1970s oil crisis, where predictions of 'energy independence by 1980' proved wildly optimistic. Historical analysis of 15 similar national energy initiatives shows only 2 achieved even 50% of stated goals, primarily due to underestimating infrastructure requirements and overestimating political continuity across administrations."
"""