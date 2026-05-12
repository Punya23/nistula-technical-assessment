"""
Mock property context data for Villa B1.

In production, this would come from a database. For the assessment,
we use structured data that the AI drafter includes in its prompt.
"""

# Property context used in Claude prompts for accurate, grounded responses
PROPERTIES = {
    "villa-b1": {
        "name": "Villa B1",
        "location": "Assagao, North Goa",
        "bedrooms": 3,
        "max_guests": 6,
        "private_pool": True,
        "check_in_time": "2:00 PM",
        "check_out_time": "11:00 AM",
        "base_rate_inr": 18000,
        "base_rate_guests_included": 4,
        "extra_guest_rate_inr": 2000,
        "wifi_password": "Nistula@2024",
        "caretaker_hours": "8:00 AM to 10:00 PM",
        "chef_available": True,
        "chef_note": "Pre-booking required",
        "cancellation_policy": "Free cancellation up to 7 days before check-in",
        "availability": {
            "2026-04-20_to_2026-04-24": True,
        },
        "amenities": [
            "Private pool",
            "3 bedrooms",
            "Fully equipped kitchen",
            "WiFi",
            "Air conditioning",
            "Garden",
            "Parking",
            "Caretaker on-site",
        ],
    }
}

# Default property for messages without a property_id
DEFAULT_PROPERTY_ID = "villa-b1"


def get_property_context(property_id: str | None) -> dict | None:
    """
    Retrieve property context by ID.

    Falls back to the default property if property_id is None.
    Returns None if the property is not found.
    """
    pid = property_id or DEFAULT_PROPERTY_ID
    return PROPERTIES.get(pid)


def format_property_for_prompt(property_id: str | None) -> str:
    """
    Format property data as a readable string for inclusion in Claude prompts.

    This gives the AI all the factual context it needs to answer
    guest queries without making up information.
    """
    prop = get_property_context(property_id)
    if not prop:
        return "Property information not available."

    return f"""Property: {prop['name']}, {prop['location']}
Bedrooms: {prop['bedrooms']} | Max guests: {prop['max_guests']} | Private pool: {'Yes' if prop['private_pool'] else 'No'}
Check-in: {prop['check_in_time']} | Check-out: {prop['check_out_time']}
Base rate: INR {prop['base_rate_inr']:,} per night (up to {prop['base_rate_guests_included']} guests)
Extra guest: INR {prop['extra_guest_rate_inr']:,} per night per person
WiFi password: {prop['wifi_password']}
Caretaker: Available {prop['caretaker_hours']}
Chef on call: {'Yes' if prop['chef_available'] else 'No'}, {prop['chef_note']}
Availability April 20-24: {'Available' if prop['availability'].get('2026-04-20_to_2026-04-24') else 'Check with team'}
Cancellation: {prop['cancellation_policy']}
Amenities: {', '.join(prop['amenities'])}"""
