-- Drop existing objects in correct order
DROP VIEW IF EXISTS research_results_with_resources CASCADE;
DROP TABLE IF EXISTS research_resources CASCADE;
DROP TABLE IF EXISTS research_results CASCADE;
DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;
DROP FUNCTION IF EXISTS get_research_result(UUID) CASCADE;
DROP FUNCTION IF EXISTS search_research_results(TEXT, TEXT, INTEGER, INTEGER) CASCADE;

-- Create enum for statement categories
DO $$ BEGIN
    CREATE TYPE statement_category AS ENUM (
        'politics',
        'economy', 
        'environment',
        'military',
        'healthcare',
        'education',
        'technology',
        'social',
        'international',
        'other'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create the main research_results table with new fields
CREATE TABLE research_results (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    
    -- Request data
    statement TEXT NOT NULL,
    source TEXT,
    context TEXT,
    request_datetime TIMESTAMPTZ NOT NULL,
    statement_date DATE,  -- When the statement was made
    country VARCHAR(2),   -- ISO country code (e.g., 'us', 'gb', 'de')
    category statement_category, -- Statement category
    
    -- Research results  
    valid_sources TEXT,
    verdict TEXT,
    status TEXT CHECK (status IN ('TRUE', 'FALSE', 'MISLEADING', 'PARTIALLY_TRUE', 'UNVERIFIABLE')),
    correction TEXT,
    
    -- Extended research data (stored as JSONB)
    resources_agreed JSONB,    -- ResourceAnalysis object
    resources_disagreed JSONB, -- ResourceAnalysis object
    experts JSONB,             -- Expert opinions
    
    -- Metadata
    processed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create the resources table for verification sources (legacy support)
CREATE TABLE research_resources (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    research_result_id UUID REFERENCES research_results(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX idx_research_results_status ON research_results(status);
CREATE INDEX idx_research_results_processed_at ON research_results(processed_at);
CREATE INDEX idx_research_results_request_datetime ON research_results(request_datetime);
CREATE INDEX idx_research_results_statement_date ON research_results(statement_date);
CREATE INDEX idx_research_results_source ON research_results(source);
CREATE INDEX idx_research_results_country ON research_results(country);
CREATE INDEX idx_research_results_category ON research_results(category);
CREATE INDEX idx_research_results_statement_hash ON research_results USING hash(statement);

-- Indexes for research_resources table
CREATE INDEX idx_research_resources_research_result_id ON research_resources(research_result_id);

-- Create full-text search index for better search performance
CREATE INDEX idx_research_results_search ON research_results USING gin(
    to_tsvector('english', statement || ' ' || COALESCE(source, '') || ' ' || COALESCE(context, ''))
);

-- Create a function to automatically update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at
CREATE TRIGGER update_research_results_updated_at 
    BEFORE UPDATE ON research_results 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Add RLS (Row Level Security) policies
ALTER TABLE research_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_resources ENABLE ROW LEVEL SECURITY;

-- Create policies for authenticated users
CREATE POLICY "Allow all operations for authenticated users" ON research_results
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Allow all operations for authenticated users" ON research_resources
    FOR ALL USING (auth.role() = 'authenticated');

-- Create a view for easier querying with joined data (maintaining backwards compatibility)
CREATE VIEW research_results_with_resources AS
SELECT 
    rr.id,
    rr.statement,
    rr.source,
    rr.context,
    rr.request_datetime,
    rr.statement_date,
    rr.country,
    rr.category,
    rr.valid_sources,
    rr.verdict,
    rr.status,
    rr.correction,
    rr.resources_agreed,
    rr.resources_disagreed,
    rr.experts,
    rr.processed_at,
    rr.created_at,
    rr.updated_at,
    -- Legacy resources field for backwards compatibility
    COALESCE(
        JSON_AGG(
            JSON_BUILD_OBJECT(
                'url', res.url,
                'order_index', res.order_index
            ) ORDER BY res.order_index
        ) FILTER (WHERE res.url IS NOT NULL),
        '[]'::json
    ) AS resources
FROM research_results rr
LEFT JOIN research_resources res ON rr.id = res.research_result_id
GROUP BY rr.id, rr.statement, rr.source, rr.context, rr.request_datetime, 
         rr.statement_date, rr.country, rr.category, rr.valid_sources, 
         rr.verdict, rr.status, rr.correction, rr.resources_agreed, 
         rr.resources_disagreed, rr.experts, rr.processed_at, rr.created_at, rr.updated_at;

-- Function to get research results with formatted data
CREATE OR REPLACE FUNCTION get_research_result(result_id UUID)
RETURNS JSON AS $$
DECLARE
    result JSON;
BEGIN
    SELECT JSON_BUILD_OBJECT(
        'id', rr.id,
        'request', JSON_BUILD_OBJECT(
            'statement', rr.statement,
            'source', rr.source,
            'context', rr.context,
            'datetime', rr.request_datetime,
            'statement_date', rr.statement_date,
            'country', rr.country,
            'category', rr.category
        ),
        'valid_sources', rr.valid_sources,
        'verdict', rr.verdict,
        'status', rr.status,
        'correction', rr.correction,
        'country', rr.country,
        'category', rr.category,
        'resources_agreed', rr.resources_agreed,
        'resources_disagreed', rr.resources_disagreed,
        'resources', COALESCE(
            (SELECT JSON_AGG(res.url ORDER BY res.order_index)
             FROM research_resources res 
             WHERE res.research_result_id = rr.id),
            '[]'::json
        ),
        'experts', rr.experts,
        'processed_at', rr.processed_at
    ) INTO result
    FROM research_results rr
    WHERE rr.id = result_id;
    
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Function to search research results with enhanced filtering
CREATE OR REPLACE FUNCTION search_research_results(
    search_text TEXT DEFAULT NULL,
    status_filter TEXT DEFAULT NULL,
    country_filter VARCHAR(2) DEFAULT NULL,
    category_filter TEXT DEFAULT NULL,
    limit_count INTEGER DEFAULT 50,
    offset_count INTEGER DEFAULT 0
)
RETURNS TABLE(
    id UUID,
    statement TEXT,
    source TEXT,
    status TEXT,
    country VARCHAR(2),
    category statement_category,
    processed_at TIMESTAMPTZ,
    match_rank REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        rr.id,
        rr.statement,
        rr.source,
        rr.status,
        rr.country,
        rr.category,
        rr.processed_at,
        CASE 
            WHEN search_text IS NOT NULL THEN
                ts_rank(
                    to_tsvector('english', rr.statement || ' ' || COALESCE(rr.source, '') || ' ' || COALESCE(rr.context, '')),
                    plainto_tsquery('english', search_text)
                )
            ELSE 1.0
        END as match_rank
    FROM research_results rr
    WHERE 
        (search_text IS NULL OR 
         to_tsvector('english', rr.statement || ' ' || COALESCE(rr.source, '') || ' ' || COALESCE(rr.context, '')) 
         @@ plainto_tsquery('english', search_text))
        AND (status_filter IS NULL OR rr.status = status_filter)
        AND (country_filter IS NULL OR rr.country = country_filter)
        AND (category_filter IS NULL OR rr.category::text = category_filter)
    ORDER BY match_rank DESC, rr.processed_at DESC
    LIMIT limit_count
    OFFSET offset_count;
END;
$$ LANGUAGE plpgsql;

-- Insert enhanced sample data for testing
INSERT INTO research_results (
    statement,
    source,
    context,
    request_datetime,
    statement_date,
    country,
    category,
    valid_sources,
    verdict,
    status,
    correction,
    resources_agreed,
    resources_disagreed,
    experts
) VALUES (
    'Brazil''s Amazon rainforest produces 20% of the world''s oxygen.',
    'Environmental groups and media since the 1960s',
    'Used to emphasize Amazon''s importance; famously repeated by Emmanuel Macron during 2019 Amazon fires',
    '2025-05-31T12:00:00Z',
    '2019-08-22',
    'br',
    'environment',
    '12 (67% agreement across 18 unique sources)',
    'The Amazon rainforest produces approximately 6-9% of the world''s oxygen, not 20% as commonly claimed.',
    'FALSE',
    'Brazil''s Amazon rainforest produces approximately 6-9% of the world''s oxygen, with most oxygen coming from oceanic phytoplankton.',
    '{
        "total": "67%",
        "count": 12,
        "mainstream": 5,
        "governance": 3,
        "academic": 4,
        "medical": 0,
        "other": 0,
        "major_countries": ["us", "gb", "br"],
        "references": [
            {
                "url": "https://www.nationalgeographic.com/environment/article/why-amazon-doesnt-produce-20-percent-worlds-oxygen",
                "title": "Why the Amazon doesn''t really produce 20% of the world''s oxygen",
                "category": "mainstream",
                "country": "us",
                "credibility": "high"
            },
            {
                "url": "https://www.scientificamerican.com/article/why-the-amazon-doesnt-really-produce-20-percent-of-the-worlds-oxygen/",
                "title": "Why the Amazon Doesn''t Really Produce 20% of the World''s Oxygen",
                "category": "mainstream", 
                "country": "us",
                "credibility": "high"
            },
            {
                "url": "https://academic.oup.com/bioscience/article/70/10/891/5895115",
                "title": "The Role of the Amazon in Global Oxygen Production",
                "category": "academic",
                "country": "us", 
                "credibility": "high"
            }
        ]
    }'::jsonb,
    '{
        "total": "33%",
        "count": 6,
        "mainstream": 2,
        "governance": 1,
        "academic": 2,
        "medical": 0,
        "other": 1,
        "major_countries": ["br", "fr"],
        "references": [
            {
                "url": "https://example-environmental-blog.com/amazon-oxygen-production",
                "title": "Amazon Oxygen Production Higher Than Reported",
                "category": "other",
                "country": "br",
                "credibility": "low"
            }
        ]
    }'::jsonb,
    '{
        "critic": "This 20% figure has been weaponized by environmental groups since the 1960s without proper scientific backing, creating a false narrative about Amazon''s role. The persistent repetition despite debunking reveals coordinated misinformation campaigns. Hidden agenda seeks to inflate Amazon''s importance for political leverage in climate negotiations.",
        "devil": "The 33% of dissenting sources arguing for higher oxygen production aren''t entirely wrong about seasonal variations and measurement difficulties. Some regions of the Amazon do produce significant oxygen during peak photosynthesis periods. Local Brazilian scientists have legitimate concerns about foreign dismissal of their research.",
        "nerd": "Precise calculations show the Amazon covers 5.5 million km² and contains approximately 390 billion trees, producing roughly 28% of terrestrial oxygen. However, it also consumes about 60% of what it produces through respiration and decomposition. Net oxygen contribution is actually 6-9%, with oceans producing 70% of global oxygen through phytoplankton.",
        "psychic": "Macron''s repetition during the 2019 fires reveals classic fear-based manipulation tactics designed to justify international intervention. The emotional appeal to ''lungs of the Earth'' bypasses rational analysis and triggers protective instincts. Politicians exploit environmental anxiety to advance geopolitical agendas while appearing morally superior."
    }'::jsonb
);

-- Insert corresponding legacy resources for backwards compatibility
INSERT INTO research_resources (research_result_id, url, order_index)
SELECT 
    id,
    unnest(ARRAY[
        'https://www.nationalgeographic.com/environment/article/why-amazon-doesnt-produce-20-percent-worlds-oxygen',
        'https://www.scientificamerican.com/article/why-the-amazon-doesnt-really-produce-20-percent-of-the-worlds-oxygen/',
        'https://academic.oup.com/bioscience/article/70/10/891/5895115'
    ]),
    unnest(ARRAY[1, 2, 3])
FROM research_results 
WHERE statement LIKE 'Brazil%Amazon%';

-- Create useful views for analytics
CREATE VIEW research_analytics AS
SELECT 
    country,
    category,
    status,
    DATE_TRUNC('day', processed_at) as day,
    COUNT(*) as statement_count
FROM research_results
WHERE country IS NOT NULL AND category IS NOT NULL
GROUP BY country, category, status, DATE_TRUNC('day', processed_at);

-- Grant permissions
GRANT ALL ON research_results TO authenticated;
GRANT ALL ON research_resources TO authenticated;
GRANT SELECT ON research_results_with_resources TO authenticated;
GRANT SELECT ON research_analytics TO authenticated;
GRANT EXECUTE ON FUNCTION get_research_result(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION search_research_results(TEXT, TEXT, VARCHAR(2), TEXT, INTEGER, INTEGER) TO authenticated;