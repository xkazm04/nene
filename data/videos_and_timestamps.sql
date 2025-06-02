-- Drop existing objects in correct order
DROP VIEW IF EXISTS video_analysis_summary CASCADE;
DROP TABLE IF EXISTS video_timestamps CASCADE;
DROP TABLE IF EXISTS videos CASCADE;

-- Create the videos table
CREATE TABLE videos (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    video_url TEXT NOT NULL UNIQUE,  -- YouTube URL or other video source
    source VARCHAR(50) NOT NULL,     -- 'youtube', 'tiktok', 'twitter', etc.
    researched BOOLEAN DEFAULT FALSE NOT NULL,
    title TEXT,                      -- Optional video title (filled later)
    verdict TEXT,                    -- Optional overall verdict (filled later)
    
    -- Video metadata
    duration_seconds INTEGER,        -- Video duration if available
    speaker_name TEXT,              -- Main speaker identified
    language_code VARCHAR(10),      -- Detected language (ISO code)
    
    -- Processing status
    audio_extracted BOOLEAN DEFAULT FALSE,
    transcribed BOOLEAN DEFAULT FALSE,
    analyzed BOOLEAN DEFAULT FALSE,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ,       -- When fully processed
    
    -- Constraints
    CONSTRAINT valid_source CHECK (source IN ('youtube', 'tiktok', 'twitter', 'facebook', 'instagram', 'other')),
    CONSTRAINT valid_url CHECK (video_url ~ '^https?://.+')
);

-- Create the video_timestamps table
CREATE TABLE video_timestamps (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    video_id UUID REFERENCES videos(id) ON DELETE CASCADE NOT NULL,
    research_id UUID REFERENCES research_results(id) ON DELETE SET NULL,  -- Optional, filled when researched
    
    -- Timestamp data
    time_from_seconds INTEGER NOT NULL,
    time_to_seconds INTEGER NOT NULL,
    
    -- Statement data
    statement TEXT NOT NULL,
    context TEXT,                   -- Context for this specific statement
    category statement_category,    -- Statement category from analysis
    confidence_score REAL,          -- LLM confidence in timestamp accuracy (0.0-1.0)
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_time_range CHECK (time_from_seconds >= 0 AND time_to_seconds > time_from_seconds),
    CONSTRAINT valid_confidence CHECK (confidence_score IS NULL OR (confidence_score >= 0.0 AND confidence_score <= 1.0))
);

-- Create indexes for better query performance
CREATE INDEX idx_videos_video_url ON videos(video_url);
CREATE INDEX idx_videos_source ON videos(source);
CREATE INDEX idx_videos_researched ON videos(researched);
CREATE INDEX idx_videos_processed_at ON videos(processed_at);
CREATE INDEX idx_videos_speaker_name ON videos(speaker_name);
CREATE INDEX idx_videos_language_code ON videos(language_code);

-- Indexes for video_timestamps
CREATE INDEX idx_video_timestamps_video_id ON video_timestamps(video_id);
CREATE INDEX idx_video_timestamps_research_id ON video_timestamps(research_id);
CREATE INDEX idx_video_timestamps_time_range ON video_timestamps(time_from_seconds, time_to_seconds);
CREATE INDEX idx_video_timestamps_category ON video_timestamps(category);

-- Full-text search for statements in timestamps
CREATE INDEX idx_video_timestamps_statement_search ON video_timestamps USING gin(
    to_tsvector('english', statement || ' ' || COALESCE(context, ''))
);

-- Create trigger to automatically update updated_at
CREATE TRIGGER update_videos_updated_at 
    BEFORE UPDATE ON videos 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_video_timestamps_updated_at 
    BEFORE UPDATE ON video_timestamps 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Add RLS (Row Level Security) policies
ALTER TABLE videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE video_timestamps ENABLE ROW LEVEL SECURITY;

-- Create policies for authenticated users
CREATE POLICY "Allow all operations for authenticated users" ON videos
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Allow all operations for authenticated users" ON video_timestamps
    FOR ALL USING (auth.role() = 'authenticated');

-- Create a comprehensive view for video analysis
CREATE VIEW video_analysis_summary AS
SELECT 
    v.id,
    v.video_url,
    v.source,
    v.title,
    v.verdict,
    v.speaker_name,
    v.language_code,
    v.duration_seconds,
    v.researched,
    v.audio_extracted,
    v.transcribed,
    v.analyzed,
    v.created_at,
    v.processed_at,
    
    -- Aggregated timestamp data
    COUNT(vt.id) as total_statements,
    COUNT(CASE WHEN vt.research_id IS NOT NULL THEN 1 END) as researched_statements,
    MIN(vt.time_from_seconds) as earliest_statement_time,
    MAX(vt.time_to_seconds) as latest_statement_time,
    
    -- Category distribution
    JSON_AGG(
        DISTINCT vt.category
        ORDER BY vt.category
    ) FILTER (WHERE vt.category IS NOT NULL) as statement_categories,
    
    -- Average confidence
    AVG(vt.confidence_score) FILTER (WHERE vt.confidence_score IS NOT NULL) as avg_confidence
    
FROM videos v
LEFT JOIN video_timestamps vt ON v.id = vt.video_id
GROUP BY v.id, v.video_url, v.source, v.title, v.verdict, v.speaker_name, 
         v.language_code, v.duration_seconds, v.researched, v.audio_extracted,
         v.transcribed, v.analyzed, v.created_at, v.processed_at;

-- Function to get video with all timestamps
CREATE OR REPLACE FUNCTION get_video_with_timestamps(video_uuid UUID)
RETURNS JSON AS $$
DECLARE
    result JSON;
BEGIN
    SELECT JSON_BUILD_OBJECT(
        'video', JSON_BUILD_OBJECT(
            'id', v.id,
            'video_url', v.video_url,
            'source', v.source,
            'title', v.title,
            'verdict', v.verdict,
            'speaker_name', v.speaker_name,
            'language_code', v.language_code,
            'duration_seconds', v.duration_seconds,
            'researched', v.researched,
            'audio_extracted', v.audio_extracted,
            'transcribed', v.transcribed,
            'analyzed', v.analyzed,
            'created_at', v.created_at,
            'processed_at', v.processed_at
        ),
        'timestamps', COALESCE(
            JSON_AGG(
                JSON_BUILD_OBJECT(
                    'id', vt.id,
                    'time_from_seconds', vt.time_from_seconds,
                    'time_to_seconds', vt.time_to_seconds,
                    'statement', vt.statement,
                    'context', vt.context,
                    'category', vt.category,
                    'confidence_score', vt.confidence_score,
                    'research_id', vt.research_id,
                    'created_at', vt.created_at
                )
                ORDER BY vt.time_from_seconds
            ) FILTER (WHERE vt.id IS NOT NULL),
            '[]'::json
        )
    ) INTO result
    FROM videos v
    LEFT JOIN video_timestamps vt ON v.id = vt.video_id
    WHERE v.id = video_uuid
    GROUP BY v.id, v.video_url, v.source, v.title, v.verdict, v.speaker_name,
             v.language_code, v.duration_seconds, v.researched, v.audio_extracted,
             v.transcribed, v.analyzed, v.created_at, v.processed_at;
    
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Function to search videos by various criteria
CREATE OR REPLACE FUNCTION search_videos(
    search_text TEXT DEFAULT NULL,
    source_filter TEXT DEFAULT NULL,
    researched_filter BOOLEAN DEFAULT NULL,
    speaker_filter TEXT DEFAULT NULL,
    language_filter TEXT DEFAULT NULL,
    limit_count INTEGER DEFAULT 50,
    offset_count INTEGER DEFAULT 0
)
RETURNS TABLE(
    id UUID,
    video_url TEXT,
    source VARCHAR(50),
    title TEXT,
    speaker_name TEXT,
    total_statements BIGINT,
    researched_statements BIGINT,
    processed_at TIMESTAMPTZ,
    match_rank REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        vas.id,
        vas.video_url,
        vas.source,
        vas.title,
        vas.speaker_name,
        vas.total_statements,
        vas.researched_statements,
        vas.processed_at,
        CASE 
            WHEN search_text IS NOT NULL THEN
                ts_rank(
                    to_tsvector('english', 
                        COALESCE(vas.title, '') || ' ' || 
                        COALESCE(vas.speaker_name, '') || ' ' ||
                        vas.video_url
                    ),
                    plainto_tsquery('english', search_text)
                )
            ELSE 1.0
        END as match_rank
    FROM video_analysis_summary vas
    WHERE 
        (search_text IS NULL OR 
         to_tsvector('english', 
            COALESCE(vas.title, '') || ' ' || 
            COALESCE(vas.speaker_name, '') || ' ' ||
            vas.video_url
         ) @@ plainto_tsquery('english', search_text))
        AND (source_filter IS NULL OR vas.source = source_filter)
        AND (researched_filter IS NULL OR vas.researched = researched_filter)
        AND (speaker_filter IS NULL OR vas.speaker_name ILIKE '%' || speaker_filter || '%')
        AND (language_filter IS NULL OR vas.language_code = language_filter)
    ORDER BY match_rank DESC, vas.processed_at DESC NULLS LAST
    LIMIT limit_count
    OFFSET offset_count;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT ALL ON videos TO authenticated;
GRANT ALL ON video_timestamps TO authenticated;
GRANT SELECT ON video_analysis_summary TO authenticated;
GRANT EXECUTE ON FUNCTION get_video_with_timestamps(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION search_videos(TEXT, TEXT, BOOLEAN, TEXT, TEXT, INTEGER, INTEGER) TO authenticated;

-- Insert sample data for testing
INSERT INTO videos (
    video_url,
    source,
    title,
    speaker_name,
    language_code,
    duration_seconds,
    audio_extracted,
    transcribed,
    analyzed
) VALUES (
    'https://www.youtube.com/watch?v=example123',
    'youtube',
    'Sample Political Speech',
    'John Politician',
    'en',
    1800,
    true,
    true,
    true
);

-- Insert sample timestamps
INSERT INTO video_timestamps (
    video_id,
    time_from_seconds,
    time_to_seconds,
    statement,
    context,
    category,
    confidence_score
) SELECT 
    v.id,
    120,
    135,
    'Our economy has grown by 15% in the last quarter',
    'Discussing economic performance during campaign rally',
    'economy',
    0.85
FROM videos v 
WHERE v.video_url = 'https://www.youtube.com/watch?v=example123';