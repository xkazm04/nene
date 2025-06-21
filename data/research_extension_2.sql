-- Add expert_perspectives column to research_results table

-- Add the new column for storing expert perspectives
ALTER TABLE research_results 
ADD COLUMN expert_perspectives JSONB;

-- Create index for better query performance on expert perspectives
CREATE INDEX idx_research_results_expert_perspectives 
ON research_results USING gin(expert_perspectives);

-- Update the view to include expert_perspectives
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
    rr.expert_perspectives,  -- New field
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
         rr.resources_disagreed, rr.experts, rr.expert_perspectives,
         rr.processed_at, rr.created_at, rr.updated_at;

-- Update the get_research_result function to include expert_perspectives
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
        'expert_perspectives', rr.expert_perspectives,  -- New field
        'processed_at', rr.processed_at
    ) INTO result
    FROM research_results rr
    WHERE rr.id = result_id;
    
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT UPDATE ON research_results TO authenticated;

-- Sample data update to test the new column
UPDATE research_results 
SET expert_perspectives = '[
    {
        "expert_name": "Critical Analyst",
        "stance": "NEUTRAL",
        "reasoning": "This 20% figure has been weaponized by environmental groups since the 1960s without proper scientific backing, creating a false narrative about Amazon''s role.",
        "confidence_level": 75.0,
        "source_type": "llm",
        "expertise_area": "Critical Analysis",
        "publication_date": null
    },
    {
        "expert_name": "Devil''s Advocate", 
        "stance": "OPPOSING",
        "reasoning": "The 33% of dissenting sources arguing for higher oxygen production aren''t entirely wrong about seasonal variations and measurement difficulties.",
        "confidence_level": 70.0,
        "source_type": "llm",
        "expertise_area": "Counter-Analysis",
        "publication_date": null
    }
]'::jsonb
WHERE statement LIKE 'Brazil%Amazon%';