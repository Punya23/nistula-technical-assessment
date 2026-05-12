# Nistula Guest Message Handler

AI-powered unified guest messaging backend for [Nistula](https://nistula.life) — a luxury villa and apartment rental company based in Assagao, Goa.

Built with FastAPI, Claude API integration, rule-based query classification, and a PostgreSQL schema designed for multi-channel hospitality operations.

---

## The Problem

Nistula manages luxury villas across multiple booking platforms — WhatsApp, Booking.com, Airbnb, Instagram, and direct enquiries. Each channel brings its own message format, its own quirks, and its own urgency.

A guest asking "Is the villa available?" on WhatsApp at 2pm is a sales opportunity. A guest writing "The AC is not working. I want a refund." at 3am is a fire drill.

The challenge: **build a system that understands the difference, drafts intelligent responses, and knows when to let AI handle it vs. when to wake up a human.**

That's what this project does.

---

## How It Works

```
Guest sends message (WhatsApp / Booking.com / Airbnb / Instagram / Direct)
        │
        ▼
┌───────────────┐
│   Validate    │  Pydantic checks source, fields, types
│   Payload     │  → 422 if invalid
└───────┬───────┘
        │
        ▼
┌───────────────┐
│  Normalise    │  Strip channel artifacts, generate UUID
│  Message      │  → One unified schema regardless of source
└───────┬───────┘
        │
        ▼
┌───────────────┐
│  Classify     │  Rule-based keyword matching
│  Query Type   │  → availability, pricing, checkin, complaint, etc.
└───────┬───────┘
        │
        ▼
┌───────────────┐
│  Draft Reply  │  Claude API with property context
│  (Claude AI)  │  → Fallback reply if API is down
└───────┬───────┘
        │
        ▼
┌───────────────┐
│  Score        │  Additive confidence model
│  Confidence   │  → auto_send / agent_review / escalate
└───────┬───────┘
        │
        ▼
┌───────────────┐
│   Return      │  message_id, drafted_reply, score, action
│   Response    │  + full breakdown of why
└───────────────┘
```

---

## The Journey — What I Built, Broke, and Rebuilt

Building this wasn't a straight line. Here's what actually happened.

### 1. The Schema Problem

My first database schema had 7 tables — separate `ai_responses` for AI draft history, `guest_channel_identifiers` for cross-channel identity resolution, an `escalation_log` for tracking handoffs.

It was architecturally "correct." But when I started writing queries for the agent dashboard, every single one needed 3-4 JOINs just to show a message with its confidence score. For a startup processing maybe 50 messages a day, that's over-engineering.

**What I did:** Merged AI fields directly into the `messages` table. Flattened guest identifiers into the `guests` table. Went from 7 tables to 5. The queries got simpler, the schema got readable, and nothing was lost — we can always split tables later when scale demands it.

### 2. The Confidence Score Dilemma

First attempt: a 4-factor weighted average.

```
confidence = (classification × 0.30) + (context_coverage × 0.30)
           + (sentiment_clarity × 0.20) + (response_specificity × 0.20)
```

It worked numerically. But when I tested it and got a score of 0.73, I couldn't explain *why* it was 0.73 without tracing through four weighted calculations. If I can't explain it, an operations manager at 3am definitely can't.

**What I did:** Replaced it with an additive model. Start at 0.50, add or subtract based on clear rules:

```
Start: 0.50 (neutral)

+ 0.20  if classifier found a clear keyword match
+ 0.10  if booking reference is present
+ 0.15  if property context contains the answer
+ 0.10  if AI returned a substantive reply (>50 chars)
- 0.10  if message contains multiple questions
cap 0.55 if complaint (always needs human)

→ Clamp to [0.0, 1.0]
```

Now every score is explainable. "This scored 0.85 because: clear keyword match (+0.20), booking ref present (+0.10), context has the answer (+0.15), and the AI gave a solid reply (+0.10). Minus 0.10 because there were 2 questions."

An agent can read that at 3am and make a decision.

### 3. The "What If Claude Goes Down?" Problem

The biggest risk in any AI-powered system: the AI is an external dependency. Claude API could timeout, rate-limit, or go down entirely. A guest should never send a message and get... nothing.

**What I did:** Every query type has a handwritten fallback reply. If Claude is unavailable, the guest gets a polite, specific response like:

> "Hi Rahul, thank you for your interest! Let me check the availability details for you — our team will get back to you shortly with confirmed dates and rates."

Not perfect. But the guest knows they were heard, and the message is flagged for human follow-up. The system never goes silent.

---

## Action Thresholds

| Score | Action | What Happens |
|-------|--------|-------------|
| > 0.85 | `auto_send` | Reply sent without human review |
| 0.60 – 0.85 | `agent_review` | Reply shown to agent for approval |
| < 0.60 | `escalate` | Routed to human, AI draft attached |
| Any complaint | `escalate` | Always human — regardless of score |

Complaints are hard-coded to escalate because no AI should auto-send "sorry about that" when a guest is demanding a refund at 3am. That requires human empathy and authority.

---

## Quick Start

```bash
# Clone
git clone https://github.com/Punya23/nistula-technical-assessment.git
cd nistula-technical-assessment

# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env

# Run
uvicorn app.main:app --reload

# Test
open http://localhost:8000/docs
```

### Docker (Optional)

```bash
docker build -t nistula-handler .
docker run -p 8000:8000 --env-file .env nistula-handler
```

Why Docker? A reviewer can spin up the project in one command without worrying about Python versions, virtualenvs, or dependency conflicts. It also mirrors how this would actually deploy — containerised behind a load balancer, scaling horizontally as message volume grows.

---

## API Reference

### `POST /webhook/message`

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

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `source` | string | Yes | `whatsapp`, `booking_com`, `airbnb`, `instagram`, `direct` |
| `guest_name` | string | Yes | Guest's display name |
| `message` | string | Yes | Raw message text (max 5000 chars) |
| `timestamp` | string | Yes | ISO 8601 |
| `booking_ref` | string | No | Booking reference (boosts confidence) |
| `property_id` | string | No | Defaults to `villa-b1` |

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

Returns service status, model config, and API key status.

### `GET /docs`

Interactive Swagger UI — test payloads directly in the browser.

---

## Testing — What We Covered and What We Didn't

### What's tested (41 tests passing)

```bash
pytest tests/ -v
```

- **Classification accuracy** — All 6 query types correctly identified from keyword patterns
- **Confidence scoring** — Base score, each adjustment rule, complaint capping, multi-question penalty
- **Normalisation** — UUID generation, Booking.com prefix stripping, whitespace handling
- **Webhook integration** — Full pipeline from payload to response
- **Validation** — Missing fields → 422, invalid channels → 422, empty messages → 422
- **Edge cases** — Optional fields missing, boundary thresholds (0.85, 0.60)

### What's NOT tested (honest gaps)

- **Real Claude API responses** — Tests use fallback replies to avoid API calls in CI. In production, you'd want integration tests that hit the actual API with a test key.
- **Concurrent load** — Haven't load-tested with 100+ simultaneous messages. FastAPI handles async well, but the Claude API has rate limits that would need queuing.
- **Multi-language messages** — A guest writing in Hindi or German would hit `general_enquiry` because keywords are English-only. Real system needs language detection.
- **Adversarial inputs** — No testing for prompt injection, XSS in messages, or intentionally malformed payloads beyond Pydantic validation.

These aren't bugs — they're scope decisions. For an MVP assessment, the 41 tests prove the pipeline works. For production, they'd be the first items on the backlog.

### Manual Testing

```bash
chmod +x examples/sample_requests.sh
./examples/sample_requests.sh
```

Runs 7 scenarios covering all channels and query types.

---

## Design Decisions

| Decision | What I chose | What I considered | Why |
|----------|-------------|-------------------|-----|
| **Framework** | FastAPI | Flask, Django | Auto Swagger docs, Pydantic validation, native async for Claude API calls |
| **Classification** | Rule-based keywords | Claude for every message | Keywords handle ~80% of messages free and instant. Don't burn API credits when "Is the villa available?" is an obvious match |
| **Confidence** | Additive rules | Weighted average | Debuggable at 3am. Every adjustment maps to a plain-English reason |
| **AI failover** | Per-type fallback replies | Generic "we'll get back to you" | A complaint fallback should sound different from an availability fallback |
| **Schema** | AI fields on messages table | Separate ai_responses table | One draft per message at MVP. Fewer JOINs, simpler dashboard queries |
| **Docker** | Included | Not required for assessment | One-command setup for reviewers. Mirrors real deployment |

---

## Error Handling

| Scenario | HTTP | What happens |
|----------|------|-------------|
| Missing required fields | 422 | Pydantic validation error with field details |
| Invalid source channel | 422 | Lists valid channels in error |
| Claude API timeout | 200 | Fallback reply returned, flagged as fallback |
| Claude API error | 200 | Fallback reply, error logged |
| Unexpected exception | 500 | Error logged with traceback |

Key design choice: Claude failures return 200 with a fallback reply, not 500. The guest doesn't care that our AI broke — they care that they got a response. The `confidence_breakdown` will show `"fallback": true` so the ops team knows.

---

## Project Structure

```
├── app/
│   ├── main.py                 # FastAPI app, webhook endpoint, pipeline
│   ├── config.py               # Pydantic settings from .env
│   ├── models/
│   │   ├── webhook.py          # Inbound payload validation
│   │   ├── unified.py          # Normalised message schema
│   │   └── response.py         # API response model
│   ├── services/
│   │   ├── normalizer.py       # Channel payloads → unified format
│   │   ├── classifier.py       # Keyword-based query classification
│   │   ├── ai_drafter.py       # Claude API integration + fallbacks
│   │   └── confidence.py       # Additive confidence scoring
│   └── data/
│       └── property_context.py # Villa B1 mock data
├── tests/                      # 41 automated tests (pytest)
├── examples/                   # curl test scripts
├── schema.sql                  # PostgreSQL schema (Part 2)
├── thinking.md                 # Written response (Part 3)
├── Dockerfile                  # Container deployment
├── .env.example                # Environment template
└── requirements.txt            # Pinned dependencies
```

---

## What I'd Build Next

If this were going into production at Nistula:

1. **Conversation memory** — Right now each message is stateless. Store conversation history so the AI knows "this guest asked about pricing yesterday, now they're asking about availability — they're close to booking."

2. **Channel delivery** — Actually send replies back via WhatsApp Business API, Booking.com messaging API, Airbnb API. Right now we draft the reply but don't deliver it.

3. **Agent dashboard** — Web UI showing pending reviews, escalations, conversation timelines. The confidence breakdown is already structured for this — it just needs a frontend.

4. **Language detection** — Run message through a language detector before classification. Respond in the guest's language. Huge for Goa where guests are international.

5. **Prompt feedback loop** — Track which AI drafts agents edit vs. send as-is. Use the edits to improve prompts over time. If agents keep changing the pricing format, the prompt should learn that.

6. **Rate-limited queue** — Claude API has rate limits. At scale, queue messages through Redis/Celery instead of hitting the API synchronously per request.

---

## About Nistula

[Nistula](https://nistula.life) (निस्तुला — "incomparable") is a hospitality startup in Assagao, North Goa, built by a group of startup founders and entrepreneurs who moved to Goa post-COVID looking for a different way to live and work.

They run luxury private pool villas and apartments that combine the privacy of a home with five-star concierge services — in-house chefs, airport transfers, curated experiences. Guests book through WhatsApp, Booking.com, Airbnb, Instagram, and direct enquiries.

This assessment builds the backend that would power their guest communication — understanding what each guest needs, drafting intelligent replies, and knowing when AI can handle it vs. when a human needs to step in.

---

## Author

Built by **Punya Surana** for the Nistula Summer Technology Internship 2026 Technical Assessment.
