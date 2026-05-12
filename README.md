# Nistula Guest Message Handler

A webhook-based API that processes guest messages from multiple hospitality channels, drafts AI-powered replies using Claude, and returns confidence-scored responses with recommended actions.

Built for the Nistula Summer Technology Internship 2026 Technical Assessment.

---

## Quick Start

```bash
# 1. Clone and enter the project
git clone https://github.com/Punya23/nistula-technical-assessment.git
cd nistula-technical-assessment

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # macOS/Linux

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
│   Validate    │  Pydantic validates source, fields, types
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
│  Classify     │  Rule-based keyword matching
│  Query Type   │  Fast, free, deterministic
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
│  Calculate    │  Additive rule-based scoring
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
  "confidence_score": 0.85,
  "action": "agent_review",
  "confidence_breakdown": {
    "base_score": 0.50,
    "adjustments": [
      "clear_keyword_match: +0.20",
      "booking_ref_present: +0.10",
      "context_has_answer: +0.15",
      "substantive_reply: +0.10",
      "multiple_questions(2): -0.10"
    ],
    "final_score": 0.85,
    "action": "agent_review"
  }
}
```

### `GET /health`

Health check endpoint — returns service status and configuration.

### `GET /docs`

Interactive Swagger UI — test the API directly in your browser.

---

## Confidence Scoring Logic

The confidence score determines whether an AI reply should be sent automatically, reviewed by a human, or escalated. It uses a simple additive model — start at 0.50, apply clear rules.

### How It Works

```
Start: 0.50 (neutral)

+ 0.20  if classifier found a clear keyword match
+ 0.10  if booking reference is present
+ 0.15  if property context contains the answer
+ 0.10  if AI returned a substantive reply (>50 chars)
- 0.10  if message contains multiple questions
cap 0.55 if message is a complaint

Clamp to [0.0, 1.0]
```

### Why Additive?

I initially built a 4-factor weighted average (classification confidence × 0.30, context coverage × 0.30, sentiment clarity × 0.20, response specificity × 0.20). It worked, but during testing I realised:

- **It was hard to explain** — "why did this score 0.73?" required tracing through 4 weighted calculations
- **It was hard to debug** — changing one factor had ripple effects across the formula
- **It was overkill** — for a messaging platform MVP, you need to know: did we understand the question? Do we have the answer? Is it a complaint?

The additive model answers those questions directly. Every adjustment is a yes/no rule that maps to a plain-English explanation. An agent can read the breakdown and immediately understand why the AI decided what it did.

### Action Thresholds

| Score | Action | What Happens |
|-------|--------|-------------|
| > 0.85 | `auto_send` | Reply sent without human review |
| 0.60 – 0.85 | `agent_review` | Reply shown to agent for review |
| < 0.60 | `escalate` | Routed to human agent |
| Any complaint | `escalate` | Always escalated, regardless of score |

---

## Design Decisions

1. **FastAPI** — Auto-generated Swagger docs, Pydantic validation, native async. The right tool for a Python API with AI integration.

2. **Rule-based classification** — Keywords handle the common cases without API calls. A startup shouldn't burn Claude credits on every message when "Is the villa available?" clearly maps to `pre_sales_availability`.

3. **Graceful AI fallbacks** — If Claude is unavailable, the system returns a polite holding response tailored to the query type. The guest is never left without a response.

4. **Additive confidence scoring** — Transparent, debuggable, deterministic. Replaced an initial weighted-average approach after realising simpler was better for this scope.

5. **AI fields on messages table** — Originally built a separate `ai_responses` table. Merged it because at MVP stage, there's one draft per message — a separate table just adds JOINs without benefit.

---

## Error Handling

| Scenario | HTTP Code | Behavior |
|----------|-----------|----------|
| Missing required fields | 422 | Pydantic validation errors |
| Unsupported source channel | 422 | "Input should be 'whatsapp', 'booking_com'..." |
| Claude API timeout | 504 | Fallback reply + escalate |
| Claude API error | 502 | Fallback reply + escalate |
| Unexpected error | 500 | Error logged + meaningful error response |

---

## Testing

### Automated Tests (pytest)
```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_classifier.py -v
pytest tests/test_confidence.py -v
```

### Manual Testing (curl)
```bash
chmod +x examples/sample_requests.sh
./examples/sample_requests.sh
```

### Interactive Testing
Open `http://localhost:8000/docs` — test any payload directly in the browser.

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
├── tests/                      # Automated test suite
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
2. **Multi-language support** — Detect the guest's language and respond accordingly.
3. **Channel delivery** — Send replies back to the source channel via WhatsApp Business API, Booking.com API, etc.
4. **Agent dashboard** — Web UI for pending reviews, escalations, and conversation timelines.
5. **Model evaluation** — Track which drafts agents edit, feed corrections back to improve prompts.

---

## Author

Built by Punya Surana for the Nistula Summer Technology Internship 2026 Technical Assessment.
