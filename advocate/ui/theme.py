"""WCAG-AA light theme + craft polish for the Advocate wizard.

Explicitly a LIGHT theme with AA-contrast tokens — the ADK dev UI is dark-locked
(adk-web issue #7) with no contrast control, which is a Section-508 procurement risk
for a university buyer. Tokens below are chosen for >= 4.5:1 body text and >= 3:1 UI:
  - body text  #1f2937 (gray-800) on #ffffff       ~ 12.6:1
  - primary    #1d4ed8 (blue-700) bg + #ffffff text ~ 7.0:1
  - accent link #1d4ed8 on #ffffff                  ~ 7.0:1

Beyond contrast, the CSS turns stock Gradio into something that reads as a finished
product: a centered max-width column on a soft-slate page, each step rendered as a
white card (killing Gradio's grey `.gr-group` slab), a refined pill stepper, right-sized
buttons with a hover lift, a real disabled state, and the framework footer removed. A
visible :focus-visible ring is never suppressed and prefers-reduced-motion is honored.
"""
from __future__ import annotations

import gradio as gr

# Brand/accent — blue-700; pairs with white text at AA.
_PRIMARY = gr.themes.colors.blue
_NEUTRAL = gr.themes.colors.gray


def advocate_theme() -> gr.themes.Base:
    """Construct the light, AA-contrast Advocate theme."""
    return gr.themes.Base(
        primary_hue=_PRIMARY,
        neutral_hue=_NEUTRAL,
        font=(gr.themes.GoogleFont("Inter"), "system-ui", "sans-serif"),
        radius_size=gr.themes.sizes.radius_lg,
    ).set(
        # Soft-slate page so the white step cards visibly float (depth without dark mode).
        body_background_fill="#f6f7f9",
        body_background_fill_dark="#f6f7f9",
        background_fill_primary="#ffffff",
        background_fill_secondary="#f8fafc",  # slate-50, subtle panel separation
        body_text_color="#1f2937",            # gray-800 on white ~12.6:1
        body_text_color_subdued="#475569",    # slate-600 ~7.5:1 (still AA)
        block_title_text_color="#0f172a",
        block_label_text_color="#1f2937",
        block_border_color="#e6e8ec",
        input_background_fill="#ffffff",        # crisp white fields, not muddy grey
        input_background_fill_focus="#ffffff",
        input_border_color="#d8dce2",
        input_border_color_focus="#1d4ed8",
        # Primary action: blue-700 + white text (~7:1).
        button_primary_background_fill="#1d4ed8",
        button_primary_background_fill_hover="#1e40af",
        button_primary_text_color="#ffffff",
        button_secondary_background_fill="#ffffff",
        button_secondary_background_fill_hover="#f1f5f9",
        button_secondary_text_color="#1f2937",
        button_secondary_border_color="#cbd5e1",
        button_large_radius="10px",
        button_small_radius="999px",
        # Visible focus ring colour (the CSS below enforces it being shown).
        border_color_accent="#1d4ed8",
    )


# The theme tokens don't reach Gradio's `.gr-group` slab, the framework footer, the
# full-bleed buttons, or focus/motion guarantees — so those are enforced in CSS.
ADVOCATE_CSS = """
:root {
  color-scheme: light;
  --adv-ink: #0f172a;
  --adv-line: #e6e8ec;
  --adv-card-shadow: 0 1px 2px rgba(16,24,40,.04), 0 6px 20px rgba(16,24,40,.06);
}

/* ---- Centered product column on a soft-slate page ---- */
body, gradio-app, .gradio-container { background: #f6f7f9 !important; }
.gradio-container {
  /* viewport-relative hard width: caps at 1040 on desktop, forces = viewport on mobile so a
     content-driven child (the wide table) can't stretch the page. min-width:0 chain below then
     lets the table scroll inside its own card instead. */
  width: min(1040px, 100vw) !important;
  margin: 0 auto !important;
  padding: 10px 20px 72px !important;
  overflow-x: hidden;
}

/* ---- Drop the framework footer ("Built with Gradio · Settings") ---- */
footer { display: none !important; }

/* ---- App header ---- */
#app-header { margin: 14px 2px 2px; }
#app-header h1 {
  font-size: 30px; font-weight: 750; letter-spacing: -0.022em;
  color: var(--adv-ink); margin: 0 0 2px;
}
#app-header p { color: #475569; font-size: 15px; margin: 0; }
#app-header h1::before {
  content: ""; display: inline-block; width: 10px; height: 10px;
  margin-right: 10px; border-radius: 3px; background: #1d4ed8;
  transform: translateY(-3px);
}

/* App footer (replaces the removed Gradio one). */
#app-footer { margin-top: 22px; text-align: center; }
#app-footer p { color: #94a3b8 !important; font-size: 12.5px !important; }

/* ---- Progress rail: a refined pill stepper (fits on desktop, swipes on mobile) ---- */
#rail {
  gap: 8px !important; flex-wrap: nowrap !important; margin: 14px 0 2px !important;
  overflow-x: auto; padding-bottom: 4px;
  scrollbar-width: thin;
}
#rail.unequal-height { align-items: center; }
#rail > * { flex: 0 0 auto !important; min-width: 0 !important; }  /* pills keep natural width, never collide */
.rail-btn {
  min-width: 0 !important;
  white-space: nowrap !important;       /* one line per pill -> even heights */
  border-radius: 999px !important;
  font-size: 13px !important; font-weight: 600 !important;
  padding: 7px 15px !important;
  border: 1px solid #d7dbe2 !important;
  background: #ffffff !important; color: #475569 !important;
  box-shadow: none !important; transition: background .12s, border-color .12s, color .12s;
}
.rail-btn:hover { background: #eef2ff !important; border-color: #c7d2fe !important; color: #1e3a8a !important; }
.rail-btn.primary {            /* the active step */
  background: #1d4ed8 !important; color: #ffffff !important; border-color: #1d4ed8 !important;
}

/* ---- Each step Group becomes a clean white card (was a grey #e5e7eb slab) ---- */
.gr-group {
  background: #ffffff !important;
  border: 1px solid var(--adv-line) !important;
  border-radius: 16px !important;
  box-shadow: var(--adv-card-shadow) !important;
  padding: 24px 26px !important;
  margin-top: 14px !important;
  overflow: hidden;
  animation: adv-rise .22s ease both;   /* replays when a step toggles display:none->block */
}
.gr-group > .styler { background: transparent !important; }

/* Step heading typography inside the card. */
.gr-group h2 {
  font-size: 19px !important; font-weight: 700 !important;
  color: var(--adv-ink) !important; letter-spacing: -0.012em; margin: 0 0 4px !important;
}
.gr-group h2 + p, .gr-group .prose p { color: #475569 !important; }

/* ---- Buttons: right-size (no full-bleed bars) + hover lift + real disabled ---- */
.gr-group button.lg {
  width: fit-content !important;
  min-width: 220px;
  padding: 0 22px !important;
  font-weight: 600 !important;
  transition: transform .12s ease, box-shadow .12s ease, background .12s ease;
}
.gr-group button.lg.primary { box-shadow: 0 1px 2px rgba(29,78,216,.25); }
.gr-group button.lg:hover { transform: translateY(-1px); }
.gr-group button.lg.primary:hover { box-shadow: 0 4px 12px rgba(29,78,216,.28); }
.gr-group button.lg:disabled,
.gr-group button.lg[disabled] {
  background: #eef1f5 !important; color: #8a93a3 !important;
  border-color: #e6e8ec !important; box-shadow: none !important;
  cursor: not-allowed !important; transform: none !important;
}
/* The Approve / Regenerate / Discard action row reads as one tight, left-aligned group. */
#action-row { gap: 10px !important; justify-content: flex-start; }
#action-row > * { flex: 0 0 auto !important; min-width: 0 !important; }
#action-row button.lg { min-width: auto !important; white-space: nowrap !important; }

/* ---- Helper / hint copy under gated actions ---- */
.adv-hint { margin-top: 2px; }
.adv-hint p { color: #64748b !important; font-size: 13.5px !important; }

/* ---- Inputs: firm border on the white card (single-line fields render as <input>) ---- */
.gr-group textarea { border: 1px solid #d6dae1 !important; border-radius: 10px !important; }

/* ---- Dataframe: Inter (not Gradio's mono) + softer chrome ---- */
.gr-group table th, .gr-group table td { font-family: 'Inter', system-ui, sans-serif !important; }
.gr-group table th { font-weight: 600 !important; color: var(--adv-ink) !important; }
/* On narrow viewports the multi-column table scrolls inside its card, never the whole page.
   The min-width:0 is the flexbox fix: without it a flex item won't shrink below its content
   (the 684px table), so the table would push the page wider instead of scrolling internally. */
.gr-group .table-wrap, .gr-group .table-container {
  overflow-x: auto !important; max-width: 100% !important; min-width: 0 !important;
}
.gr-group .block, .gr-group .column, .gr-group .form { min-width: 0 !important; }
/* Gradio's `main.fillable` is content-sized; clamp it to the (now hard-bounded) container. */
main.fillable, .gradio-container > main { width: 100% !important; max-width: 100% !important; min-width: 0 !important; }

/* ---- Accessibility: never suppress focus (WCAG 2.4.7) ---- */
*:focus-visible {
  outline: 3px solid #1d4ed8 !important;
  outline-offset: 2px !important;
  border-radius: 4px;
}

@keyframes adv-rise { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }

/* ---- Mobile: stack in-card rows (target inputs, action buttons) so they aren't cramped.
   Scoped to .gr-group so the horizontal scroll rail (#rail, outside cards) is untouched. ---- */
@media (max-width: 600px) {
  .gr-group .row { flex-direction: column !important; }
  #app-header h1 { font-size: 26px; }
}

/* ---- Honor reduced-motion: kill the reveal, hover lift, streaming cursor ---- */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.001ms !important;
    scroll-behavior: auto !important;
  }
  .gr-group, .gr-group button.lg:hover { transform: none !important; }
}

/* Locked steps carry a text/aria cue, not colour alone. */
.step-locked { opacity: 0.65; }
"""
