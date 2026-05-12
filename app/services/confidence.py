"""
Confidence scoring — additive rule-based.
Starts at 0.50, adjusts with clear rules. See thresholds below.

Actions:
    >0.85 auto_send | 0.60-0.85 agent_review | <0.60 escalate
    complaint = always escalate
"""

from app.models.unified import UnifiedMessage, QueryType
from app.models.response import ActionType


def calculate_confidence(
    unified_message: UnifiedMessage,
    classification_confidence: float,
    drafted_reply: str,
    property_context: dict | None,
) -> tuple[float, dict, ActionType]:
    """Calculate confidence score using additive rules. Returns (score, breakdown, action)."""
    score = 0.50
    adjustments = []

    # Strong keyword match -> more confident about intent
    if classification_confidence >= 0.70:
        score += 0.20
        adjustments.append("clear_keyword_match: +0.20")

    # Booking ref lets us verify the reservation
    if unified_message.booking_ref:
        score += 0.10
        adjustments.append("booking_ref_present: +0.10")

    # Answer grounded in property data
    if _context_has_answer(unified_message.query_type, property_context):
        score += 0.15
        adjustments.append("context_has_answer: +0.15")

    # Substantive reply = likely addressed the question
    if drafted_reply and len(drafted_reply) > 50:
        score += 0.10
        adjustments.append("substantive_reply: +0.10")

    # Multiple questions = harder to answer completely
    question_count = unified_message.message_text.count("?")
    if question_count > 1:
        score -= 0.10
        adjustments.append(f"multiple_questions({question_count}): -0.10")

    # Complaints always need human handling
    if unified_message.query_type == "complaint":
        score = min(score, 0.55)
        adjustments.append("complaint_cap: capped at 0.55")


    final_score = round(max(0.0, min(1.0, score)), 2)


    action = _determine_action(final_score, unified_message.query_type)

    breakdown = {
        "base_score": 0.50,
        "adjustments": adjustments,
        "final_score": final_score,
        "action": action,
    }

    return final_score, breakdown, action


def _context_has_answer(query_type: QueryType, property_context: dict | None) -> bool:
    """Check if property context has the fields needed for this query type."""
    if not property_context:
        return False


    required_fields = {
        "pre_sales_availability": ["availability"],
        "pre_sales_pricing": ["base_rate_inr", "extra_guest_rate_inr"],
        "post_sales_checkin": ["check_in_time", "check_out_time", "wifi_password"],
        "special_request": ["chef_available", "caretaker_hours"],
        "general_enquiry": ["amenities", "max_guests"],
        "complaint": [],  # Complaints need human judgement, not data
    }

    fields = required_fields.get(query_type, [])
    if not fields:
        return False

    return all(field in property_context for field in fields)


def _determine_action(confidence_score: float, query_type: QueryType) -> ActionType:
    """Map confidence score to action. Complaints always escalate."""
    if query_type == "complaint":
        return "escalate"

    if confidence_score > 0.85:
        return "auto_send"
    elif confidence_score >= 0.60:
        return "agent_review"
    else:
        return "escalate"
