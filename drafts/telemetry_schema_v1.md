# TELEMETRY SCHEMA v1
# KeepYourContracts.com

## Purpose

Create one clean event language for the revenue organism.

Every visitor, click, inquiry, checkout intent, project creation, follow-up, and conversion should become a structured event.

## Canonical Event Fields

- event_id
- event_type
- occurred_utc
- session_id
- visitor_id
- lead_id
- page_url
- referrer
- utm_source
- utm_medium
- utm_campaign
- user_agent
- timezone
- language
- screen_width
- screen_height
- metadata

## Core Event Types

- session_start
- page_view
- cta_click
- scroll_depth
- inquiry_submit
- stripe_intent
- checkout_started
- checkout_completed
- repeat_visit
- lead_score_update
- ai_followup_trigger
- project_created
- conversion_event

## Lead Score Inputs

- pricing page visit
- repeated visit
- inquiry submit
- Stripe checkout click
- business email
- high dwell time
- multiple product views
- return within 7 days

## Lead Stages

- cold
- warm
- hot
- enterprise

## Next Implementation

1. Add telemetry endpoint.
2. Add JS telemetry client.
3. Store events locally first.
4. Add dashboard view.
5. Add lead scoring.
6. Add autonomous follow-up triggers.
