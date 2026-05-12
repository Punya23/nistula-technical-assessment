"""Rule-based query classifier using keyword matching."""

import re
from app.models.unified import QueryType


# Ordered by priority — more specific patterns first
CLASSIFICATION_RULES: list[tuple[QueryType, list[str]]] = [
    # Complaints first
    (
        "complaint",
        [
            "not working",
            "broken",
            "not happy",
            "unhappy",
            "unacceptable",
            "terrible",
            "worst",
            "disgusting",
            "disappointed",
            "refund",
            "compensation",
            "complain",
            "horrible",
            "dirty",
            "noisy",
            "rude",
            "damaged",
            "unsafe",
            "not clean",
            "cockroach",
            "insect",
            "bug",
            "smell",
            "stink",
        ],
    ),
    # Special requests
    (
        "special_request",
        [
            "early check-in",
            "early checkin",
            "late check-out",
            "late checkout",
            "airport transfer",
            "airport pickup",
            "airport drop",
            "extra bed",
            "baby cot",
            "high chair",
            "decoration",
            "birthday",
            "anniversary",
            "surprise",
            "cake",
            "flowers",
            "candles",
            "special arrangement",
            "celebrate",
            "honeymoon",
        ],
    ),
    # Check-in / logistics
    (
        "post_sales_checkin",
        [
            "check-in",
            "check in",
            "checkin",
            "check-out",
            "check out",
            "checkout",
            "wifi",
            "wi-fi",
            "password",
            "directions",
            "how to reach",
            "address",
            "location",
            "caretaker",
            "contact number",
            "key",
            "access",
            "gate",
            "parking",
            "where is",
            "how do i",
        ],
    ),
    # Pricing
    (
        "pre_sales_pricing",
        [
            "rate",
            "price",
            "pricing",
            "cost",
            "per night",
            "per person",
            "charge",
            "tariff",
            "how much",
            "total cost",
            "quote",
            "estimate",
            "discount",
            "offer",
            "deal",
            "package",
            "budget",
            "affordable",
            "expensive",
            "cheap",
        ],
    ),
    # Availability / booking
    (
        "pre_sales_availability",
        [
            "available",
            "availability",
            "book",
            "booking",
            "reserve",
            "reservation",
            "dates",
            "vacant",
            "free dates",
            "open dates",
            "can i stay",
            "looking for",
            "planning",
            "trip",
            "holiday",
            "vacation",
            "getaway",
            "weekend",
        ],
    ),
]


def classify_query(message_text: str) -> QueryType:
    """
    Classify a guest message into a query type using keyword matching.

    The classifier checks patterns in order of specificity:
    1. Complaints (highest priority — always catch these)
    2. Special requests
    3. Post-sales/check-in queries
    4. Pricing queries
    5. Availability queries
    6. Default: general_enquiry

    Args:
        message_text: The normalised message text to classify.

    Returns:
        The classified QueryType.
    """
    text_lower = message_text.lower()

    for query_type, keywords in CLASSIFICATION_RULES:
        for keyword in keywords:
            # Use word boundary matching to avoid partial matches
            # e.g., "booking" shouldn't match "rebooking" context incorrectly
            if keyword in text_lower:
                return query_type

    return "general_enquiry"


def get_classification_confidence(message_text: str, query_type: QueryType) -> float:
    """
    Calculate how confident the classifier is in its classification.

    Returns a score between 0 and 1 based on:
    - Number of matching keywords (more matches = higher confidence)
    - Whether the message is short and focused vs. long and mixed

    Args:
        message_text: The normalised message text.
        query_type: The classified query type.

    Returns:
        Confidence score between 0.0 and 1.0.
    """
    text_lower = message_text.lower()
    matching_keywords = 0
    total_keywords_checked = 0

    # Count how many keywords from the matched category appear
    for qt, keywords in CLASSIFICATION_RULES:
        if qt == query_type:
            for keyword in keywords:
                total_keywords_checked += 1
                if keyword in text_lower:
                    matching_keywords += 1
            break

    if total_keywords_checked == 0:
        # general_enquiry — no keywords matched at all
        return 0.5


    keyword_ratio = min(matching_keywords / 3, 1.0)  # Cap at 3 matches = 1.0

    # Long messages are harder to classify
    word_count = len(text_lower.split())
    length_penalty = 0.0
    if word_count > 50:
        length_penalty = 0.1
    elif word_count > 100:
        length_penalty = 0.2

    # Multiple categories matching = ambiguous
    categories_matched = 0
    for qt, keywords in CLASSIFICATION_RULES:
        if any(kw in text_lower for kw in keywords):
            categories_matched += 1

    ambiguity_penalty = 0.0
    if categories_matched > 1:
        ambiguity_penalty = 0.1 * (categories_matched - 1)

    confidence = max(0.3, min(1.0, 0.5 + (keyword_ratio * 0.4) - length_penalty - ambiguity_penalty))

    return round(confidence, 2)
