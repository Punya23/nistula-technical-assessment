# Nistula Guest Message Handler

A webhook-based API that processes guest messages from multiple hospitality channels, drafts AI-powered replies using Claude, and returns confidence-scored responses with recommended actions.

Built for the Nistula Summer Technology Internship 2026 Technical Assessment.

---

## Quick Start

```bash
# 1. Clone and enter the project
git clone https://github.com/YOUR_USERNAME/nistula-technical-assessment.git
cd nistula-technical-assessment

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# 5. Run the server
uvicorn app.main:app --reload

# 6. Open the interactive API docs
# http://localhost:8000/docs
```

The server starts on `http://localhost:8000`. Hit `/health` to verify.

---

## Architecture

```
POST /webhook/message
        │
        ▼
┌───────────────┐
│   Validate    │  Pydantic model validates source, fields, types
│   Payload     │  → 422 if invalid
└───────┬───────┘
        │
        ▼
┌───────────────┐
│  Normalise    │  Map channel-specific fields → unified schema
│  Message      │  Strip channel artifacts, generate UUID
└───────┬───────┘
        │
        ▼
┌───────────────┐
│  Classify     │  Hybrid: keyword rules (fast, free)
│  Query Type   │  → Claude validates during drafting
└───────┬───────┘
        │
        ▼
┌───────────────┐
│  Draft Reply  │  Claude API with property context
│  (Claude AI)  │  → Fallback reply if API unavailable
└───────┬───────┘
        │
        ▼
┌───────────────┐
│  Calculate    │  4-factor weighted score + adjustments
│  Confidence   │  → Determine action (auto/review/escalate)
└───────┬───────┘
        │
        ▼
┌───────────────┐
│   Return      │  { message_id, query_type, drafted_reply,
│   Response    │    confidence_score, action, breakdown }
└───────────────┘
```

---

## API Reference

### `POST /webhook/message`

Process an inbound guest message.

**Request:**
```json
{
  "source": "whatsapp",
  "guest_name": "Rahul Sharma",
  "message": "Is the villa available from April 20 to 24? What is the rate for 2 adults?",
  "timestamp": "2026-05-05T10:30:00Z",
  "booking_ref": "NIS-2024-0891",
  "property_id": "villa-b1"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source` | string | Yes | `whatsapp`, `booking_com`, `airbnb`, `instagram`, `direct` |
| `guest_name` | string | Yes | Guest's display name |
| `message` | string | Yes | Raw message text |
| `timestamp` | string | Yes | ISO 8601 timestamp |
| `booking_ref` | string | No | Booking reference |
| `property_id` | string | No | Property identifier |

**Response:**
```json
{
  "message_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "query_type": "pre_sales_availability",
  "drafted_reply": "Hi Rahul! Great news — Villa B1 is available from April 20 to 24...",
  "confidence_score": 0.91,
  "action": "auto_send",
  "confidence_breakdown": {
    "classification_confidence": 0.85,
    "context_coverage": 1.0,
    "sentiment_clarity": 0.75,
    "response_specificity": 0.8,
    "adjustments": ["multi_question(2): -0.05", "direct_context_match: +0.10"],
    "final_score": 0.91,
    "action": "auto_send"
  }
}
```

### `GET /health`

Health check endpoint.

### `GET /docs`

Interactive Swagger UI — test the API directly in your browser.

---

## Confidence Scoring Logic

The confidence score determines whether an AI-drafted reply should be sent automatically, reviewed by a human, or escalated. It's not a random number — it's a **documented, explainable system**.

### Formula

```
confidence = weighted_average(
    classification_confidence × 0.30    # How clearly the message maps to a query type
    context_coverage          × 0.30    # Is the answer in our property data?
    sentiment_clarity         × 0.20    # Clear positive/negative vs ambiguous
    response_specificity      × 0.20    # Does the reply cite specific facts?
)
```

### Adjustment Rules

| Condition | Adjustment | Reason |
|-----------|------------|--------|
| Query is a `complaint` | Cap at 0.55 | Complaints need human empathy and authority |
| Post-sales without `booking_ref` | −0.15 | Can't verify the guest's reservation |
| Multiple questions (`?` count > 1) | −0.05 per extra `?` | Harder to answer all parts correctly |
| Direct match in property context | +0.10 | High confidence the answer is factual |

### Action Thresholds

| Score | Action | What Happens |
|-------|--------|-------------|
| > 0.85 | `auto_send` | Reply sent to guest without human review |
| 0.60 – 0.85 | `agent_review` | Reply shown to agent for review before sending |
| < 0.60 | `escalate` | Routed to human agent for manual response |
| Any complaint | `escalate` | Complaints are always escalated, regardless of score |

### Why This Approach?

A startup can't afford to have a human review every message, but it also can't afford to auto-send bad replies. This system:
- **Auto-sends** clear, factual queries (availability, pricing, check-in info) — ~60% of messages
- **Routes for review** ambiguous or multi-part queries — ~25% of messages  
- **Escalates** complaints and edge cases — ~15% of messages

The breakdown is included in every response so agents can understand *why* the AI made its decision.

---

## Design Decisions

1. **FastAPI over Express** — Auto-generated Swagger docs, Pydantic validation, native async, type hints. The right tool for a Python-first AI integration.

2. **Hybrid query classification** — Keyword rules handle 80% of messages without an API call. Claude catches edge cases during drafting. A startup shouldn't burn API credits on every message.

3. **Graceful AI fallbacks** — If Claude is unavailable (timeout, error, rate limit), the system returns a polite holding response tailored to the query type. The guest is never left without a response.

4. **Confidence breakdown transparency** — Every response includes the full scoring breakdown. This builds trust with agents and makes debugging easy.

5. **Channel-specific normalisation** — Each channel has quirks (Booking.com prefixes, WhatsApp formatting). The normaliser handles these before the AI sees the message.

---

## Testing

### Automated Tests (pytest)
```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_webhook.py -v
pytest tests/test_classifier.py -v
pytest tests/test_confidence.py -v
```

### Manual Testing (curl)
```bash
# Run the sample requests script
chmod +x examples/sample_requests.sh
./examples/sample_requests.sh
```

### Interactive Testing
Open `http://localhost:8000/docs` for Swagger UI — test any payload directly in the browser.

---

## Project Structure

```
├── app/
│   ├── main.py                 # FastAPI app + webhook endpoint
│   ├── config.py               # Environment config (Pydantic)
│   ├── models/
│   │   ├── webhook.py          # Inbound payload model
│   │   ├── unified.py          # Unified message schema
│   │   └── response.py         # API response model
│   ├── services/
│   │   ├── normalizer.py       # Webhook → Unified schema
│   │   ├── classifier.py       # Query type classification
│   │   ├── ai_drafter.py       # Claude API integration
│   │   └── confidence.py       # Confidence scoring engine
│   └── data/
│       └── property_context.py # Mock property data
├── tests/                      # pytest test suite
├── examples/                   # curl test scripts
├── schema.sql                  # Part 2 — PostgreSQL schema
├── thinking.md                 # Part 3 — Written answers
├── .env.example                # Environment template
└── requirements.txt            # Dependencies
```

---

## What I'd Build Next

If this were a real product, the next iterations would be:

1. **Conversation memory** — Store conversation history so the AI has context from previous messages with the same guest.
2. **Multi-language support** — Detect the guest's language and respond accordingly (Goa gets international tourists).
3. **Webhook delivery** — Send the drafted reply back to the source channel (WhatsApp Business API, Booking.com messaging API).
4. **Agent dashboard** — Web UI showing pending reviews, escalations, and conversation timelines.
5. **Model evaluation pipeline** — A/B test different models and prompts, track which drafts get edited by agents, feed edits back as training data.
6. **Rate limiting** — Per-channel rate limits to prevent API abuse.

---

## Author

Built by Punya Surana for the Nistula Summer Technology Internship 2026 Technical Assessment.
