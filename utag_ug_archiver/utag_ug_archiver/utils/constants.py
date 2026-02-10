executive_members_position_order = ['President', 'Vice President', 'Secretary', 'Treasurer',"Women's Executive Officer"]
executive_committee_members_position_order = ['President', 'Vice President', 'Secretary', 'Treasurer',"Women's Executive Officer","National President","CBAS Rep", "CHS Rep", "COE Rep", "COH Rep"]
# Mapping of old position names to new abbreviated names for backward compatibility
POSITION_NAME_MAPPING = {
    'College of Humanities Rep': 'COH Rep',
    'College of Health Rep': 'CHS Rep',
    'College of Education Rep': 'COE Rep',
}

def normalize_position_name(position):
    """
    Normalize old position names to new abbreviated names.
    Returns the normalized name or the original if not in mapping.
    """
    return POSITION_NAME_MAPPING.get(position, position)