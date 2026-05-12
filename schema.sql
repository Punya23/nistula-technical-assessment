-- ============================================================
-- NISTULA UNIFIED MESSAGING PLATFORM — DATABASE SCHEMA
-- ============================================================
-- PostgreSQL 15+
-- Part 2 of the Nistula Technical Assessment
--
-- Design principles:
--   1. One canonical guest record, regardless of how many channels they use
--   2. All messages (inbound + outbound) in a single table for unified search
--   3. Conversations as logical groupings, not physical separations
--   4. Full AI audit trail — every draft, edit, and send is tracked
--   5. Soft deletes everywhere — hospitality data has legal retention requirements
-- ============================================================


-- ============================================================
-- 1. GUEST PROFILES
-- ============================================================
-- One record per guest, deduplicated across all channels.
-- A guest who messages via WhatsApp and Booking.com is ONE guest.
-- Channel-specific identifiers are stored in guest_channel_identifiers.

CREATE TABLE guests (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name       VARCHAR(200) NOT NULL,
    email           VARCHAR(255),                   -- May be null (WhatsApp-only guests)
    phone           VARCHAR(30),                    -- E.164 format preferred
    preferred_lang  VARCHAR(10) DEFAULT 'en',       -- ISO 639-1 language code
    notes           TEXT,                            -- Internal notes about this guest
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Deduplication: email OR phone must be present
    -- This allows matching across channels
    CONSTRAINT guest_has_contact CHECK (email IS NOT NULL OR phone IS NOT NULL)
);

-- Indexes for fast lookup during deduplication
CREATE UNIQUE INDEX idx_guests_email ON guests (email) WHERE email IS NOT NULL;
CREATE UNIQUE INDEX idx_guests_phone ON guests (phone) WHERE phone IS NOT NULL;
CREATE INDEX idx_guests_name ON guests (full_name);


-- ============================================================
-- 2. GUEST CHANNEL IDENTIFIERS
-- ============================================================
-- Maps channel-specific IDs to canonical guest records.
-- A guest might be "+91-98765-43210" on WhatsApp but "rahul.sharma@gmail.com"
-- on Booking.com — both link to the same guest record.

CREATE TABLE guest_channel_identifiers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guest_id        UUID NOT NULL REFERENCES guests(id) ON DELETE CASCADE,
    channel         VARCHAR(30) NOT NULL,            -- whatsapp, booking_com, airbnb, instagram, direct
    channel_user_id VARCHAR(255) NOT NULL,            -- Channel-specific identifier
    display_name    VARCHAR(200),                     -- Name as shown on that channel
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- A channel user ID should only map to one guest
    CONSTRAINT uq_channel_user UNIQUE (channel, channel_user_id)
);

CREATE INDEX idx_channel_lookup ON guest_channel_identifiers (channel, channel_user_id);


-- ============================================================
-- 3. PROPERTIES
-- ============================================================
-- Property catalog. In production, this would be much richer.
-- Kept minimal here as the focus is on the messaging schema.

CREATE TABLE properties (
    id              VARCHAR(50) PRIMARY KEY,          -- e.g., "villa-b1"
    name            VARCHAR(200) NOT NULL,
    location        VARCHAR(500),
    bedrooms        SMALLINT,
    max_guests      SMALLINT,
    base_rate_inr   INTEGER,                          -- Per night in INR
    check_in_time   TIME,
    check_out_time  TIME,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================
-- 4. RESERVATIONS
-- ============================================================
-- Bookings linking guests to properties for specific dates.
-- One guest can have multiple reservations (repeat guests are common).

CREATE TABLE reservations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_ref     VARCHAR(50) NOT NULL UNIQUE,      -- e.g., "NIS-2024-0891"
    guest_id        UUID NOT NULL REFERENCES guests(id),
    property_id     VARCHAR(50) NOT NULL REFERENCES properties(id),
    check_in_date   DATE NOT NULL,
    check_out_date  DATE NOT NULL,
    num_guests      SMALLINT NOT NULL DEFAULT 1,
    total_amount    INTEGER,                          -- Total in INR
    status          VARCHAR(30) NOT NULL DEFAULT 'confirmed',
                                                      -- confirmed, checked_in, checked_out, cancelled
    source_channel  VARCHAR(30),                      -- Channel where booking originated
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_dates CHECK (check_out_date > check_in_date)
);

CREATE INDEX idx_reservations_guest ON reservations (guest_id);
CREATE INDEX idx_reservations_property ON reservations (property_id);
CREATE INDEX idx_reservations_dates ON reservations (check_in_date, check_out_date);
CREATE INDEX idx_reservations_status ON reservations (status);


-- ============================================================
-- 5. CONVERSATIONS
-- ============================================================
-- A conversation is a logical thread grouping messages between
-- a guest and the team about a specific topic/stay.
--
-- Why a separate table?
-- A guest may have multiple conversations (pre-booking, during stay,
-- post-checkout). Each conversation has its own lifecycle and can
-- be assigned to different agents.

CREATE TABLE conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guest_id        UUID NOT NULL REFERENCES guests(id),
    property_id     VARCHAR(50) REFERENCES properties(id),
    reservation_id  UUID REFERENCES reservations(id), -- Null for pre-booking enquiries
    channel         VARCHAR(30) NOT NULL,              -- Primary channel for this conversation
    status          VARCHAR(30) NOT NULL DEFAULT 'open',
                                                       -- open, waiting_on_guest, resolved, escalated
    assigned_agent  VARCHAR(100),                       -- Agent handling this conversation
    priority        VARCHAR(10) DEFAULT 'normal',       -- low, normal, high, urgent
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ                         -- When the conversation was closed
);

CREATE INDEX idx_conversations_guest ON conversations (guest_id);
CREATE INDEX idx_conversations_status ON conversations (status);
CREATE INDEX idx_conversations_priority ON conversations (priority);


-- ============================================================
-- 6. MESSAGES
-- ============================================================
-- The core table. Every message — inbound from guests, outbound from AI
-- or agents — lives here. Single table design for unified search,
-- analytics, and audit trail.

CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id),
    direction       VARCHAR(10) NOT NULL,              -- 'inbound' or 'outbound'

    -- Content
    message_text    TEXT NOT NULL,
    source_channel  VARCHAR(30) NOT NULL,              -- Channel this message was sent on

    -- Sender info
    sender_type     VARCHAR(20) NOT NULL,               -- 'guest', 'ai', 'agent'
    sender_id       VARCHAR(255),                       -- Guest UUID or agent ID

    -- Classification (for inbound messages)
    query_type      VARCHAR(50),                        -- pre_sales_availability, complaint, etc.

    -- Delivery tracking
    status          VARCHAR(20) NOT NULL DEFAULT 'received',
                                                        -- received, drafted, reviewed, sent, failed
    sent_at         TIMESTAMPTZ,
    delivered_at    TIMESTAMPTZ,
    read_at         TIMESTAMPTZ,

    -- Metadata
    metadata        JSONB DEFAULT '{}',                 -- Channel-specific metadata, attachments, etc.
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation ON messages (conversation_id, created_at);
CREATE INDEX idx_messages_direction ON messages (direction);
CREATE INDEX idx_messages_query_type ON messages (query_type);
CREATE INDEX idx_messages_status ON messages (status);
CREATE INDEX idx_messages_created ON messages (created_at DESC);

-- Full-text search on message content (for searching across all conversations)
CREATE INDEX idx_messages_fts ON messages USING gin(to_tsvector('english', message_text));


-- ============================================================
-- 7. AI RESPONSES
-- ============================================================
-- Tracks every AI-generated draft: which model, what confidence,
-- whether it was edited by a human, and what ultimately got sent.
-- This is the audit trail that answers "what did the AI do?"

CREATE TABLE ai_responses (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id          UUID NOT NULL REFERENCES messages(id),
    inbound_message_id  UUID NOT NULL REFERENCES messages(id),  -- The message this was a reply to

    -- AI generation details
    model_used          VARCHAR(100) NOT NULL,           -- e.g., "claude-sonnet-4-20250514"
    prompt_tokens       INTEGER,                         -- Token usage tracking
    completion_tokens   INTEGER,
    response_time_ms    INTEGER,                         -- Latency tracking

    -- Confidence scoring
    confidence_score    FLOAT NOT NULL,                  -- 0.0 to 1.0
    confidence_breakdown JSONB,                          -- Detailed scoring factors
    query_type          VARCHAR(50) NOT NULL,            -- Classified query type

    -- Human review tracking
    action_taken        VARCHAR(20) NOT NULL,            -- auto_send, agent_review, escalate
    was_edited          BOOLEAN DEFAULT FALSE,           -- Did an agent modify the draft?
    edited_by           VARCHAR(100),                    -- Agent who edited
    original_draft      TEXT,                            -- Original AI text (before edits)
    final_text          TEXT NOT NULL,                   -- What was actually sent

    -- Timestamps
    drafted_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at         TIMESTAMPTZ,
    sent_at             TIMESTAMPTZ
);

CREATE INDEX idx_ai_responses_message ON ai_responses (message_id);
CREATE INDEX idx_ai_responses_confidence ON ai_responses (confidence_score);
CREATE INDEX idx_ai_responses_action ON ai_responses (action_taken);
CREATE INDEX idx_ai_responses_model ON ai_responses (model_used);


-- ============================================================
-- 8. ESCALATION LOG (Bonus)
-- ============================================================
-- Tracks when and why messages were escalated to humans.
-- Useful for identifying AI gaps and training data opportunities.

CREATE TABLE escalation_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id      UUID NOT NULL REFERENCES messages(id),
    conversation_id UUID NOT NULL REFERENCES conversations(id),
    reason          VARCHAR(50) NOT NULL,               -- low_confidence, complaint, ai_error, manual
    escalated_to    VARCHAR(100),                        -- Agent who received the escalation
    resolved        BOOLEAN DEFAULT FALSE,
    resolution_note TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ
);

CREATE INDEX idx_escalations_conversation ON escalation_log (conversation_id);
CREATE INDEX idx_escalations_resolved ON escalation_log (resolved);


-- ============================================================
-- DESIGN DECISIONS
-- ============================================================
--
-- 1. SINGLE MESSAGES TABLE (inbound + outbound)
--    Considered separate tables for inbound vs outbound, but a single
--    table with a `direction` column makes queries simpler, enables
--    unified full-text search, and keeps the conversation timeline
--    in one place. The `sender_type` field distinguishes guest/AI/agent.
--
-- 2. GUEST DEDUPLICATION VIA CHANNEL IDENTIFIERS
--    This was the hardest design decision. A guest on WhatsApp and
--    Booking.com is often the same person, but they have different
--    identifiers. Rather than storing channel-specific IDs directly on
--    the guests table (which would mean nullable columns for each channel),
--    I used a separate `guest_channel_identifiers` table. This is more
--    normalised, handles unlimited channels without schema changes, and
--    makes the dedup logic explicit: match on email/phone first, then
--    link channel identifiers. The trade-off is an extra JOIN for lookups,
--    but this scales better as Nistula adds more channels.
--
-- 3. AI RESPONSES AS A SEPARATE TABLE
--    AI metadata (model, tokens, confidence, edits) doesn't belong on
--    the messages table — it would bloat every row (most messages don't
--    have AI data). A separate table keeps messages lean and gives us
--    a clean audit trail for AI behaviour analysis and model evaluation.
--
-- 4. JSONB FOR METADATA AND CONFIDENCE BREAKDOWN
--    Channel-specific metadata varies widely (WhatsApp has message IDs,
--    Booking.com has reservation numbers, etc.). JSONB handles this without
--    schema changes per channel. Confidence breakdown is also JSONB because
--    the scoring formula may evolve — we don't want to migrate columns
--    every time we add a new confidence factor.
--
-- 5. SOFT STATE TRACKING
--    Messages have a `status` field tracking their lifecycle (received →
--    drafted → reviewed → sent). This enables dashboards showing "pending
--    review" counts and helps identify bottlenecks in the response pipeline.


-- ============================================================
-- HARDEST DESIGN DECISION
-- ============================================================
--
-- The hardest decision was guest deduplication across channels.
--
-- In hospitality, the same guest frequently contacts through multiple
-- channels — they might discover a villa on Instagram, enquire on
-- WhatsApp, and eventually book through Booking.com. Without proper
-- deduplication, this creates three separate "guests" and fragments
-- their conversation history. An agent responding on WhatsApp wouldn't
-- see the Booking.com reservation details.
--
-- I considered three approaches:
-- (a) Store all channel IDs as columns on the guests table — simple but
--     requires schema changes for every new channel.
-- (b) Use a single composite key (email+phone) — works until a guest
--     uses different emails on different platforms.
-- (c) A separate channel identifiers table with email/phone as the
--     dedup bridge — more complex but handles real-world messiness.
--
-- I chose (c) because Nistula is a growing startup that will inevitably
-- add new channels (Google Messages, Telegram, etc.). The extra JOIN
-- cost is negligible compared to the operational cost of duplicated
-- guest records. The `guest_channel_identifiers` table also serves as
-- a natural audit trail of where each guest has contacted from.
