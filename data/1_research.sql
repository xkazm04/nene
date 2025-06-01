-- Create the main research_results table
CREATE TABLE research_results (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    
    -- Request data
    statement TEXT NOT NULL,
    source TEXT,
    context TEXT,
    request_datetime TIMESTAMPTZ NOT NULL,
    
    -- Research results
    valid_sources TEXT,
    verdict TEXT,
    status TEXT CHECK (status IN ('TRUE', 'FALSE', 'MISLEADING', 'PARTIALLY_TRUE', 'UNVERIFIABLE')),
    correction TEXT,
    
    -- Expert opinions (stored as JSONB for flexibility)
    experts JSONB,
    
    -- Metadata
    processed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create the resources table for verification sources
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
CREATE INDEX idx_research_results_source ON research_results(source);
CREATE INDEX idx_research_resources_research_result_id ON research_resources(research_result_id);

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

-- Add RLS (Row Level Security) policies if needed
ALTER TABLE research_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_resources ENABLE ROW LEVEL SECURITY;

-- Create policies (adjust based on your authentication needs)
-- Allow all operations for authenticated users (modify as needed)
CREATE POLICY "Allow all operations for authenticated users" ON research_results
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Allow all operations for authenticated users" ON research_resources
    FOR ALL USING (auth.role() = 'authenticated');

-- Create a view for easier querying with joined data
CREATE VIEW research_results_with_resources AS
SELECT 
    rr.id,
    rr.statement,
    rr.source,
    rr.context,
    rr.request_datetime,
    rr.valid_sources,
    rr.verdict,
    rr.status,
    rr.correction,
    rr.experts,
    rr.processed_at,
    rr.created_at,
    rr.updated_at,
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
         rr.valid_sources, rr.verdict, rr.status, rr.correction, rr.experts, 
         rr.processed_at, rr.created_at, rr.updated_at;

-- Insert sample data for testing (optional)
INSERT INTO research_results (
    statement,
    source,
    context,
    request_datetime,
    valid_sources,
    verdict,
    status,
    correction,
    experts
) VALUES (
    'Brazil''s Amazon rainforest produces 20% of the world''s oxygen.',
    'Environmental groups and media since the 1960s',
    'Used to emphasize Amazon''s importance; famously repeated by Emmanuel Macron during 2019 Amazon fires',
    '2025-05-31T12:00:00Z',
    '12 (67% agreement across 18 unique sources)',
    'The Amazon rainforest produces approximately 6-9% of the world''s oxygen, not 20% as commonly claimed.',
    'FALSE',
    'Brazil''s Amazon rainforest produces approximately 6-9% of the world''s oxygen, with most oxygen coming from oceanic phytoplankton.',
    '{
        "critic": "This 20% figure has been weaponized by environmental groups since the 1960s without proper scientific backing...",
        "devil": "The 33% of dissenting sources arguing for higher oxygen production aren''t entirely wrong...",
        "nerd": "Precise calculations show the Amazon covers 5.5 million km² and contains approximately 390 billion trees...",
        "psychic": "Macron''s repetition during the 2019 fires reveals classic fear-based manipulation tactics..."
    }'::jsonb
);

-- Insert corresponding resources for the sample data
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