-- Create timeline table
CREATE TABLE IF NOT EXISTS edu_timeline (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    question TEXT NOT NULL,
    dimension_top_title TEXT NOT NULL,
    dimension_bottom_title TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create milestone table
CREATE TABLE IF NOT EXISTS edu_milestone (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timeline_id UUID NOT NULL REFERENCES edu_timeline(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    is_top BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create event table
CREATE TABLE IF NOT EXISTS edu_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    milestone_id UUID NOT NULL REFERENCES edu_milestone(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    text_1 TEXT,
    text_2 TEXT,
    text_3 TEXT,
    text_4 TEXT,
    reference_url TEXT,
    order_index INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_edu_milestone_timeline_id ON edu_milestone(timeline_id);
CREATE INDEX IF NOT EXISTS idx_edu_milestone_order ON edu_milestone(timeline_id, order_index);
CREATE INDEX IF NOT EXISTS idx_edu_event_milestone_id ON edu_event(milestone_id);
CREATE INDEX IF NOT EXISTS idx_edu_event_order ON edu_event(milestone_id, order_index);

-- Add updated_at trigger function if it doesn't exist
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_edu_timeline_updated_at BEFORE UPDATE ON edu_timeline 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_edu_milestone_updated_at BEFORE UPDATE ON edu_milestone 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_edu_event_updated_at BEFORE UPDATE ON edu_event 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Add some constraints
ALTER TABLE edu_milestone ADD CONSTRAINT unique_timeline_order UNIQUE (timeline_id, order_index);
ALTER TABLE edu_event ADD CONSTRAINT unique_milestone_order UNIQUE (milestone_id, order_index);

-- Add comments for documentation
COMMENT ON TABLE edu_timeline IS 'Educational timelines for fact-checking and misinformation analysis';
COMMENT ON TABLE edu_milestone IS 'Timeline milestones with dates and positioning';
COMMENT ON TABLE edu_event IS 'Events within milestones with detailed content and expert perspectives';

COMMENT ON COLUMN edu_timeline.dimension_top_title IS 'Title for the top dimension of the timeline visualization';
COMMENT ON COLUMN edu_timeline.dimension_bottom_title IS 'Title for the bottom dimension of the timeline visualization';
COMMENT ON COLUMN edu_milestone.is_top IS 'Whether milestone appears on top or bottom of timeline';
COMMENT ON COLUMN edu_event.text_1 IS 'Critical analysis perspective';
COMMENT ON COLUMN edu_event.text_2 IS 'Economic dimension perspective';
COMMENT ON COLUMN edu_event.text_3 IS 'Popular/common perspective';
COMMENT ON COLUMN edu_event.text_4 IS 'Psychological analysis perspective';