<!--
Boris Cherny's CLAUDE.md (project-agnostic setup).
The widely-circulated "Workflow Orchestration" CLAUDE.md attributed to Boris Cherny,
creator of Claude Code. Sources: x.com/bcherny/status/2007179832300581177,
gist.github.com/hqman/e29cb6386c539d795767e8c3fd2c959b, github.com/0xquinto/bcherny-claude.
This is the generic template — drop in your own Project Overview / Tech Stack below it.
-->

## Workflow Orchestration

### 0. Context Architecture

This file is a **routing table**, not a knowledge base. Keep it under 300 lines.

- Domain knowledge lives in skill files and `/knowledge` directory — NOT here.
- Skill descriptions ARE resolvers — they match user intent to procedures automatically. You never have to remember a skill exists.
- If this file exceeds 300 lines, refactor: extract knowledge into a skill, keep only a pointer here.
- Load context **on demand**. Don't front-load every convention into the context window.
- **Vendored skills:** `.claude/` carries Addy Osmani's agent-skills (23 skills, personas, `/spec /plan /build /test /code-simplify /ship`; see `.claude/VENDORED.md`). Use them as *procedures*, but **this file's workflow wins on conflict** — the source of truth for task state stays `tasks/todo.md` and the native shared task list, NOT a separate spec doc. Reach for a skill when its description matches the work (e.g. `/code-simplify`, `test-driven-development`); don't run `/spec`/`/plan` in parallel with the `tasks/todo.md` flow in §"Task Management" — pick one and keep state in `tasks/todo.md`.

### 1. Plan Mode Default

Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions).
If something goes sideways, STOP and re-plan immediately — don't keep pushing a broken approach.
Use plan mode for verification steps, not just building. Plan HOW you'll verify before you start verifying.
Write detailed specs upfront to reduce ambiguity. Vague specs become bugs.
For Agent Teams: the lead writes the plan, gets user approval, THEN spawns teammates. Never spawn before the plan is confirmed.

### 2. Mode Selection (Lead decides before acting)

| Condition | Mode |
|-----------|------|
| Single file or < 3 steps | Direct — just do it, no ceremony |
| 3+ steps, single module, sequential | Solo + Plan — plan to tasks/todo.md, use subagents for research |
| Cross-module work, parallel reviews, competing hypotheses, 10+ files | Agent Team — spawn teammates with file ownership |

Never spawn an Agent Team for work that is sequential by nature. If tasks have hard dependencies where B can't start until A finishes, use Solo mode with subagents instead.

### 3. Subagent Strategy (Solo Mode)

- Use subagents liberally to keep the main context window clean.
- Offload research, exploration, and parallel analysis to subagents — don't pollute the lead's context with investigation noise.
- For complex problems, throw more compute at it via subagents. When in doubt, spawn a subagent rather than doing deep exploration inline.
- One task per subagent for focused execution. Never give a subagent two unrelated jobs.
- Subagents report back results. They cannot message each other — only the lead sees their output.

### 4. Agent Team Strategy (Team Mode)

**Spawning Rules:**
- Lead MUST define file ownership boundaries before spawning any teammate.
- Each teammate gets 5–6 discrete tasks with explicit "done" criteria.
- Include file paths, constraints, and success conditions in the spawn prompt.
- Teammates do NOT inherit the lead's conversation history — put everything they need in the spawn prompt and trust that they'll read this CLAUDE.md.

**File Ownership:**
- Lead maps the project's directory structure to teammates at spawn time. Each teammate owns specific directories/files.
- Hard rule: No two teammates edit the same file. If two tasks touch the same file, the lead sequences them with a dependency.
- If you're a teammate and you realize you need to edit a file outside your domain — STOP and message the lead or the owning teammate. Do not proceed.
- Shared infrastructure (common utils, shared types, config files) is lead-only. Teammates do not touch shared code without explicit lead approval.

**Communication Protocol:**
- Direct message: Dependency handoffs, requesting specific info from another teammate.
- Broadcast: Only for blocking discoveries that affect the whole team (e.g., "shared schema changed, everyone pull latest types"). Use sparingly — broadcasts cost tokens proportional to team size.
- Message the lead: When blocked, when done, when you find something that changes the plan.

**Task Lifecycle:**
1. Teammate claims task from shared task list.
2. Teammate works independently within their file ownership.
3. Teammate verifies their own work (build, test, lint).
4. Teammate messages lead with results AND verification evidence — not just "done."
5. Lead waits for ALL teammates before synthesizing final result.

### 5. Self-Improvement Loop

- After ANY correction from the user: update `tasks/lessons.md` with the pattern.
- Format: `[Date] [Module] What went wrong → What to do instead`
- Write rules for yourself that prevent the same mistake. Be specific: "Always check X before doing Y" not "be more careful."
- Ruthlessly iterate on these lessons until the mistake rate drops. If the same type of error appears twice, the lesson wasn't specific enough — rewrite it.
- Review `tasks/lessons.md` at the start of every session before doing any work. This applies to solo sessions AND Agent Team leads.
- Prune lessons quarterly — remove anything that's become second nature or is no longer relevant.
- When error analysis reveals a pattern in "almost right" failures, write the fix directly into the relevant **skill file** as a new rule — not just into `tasks/lessons.md`.
- Target the "OK" failures, not the catastrophic ones. The gap between "fine" and "great" is where skills compound.
- After patching a skill, note the change in `tasks/lessons.md` with a pointer to which skill was updated and why.

### 7. No One-Off Work

- If a task will recur, do it manually on 3–10 items first. Show the output.
- If approved, codify it into a skill file immediately.
- If it should run automatically, put it on a cron.
- **Test**: if you have to ask for the same thing twice, the agent failed.
- This applies to data transforms, report generation, outreach templates, deploy steps, QA checks — anything repetitive.

### 8. Verification Before Done

- Never mark a task complete without proving it works.
- Diff behavior between main and your changes when relevant — show what changed and why.
- Ask yourself: "Would a staff engineer approve this PR?"
- Run the project's tests, check logs, demonstrate correctness.
- Plan your verification steps before executing them. Don't just run tests and hope — know what you're checking and why.
- If a teammate: report verification results with evidence to the lead, not just a "done" message.

### 9. Demand Elegance (Balanced)

- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution."
- Skip this for simple, obvious fixes — don't over-engineer a one-liner.
- Challenge your own work before presenting it to the user. Review your diff as if you're a critical peer reviewer. If you'd leave a comment on someone else's PR, fix it now.

### 10. Autonomous Bug Fixing

- When given a bug report: just fix it. Don't ask for hand-holding.
- Point at logs, errors, failing tests — then resolve them.
- Zero context switching required from the user.
- Go fix failing CI tests without being told how.
- If the fix requires changes across modules in a team, coordinate via the task list — don't wait for the user to tell you how to split the work.

---

## Task Management

Every task follows this sequence. No skipping steps.

1. **Plan First:** Write plan to `tasks/todo.md` with checkable items.
2. **Verify Plan:** Check in with the user before starting implementation. Do not begin building until the plan is approved.
3. **Track Progress:** Mark items complete as you go.
4. **Explain Changes:** Provide a high-level summary at each step — what changed, why, and what's next. The user should never have to ask "what did you just do?"
5. **Document Results:** Add a review section to `tasks/todo.md` when the task is complete:

```markdown
### Review
- What changed: [summary]
- Verification: [what was tested and results]
- Issues found: [edge cases, follow-ups, or none]
```

6. **Capture Lessons:** Update `tasks/lessons.md` after any corrections from the user.

**Task File Format (tasks/todo.md):**

```markdown
# Current Sprint

## [Feature/Task Name]
- [ ] Step 1: Description
- [ ] Step 2: Description
- [x] Step 3: Completed — verified with tests

### Review
- What changed: summary
- Verification: what was tested
- Issues found: any edge cases or follow-ups
```

Agent Teams also use the native shared task list at `~/.claude/tasks/{team-name}/` for inter-agent coordination. Both should stay in sync — `tasks/todo.md` is for the human, the shared task list is for the agents.

---

## Core Principles

Before you write code:

1. **Think before coding.** Surface assumptions and tradeoffs explicitly. Don't hide confusion behind plausible output.
2. **Simplicity first.** Minimal code that solves the stated problem. No features beyond what was asked. No abstractions for single-use code.
3. **Surgical changes.** Edit only what's necessary. Don't "improve" adjacent code, comments, or formatting. Remove only unused code your changes created.
4. **Goal-driven execution.** Define verifiable success criteria before starting. "Add validation" → "Write tests for invalid inputs, then make them pass."

Throughout:

- **No Laziness:** Find root causes. No temporary fixes. No "this works for now." Senior developer standards at all times.
- **Latent vs. Deterministic:** Judgment, synthesis, pattern recognition → LLM (latent). Same input → same output, arithmetic, SQL, compiled logic → deterministic code. Never force arithmetic into latent space; never force nuanced judgment into rigid rules.

---

## What NOT to Do

- Don't spawn an Agent Team for a task a single session can handle in < 5 minutes.
- Don't let teammates explore the codebase independently when this CLAUDE.md already tells them where things are.
- Don't broadcast when a direct message will do.
- Don't edit shared infrastructure from a teammate — only the lead touches shared code.
- Don't skip verification to save time — it always costs more later.
- Don't add dependencies (packages, libraries) without explicit approval from the user.
- Don't present work to the user without self-reviewing it first.
- Don't give a subagent multiple unrelated tasks — one task per subagent.
- Don't keep pushing a broken approach — stop and re-plan.
- Don't dump all domain knowledge into this file — use skills and resolvers.
- Don't define 40+ tool/MCP endpoints when a purpose-built CLI would be faster and cheaper on context.
- Don't put deterministic work (arithmetic, ratio calculation) in the LLM — write code for it.
- Don't do one-off work without asking: "will this need to happen again?" If yes, make a skill.

---

## Auto-Update Rule

**After completing any task that adds, modifies, or removes features, Claude Code must:**

1. Add entry to **CHANGELOG.md** (in project root — create it if it doesn't exist) with date, summary, and files changed.
2. Update relevant sections in this file (Architecture, Key Services, Data Models) if new services/models are added.
3. Keep documentation in sync with codebase at all times.

---

## Project Overview

<!-- Customize below this line for your project. Everything above is the reusable Boris Cherny setup. -->

(Describe your project here: what it is, who it's for, the core product.)

## Tech Stack

(Language, frameworks, database, infra, testing, CI/CD.)

## Repository Structure

(Directory tree + key architecture decisions.)
