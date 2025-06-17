-- Extended Profile Schema with new attributes

-- Add new columns to existing profiles table
ALTER TABLE public.profiles 
ADD COLUMN IF NOT EXISTS type VARCHAR(50) DEFAULT 'person',
ADD COLUMN IF NOT EXISTS position VARCHAR(255),
ADD COLUMN IF NOT EXISTS bg_url TEXT,
ADD COLUMN IF NOT EXISTS score DECIMAL(5,2) DEFAULT 0.00;

-- Create indexes for new columns
CREATE INDEX IF NOT EXISTS idx_profiles_type ON public.profiles (type);
CREATE INDEX IF NOT EXISTS idx_profiles_position ON public.profiles (position);
CREATE INDEX IF NOT EXISTS idx_profiles_score ON public.profiles (score);

-- Update existing records with default values if needed
UPDATE public.profiles 
SET 
    type = 'person',
    score = 0.00
WHERE type IS NULL OR score IS NULL;

-- Add constraints
ALTER TABLE public.profiles 
ADD CONSTRAINT chk_profiles_score CHECK (score >= 0.00 AND score <= 100.00);

-- Add some sample data with extended fields
INSERT INTO public.profiles (name, name_normalized, country, party, type, position, score) VALUES
('Elon Musk', 'elon musk', 'US', NULL, 'person', 'CEO', 78.5),
('CNN', 'cnn', 'US', NULL, 'media', 'News Network', 65.2),
('Anthony Fauci', 'anthony fauci', 'US', NULL, 'person', 'Medical Expert', 82.1)
ON CONFLICT (name) DO NOTHING;

-- Create view for profile statistics (optional, for future use)
CREATE OR REPLACE VIEW profile_stats AS
SELECT 
    p.*,
    COALESCE(stmt_count.total_statements, 0) as total_statements,
    COALESCE(stmt_count.recent_statements, 0) as recent_statements_30d
FROM public.profiles p
LEFT JOIN (
    -- This would join with statements table when available
    -- For now, we'll use dummy data
    SELECT 
        profile_id,
        COUNT(*) as total_statements,
        COUNT(CASE WHEN created_at >= NOW() - INTERVAL '30 days' THEN 1 END) as recent_statements
    FROM (VALUES 
        -- Dummy data - replace with actual statements table join
        (NULL::UUID, 0, NOW())
    ) AS dummy_statements(profile_id, total_statements, created_at)
    GROUP BY profile_id
) stmt_count ON p.id = stmt_count.profile_id;

COMMENT ON COLUMN public.profiles.type IS 'Type of profile: person, media, organization, etc.';
COMMENT ON COLUMN public.profiles.position IS 'Position or role: president, politician, CEO, etc.';
COMMENT ON COLUMN public.profiles.bg_url IS 'Background image URL for profile';
COMMENT ON COLUMN public.profiles.score IS 'Profile credibility/reliability score (0-100)';