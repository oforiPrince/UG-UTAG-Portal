executive_members_position_order = ['President', 'Vice President', 'Secretary', 'Treasurer',"Women's Executive Officer"]
executive_committee_members_position_order = ['President', 'Vice President', 'Secretary', 'Treasurer',"Women's Executive Officer","National President","CBAS Rep", "CHS Rep", "COE Rep", "COH Rep"]# Legacy position names that should also be matched in DB queries
LEGACY_POSITION_NAMES = [
    'College of Humanities Rep', 'College of Health Rep', 'College of Education Rep',
    "Women's Executive\xa0Officer",  # non-breaking space variant
]
# Combined list for DB filtering (catches both old and new names)
executive_committee_members_all_positions = executive_committee_members_position_order + LEGACY_POSITION_NAMES# Mapping of old position names to new abbreviated names for backward compatibility
POSITION_NAME_MAPPING = {
    'College of Humanities Rep': 'COH Rep',
    'College of Health Rep': 'CHS Rep',
    'College of Education Rep': 'COE Rep',
    "Women's Executive\xa0Officer": "Women's Executive Officer",
    "Women\u2019s Executive Officer": "Women's Executive Officer",
    "Women\u2019s Executive\xa0Officer": "Women's Executive Officer",
}

def normalize_position_name(position):
    """
    Normalize old position names to new abbreviated names.
    Also fixes non-breaking spaces and special characters.
    Returns the normalized name or the original if not in mapping.
    """
    if not position:
        return position
    # First check direct mapping
    mapped = POSITION_NAME_MAPPING.get(position)
    if mapped:
        return mapped
    # Also try normalizing non-breaking spaces
    normalized = position.replace('\xa0', ' ').replace('\u00A0', ' ')
    return POSITION_NAME_MAPPING.get(normalized, normalized)