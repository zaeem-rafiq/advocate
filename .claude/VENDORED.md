# Vendored: Addy Osmani's Agent Skills

The `skills/`, `agents/`, `commands/`, and `references/` directories here are
vendored from the open-source [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills)
project, licensed under MIT (see `skills/LICENSE`).

- **Source:** https://github.com/addyosmani/agent-skills
- **Pinned upstream commit:** `c076972e2626fe2acc30b00a6c7240d4c5fb786a`
- **Vendored on:** 2026-06-08

## What's included

- `skills/` — 23 SKILL.md skill definitions (auto-discovered by Claude Code)
- `agents/` — 3 specialist agent personas (code-reviewer, security-auditor, test-engineer)
- `commands/` — 7 slash commands (`/spec`, `/plan`, `/build`, `/test`, `/review`, `/ship`, `/code-simplify`)
- `references/` — supplementary checklists referenced by several skills

## Not included

- `hooks/` — upstream ships session lifecycle hooks that require wiring into
  `settings.json`. They were intentionally left out to avoid conflicting with
  this repo's existing hooks. To adopt them, copy from upstream and register
  them in `.claude/settings.json`.

## Updating

To refresh, re-clone the upstream repo at a newer commit and re-copy the four
directories, then update the pinned commit above.
