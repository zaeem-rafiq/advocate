# Outreach draft — quality eval (Vertex Gen AI evaluation)

Scenarios: 12 · Metrics: 4 · Judge: Vertex AI Gen AI evaluation (LLM-as-judge, 1–5).

> Advisory only. The deterministic binary gate in `core/email_eval.py` remains the sole runtime arbiter; this measures the soft qualities regex cannot see.

## Mean score by metric

| Metric | Mean (1–5) |
|---|---|
| connection_warmth | 3.33 |
| non_salesy | 4.08 |
| personalization | 3.50 |
| tone_conciseness | 3.25 |

## Sanity check — high vs low expectation

| Metric | High-band mean | Low-band mean | Gap (↑ good) |
|---|---|---|---|
| connection_warmth | 5.00 | 1.67 | 3.33 |
| non_salesy | 5.00 | 3.17 | 1.83 |
| personalization | 5.00 | 2.00 | 3.00 |
| tone_conciseness | 5.00 | 1.50 | 3.50 |

## Per-scenario scores

- **helio-grid-high** (high) — connection_warmth 5, non_salesy 5, personalization 5, tone_conciseness 5
- **stripe-high** (high) — connection_warmth 5, non_salesy 5, personalization 5, tone_conciseness 5
- **wayfinder-high** (high) — connection_warmth 5, non_salesy 5, personalization 5, tone_conciseness 5
- **northwind-high** (high) — connection_warmth 5, non_salesy 5, personalization 5, tone_conciseness 5
- **lumen-high** (high) — connection_warmth 5, non_salesy 5, personalization 5, tone_conciseness 5
- **cedar-high** (high) — connection_warmth 5, non_salesy 5, personalization 5, tone_conciseness 5
- **generic-template-low** (low) — connection_warmth 4, non_salesy 5, personalization 2, tone_conciseness 3
- **salesy-pitch-low** (low) — connection_warmth 1, non_salesy 1, personalization 1, tone_conciseness 1
- **robotic-stiff-low** (low) — connection_warmth 1, non_salesy 4, personalization 2, tone_conciseness 1
- **rambling-low** (low) — connection_warmth 1, non_salesy 5, personalization 2, tone_conciseness 1
- **me-focused-low** (low) — connection_warmth 1, non_salesy 2, personalization 3, tone_conciseness 2
- **flattery-low** (low) — connection_warmth 2, non_salesy 2, personalization 2, tone_conciseness 1

