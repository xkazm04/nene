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
            'datetime', rr.request_datetime
        ),
        'valid_sources', rr.valid_sources,
        'verdict', rr.verdict,
        'status', rr.status,
        'correction', rr.correction,
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

-- Function to search research results
CREATE OR REPLACE FUNCTION search_research_results(
    search_text TEXT DEFAULT NULL,
    status_filter TEXT DEFAULT NULL,
    limit_count INTEGER DEFAULT 50,
    offset_count INTEGER DEFAULT 0
)
RETURNS TABLE(
    id UUID,
    statement TEXT,
    source TEXT,
    status TEXT,
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
    ORDER BY match_rank DESC, rr.processed_at DESC
    LIMIT limit_count
    OFFSET offset_count;
END;
$$ LANGUAGE plpgsql;