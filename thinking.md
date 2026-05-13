# Part 3 — Thinking Question

**Scenario**: It is 3am. A guest at Villa B1 sends a WhatsApp message: *"There is no hot water and we have guests arriving for breakfast in 4 hours. This is unacceptable. I want a refund for tonight."*

---

## Question A — The Immediate Response

**The AI reply at 3am:**

> Hi Vikram, I'm truly sorry about the hot water issue — I completely understand how frustrating this is, especially with guests arriving in the morning. I've immediately alerted our maintenance team to get this fixed. Someone will reach out to you within the next 30 minutes. Regarding tonight's stay, I've flagged this with our team and they'll follow up with you directly. Please call our emergency line if you need anything before then.

**Why this wording**: At 3am, a guest needs three things: acknowledgement that the problem is real, assurance that action is happening *now*, and a specific timeline (30 minutes, not "soon"). The refund is acknowledged but deferred — AI should never commit to financial decisions.

---

## Question B — The System Design

The platform triggers a multi-step incident response:

1. **Classify & escalate**: Tagged `complaint` + `urgent` (3am + "unacceptable" + "refund"). Confidence capped, action set to `escalate`.

2. **Notify immediately**: SMS + push notification to the on-call manager and Villa B1 caretaker.

3. **Create incident ticket**: Auto-generate with severity `high`, tagged to property and reservation. Attach conversation history.

4. **Send the AI reply**: The holding response goes out via WhatsApp immediately — the guest shouldn't wait for a human to wake up.

5. **Start 30-minute countdown**: If no human responds within 30 minutes, escalate further — call the ops manager, notify the founder, send the guest a follow-up: *"Our team is on their way."*

6. **Log everything**: Message, AI response, escalation events, notification timestamps, and resolution — stored for post-incident review.

---

## Question C — The Learning

Three hot water complaints in two months at Villa B1 is a maintenance pattern, not a coincidence.

1. **Detect automatically**: A recurring-issue detector groups complaints by property + category weekly. Three complaints about the same system triggers an alert: *"Villa B1: 3 hot water complaints in 60 days — dates, guests, resolution times attached."*

2. **Preventive maintenance**: Auto-create a task to inspect and service the water heater before the next check-in. Link to complaint history so the technician has context.

3. **Pre-arrival check**: Add "verify hot water in all bathrooms" to Villa B1's mandatory pre-check-in checklist, confirmed by caretaker 2 hours before arrival.

4. **Update AI context**: If another hot water complaint comes in, the AI responds with: *"We're aware this has been an issue and our team has been working on a permanent fix."*

The goal: build a system where the fourth complaint never happens.
