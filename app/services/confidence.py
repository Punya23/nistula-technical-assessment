"""
Confidence scoring engine.

Uses a simple, deterministic, additive rule-based approach.
Each rule adds or subtracts a fixed amount from a base score of 0.50.

Why additive over weighted-average?
- Every adjustment is explainable ("booking ref present → +0.10")
- Easy to debug: just read the adjustments list
- Deterministic: same input always produces same output
- A reviewer can verify the logic in 30 seconds

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
    Calculate confidence score using additive rules.

    Starts at 0.50 (neutral), then adjusts based on concrete,
    verifiable conditions. Each adjustment is logged for transparency.

    Args:
        unified_message: The normalised inbound message.
        classification_confidence: How confident the classifier was.
        drafted_reply: The AI-generated reply text.
        property_context: Property data used to verify factual grounding.

    Returns:
        Tuple of (confidence_score, breakdown_dict, recommended_action).
    """
    score = 0.50
    adjustments = []

    # Rule 1: Clear keyword match in classification → +0.20
    # If the classifier found strong keyword matches, we're more confident
    # about understanding the guest's intent.
    if classification_confidence >= 0.70:
        score += 0.20
        adjustments.append("clear_keyword_match: +0.20")

    # Rule 2: Booking reference present → +0.10
    # A booking ref lets us verify the guest's reservation,
    # so we can give more specific, trustworthy answers.
    if unified_message.booking_ref:
        score += 0.10
        adjustments.append("booking_ref_present: +0.10")

    # Rule 3: Property context contains the answer → +0.15
    # If the answer is in our structured data, the AI reply
    # is grounded in facts rather than guessing.
    if _context_has_answer(unified_message.query_type, property_context):
        score += 0.15
        adjustments.append("context_has_answer: +0.15")

    # Rule 4: AI returned a substantive reply → +0.10
    # A reply longer than 50 chars likely addresses the question.
    # Very short replies may indicate the AI couldn't help.
    if drafted_reply and len(drafted_reply) > 50:
        score += 0.10
        adjustments.append("substantive_reply: +0.10")

    # Rule 5: Multiple questions in the message → -0.10
    # Multi-part messages are harder to answer completely.
    # The AI might miss one of the questions.
    question_count = unified_message.message_text.count("?")
    if question_count > 1:
        score -= 0.10
        adjustments.append(f"multiple_questions({question_count}): -0.10")

    # Rule 6: Complaint → cap at 0.55
    # Complaints need human empathy and authority to handle refunds.
    # AI should never auto-send a complaint response.
    if unified_message.query_type == "complaint":
        score = min(score, 0.55)
        adjustments.append("complaint_cap: capped at 0.55")

    # Clamp to [0, 1]
    final_score = round(max(0.0, min(1.0, score)), 2)

    # Determine recommended action
    action = _determine_action(final_score, unified_message.query_type)

    breakdown = {
        "base_score": 0.50,
        "adjustments": adjustments,
        "final_score": final_score,
        "action": action,
    }

    return final_score, breakdown, action


def _context_has_answer(query_type: QueryType, property_context: dict | None) -> bool:
    """
    Check if the property context contains data needed to answer this query type.

    Returns True if the relevant fields exist in the context.
    """
    if not property_context:
        return False

    # Map query types to the property fields needed
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
    """
    Determine the recommended action based on confidence score and query type.

    Thresholds:
        > 0.85         → auto_send
        0.60 – 0.85    → agent_review
        < 0.60         → escalate
        complaint      → escalate (regardless of score)
    """
    if query_type == "complaint":
        return "escalate"

    if confidence_score > 0.85:
        return "auto_send"
    elif confidence_score >= 0.60:
        return "agent_review"
    else:
        return "escalate"
