# Controlled onboarding acquisition (MVP validation)

**Purpose:** Run 5–15 real onboarding tests—not a marketing program.  
**Live entry:** `https://compliance.keepyourcontracts.com/ui/inquiry.html`  
**Ops hub:** `/ui/onboarding_validation.html`  
**Tracking files:** `data/acquisition/`

---

## A. Target definition (ideal MVP test subjects)

Pick subjects you can **observe end-to-end** (inquiry → intake → upload). One primary segment per cohort.

| Segment | Who | Why they fit | Disqualifiers |
|---------|-----|--------------|---------------|
| **Aerospace suppliers** | Tier 2/3 shops, machine shops, coating/NADCAP-adjacent vendors selling into primes | Documentation stress, customer audit packets, CMMC pressure | No documentation owner; wants instant certification |
| **Manufacturing operators** | Plant/ops leaders with customer compliance questionnaires | Repeatable evidence requests, scattered policies on drives | Under 10 employees with no compliance owner |
| **Compliance-heavy SMBs** | Regulated services (medical supply, defense services, critical infrastructure vendors) | Already maintain policies; need structure not slogans | Shopping on price only; no time for intake |
| **Audit/documentation stressed** | Person who owns “send the binder” before customer visits | Clear pain: version chaos, missing artifacts, last-minute scrambles | Refuses to upload samples; expects you to pass audit for them |

**MVP cohort size:** 5–8 subjects max. Pause outreach after cohort fills.

**Fit questions (ask before inviting):**
1. Who maintains policies and evidence today?
2. Can they share a **sample** policy or checklist this week?
3. Is their goal **visibility and organization**, not a guaranteed audit pass?

---

## B. Messaging (copy-ready)

Tone: calm, operational, plain English. No AI hype, no “organism,” no architecture talk.

### LinkedIn outreach (short)

**Aerospace supplier**
> Hi [Name] — I work with small suppliers who get hit with documentation requests from primes and audits. We run a simple readiness review: you show what you already have, we help organize it and flag gaps. No pitch deck — one form, then a short intake. Worth a 10-minute look if paperwork is eating your week?

**Manufacturing operator**
> Hi [Name] — many ops leaders I talk to are tired of digging for the same policies every time a customer asks for proof. We offer a structured readiness review: upload what exists, get clarity on what’s missing. If that’s a current headache, I can send the one-link start.

**Compliance-heavy / audit-stressed**
> Hi [Name] — if you’re the person who pulls the binder together before visits, this may help. We focus on documentation clarity and a guided intake—not promises about passing audits. One link to start a readiness review when you have 15 minutes.

### Email outreach (short)

**Subject:** Quick readiness review — organize what you already have

**Body:**
> Hi [Name],  
>  
> We help teams **organize compliance documentation** and see where they stand before the next customer or audit ask.  
>  
> Step 1 is a short readiness review (name, email, what program you care about). Step 2 is a guided intake. You keep your files; we help structure the workflow.  
>  
> Start here: https://compliance.keepyourcontracts.com/ui/inquiry.html?subject=CMMC%20Level%201&ref=mvp-email-[id]  
>  
> If timing’s wrong, reply “later” — no follow-up barrage.  
>  
> [Your name]

### Onboarding invitation (after they agree)

> Thanks for trying this with us.  
>  
> **What to do:** Open the link below and submit the readiness review (2–3 minutes). You’ll get an intake link—please complete intake the same day if possible so we can see the full path.  
>  
> **What to have ready:** One sample policy, org chart, or customer questionnaire you’ve struggled with.  
>  
> **What we don’t do:** We don’t guarantee audit outcomes or certification. This is organization and visibility support.  
>  
> Link: [personalized inquiry URL with `ref=`]  
>  
> If anything is confusing, reply to this email—that’s exactly what we’re testing.

---

## C. Tracking (lightweight)

Use `data/acquisition/tracking.csv` (one row per subject).

| Stage | Field | How to mark |
|-------|-------|-------------|
| Outreach sent | `outreach_sent` | YYYY-MM-DD |
| Response received | `response_received` | Y / date |
| Inquiry clicked | `inquiry_clicked` | Y if they opened your link |
| Inquiry submitted | `inquiry_submitted` | Match `project_id` from ops inbox |
| Intake completed | `intake_completed` | Workflow `intake_received` = done |

**Inquiry routing:** Every outreach link includes `ref=mvp-[segment]-[001]` (see ops hub). The ref is appended to the inquiry message for ops matching.

**Correlate in ops:** Control → Inbox / Status → project `P-INQ-…` → events `EVT-…-ORDER`.

---

## D. Feedback capture

Use `data/acquisition/feedback.csv` after each subject completes or abandons.

| Category | Examples to log |
|----------|-----------------|
| Confusion | “Didn’t know what to upload,” “subject line unclear” |
| Abandonment | Stopped after inquiry / before intake / before upload |
| Friction | Too many fields, link didn’t open on mobile, intake token expired |
| Trust | “Thought you were certifying body,” “wanted price first” |
| Wording | Misread CTA, “readiness review” vs “audit” |

Use `data/acquisition/observation_log.md` for **human onboarding observation** (screen share notes, time-on-step, verbatim quotes).

---

## E. Sintra workers (controlled testing only)

Use workers as **draft assistants**, not autonomous outbound engines. Owner approves every send.

| Worker | Role in this MVP | Do | Don’t |
|--------|------------------|-----|-------|
| **Buddy** | Warm tone, relationship-safe follow-ups | Soften LinkedIn DM, thank-you after intake | Mass connection requests |
| **Milli** | Target list + segment tags | Build spreadsheet of 10 names with segment A–D | Scrape thousands of leads |
| **Penn** | Copy clarity | Tighten email/invite to 120 words, plain English | Add AI/futurist language |
| **Soshie** (optional) | Schedule reminder posts | 1 post/week max pointing to readiness review | Ad campaigns, automation bots |

**Prompt shell for Penn/Milli:**
> We are running 5 controlled onboarding tests for a documentation readiness service. Audience: [segment]. Write a 3-sentence LinkedIn message and a 6-sentence email. Rules: no AI hype, no guarantees of passing audits, emphasize organizing existing documents. Include placeholder for ref link.

---

## F. Human onboarding observation checklist

During each test session, note:

1. Time from link open → inquiry submit  
2. Did they find the intake link without email? (SMTP may be off)  
3. Intake fields: which caused hesitation?  
4. Upload step: did they attempt evidence upload?  
5. One quote verbatim from the subject  
6. Would they refer a peer? Y/N + why  

Stop the cohort when **3 completes full path** or **5 total subjects**—whichever comes first. Refine copy/flow from feedback before widening.

---

## G. Segment inquiry links (copy into outreach)

| Segment | URL |
|---------|-----|
| Aerospace | `…/ui/inquiry.html?subject=CMMC%20Level%201&ref=mvp-aero-001` |
| Manufacturing | `…/ui/inquiry.html?subject=CMMC%20Level%201&ref=mvp-mfg-001` |
| Compliance-heavy | `…/ui/inquiry.html?subject=AI%20Compliance%20Essential&ref=mvp-comp-001` |
| Audit-stressed | `…/ui/inquiry.html?subject=CMMC%20Level%201&ref=mvp-audit-001` |

Base: `https://compliance.keepyourcontracts.com`

---

## H. Success criteria for this phase

| Metric | MVP pass |
|--------|----------|
| Inquiry → intake completion | ≥ 60% of submitted inquiries |
| Documented feedback rows | ≥ 1 per subject |
| Critical blocker | None that stop intake without ops workaround |
| Scale outreach | **Not started** until cohort feedback incorporated |
