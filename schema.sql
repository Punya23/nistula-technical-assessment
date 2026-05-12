-- ============================================================
-- NISTULA UNIFIED MESSAGING PLATFORM — DATABASE SCHEMA
-- ============================================================
-- PostgreSQL 15+
-- Part 2 of the Nistula Technical Assessment
--
-- Design principles:
--   1. One canonical guest record, regardless of channel
--   2. All messages in a single table for unified search
--   3. Conversations grouped by guest + reservation
--   4. AI metadata stored directly on messages (no separate table)
--   5. Simple, pragmatic — easy to extend as the platform grows
--
-- Initial design note:
--   I originally separated AI response data into its own table
--   (ai_responses) and built a guest_channel_identifiers table for
--   cross-channel identity resolution. During review, I simplified:
--   - AI fields merged into messages — every message can optionally
--     carry AI metadata without a JOIN. Simpler queries, fewer tables.
--   - Channel identifiers moved to guests table — for this scope,
--     a channel + external_id on the guest record is enough.
--   The separate tables would make sense at scale (multi-model A/B
--   testing, identity graphs), but for a startup MVP they add
--   complexity without immediate value.
-- ============================================================


-- ============================================================
-- 1. GUESTS
-- ============================================================
-- One record per guest, deduplicated across all channels.
-- A guest who messages via WhatsApp and Booking.com is ONE guest,
-- matched by email or phone.

CREATE TABLE guests (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name       VARCHAR(200) NOT NULL,
    email           VARCHAR(255),                    -- May be null (WhatsApp-only guests)
    phone           VARCHAR(30),                     -- E.164 format preferred
    primary_channel VARCHAR(30),                     -- whatsapp, booking_com, airbnb, etc.
    external_channel_id VARCHAR(255),                -- Channel-specific guest identifier
    preferred_lang  VARCHAR(10) DEFAULT 'en',        -- ISO 639-1 language code
    notes           TEXT,                             -- Internal notes about this guest
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- At least one contact method must exist for deduplication
    CONSTRAINT guest_has_contact CHECK (email IS NOT NULL OR phone IS NOT NULL)
);

-- Fast lookup for deduplication
CREATE UNIQUE INDEX idx_guests_email ON guests (email) WHERE email IS NOT NULL;
CREATE UNIQUE INDEX idx_guests_phone ON guests (phone) WHERE phone IS NOT NULL;
CREATE INDEX idx_guests_name ON guests (full_name);


-- ============================================================
-- 2. PROPERTIES
-- ============================================================
-- Property catalog. Kept minimal — in production this would be
-- much richer with amenities, photos, pricing rules, etc.

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
-- 3. RESERVATIONS
-- ============================================================
-- Bookings linking guests to properties for specific dates.
-- One guest can have multiple reservations (repeat guests).

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


-- ============================================================
-- 4. CONVERSATIONS
-- ============================================================
-- A conversation groups messages into a logical thread.
-- One guest can have multiple conversations (pre-booking, during
-- stay, post-checkout). Each can be assigned to a different agent.

CREATE TABLE conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guest_id        UUID NOT NULL REFERENCES guests(id),
    property_id     VARCHAR(50) REFERENCES properties(id),
    reservation_id  UUID REFERENCES reservations(id),  -- Null for pre-booking enquiries
    channel         VARCHAR(30) NOT NULL,               -- Primary channel
    status          VARCHAR(30) NOT NULL DEFAULT 'open',
                                                        -- open, waiting_on_guest, resolved, escalated
    assigned_agent  VARCHAR(100),                        -- Agent handling this conversation
    priority        VARCHAR(10) DEFAULT 'normal',        -- low, normal, high, urgent
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ
);

CREATE INDEX idx_conversations_guest ON conversations (guest_id);
CREATE INDEX idx_conversations_status ON conversations (status);


-- ============================================================
-- 5. MESSAGES
-- ============================================================
-- The core table. Every message — inbound and outbound — lives here.
-- AI metadata is stored directly on the message row rather than in
-- a separate table. This keeps queries simple: one SELECT gives you
-- the message, its classification, the AI draft, and the confidence
-- score without any JOINs.
--
-- Design decision: I initially created a separate ai_responses table
-- to track AI drafts independently. I merged it back because:
-- (a) For this scope, there's one AI draft per message — no versioning needed
-- (b) Fewer tables = simpler queries for the agent dashboard
-- (c) The AI fields are nullable, so non-AI messages carry no overhead

CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id),
    direction       VARCHAR(10) NOT NULL,              -- 'inbound' or 'outbound'

    -- Content
    message_text    TEXT NOT NULL,
    source_channel  VARCHAR(30) NOT NULL,

    -- Sender info
    sender_type     VARCHAR(20) NOT NULL,               -- 'guest', 'ai', 'agent'
    sender_id       VARCHAR(255),                       -- Guest UUID or agent ID

    -- Classification (for inbound messages)
    query_type      VARCHAR(50),                        -- pre_sales_availability, complaint, etc.

    -- AI draft metadata (nullable — only present for AI-generated messages)
    ai_drafted      BOOLEAN DEFAULT FALSE,              -- Was this message drafted by AI?
    ai_model        VARCHAR(100),                       -- e.g., "claude-sonnet-4-20250514"
    confidence_score DECIMAL(3,2),                      -- 0.00 to 1.00
    action_taken    VARCHAR(20),                        -- auto_send, agent_review, escalate
    agent_edited    BOOLEAN DEFAULT FALSE,              -- Did an agent modify the AI draft?
    original_draft  TEXT,                               -- Original AI text before agent edits

    -- Delivery tracking
    status          VARCHAR(20) NOT NULL DEFAULT 'received',
                                                        -- received, drafted, reviewed, sent, failed
    sent_at         TIMESTAMPTZ,
    delivered_at    TIMESTAMPTZ,
    read_at         TIMESTAMPTZ,

    -- Metadata
    metadata        JSONB DEFAULT '{}',                 -- Channel-specific metadata
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation ON messages (conversation_id, created_at);
CREATE INDEX idx_messages_query_type ON messages (query_type);
CREATE INDEX idx_messages_status ON messages (status);
CREATE INDEX idx_messages_created ON messages (created_at DESC);
CREATE INDEX idx_messages_ai_drafted ON messages (ai_drafted) WHERE ai_drafted = TRUE;

-- Full-text search on message content
CREATE INDEX idx_messages_fts ON messages USING gin(to_tsvector('english', message_text));


-- ============================================================
-- DESIGN DECISIONS
-- ============================================================
--
-- 1. SINGLE MESSAGES TABLE (inbound + outbound)
--    A single table with a `direction` column keeps the conversation
--    timeline in one place and enables unified full-text search.
--    The `sender_type` field distinguishes guest/AI/agent messages.
--
-- 2. AI FIELDS ON MESSAGES, NOT A SEPARATE TABLE
--    I initially created a separate ai_responses table with columns
--    for token usage, response time, model versioning, and draft history.
--    I simplified because: at this stage, there's one AI draft per
--    inbound message. A separate table adds a JOIN to every dashboard
--    query without immediate benefit. The AI columns are nullable,
--    so non-AI messages carry zero overhead. When Nistula needs
--    multi-model A/B testing or draft versioning, a separate table
--    makes sense — but that's a future problem.
--
-- 3. GUEST DEDUPLICATION VIA EMAIL/PHONE
--    Guests are matched across channels using email or phone as unique
--    keys. I considered a separate guest_channel_identifiers table for
--    channel-specific IDs (WhatsApp number, Booking.com guest ID, etc.)
--    but simplified to a single primary_channel + external_channel_id
--    on the guests table. This handles the common case (one guest,
--    one primary channel) without the complexity of an identity
--    resolution system. If a guest contacts from a second channel,
--    we match on email/phone and update the record.
--
-- 4. JSONB FOR METADATA
--    Channel-specific data varies widely (WhatsApp has message IDs,
--    Booking.com has reservation numbers). JSONB handles this without
--    schema changes per channel.
--
-- 5. CONVERSATIONS AS A GROUPING LAYER
--    A guest may have multiple conversations about the same property
--    (pre-booking, during stay, post-checkout). The conversation
--    abstraction keeps the timeline clean and lets us assign different
--    agents to different threads.


-- ============================================================
-- HARDEST DESIGN DECISION
-- ============================================================
--
-- The hardest decision was where to store AI-generated draft metadata.
--
-- Option A: A separate ai_responses table with full audit trail
-- (model, tokens, latency, confidence breakdown, draft history).
-- This is architecturally "correct" and supports future features
-- like model comparison and A/B testing.
--
-- Option B: AI fields directly on the messages table as nullable
-- columns. Simpler queries, fewer JOINs, but mixes concerns.
--
-- I started with Option A — it felt more professional. But during
-- implementation I realised that for an MVP, every agent dashboard
-- query would need a JOIN just to show the confidence score next to
-- the message. That's unnecessary complexity when there's exactly
-- one AI draft per inbound message.
--
-- I chose Option B because Nistula is a startup. The schema should
-- be as simple as possible while still capturing everything needed
-- for operations (was this AI-drafted? was it edited? what was the
-- confidence?). If the platform grows to need draft versioning or
-- multi-model evaluation, migrating to a separate table is a
-- straightforward ALTER + INSERT...SELECT — not a rewrite.
--
-- The lesson: optimise for the queries you'll run today, not the
-- features you might build next year.
