"""AI reply drafting via Claude API. Handles errors with fallback responses."""

import json
import logging
import httpx

from app.config import settings
from app.models.unified import UnifiedMessage
from app.data.property_context import format_property_for_prompt, get_property_context

logger = logging.getLogger(__name__)


# System prompt for the AI
SYSTEM_PROMPT = """You are a warm, professional hospitality concierge for Nistula — a luxury villa rental company in Goa, India.

Your role:
- Respond to guest messages with warmth, accuracy, and professionalism
- Use the property context provided to give factual, specific answers
- Match the guest's tone — casual if they're casual, formal if they're formal
- Address the guest by their first name
- Keep responses concise but complete (2-4 sentences for simple queries, more for complex ones)

Critical rules:
- NEVER make up information. Only use facts from the property context provided.
- If you don't have the information to answer a question, say you'll check with the team and get back to them.
- For complaints, always acknowledge the issue, apologise sincerely, and assure the guest that someone will follow up.
- Do NOT include greetings like "Dear" — keep it natural and friendly.
- Respond in the same language the guest uses.

You must also assess your own confidence in the response by considering:
1. Is the answer fully supported by the property context?
2. Is there any ambiguity in the guest's question?
3. Would a human agent likely change this response?

Return your response as a JSON object with exactly these fields:
{
    "drafted_reply": "Your response to the guest",
    "confidence_factors": {
        "context_supported": true/false,
        "ambiguity_level": "low" | "medium" | "high",
        "needs_human_review": true/false,
        "reasoning": "Brief explanation of confidence assessment"
    }
}"""


def _build_user_prompt(unified_message: UnifiedMessage) -> str:
    """Build the user prompt with guest message and property context."""
    property_context = format_property_for_prompt(unified_message.property_id)

    return f"""Guest Message Details:
- Guest Name: {unified_message.guest_name}
- Source Channel: {unified_message.source}
- Query Type: {unified_message.query_type}
- Booking Reference: {unified_message.booking_ref or 'Not provided'}
- Message: "{unified_message.message_text}"

Property Context:
{property_context}

Respond to this guest message. Return your response as the specified JSON object."""


async def draft_reply(unified_message: UnifiedMessage) -> tuple[str, dict]:
    """Send message to Claude, return (reply_text, confidence_factors)."""
    user_prompt = _build_user_prompt(unified_message)

    try:
        async with httpx.AsyncClient(timeout=settings.claude_timeout) as client:
            response = await client.post(
                settings.claude_api_url,
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": settings.claude_model,
                    "max_tokens": settings.claude_max_tokens,
                    "system": SYSTEM_PROMPT,
                    "messages": [
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )

            if response.status_code != 200:
                logger.error(
                    f"Claude API returned {response.status_code}: {response.text}"
                )
                return _fallback_reply(unified_message), {
                    "error": f"API returned {response.status_code}",
                    "fallback": True,
                }

            # Parse response
            data = response.json()
            content = data.get("content", [{}])[0].get("text", "")

            return _parse_ai_response(content, unified_message)

    except httpx.TimeoutException:
        logger.error(
            f"Claude API timeout after {settings.claude_timeout}s for message {unified_message.message_id}"
        )
        return _fallback_reply(unified_message), {
            "error": "API timeout",
            "fallback": True,
        }

    except httpx.ConnectError as e:
        logger.error(f"Claude API connection error: {e}")
        return _fallback_reply(unified_message), {
            "error": "Connection failed",
            "fallback": True,
        }

    except Exception as e:
        logger.error(f"Unexpected error calling Claude API: {e}")
        return _fallback_reply(unified_message), {
            "error": str(e),
            "fallback": True,
        }


def _parse_ai_response(
    raw_content: str, unified_message: UnifiedMessage
) -> tuple[str, dict]:
    """Parse JSON response. Handles markdown-wrapped JSON and plain text."""
    try:
        # Strip markdown code blocks if present
        cleaned = raw_content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        parsed = json.loads(cleaned)
        drafted_reply = parsed.get("drafted_reply", "")
        confidence_factors = parsed.get("confidence_factors", {})

        if not drafted_reply:
            logger.warning("Claude returned empty drafted_reply, using fallback")
            return _fallback_reply(unified_message), {
                "error": "Empty AI response",
                "fallback": True,
            }

        return drafted_reply, confidence_factors

    except json.JSONDecodeError:
        # Not valid JSON — use raw text if it looks like a normal reply
        logger.warning(
            "Claude response was not valid JSON, using raw text as reply"
        )

        if len(raw_content) > 20 and not raw_content.startswith("{"):
            return raw_content.strip(), {
                "warning": "Response was plain text, not JSON",
                "fallback": False,
            }
        return _fallback_reply(unified_message), {
            "error": "Invalid JSON response",
            "fallback": True,
        }


def _fallback_reply(unified_message: UnifiedMessage) -> str:
    """Safe fallback when AI is unavailable. Guest always gets a response."""
    first_name = unified_message.guest_name.split()[0]

    fallback_messages = {
        "complaint": (
            f"Hi {first_name}, thank you for reaching out. I sincerely apologise "
            f"for the inconvenience. I've flagged this with our team and someone "
            f"will get back to you very shortly to resolve this."
        ),
        "pre_sales_availability": (
            f"Hi {first_name}, thank you for your interest! Let me check the "
            f"availability details for you — our team will get back to you shortly "
            f"with confirmed dates and rates."
        ),
        "pre_sales_pricing": (
            f"Hi {first_name}, thanks for asking about rates! Let me get the "
            f"exact pricing details for you — someone from our team will respond "
            f"shortly with a quote."
        ),
        "post_sales_checkin": (
            f"Hi {first_name}, thanks for your message! Our team will send you "
            f"all the check-in details shortly. If it's urgent, our caretaker "
            f"is available during daytime hours."
        ),
        "special_request": (
            f"Hi {first_name}, thank you for the request! I'll check with our "
            f"team about this and get back to you as soon as possible."
        ),
        "general_enquiry": (
            f"Hi {first_name}, thanks for reaching out! Let me look into this "
            f"for you — our team will respond shortly."
        ),
    }

    return fallback_messages.get(
        unified_message.query_type,
        f"Hi {first_name}, thank you for your message. Our team will get back to you shortly.",
    )
