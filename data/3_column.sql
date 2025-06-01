-- Add statement_date column to research_results table
ALTER TABLE research_results 
ADD COLUMN statement_date DATE;

-- Create index for better performance on duplicate checking
CREATE INDEX idx_research_results_statement_hash ON research_results USING hash(statement);

-- Add index on statement_date for better querying
CREATE INDEX idx_research_results_statement_date ON research_results(statement_date);

-- Update the view to include statement_date
DROP VIEW IF EXISTS research_results_with_resources;

CREATE VIEW research_results_with_resources AS
SELECT 
    rr.id,
    rr.statement,
    rr.source,
    rr.context,
    rr.request_datetime,
    rr.statement_date,
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
         rr.statement_date, rr.valid_sources, rr.verdict, rr.status, rr.correction, 
         rr.experts, rr.processed_at, rr.created_at, rr.updated_at;