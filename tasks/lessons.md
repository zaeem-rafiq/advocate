# Lessons

## 2026-06-06 — git branch-per-slice
- **What went wrong:** After merging slice #8 to main, I started slice #9 work without
  first creating a `slice/9-*` branch, so all of #9 was committed directly to main —
  violating the "branch per slice, never commit to main directly" rule. Only caught it
  when the `git merge slice/9-...` step failed ("not something we can merge").
- **What to do instead:** Immediately after each `merge → main`, create the NEXT slice
  branch before writing any code. Make branch creation the first step of a slice, not an
  afterthought. (No remote here so impact was low, but the habit matters.)

## 2026-06-06 — verify imported doc refinements against the as-built code
- **What went wrong:** When consolidating the v0.1 product PRD into the canonical
  `prd-advocate.md` (an already-built, deployed system), I imported three of v0.1's
  "refinements" as spec without first checking them against the code: responder thresholds
  (v0.1 said Booster ≤1/Obligate 2–5/Curmudgeon >5; as-built is ≤3/>3/silence-past-day-7),
  the ranker tiebreak (wrote alphabetical-name; as-built is stable input order), and the
  send channel (wrote consented-send as if reversible now; as-built ships draft-only with a
  *tested* no-send guardrail). All three silently contradicted the shipped build. Caught
  only when I read `classification.py` / `ranker.py` / DECISIONS.md during the follow-on
  code task — not in the doc pass.
- **What to do instead:** Before writing any imported refinement into a canonical doc for an
  already-built system, grep/read the matching module + test and make the doc state the
  as-built behavior, marking divergent proposals as explicitly "deferred vN". A PRD for a
  shipped system is a contract with the code, not a greenfield wishlist — reconcile to the
  build first, propose changes second. (Generalizes the existing "Compiling ≠ done / trace
  end-to-end" and "grep all call sites before changing a contract" anti-patterns to docs.)
