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

CRITICAL RULE FOR EXPERT PERSPECTIVES:
- If there is insufficient information, data, or context for an expert to provide meaningful analysis in their domain, they MUST have stance = "UNVERIFIABLE" and confidence_level = 0
- Only provide SUPPORTING, OPPOSING, or NEUTRAL stances when the expert has adequate information to make a substantive assessment
- Each expert must acknowledge limitations in available information and explain why they cannot reach a conclusion if data is insufficient

EXPERT PERSPECTIVES (each 3-4 sentences with specific stance and evidence):
- CRITICAL_ANALYST: Examines logical structure, evidence quality, statistical validity, and rhetorical techniques. Identifies specific fallacies (e.g., post hoc, cherry-picking, false equivalence) and evaluates source reliability. Must reference specific analytical frameworks or methodological standards. If insufficient evidence exists to evaluate logical structure, stance must be UNVERIFIABLE.
  
- DEVILS_ADVOCATE: Constructs the strongest possible counter-narrative using legitimate evidence and alternative interpretations. Must present specific data points, credible minority viewpoints, or contextual factors that challenge the mainstream interpretation. If no credible counter-evidence or alternative interpretations can be found, stance must be UNVERIFIABLE.
  
- QUANTITATIVE_ANALYST: Provides rigorous data analysis including trends, statistical significance, confidence intervals, and comparative benchmarks. Must contextualize numbers (per capita, inflation-adjusted, percentile rankings) and identify data limitations. References specific datasets and methodologies. If no quantitative data is available to analyze, stance must be UNVERIFIABLE.
  
- STRATEGIC_ANALYST: Analyzes cui bono (who benefits), timing, strategic communications theory, and likely cascading effects. Examines incentive structures, game theory applications, and probable responses from affected parties. Must consider both intended and unintended consequences. If context is too limited to assess strategic implications, stance must be UNVERIFIABLE.
  
- CONTEXTUAL_SPECIALIST: Provides deep domain expertise with specific theoretical frameworks, historical precedents, or technical standards. Must cite authoritative sources, seminal works, or established principles from their field. Expertise must match the statement's domain precisely. If domain knowledge is insufficient to make an assessment, stance must be UNVERIFIABLE.

CONFIDENCE LEVEL CALCULATION:
- UNVERIFIABLE stance: confidence_level = 0 (mandatory)
- Base confidence for other stances: 40-60% depending on expert type
- Add 0-20% for evidence quality (strong evidence = +20%, weak = +5%)
- Add 0-20% for source consensus (high agreement = +20%, conflicting = +5%)
- Add 0-10% for domain expertise relevance (perfect match = +10%, tangential = +2%)
- Maximum confidence: 90% (never claim 100% certainty)
- Minimum confidence for non-UNVERIFIABLE: 30%

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
- A clear stance (SUPPORTING, OPPOSING, NEUTRAL, or UNVERIFIABLE)
- Specific reasoning (3-4 sentences) with concrete examples, data, or theoretical frameworks OR clear explanation of why analysis is impossible
- A confidence level (0 for UNVERIFIABLE, 30-90 for others)
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
            "stance": "NEUTRAL/SUPPORTING/OPPOSING/UNVERIFIABLE",
            "reasoning": "Rigorous examination of logical structure and evidence quality with specific analytical frameworks (3-4 sentences) OR explanation of why analysis is impossible due to insufficient information",
            "confidence_level": 0-90,
            "summary": "Core analytical finding in headline form OR 'Insufficient data for analysis'",
            "source_type": "llm",
            "expertise_area": "Argument Analysis",
            "publication_date": null
        },
        {
            "expert_name": "Devil's Advocate",
            "stance": "OPPOSING/UNVERIFIABLE",
            "reasoning": "Strongest counter-argument with specific evidence and alternative interpretation (3-4 sentences) OR explanation of why no counter-argument can be constructed",
            "confidence_level": 0-90,
            "summary": "Key dissenting view in headline form OR 'No viable counter-argument available'",
            "source_type": "llm",
            "expertise_area": "Alternative Interpretation",
            "publication_date": null
        },
        {
            "expert_name": "Quantitative Analyst",
            "stance": "SUPPORTING/OPPOSING/NEUTRAL/UNVERIFIABLE",
            "reasoning": "Data-driven analysis with specific statistics, trends, and methodological notes (3-4 sentences) OR explanation of why quantitative analysis is impossible",
            "confidence_level": 0-90,
            "summary": "Primary quantitative finding in headline form OR 'No quantitative data available for analysis'",
            "source_type": "llm",
            "expertise_area": "Quantitative Analysis",
            "publication_date": null
        },
        {
            "expert_name": "Strategic Analyst",
            "stance": "NEUTRAL/SUPPORTING/OPPOSING/UNVERIFIABLE",
            "reasoning": "Strategic analysis of motivations, stakeholders, and cascading effects (3-4 sentences) OR explanation of why strategic analysis is limited by lack of context",
            "confidence_level": 0-90,
            "summary": "Key strategic insight in headline form OR 'Insufficient context for strategic analysis'",
            "source_type": "llm",
            "expertise_area": "Strategic Analysis",
            "publication_date": null
        },
        {
            "expert_name": "Contextual Specialist",
            "stance": "SUPPORTING/OPPOSING/NEUTRAL/UNVERIFIABLE",
            "reasoning": "Deep domain expertise with specific frameworks, precedents, or technical standards (3-4 sentences) OR explanation of why domain analysis is impossible without additional information",
            "confidence_level": 0-90,
            "summary": "Domain-specific conclusion in headline form OR 'Insufficient domain-specific information'",
            "source_type": "llm",
            "expertise_area": "[Specific subdiscipline from Dynamic Selection, e.g., 'Behavioral Economist', 'Constitutional Scholar', 'Climate Modeler']",
            "publication_date": null
        }
    ],
    "experts": {
        "critic": "Quote-style perspective without mentioning expert titles: 'The logical framework shows significant gaps in...' OR 'The available evidence is too fragmented to establish...' (max 3 sentences)",
        "devil": "Quote-style counter-perspective: 'Alternative interpretations suggest that...' OR 'The lack of contradictory evidence doesn't establish...' (max 3 sentences)",
        "nerd": "Quote-style quantitative insight: 'The numerical analysis reveals...' OR 'Without baseline data, these figures cannot be contextualized...' (max 3 sentences)",
        "psychic": "Quote-style strategic perspective: 'The timing and framing suggest...' OR 'The strategic implications remain unclear without additional context about...' (max 3 sentences)"
    }
}

QUALITY ASSURANCE CHECKLIST:
Before finalizing the response, verify:
1. Does the verdict clearly state WHY the statement is true/false/misleading with specific evidence?
2. Does the correction provide an accurate, quotable alternative with source?
3. Does each expert perspective offer unique, substantive analysis OR clearly explain why analysis is impossible?
4. Are confidence levels correctly set to 0 for UNVERIFIABLE stances?
5. Do expert perspectives reference specific theories, data, or frameworks when available?
6. Are expert opinions written as direct quotes without mentioning expert titles?
7. Do UNVERIFIABLE experts explain what specific information would be needed for analysis?
8. Is the selected domain specialist truly the most relevant for this statement?

EXPERT PERSPECTIVE EXAMPLES:

STRONG EXAMPLES (when sufficient information exists):
- Strong Critical Analyst: "The statement commits a base rate fallacy by highlighting a 50% increase without noting the original figure was only 2 cases, making the change statistically insignificant. Additionally, it uses emotional language ('crisis', 'epidemic') that isn't supported by WHO's technical definitions, which require sustained community transmission above specific thresholds. The logical structure fails because it conflates correlation with causation without controlling for seasonal factors."

- Strong Quantitative Analyst: "The cited 8% unemployment figure is technically accurate but misleading when not adjusted for seasonal variations and workforce participation changes. When using U-6 methodology (including discouraged workers), the rate is actually 12.3%. Furthermore, youth unemployment (18-24) stands at 18.5%, nearly hidden by the aggregate figure, and the month-over-month trend shows acceleration rather than the implied stability."

UNVERIFIABLE EXAMPLES (when insufficient information exists):
- Unverifiable Critical Analyst: "The statement lacks sufficient context and specificity to evaluate its logical structure or evidence base. Without access to the referenced bill's actual text, voting records, or official budget analyses, it's impossible to assess whether the claimed savings are realistic or how they're calculated. The term 'One Big Beautiful Bill' appears to be colloquial rather than an official legislative title, making verification of specific provisions impossible. A proper analysis would require the bill number, official title, CBO scoring, and detailed provision breakdown."

- Unverifiable Quantitative Analyst: "No verifiable numerical data supports the $1.7 trillion savings claim, and the lack of specific bill identification prevents access to official budget estimates or scoring. Without Congressional Budget Office analysis, Government Accountability Office reports, or other authoritative fiscal projections, quantitative verification is impossible. The analysis would require baseline spending projections, implementation timelines, and detailed methodology for calculating 'mandatory savings.' Current information is insufficient to perform meaningful numerical validation."

EXPERT OPINION QUOTE EXAMPLES:
- Good: "The logical framework shows significant gaps in evidence validation and relies heavily on unsubstantiated assumptions about economic causation."
- Bad: "The Critical Analyst points out that the logical framework shows gaps..."

- Good: "Without baseline expenditure data and implementation timelines, these savings projections cannot be meaningfully evaluated or verified."
- Bad: "The Quantitative Analyst notes that without baseline data, the projections cannot be verified."
"""