"""Assembled Advocate "Guided Sprint" wizard (Gradio).

A single gr.Blocks: a clickable progress rail (one button per step, keyboard-reachable)
+ seven step panels toggled by a `step` gr.State. The pure step/visibility logic is in
steps.py; the WCAG-AA light theme in theme.py. Step bodies are filled in incrementally
(T1.x/T2.x/T3.x) — the skeleton wires navigation and states first (T0.2).
"""
from __future__ import annotations

import functools
import os

import gradio as gr

from advocate.ui.steps import NUM_STEPS, STEPS, visibility_for
from advocate.ui.theme import ADVOCATE_CSS, advocate_theme


def _nav_updates(target: int) -> list:
    """Updates for all step-panel visibilities + rail-button variants + the step state.

    Positionally matches `outputs = groups + rail_buttons + [step]` in build_app.
    """
    group_updates = [gr.update(visible=v) for v in visibility_for(target)]
    button_updates = [
        gr.update(variant=("primary" if i == target else "secondary"))
        for i in range(NUM_STEPS)
    ]
    return group_updates + button_updates + [target]


def build_app() -> gr.Blocks:
    """Construct the wizard Blocks (no network until launched)."""
    with gr.Blocks(
        theme=advocate_theme(),
        css=ADVOCATE_CSS,
        title="Advocate",
        analytics_enabled=False,  # privacy: no Gradio telemetry
    ) as demo:
        step = gr.State(0)

        gr.Markdown("# Advocate\nYour 2-Hour Job Search, guided — source, rank, reach out, follow up.")

        # Progress rail: real buttons (keyboard-reachable, native focus) styled as a rail.
        rail_buttons: list[gr.Button] = []
        with gr.Row(elem_id="rail"):
            for i, s in enumerate(STEPS):
                rail_buttons.append(
                    gr.Button(
                        f"{i} · {s.title}",
                        variant=("primary" if i == 0 else "secondary"),
                        size="sm",
                        elem_classes=["rail-btn"],
                    )
                )

        # Step panels — exactly one visible at a time.
        groups: list[gr.Group] = []
        for i, s in enumerate(STEPS):
            with gr.Group(visible=(i == 0)) as g:
                gr.Markdown(f"## Step {i} — {s.title}\n\n{s.description}")
                gr.Markdown("_Coming soon — this step is being built._")
            groups.append(g)

        # Wire navigation: clicking a rail button reveals its step + highlights it.
        outputs = groups + rail_buttons + [step]
        for i, button in enumerate(rail_buttons):
            button.click(fn=functools.partial(_nav_updates, i), outputs=outputs)

    return demo


def launch() -> None:
    """Serve the wizard. Cloud Run provides $PORT; bind 0.0.0.0 for the container."""
    build_app().launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", "7860")),
        show_api=False,
    )


if __name__ == "__main__":
    launch()
