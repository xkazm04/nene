-- Create the profiles table
CREATE TABLE public.profiles (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    name_normalized VARCHAR(255) NOT NULL UNIQUE, -- For case-insensitive matching
    avatar_url TEXT,
    country VARCHAR(2), -- ISO 3166-1 alpha-2 country code
    party VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX idx_profiles_name_normalized ON public.profiles (name_normalized);
CREATE INDEX idx_profiles_country ON public.profiles (country);
CREATE INDEX idx_profiles_party ON public.profiles (party);

-- Create function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at
CREATE TRIGGER update_profiles_updated_at 
    BEFORE UPDATE ON public.profiles 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Add RLS (Row Level Security) policies if needed
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- Allow read access to all users (adjust as needed for your security requirements)
CREATE POLICY "Enable read access for all users" ON public.profiles
    FOR SELECT USING (true);

-- Allow insert/update/delete for authenticated users (adjust as needed)
CREATE POLICY "Enable insert for authenticated users" ON public.profiles
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Enable update for authenticated users" ON public.profiles
    FOR UPDATE USING (true);

CREATE POLICY "Enable delete for authenticated users" ON public.profiles
    FOR DELETE USING (true);

-- Add some sample data (optional)
INSERT INTO public.profiles (name, name_normalized, country, party) VALUES
('Donald Trump', 'donald trump', 'US', 'Republican'),
('Joe Biden', 'joe biden', 'US', 'Democratic'),
('Barack Obama', 'barack obama', 'US', 'Democratic'),
('Kamala Harris', 'kamala harris', 'US', 'Democratic');