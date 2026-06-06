# Demo Script (1–2 minutes)

Recorded against the seeded scenario so the 3B7 cadence and TIARA output show
convincingly within two minutes. Priya = EMBA career-switcher into climate product.

## Setup (off-camera)
- Service deployed on Cloud Run (`advocate` on `agenticprd`).
- Seeded CSVs loaded. Use a fresh `user_id` so the pipeline starts clean.

## Beat sheet

| Time | On screen | Say |
|---|---|---|
| 0:00–0:15 | Title + one-liner | "81% of hires come from networking, but it's unstructured and people freeze. Advocate runs the 2-Hour Job Search end-to-end — sourcing to follow-up." |
| 0:15–0:35 | Agent returns ranked top-5 | "Priya gives an industry, geography, and function. The Sourcing agent grounds ~40 employers; a pure-code M→P→A ranker returns her top 5 — Helio Grid first." |
| 0:35–0:55 | Drafted email | "She picks Helio Grid. Advocate finds her alum contact Maya, and drafts a connection-first email — under 100 words, no job ask, the ask is a question. A binary eval gate regenerates anything non-compliant. It's a **draft** — nothing is ever sent automatically." |
| 0:55–1:15 | 3B7 cadence | "On send, it schedules 3- and 7-business-day reminders. No reply by day 3? It surfaces the next contact, Carlos, and drafts the next email. It classifies responders Booster/Obligate/Curmudgeon by latency." |
| 1:15–1:35 | TIARA prep | "Priya books the informational. Advocate produces a grounded research brief and five TIARA questions — Trends, Insights, Advice, Resources, Assignments — so she walks in prepared." |
| 1:35–1:50 | Follow-ups + state | "After the call it schedules the thank-you, a 2-week update, and a monthly check-in. Everything persists in Firestore, isolated per user, surviving across sessions." |
| 1:50–2:00 | Buyer + close | "The buyer is the university career center — measured on employment outcomes that drive rankings. Advocate runs, at scale, the method they teach by hand." |

## Live commands (reference)
See `README.md` → "Calling the deployed agent" for the exact `curl` sequence that
produces each beat (ranked top-5 → draft → log_outreach/check_cadence →
prepare_informational → schedule_post_interview_followups).
