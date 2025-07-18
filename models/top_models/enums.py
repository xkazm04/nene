from enum import Enum

class CategoryEnum(str, Enum):
    """Category enumeration based on actual data usage"""
    sports = "sports"
    games = "games" 
    music = "music" 
    other = "other"

class AccoladeType(str, Enum):
    """Accolade type enumeration with extended types for different categories"""
    # General types
    award = "award"
    achievement = "achievement"
    record = "record"
    
    # Sports-specific
    championship = "championship"
    
    # Games-specific  
    metacritic_users = "metacritic_users"
    metacritic_critics = "metacritic_critics"
    goty = "goty"  # Game of the Year
    
    # Music-specific
    certification = "certification"  # Gold, Platinum, etc.
    chart_position = "chart_position"
    
    # General recognition
    honor = "honor"
    nomination = "nomination"

class VoteValue(int, Enum):
    """Vote value enumeration"""
    DOWNVOTE = -1
    UPVOTE = 1

class ResearchDepth(str, Enum):
    """Research depth options for metadata research"""
    quick = "quick"
    standard = "standard"
    deep = "deep"

class DuplicateAction(str, Enum):
    """Actions to take when duplicates are found"""
    reject = "reject"
    allow = "allow"
    merge = "merge"
    replace = "replace"