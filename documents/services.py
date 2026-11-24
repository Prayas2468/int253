"""Helpers shared by document ingestion and dashboards."""

STATE_BY_DISTRICT = {
    'pune': 'Maharashtra',
    'mumbai': 'Maharashtra',
    'nashik': 'Maharashtra',
    'nagpur': 'Maharashtra',
    'thane': 'Maharashtra',
    'nanded': 'Maharashtra',
    'lucknow': 'Uttar Pradesh',
    'varanasi': 'Uttar Pradesh',
    'kanpur': 'Uttar Pradesh',
    'agra': 'Uttar Pradesh',
    'noida': 'Uttar Pradesh',
    'prayagraj': 'Uttar Pradesh',
    'delhi': 'Delhi',
    'new delhi': 'Delhi',
    'jaipur': 'Rajasthan',
    'jodhpur': 'Rajasthan',
    'udaipur': 'Rajasthan',
    'ahmedabad': 'Gujarat',
    'surat': 'Gujarat',
    'vadodara': 'Gujarat',
    'bengaluru': 'Karnataka',
    'bangalore': 'Karnataka',
    'mysuru': 'Karnataka',
    'chennai': 'Tamil Nadu',
    'coimbatore': 'Tamil Nadu',
    'hyderabad': 'Telangana',
    'warangal': 'Telangana',
    'kolkata': 'West Bengal',
    'howrah': 'West Bengal',
    'bhopal': 'Madhya Pradesh',
    'indore': 'Madhya Pradesh',
    'patna': 'Bihar',
    'gaya': 'Bihar',
    'kochi': 'Kerala',
    'thiruvananthapuram': 'Kerala',
    'chandigarh': 'Chandigarh',
    'ludhiana': 'Punjab',
    'gurugram': 'Haryana',
}

STATE_COORDS = {
    'Delhi': (28.6139, 77.2090),
    'Uttar Pradesh': (26.8467, 80.9462),
    'Maharashtra': (19.7515, 75.7139),
    'Rajasthan': (27.0238, 74.2179),
    'Gujarat': (22.2587, 71.1924),
    'Karnataka': (15.3173, 75.7139),
    'Tamil Nadu': (11.1271, 78.6569),
    'Telangana': (18.1124, 79.0193),
    'West Bengal': (22.9868, 87.8550),
    'Madhya Pradesh': (23.4733, 77.9470),
    'Bihar': (25.0961, 85.3131),
    'Kerala': (10.8505, 76.2711),
    'Chandigarh': (30.7333, 76.7794),
    'Punjab': (31.1471, 75.3412),
    'Haryana': (29.0588, 76.0856),
}


def infer_state(district):
    """Best-effort mapping from an Indian district to its state."""
    if not district:
        return ''
    value = district.strip().lower()
    if value in STATE_BY_DISTRICT:
        return STATE_BY_DISTRICT[value]
    for key, state in STATE_BY_DISTRICT.items():
        if key in value:
            return state
    return ''
