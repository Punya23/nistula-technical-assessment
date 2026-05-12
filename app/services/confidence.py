"""
Confidence scoring engine.

Calculates a composite confidence score for AI-generated replies.
The score determines whether the reply should be auto-sent, reviewed
by a human agent, or escalated.

Scoring Formula:
    confidence = weighted_average(
        classification_confidence × 0.30,
        context_coverage         × 0.30,
        sentiment_clarity        × 0.20,
        response_specificity     × 0.20,
    )

Adjustment Rules:
    - Complaint → cap at 0.55 (always escalate)
    - Missing booking_ref on post-sales → reduce by 0.15
    - Multiple questions → reduce by 0.10
    - Direct context match → boost by 0.10

Action Mapping:
    > 0.85         → auto_send
    0.60 – 0.85    → agent_review
    < 0.60         → escalate
    complaint      → escalate (always)
"""

from app.models.unified import UnifiedMessage, QueryType
from app.models.response import ActionType


def calculate_confidence(
    unified_message: UnifiedMessage,
    classification_confidence: float,
    drafted_reply: str,
    property_context: dict | None,
) -> tuple[float, dict, ActionType]:
    """
    Calculate the composite confidence score for an AI-drafted reply.

    Args:
        unified_message: The normalised inbound message.
        classification_confidence: How confident the classifier was.
        drafted_reply: The AI-generated reply text.
        property_context: Property data used to verify factual grounding.

    Returns:
        Tuple of (confidence_score, breakdown_dict, recommended_action).
    """
    # --- Factor 1: Classification Confidence (30%) ---
    # How clearly the message maps to a single query type
    cls_score = classification_confidence

    # --- Factor 2: Context Coverage (30%) ---
    # Does the property context contain enough data to answer this query?
    ctx_score = _calculate_context_coverage(
        unified_message.query_type,
        unified_message.message_text,
        property_context,
    )

    # --- Factor 3: Sentiment Clarity (20%) ---
    # Is the message clearly positive/neutral or clearly negative?
    # Ambiguous sentiment = lower confidence in appropriate response
    sent_score = _calculate_sentiment_clarity(unified_message.message_text)

    # --- Factor 4: Response Specificity (20%) ---
    # Does the drafted reply contain specific facts or generic filler?
    spec_score = _calculate_response_specificity(drafted_reply, property_context)

    # --- Weighted Average ---
    raw_score = (
        cls_score * 0.30
        + ctx_score * 0.30
        + sent_score * 0.20
        + spec_score * 0.20
    )

    # --- Apply Adjustment Rules ---
    adjustments = []

    # Rule: Complaints are always escalated
    if unified_message.query_type == "complaint":
        raw_score = min(raw_score, 0.55)
        adjustments.append("complaint_cap: capped at 0.55")

    # Rule: Post-sales without booking ref = lower confidence
    if (
        unified_message.query_type in ("post_sales_checkin", "special_request")
        and not unified_message.booking_ref
    ):
        raw_score -= 0.15
        adjustments.append("missing_booking_ref: -0.15")

    # Rule: Multiple questions = harder to answer completely
    question_count = unified_message.message_text.count("?")
    if question_count > 1:
        penalty = min(0.10, 0.05 * (question_count - 1))
        raw_score -= penalty
        adjustments.append(f"multi_question({question_count}): -{penalty}")

    # Rule: Direct context match = higher confidence
    if _has_direct_context_match(unified_message.message_text, property_context):
        raw_score += 0.10
        adjustments.append("direct_context_match: +0.10")

    # Clamp to [0, 1]
    final_score = round(max(0.0, min(1.0, raw_score)), 2)

    # Determine action
    action = _determine_action(final_score, unified_message.query_type)

    # Build breakdown for transparency
    breakdown = {
        "classification_confidence": round(cls_score, 2),
        "context_coverage": round(ctx_score, 2),
        "sentiment_clarity": round(sent_score, 2),
        "response_specificity": round(spec_score, 2),
        "raw_weighted_score": round(
            cls_score * 0.30 + ctx_score * 0.30 + sent_score * 0.20 + spec_score * 0.20,
            2,
        ),
        "adjustments": adjustments,
        "final_score": final_score,
        "action": action,
    }

    return final_score, breakdown, action


def _calculate_context_coverage(
    query_type: QueryType,
    message_text: str,
    property_context: dict | None,
) -> float:
    """
    Score how well the property context can answer this type of query.
    Higher score = the answer is clearly in our data.
    """
    if not property_context:
        return 0.3  # No context → low coverage

    text_lower = message_text.lower()

    # Map query types to the property fields needed to answer them
    coverage_map = {
        "pre_sales_availability": ["availability"],
        "pre_sales_pricing": ["base_rate_inr", "extra_guest_rate_inr"],
        "post_sales_checkin": ["check_in_time", "check_out_time", "wifi_password", "caretaker_hours"],
        "special_request": ["chef_available", "caretaker_hours"],
        "complaint": [],  # Complaints need human judgement, not data
        "general_enquiry": ["amenities", "max_guests", "bedrooms"],
    }

    required_fields = coverage_map.get(query_type, [])
    if not required_fields:
        return 0.5  # No specific fields needed

    available_count = sum(
        1 for field in required_fields if field in property_context
    )
    coverage = available_count / len(required_fields)

    return max(0.3, min(1.0, coverage))


def _calculate_sentiment_clarity(message_text: str) -> float:
    """
    Score how clear the sentiment of the message is.
    Clear sentiment (positive or negative) = easier to respond appropriately.
    """
    text_lower = message_text.lower()

    # Strong negative indicators
    negative_words = [
        "not working", "broken", "terrible", "worst", "disgusting",
        "disappointed", "unacceptable", "refund", "angry", "furious",
        "horrible", "complaint", "rude", "dirty", "unsafe",
    ]

    # Strong positive/neutral indicators
    positive_words = [
        "looking forward", "excited", "thank", "appreciate", "wonderful",
        "lovely", "beautiful", "great", "amazing", "perfect",
        "interested", "planning", "would like", "please",
    ]

    neg_count = sum(1 for word in negative_words if word in text_lower)
    pos_count = sum(1 for word in positive_words if word in text_lower)

    if neg_count > 0 and pos_count > 0:
        # Mixed sentiment — harder to respond
        return 0.4
    elif neg_count > 0:
        # Clear negative — we know how to handle (empathy + action)
        return 0.7
    elif pos_count > 0:
        # Clear positive — easy to respond warmly
        return 0.9
    else:
        # Neutral/factual query — straightforward
        return 0.75


def _calculate_response_specificity(
    drafted_reply: str,
    property_context: dict | None,
) -> float:
    """
    Score how specific and factual the drafted reply is.
    Specific facts from property context = higher score.
    """
    if not drafted_reply or not property_context:
        return 0.4

    reply_lower = drafted_reply.lower()
    specificity_markers = 0

    # Check if the reply contains specific property facts
    fact_checks = [
        str(property_context.get("base_rate_inr", "")),
        str(property_context.get("check_in_time", "")),
        str(property_context.get("check_out_time", "")),
        property_context.get("wifi_password", ""),
        str(property_context.get("max_guests", "")),
        str(property_context.get("bedrooms", "")),
        property_context.get("cancellation_policy", ""),
    ]

    for fact in fact_checks:
        if fact and fact.lower() in reply_lower:
            specificity_markers += 1

    # Also check for specific numbers (prices, times, etc.)
    import re
    numbers_in_reply = len(re.findall(r'\d+', drafted_reply))
    if numbers_in_reply > 2:
        specificity_markers += 1

    # Score based on how many facts are referenced
    score = min(1.0, 0.4 + (specificity_markers * 0.1))

    return round(score, 2)


def _has_direct_context_match(message_text: str, property_context: dict | None) -> bool:
    """
    Check if the message directly asks about something we have data for.
    """
    if not property_context:
        return False

    text_lower = message_text.lower()

    # Direct matches: guest asks about X, and X is in our context
    direct_mappings = [
        (["available", "availability", "april 20", "april 24"], "availability"),
        (["rate", "price", "cost", "per night", "how much"], "base_rate_inr"),
        (["check-in", "check in", "checkin"], "check_in_time"),
        (["check-out", "check out", "checkout"], "check_out_time"),
        (["wifi", "wi-fi", "password"], "wifi_password"),
        (["pool", "swimming"], "private_pool"),
        (["chef", "cook", "food"], "chef_available"),
        (["cancel", "cancellation", "refund policy"], "cancellation_policy"),
    ]

    for keywords, field in direct_mappings:
        if any(kw in text_lower for kw in keywords) and field in property_context:
            return True

    return False


def _determine_action(confidence_score: float, query_type: QueryType) -> ActionType:
    """
    Determine the recommended action based on confidence score and query type.

    Thresholds:
        > 0.85         → auto_send
        0.60 – 0.85    → agent_review
        < 0.60         → escalate
        complaint      → escalate (regardless of score)
    """
    # Complaints are always escalated
    if query_type == "complaint":
        return "escalate"

    if confidence_score > 0.85:
        return "auto_send"
    elif confidence_score >= 0.60:
        return "agent_review"
    else:
        return "escalate"
