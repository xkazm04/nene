-- Add missing fields to research_results table for unified LLM research
-- FINAL VERSION: Fixes status constraint and adds new columns

-- First, drop the old status check constraint and add the new one
ALTER TABLE research_results DROP CONSTRAINT IF EXISTS research_results_status_check;

-- Add the updated status constraint to match the Python model
ALTER TABLE research_results ADD CONSTRAINT research_results_status_check 
CHECK (status IN ('TRUE', 'FACTUAL_ERROR', 'DECEPTIVE_LIE', 'MANIPULATIVE', 'PARTIALLY_TRUE', 'OUT_OF_CONTEXT', 'UNVERIFIABLE'));

-- Add the new columns for unified LLM research
ALTER TABLE research_results 
ADD COLUMN IF NOT EXISTS research_method TEXT,
ADD COLUMN IF NOT EXISTS confidence_score INTEGER DEFAULT 50 CHECK (confidence_score >= 0 AND confidence_score <= 100),
ADD COLUMN IF NOT EXISTS research_summary TEXT DEFAULT '',
ADD COLUMN IF NOT EXISTS additional_context TEXT DEFAULT '',
ADD COLUMN IF NOT EXISTS key_findings TEXT[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS llm_findings TEXT[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS web_findings TEXT[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS resource_findings TEXT[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS research_metadata JSONB;

-- Create basic indexes (skip the problematic GIN indexes for now)
CREATE INDEX IF NOT EXISTS idx_research_results_research_method 
ON research_results(research_method);

CREATE INDEX IF NOT EXISTS idx_research_results_confidence_score 
ON research_results(confidence_score);

-- JSONB GIN index (this works)
CREATE INDEX IF NOT EXISTS idx_research_results_research_metadata 
ON research_results USING gin(research_metadata);

-- Update the view to include new fields
DROP VIEW IF EXISTS research_results_with_resources;

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
    rr.expert_perspectives,
    rr.research_method,
    rr.confidence_score,
    rr.research_summary,
    rr.additional_context,
    rr.key_findings,
    rr.llm_findings,
    rr.web_findings,
    rr.resource_findings,
    rr.research_metadata,
    rr.processed_at,
    rr.created_at,
    rr.updated_at,
    rr.profile_id,
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
         rr.resources_disagreed, rr.experts, rr.expert_perspectives,
         rr.research_method, rr.confidence_score, rr.research_summary,
         rr.additional_context, rr.key_findings, rr.llm_findings,
         rr.web_findings, rr.resource_findings, rr.research_metadata,
         rr.processed_at, rr.created_at, rr.updated_at, rr.profile_id;

-- Update the get_research_result function to include new fields
CREATE OR REPLACE FUNCTION get_research_result(result_id UUID)
RETURNS TABLE(
    id UUID,
    statement TEXT,
    source TEXT,
    context TEXT,
    request_datetime TIMESTAMPTZ,
    statement_date DATE,
    country VARCHAR(2),
    category statement_category,
    valid_sources TEXT,
    verdict TEXT,
    status TEXT,
    correction TEXT,
    resources_agreed JSONB,
    resources_disagreed JSONB,
    experts JSONB,
    expert_perspectives JSONB,
    research_method TEXT,
    confidence_score INTEGER,
    research_summary TEXT,
    additional_context TEXT,
    key_findings TEXT[],
    llm_findings TEXT[],
    web_findings TEXT[],
    resource_findings TEXT[],
    research_metadata JSONB,
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    profile_id UUID,
    resources JSON
) AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM research_results_with_resources 
    WHERE research_results_with_resources.id = result_id;
END;
$$ LANGUAGE plpgsql;

-- Update the search function to include new fields
CREATE OR REPLACE FUNCTION search_research_results(
    search_query TEXT DEFAULT NULL,
    filter_status TEXT DEFAULT NULL,
    result_limit INTEGER DEFAULT 10,
    result_offset INTEGER DEFAULT 0
)
RETURNS TABLE(
    id UUID,
    statement TEXT,
    source TEXT,
    context TEXT,
    request_datetime TIMESTAMPTZ,
    statement_date DATE,
    country VARCHAR(2),
    category statement_category,
    valid_sources TEXT,
    verdict TEXT,
    status TEXT,
    correction TEXT,
    resources_agreed JSONB,
    resources_disagreed JSONB,
    experts JSONB,
    expert_perspectives JSONB,
    research_method TEXT,
    confidence_score INTEGER,
    research_summary TEXT,
    additional_context TEXT,
    key_findings TEXT[],
    llm_findings TEXT[],
    web_findings TEXT[],
    resource_findings TEXT[],
    research_metadata JSONB,
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    profile_id UUID,
    resources JSON
) AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM research_results_with_resources 
    WHERE 
        (search_query IS NULL OR 
         to_tsvector('english', 
                    research_results_with_resources.statement || ' ' || 
                    COALESCE(research_results_with_resources.source, '') || ' ' || 
                    COALESCE(research_results_with_resources.context, '') || ' ' ||
                    COALESCE(research_results_with_resources.research_summary, '')
         ) @@ plainto_tsquery('english', search_query))
        AND (filter_status IS NULL OR research_results_with_resources.status = filter_status)
    ORDER BY research_results_with_resources.request_datetime DESC
    LIMIT result_limit
    OFFSET result_offset;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT ALL ON research_results TO authenticated;
GRANT SELECT ON research_results_with_resources TO authenticated;
GRANT EXECUTE ON FUNCTION get_research_result(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION search_research_results(TEXT, TEXT, INTEGER, INTEGER) TO authenticated;

-- Verify the constraint was updated
SELECT conname, consrc 
FROM pg_constraint 
WHERE conrelid = 'research_results'::regclass 
AND conname = 'research_results_status_check';

-- Verify the migration worked
SELECT 
    column_name, 
    data_type, 
    is_nullable, 
    column_default 
FROM information_schema.columns 
WHERE table_name = 'research_results' 
    AND column_name IN ('research_method', 'confidence_score', 'research_summary', 'additional_context', 'key_findings', 'llm_findings', 'web_findings', 'resource_findings', 'research_metadata')
ORDER BY column_name;