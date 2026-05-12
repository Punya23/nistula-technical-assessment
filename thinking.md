# Part 3 — Thinking Question

**Scenario**: It is 3am. A guest at Villa B1 sends a WhatsApp message: *"There is no hot water and we have guests arriving for breakfast in 4 hours. This is unacceptable. I want a refund for tonight."*

---

## Question A — The Immediate Response

**The AI reply at 3am:**

> Hi Vikram, I'm truly sorry about the hot water issue — I completely understand how frustrating this must be, especially with guests arriving in the morning. I've immediately alerted our maintenance team and your caretaker to get this fixed as soon as possible. Someone will reach out to you within the next 30 minutes with an update. Regarding the refund, I've flagged this with our team and they'll follow up with you directly once the situation is resolved. Please don't hesitate to call our emergency line if you need anything before then.

**Why this wording**: At 3am, a guest needs three things: acknowledgement that the problem is real, assurance that action is being taken *right now*, and a specific timeline (30 minutes, not "soon"). The refund request is acknowledged but deferred to a human — AI should never commit to financial decisions. The tone is empathetic without being defensive.

---

## Question B — The System Design

The platform should trigger a **multi-step incident response**:

1. **Classify & escalate**: The message is tagged `complaint` + `urgent` (3am + words "unacceptable", "refund"). Confidence is capped, action is `escalate`.

2. **Notify immediately**: Push notification + SMS to the on-call operations manager and the Villa B1 caretaker. WhatsApp message to the caretaker with the guest's complaint.

3. **Create an incident ticket**: Auto-generate an incident in the ticketing system with severity `high`, tagged to the property and reservation. Attach the conversation history.

4. **Send the AI reply**: The empathetic holding response goes out immediately via WhatsApp — the guest shouldn't wait for a human to wake up.

5. **Start the 30-minute countdown**: If no human has responded or updated the ticket within 30 minutes, the system escalates further — calls the operations manager, notifies the founder, and sends the guest a follow-up: *"Our team is on their way to resolve this."*

6. **Log everything**: The message, AI response, escalation events, notification delivery timestamps, and eventual resolution are all stored for post-incident review.

---

## Question C — The Learning

Three hot water complaints in two months at Villa B1 is a **maintenance pattern, not a coincidence**.

The system should:

1. **Detect the pattern automatically**: A recurring-issue detector runs weekly, grouping complaints by property + category (plumbing, electrical, cleanliness). Three complaints about the same system triggers an alert to the operations team with a summary: *"Villa B1 has had 3 hot water complaints in 60 days — dates, guests, and resolution times attached."*

2. **Trigger a preventive maintenance order**: Auto-create a maintenance task to inspect and service the water heater at Villa B1 before the next guest checks in. Link it to the complaint history so the technician has full context.

3. **Add a pre-arrival check**: Update the Villa B1 pre-check-in checklist to include "verify hot water in all bathrooms" as a mandatory item the caretaker confirms 2 hours before every check-in.

4. **Feed back into AI context**: Update Villa B1's property context so the AI knows this is a known issue. If a future guest asks about amenities, the AI doesn't oversell — and if another hot water complaint comes in, the AI response includes *"We're aware this has been an issue and our team has already been working on a permanent fix."*

The goal isn't just to fix the heater — it's to build a system where the fourth complaint **never happens**.
