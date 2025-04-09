# app/data/mock_data.py

MOCK_CONSTRAINTS = [
    {"id": "gb1", "name": "Green Belt", "type": "Statutory", "explanation": True},
    {"id": "cons1", "name": "Conservation Area", "type": "Local Policy", "explanation": True},
    {"id": "flood2", "name": "Flood Zone 2", "type": "Statutory", "explanation": False},
    {"id": "tpo", "name": "Tree Preservation Order (Nearby)", "type": "Local Policy", "explanation": False},
    {"id": "listed_bldg", "name": "Listed Building (Grade II)", "type": "Statutory", "explanation": True},
]

MOCK_POLICIES = [
    {"id": "HOU1", "description": "General principles for new housing development."},
    {"id": "ENV3", "description": "Protection of landscape character."},
    {"id": "DES1", "description": "Achieving high quality design and place-making."},
    {"id": "TRN2", "description": "Managing travel demand and promoting sustainable transport."},
    {"id": "GB2", "description": "Development within the Green Belt - exceptional circumstances."},
]