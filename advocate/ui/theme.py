"""WCAG-AA light theme for the Advocate wizard.

Explicitly a LIGHT theme with AA-contrast tokens — the ADK dev UI is dark-locked
(adk-web issue #7) with no contrast control, which is a Section-508 procurement risk
for a university buyer. Tokens below are chosen for >= 4.5:1 body text and >= 3:1 UI:
  - body text  #1f2937 (gray-800) on #ffffff       ~ 12.6:1
  - primary    #1d4ed8 (blue-700) bg + #ffffff text ~ 7.0:1
  - accent link #1d4ed8 on #ffffff                  ~ 7.0:1
The CSS adds a visible :focus-visible ring (never suppressed) and honors
prefers-reduced-motion (kills the streaming-cursor + transitions).
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
    ).set(
        # Force light surfaces (no dark-mode contrast trap).
        body_background_fill="#ffffff",
        body_background_fill_dark="#ffffff",
        background_fill_primary="#ffffff",
        background_fill_secondary="#f8fafc",  # slate-50, subtle panel separation
        body_text_color="#1f2937",            # gray-800 on white ~12.6:1
        body_text_color_subdued="#475569",    # slate-600 on white ~7.5:1 (still AA)
        block_title_text_color="#111827",
        block_label_text_color="#1f2937",
        # Primary action: blue-700 + white text (~7:1).
        button_primary_background_fill="#1d4ed8",
        button_primary_background_fill_hover="#1e40af",
        button_primary_text_color="#ffffff",
        button_secondary_background_fill="#f1f5f9",
        button_secondary_text_color="#1f2937",
        button_secondary_border_color="#cbd5e1",
        # Visible focus ring colour (the CSS below enforces it being shown).
        border_color_accent="#1d4ed8",
    )


# Focus visibility + reduced-motion are accessibility requirements the theme tokens
# alone don't guarantee, so they're enforced in CSS.
ADVOCATE_CSS = """
:root { color-scheme: light; }

/* Never suppress focus — a hard WCAG 2.4.7 requirement. */
*:focus-visible {
  outline: 3px solid #1d4ed8 !important;
  outline-offset: 2px !important;
  border-radius: 4px;
}

/* Honor reduced-motion: disable streaming-cursor + transitions/animations. */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.001ms !important;
    scroll-behavior: auto !important;
  }
}

/* Progress rail: wrap on small viewports, keep buttons readable. */
#rail { flex-wrap: wrap; gap: 6px; }
.rail-btn { min-width: 0; }

/* Locked steps carry a text/aria cue, not colour alone. */
.step-locked { opacity: 0.65; }
"""
