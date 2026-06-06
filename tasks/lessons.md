# Lessons

## 2026-06-06 — git branch-per-slice
- **What went wrong:** After merging slice #8 to main, I started slice #9 work without
  first creating a `slice/9-*` branch, so all of #9 was committed directly to main —
  violating the "branch per slice, never commit to main directly" rule. Only caught it
  when the `git merge slice/9-...` step failed ("not something we can merge").
- **What to do instead:** Immediately after each `merge → main`, create the NEXT slice
  branch before writing any code. Make branch creation the first step of a slice, not an
  afterthought. (No remote here so impact was low, but the habit matters.)
