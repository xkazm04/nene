from enum import Enum

class StatementCategory(str, Enum):
    """Categories for statement classification."""
    POLITICS = "politics"
    ECONOMY = "economy"
    ENVIRONMENT = "environment"
    MILITARY = "military"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    TECHNOLOGY = "technology"
    SOCIAL = "social"
    INTERNATIONAL = "international"
    OTHER = "other"