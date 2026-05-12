"""
Nistula Guest Message Handler — FastAPI Application

Main entry point for the webhook-based guest message processing pipeline.
Receives inbound messages from multiple channels, normalises them,
drafts AI-powered replies using Claude, and returns confidence-scored responses.

Endpoints:
    POST /webhook/message  — Process an inbound guest message
    GET  /health           — Health check
    GET  /docs             — Interactive API documentation (Swagger UI)
"""

import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.models.webhook import WebhookPayload
from app.models.response import WebhookResponse, ErrorResponse
from app.services.normalizer import normalize_message
from app.services.classifier import get_classification_confidence
from app.services.ai_drafter import draft_reply
from app.services.confidence import calculate_confidence
from app.data.property_context import get_property_context

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle — startup and shutdown events."""
    logger.info("# Nistula Guest Message Handler starting up")
    logger.info(f"   Claude model: {settings.claude_model}")
    logger.info(f"   API key configured: {'Yes' if settings.anthropic_api_key else 'No'}")
    logger.info(f"   Debug mode: {settings.debug}")
    yield
    logger.info("# Nistula Guest Message Handler shutting down")


# --- FastAPI Application ---
app = FastAPI(
    title="Nistula Guest Message Handler",
    description=(
        "Webhook-based API that receives guest messages from multiple channels "
        "(WhatsApp, Booking.com, Airbnb, Instagram, Direct), normalises them into "
        "a unified schema, drafts AI-powered replies using Claude, and returns "
        "confidence-scored responses with recommended actions."
    ),
    version="1.0.0",
    lifespan=lifespan,
    responses={
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)

# CORS middleware — allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Endpoints ---


@app.get("/health", tags=["System"])
async def health_check():
    """
    Health check endpoint.

    Returns the service status and configuration summary.
    Useful for monitoring and deployment verification.
    """
    return {
        "status": "healthy",
        "service": "nistula-guest-message-handler",
        "version": "1.0.0",
        "claude_model": settings.claude_model,
        "api_key_configured": bool(settings.anthropic_api_key),
    }


@app.post(
    "/webhook/message",
    response_model=WebhookResponse,
    tags=["Webhook"],
    summary="Process an inbound guest message",
    description=(
        "Receives a guest message from any supported channel, normalises it, "
        "classifies the query type, drafts an AI reply using Claude, calculates "
        "a confidence score, and returns the response with a recommended action."
    ),
    responses={
        200: {
            "description": "Message processed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                        "query_type": "pre_sales_availability",
                        "drafted_reply": "Hi Rahul! Great news — Villa B1 is available from April 20 to 24! The rate is INR 18,000 per night for up to 4 guests. For 2 adults, you're all set at the base rate. Would you like me to proceed with the booking?",
                        "confidence_score": 0.91,
                        "action": "auto_send",
                    }
                }
            },
        },
        400: {"model": ErrorResponse, "description": "Bad request"},
        502: {"model": ErrorResponse, "description": "AI service unavailable"},
        504: {"model": ErrorResponse, "description": "AI service timeout"},
    },
)
async def process_message(payload: WebhookPayload):
    """
    Process an inbound guest message through the full pipeline:

    1. **Normalise** — Transform the raw payload into the unified schema
    2. **Classify** — Determine the query type (availability, pricing, etc.)
    3. **Draft** — Send to Claude API with property context for a reply
    4. **Score** — Calculate confidence and determine action
    5. **Return** — Respond with drafted reply + confidence + action
    """
    logger.info(
        f"📨 Incoming message from {payload.source} | "
        f"Guest: {payload.guest_name} | "
        f"Property: {payload.property_id}"
    )

    try:
        # Step 1: Normalise the webhook payload into unified schema
        unified = normalize_message(payload)
        logger.info(
            f"   ✅ Normalised | ID: {unified.message_id} | "
            f"Query type: {unified.query_type}"
        )

        # Step 2: Get classification confidence
        cls_confidence = get_classification_confidence(
            unified.message_text, unified.query_type
        )
        logger.info(f"   ✅ Classification confidence: {cls_confidence}")

        # Step 3: Draft reply using Claude
        drafted_reply_text, ai_confidence_factors = await draft_reply(unified)
        logger.info(f"   ✅ Reply drafted ({len(drafted_reply_text)} chars)")

        # Step 4: Calculate composite confidence score
        property_context = get_property_context(unified.property_id)
        confidence_score, breakdown, action = calculate_confidence(
            unified_message=unified,
            classification_confidence=cls_confidence,
            drafted_reply=drafted_reply_text,
            property_context=property_context,
        )
        logger.info(f"   ✅ Confidence: {confidence_score} | Action: {action}")

        # Step 5: Build and return response
        response = WebhookResponse(
            message_id=unified.message_id,
            query_type=unified.query_type,
            drafted_reply=drafted_reply_text,
            confidence_score=confidence_score,
            action=action,
            confidence_breakdown=breakdown,
        )

        logger.info(
            f"   🎯 Response ready | Score: {confidence_score} | "
            f"Action: {action}"
        )
        return response

    except Exception as e:
        logger.error(f"   ❌ Pipeline error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "processing_error",
                "message": f"Failed to process message: {str(e)}",
            },
        )


# --- Demo UI + Run with uvicorn ---
demo_dir = Path(__file__).resolve().parent.parent / "demo"
if demo_dir.exists():
    app.mount("/demo", StaticFiles(directory=str(demo_dir), html=True), name="demo")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
