# Data Sources & ToS Compliance

Advocate is built to respect third-party terms of service. This document records every
data source and why it is permitted — a hard requirement of the contest rules
(scraping LinkedIn/Indeed is a disqualification risk).

## Sources used

| Purpose | Source | Why it's permitted |
|---|---|---|
| **Sourcing** target organizations | Google Search grounding (Gemini on Vertex AI) | First-party Google grounding API. No scraping of job boards or social networks. |
| **Affiliation** (alumni) | User-provided CSV / connected export (`demo_alumni_contacts.csv`) | Data the user already has rights to (their school's alumni export / their own contacts). The same loader serves a real user export. Never scraped. |
| **Posting signal** | Demo stand-in (`demo_posting_score`) for the seeded run; Google Search grounding for the live path | No re-aggregation of LinkedIn/Indeed data. Adzuna API is an optional, terms-permitted extension. |
| **Informational research (TIARA)** | Google Search grounding | First-party grounding; brief is grounded in real results, never fabricated. |
| **State** | Firestore (the user's own pipeline, per-user isolated) | First-party storage. No PII in application logs. |

## Forbidden (enforced)

`advocate/core/guardrails.py` blocks these domains from any fetch path, and a test
(`tests/test_guardrails.py`) asserts the codebase contains **no** autonomous email-send
capability and **no** scraping of:

- `linkedin.com`, `indeed.com`, `glassdoor.com`, `ziprecruiter.com`

## Email

Email is **draft-only**. There is no SMTP/Gmail-send code anywhere in the repository —
the draft is generated, validated by the binary eval suite, and surfaced for a human to
approve and send manually. This is verified structurally by `test_guardrails.py`.
