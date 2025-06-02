-- Add profile_id column to research_results table
ALTER TABLE public.research_results 
ADD COLUMN profile_id UUID;

-- Add foreign key constraint to profiles table
ALTER TABLE public.research_results 
ADD CONSTRAINT fk_research_results_profile_id 
FOREIGN KEY (profile_id) REFERENCES public.profiles(id) 
ON DELETE SET NULL;

-- Create index for better performance on profile_id lookups
CREATE INDEX idx_research_results_profile_id ON public.research_results (profile_id);

-- Optional: Update existing records by matching source names with profiles
-- This will attempt to link existing research results with profiles based on source name
UPDATE public.research_results 
SET profile_id = p.id
FROM public.profiles p
WHERE research_results.source IS NOT NULL 
  AND research_results.profile_id IS NULL
  AND LOWER(TRIM(research_results.source)) = p.name_normalized;

-- Check how many records were updated
SELECT 
    COUNT(*) as total_research_results,
    COUNT(profile_id) as linked_to_profiles,
    COUNT(*) - COUNT(profile_id) as unlinked
FROM public.research_results;