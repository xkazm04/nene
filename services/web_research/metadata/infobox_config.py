"""
Configuration for Wikipedia infobox classes and field mappings
"""

# Wikipedia infobox class mappings by category
INFOBOX_CLASSES = {
    'games': [
        'infobox ib-video-game',
        'infobox hproduct',
        'infobox-video-game',
        'infobox videogame',
        'vevent'
    ],
    'sports': [
        'infobox biography vcard',
        'infobox football biography',
        'infobox basketball biography',
        'infobox hockey biography'
    ],
    'music': [
        'infobox musical artist',
        'infobox album',
        'infobox single'
    ]
}

# Field mapping configuration for each category
FIELD_MAPPINGS = {
    'games': {
        'description_fields': ['developer', 'developed by', 'studio'],
        'group_fields': ['genre', 'type'],
        'year_fields': ['release', 'published', 'date'],
        'additional_fields': ['platform', 'system', 'publisher']
    },
    'sports': {
        'description_fields': ['current team', 'club', 'team'],
        'group_fields': ['position', 'playing position'],
        'year_fields': ['born', 'birth date'],
        'additional_fields': ['career', 'active years']
    },
    'music': {
        'description_fields': ['label', 'record label'],
        'group_fields': ['genre', 'genres', 'style'],
        'year_fields': ['formed', 'active', 'career'],
        'additional_fields': ['origin', 'location']
    }
}

# Validation rules
VALIDATION_RULES = {
    'description': {
        'min_length': 2,
        'max_length': 500,
        'required': False
    },
    'group': {
        'min_length': 2,
        'max_length': 50,
        'required': False
    },
    'item_year': {
        'min_value': 1800,
        'max_value': 2030,
        'required': True
    }
}