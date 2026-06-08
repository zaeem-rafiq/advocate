"""Assembled Advocate "Guided Sprint" wizard (Gradio).

A single gr.Blocks: a clickable progress rail (one button per step, keyboard-reachable)
+ seven step panels toggled by a `step` gr.State. Pure step/visibility logic is in
steps.py; the WCAG-AA light theme in theme.py; the adk-free in-process pipeline (grounded
LLM + pure core) in pipeline.py. Handlers are thin wrappers over pipeline.* so the logic
stays unit-tested; this module is the Gradio glue.

DRAFT-ONLY guarantee: there is no send capability anywhere in the system. "Approve" means
"I've sent this myself" and only schedules the 3B7 reminders — nothing is ever sent for the user.
"""
from __future__ import annotations

import functools
import logging
import os
import tempfile
from datetime import date

import gradio as gr

from advocate.ui import pipeline
from advocate.ui.steps import NUM_STEPS, STEPS, visibility_for
from advocate.ui.theme import ADVOCATE_CSS, advocate_theme

_LOG = logging.getLogger("advocate.ui")

# Markdown control characters. User-typed text rendered inside a gr.Markdown component is
# escaped through this map so it can't inject links/images/emphasis/HTML/headings/tables
# (CommonMark backslash-escapes any ASCII punctuation, so the rendered text is unchanged).
_MD_ESCAPE = str.maketrans({c: "\\" + c for c in "\\`*_{}[]<>()#+!|"})


def _md_escape(text) -> str:
    """Render untrusted free-text literally inside a Markdown component."""
    return str(text).translate(_MD_ESCAPE)


def _is_safe_upload(path: str) -> bool:
    """Containment guard for an uploaded file path.

    Gradio writes uploads under the system temp dir (or GRADIO_TEMP_DIR). The handler
    accepts a path *string* in one branch, so without this check a crafted request could
    point load_contacts at an arbitrary server file (an arbitrary-file-read primitive).
    Only paths that resolve inside a known upload root are read.
    """
    try:
        real = os.path.realpath(path)
        roots = [os.path.realpath(tempfile.gettempdir())]
        gradio_tmp = os.environ.get("GRADIO_TEMP_DIR")
        if gradio_tmp:
            roots.append(os.path.realpath(gradio_tmp))
        return any(real == r or real.startswith(r + os.sep) for r in roots)
    except Exception:  # noqa: BLE001 — any resolution failure => treat as unsafe
        return False

_RATE_HEADERS = ["Company", "Sector", "Posting (1-3)", "Alumni", "Your rating (1-5)"]
_RANK_HEADERS = ["#", "Company", "Sector", "Motivation", "Posting", "Alumni", "Lenses"]
_CADENCE_PLACEHOLDER = "_Approve an outreach on the Outreach step to schedule the 3B7 reminders._"
_PREP_PLACEHOLDER = "_Rank your companies first (or type a company above), then Prepare TIARA questions._"


def _nav_updates(target: int) -> list:
    """Updates for all step-panel visibilities + rail-button variants + the step state."""
    group_updates = [gr.update(visible=v) for v in visibility_for(target)]
    button_updates = [
        gr.update(variant=("primary" if i == target else "secondary"))
        for i in range(NUM_STEPS)
    ]
    return group_updates + button_updates + [target]


def _ranked_rows(ranked: list) -> list:
    """Active-Five display rows (status shown as a text label, not colour)."""
    rows = []
    for i, o in enumerate(ranked[:5], 1):
        rows.append([
            i, o["company"], o.get("sector", ""),
            o.get("motivation") if o.get("motivation") is not None else "—",
            o.get("posting_score", 0),
            "yes" if o.get("has_alumni") else "no",
            ", ".join(o.get("lenses", [])) or "—",
        ])
    return rows


def _ranked_motivations(ranked: list) -> dict:
    """Map company -> motivation from the ranked records (each carries its own motivation)."""
    return {o["company"]: o.get("motivation") for o in (ranked or [])}


# IAP headers Cloud Run injects for an authenticated request (verified: cloud.google.com/iap/docs).
# x-goog-iap-jwt-assertion is the signed proof and is ALWAYS present; the email header is the
# plain-text convenience copy. Requiring the PRESENCE of either is a fail-closed signal that IAP is
# actually in front — NOT full JWT signature validation (that's the production-grade hardening step).
_IAP_HEADERS = ("x-goog-iap-jwt-assertion", "x-goog-authenticated-user-email")


def _iap_blocked(request) -> bool:
    """Defense-in-depth: when REQUIRE_IAP=1, refuse requests carrying no IAP-injected identity.

    The security boundary is Cloud Run + IAP; this fails CLOSED on the expensive grounded path if
    that boundary is ever misconfigured/removed. No-op locally (REQUIRE_IAP unset). Because IAP
    always adds the signed assertion to authenticated requests, enabling this cannot lock out a
    legitimately signed-in user.
    """
    if os.environ.get("REQUIRE_IAP", "").strip().upper() not in ("1", "TRUE"):
        return False
    try:
        headers = request.headers if request is not None else {}
        return not any(headers.get(h) for h in _IAP_HEADERS)
    except Exception:  # noqa: BLE001 — a missing/odd request object => treat as unauthenticated
        return True


# ----- step handlers (thin wrappers over the tested pipeline) -----

def _on_source(industry, geography, function, request: gr.Request = None):
    """Grounded sourcing with streamed status (so the ~1-min call never looks frozen)."""
    if _iap_blocked(request):
        yield ("⛔ Not authenticated — reach this service through Google sign-in (IAP).", gr.update(), [])
        return
    industry = (industry or "").strip()
    function = (function or "").strip()
    if not industry or not function:
        yield ("⚠️ Enter at least a target **industry/sector** and **function** on the Connect step first.",
               gr.update(), [])
        return
    yield ("⏳ Searching the web for target employers across the four LAMP lenses… "
           "this runs grounded Gemini and can take ~1 minute.", gr.update(), [])
    result = pipeline.source_targets(industry, geography or "", function)
    orgs = result["organizations"]
    note = ("ℹ️ Live search was unavailable, so these are the **seeded** target companies "
            "(the flow still works end-to-end)." if result.get("fallback") else
            f"✅ Sourced **{result['count']}** employers"
            + ("" if result.get("met_minimum") else " (below the 40 target, but all grounded)") + ".")
    rows = pipeline.records_to_rate_rows(orgs)
    yield (note + "  \nNow go to **Rate** and gut-rate each 1–5.",
           gr.update(value=rows), orgs)


def _on_rank(rate_rows, records):
    """Parse ratings, apply the rate-10 gate, rank M->P->A, and ENABLE outreach only when unlocked.

    Ranking always previews (gate.py never gates the ranking). Only the outreach affordance is
    gated: when locked, the Draft button is disabled and no company is pre-selected, and _on_draft
    re-checks the gate so it isn't merely a disabled button. This is a UX/integrity gate computed
    from in-session ratings — not an authorization boundary (that's Cloud Run + IAP).
    """
    motivations = pipeline.rate_rows_to_motivations(rate_rows)
    gate = pipeline.gate_status(records, motivations)
    ranked = pipeline.rank_and_activate(records, motivations)
    choices = [o["company"] for o in ranked[:5]]
    if gate["unlocked"]:
        msg = f"🔓 Outreach unlocked — **{gate['rated']}** rated. Your Active Five is on the **Rank** step."
        selected = choices[0] if choices else None
    else:
        msg = (f"🔒 Outreach locked — you've rated **{gate['rated']}/{gate['threshold']}**. "
               f"Rate **{gate['remaining']}** more to unlock drafting. (Ranking still previews below.)")
        selected = None  # don't pre-select an outreach target while locked
    return (
        msg,
        ranked,
        gr.update(value=_ranked_rows(ranked)),
        gr.update(choices=choices, value=selected),                      # outreach_company
        gr.update(choices=[o["company"] for o in ranked], value=selected),  # prep_company
        gr.update(interactive=gate["unlocked"]),                         # draft_btn (locked until 10 rated)
    )


def _on_draft(company, background, ranked, request: gr.Request = None):
    """Find a starter contact for the chosen company, then draft a compliant outreach email.

    Re-checks the rate-10 gate from the in-session ranked state so drafting isn't reachable via
    the disabled button alone. That gate is a UX/integrity control (the ranked payload is
    client-supplied), NOT an authorization boundary — the boundary is Cloud Run + IAP, re-asserted
    here by the fail-closed _iap_blocked check so this grounded (cost-bearing) endpoint can't run
    unauthenticated if IAP is ever misconfigured.
    """
    if _iap_blocked(request):
        return ("⛔ Not authenticated — reach this service through Google sign-in (IAP).",
                gr.update(value=""), {})
    if not pipeline.gate_status(ranked or [], _ranked_motivations(ranked))["unlocked"]:
        rated = sum(1 for o in (ranked or []) if o.get("motivation") is not None)
        return (f"🔒 Outreach is locked — rate at least {pipeline.OUTREACH_RATING_THRESHOLD} companies on the "
                f"**Rate** step first (you've rated {rated}).", gr.update(value=""), {})
    if not company:
        return ("Pick a company on the **Rank** step first.", gr.update(value=""), {})
    contact = pipeline.starter_contact(company)
    if not contact.get("found"):
        return (f"No connected contact found at **{company}** — pick another company "
                f"or add a contact to your alumni CSV. (Advocate never invents a contact.)",
                gr.update(value=""), {})
    result = pipeline.draft_email(contact["contact_name"], company, background or "a job seeker", contact["connection"])
    if not result.get("passed"):
        return (f"⚠️ Couldn't produce a compliant draft for **{contact['contact_name']}** at {company}: "
                f"{result.get('error', 'unknown error')}. Try **Regenerate**.",
                gr.update(value=""), {})
    meta = {"company": company, "contact": contact["contact_name"]}
    status = (f"Draft for **{contact['contact_name']}** ({contact.get('title','')}) at **{company}** — "
              f"{result['word_count']} words, passed compliance. "
              f"Edit freely, then **Approve** (nothing is sent automatically — you send it yourself).")
    return (status, gr.update(value=result["email"]), meta)


def _on_connect(f):
    """Validate an uploaded contacts CSV (display only; demo sourcing uses the seeded data)."""
    if not f:
        return "Using the **seeded** connected data for the demo. Set your targets above, then go to **Source**."
    from advocate.data.loaders import load_contacts
    path = f if isinstance(f, str) else f.name
    if not _is_safe_upload(path):
        return "⚠️ That upload couldn't be read from the expected location. Please re-upload your CSV."
    try:
        n = len(load_contacts(path))
    except Exception:  # noqa: BLE001 — never surface a stack trace or an internal path
        _LOG.exception("failed to read uploaded contacts CSV")
        return "⚠️ Couldn't read that CSV. Expected columns like company, contact_name, is_cbs_alum."
    if n == 0:
        return "⚠️ That CSV had no contact rows. Check it has a header row plus at least one contact."
    return f"✅ Read **{n}** contacts from your CSV. (Demo sourcing uses the seeded connected data.)"


def _on_approve(draft_text, meta):
    """Approve = the user sends it themselves; we only schedule the 3B7 reminders."""
    if not (draft_text or "").strip() or not meta:
        return ("Nothing to approve yet — draft an email first.", _CADENCE_PLACEHOLDER)
    plan = pipeline.schedule_3b7(date.today().isoformat())
    company, contact = meta.get("company", ""), meta.get("contact", "")
    msg = (f"✅ Logged your outreach to **{contact}** at **{company}**. "
           f"3B7 reminders scheduled: follow-up #1 **{plan['followup_3b']}** (3 business days), "
           f"follow-up #2 **{plan['followup_7b']}** (7 business days). "
           f"_Nothing was sent automatically — Advocate is draft-only._")
    cadence_md = (f"**Active thread:** {contact} at {company}\n\n"
                  f"- 📨 Follow-up #1 (advance to next contact if no reply): **{plan['followup_3b']}**\n"
                  f"- 📨 Follow-up #2 (gentle nudge to contact #1): **{plan['followup_7b']}**\n\n"
                  f"Use **Prep** to get TIARA questions once someone replies.")
    return (msg, cadence_md)


def _on_discard():
    """Discard the draft AND revert the downstream Outreach/3B7 surfaces (no stale schedule)."""
    return ("Draft discarded.", "", {}, "", _CADENCE_PLACEHOLDER)


def _on_prep(company, role, request: gr.Request = None):
    """Cited research brief + five TIARA questions for an informational interview."""
    if _iap_blocked(request):
        yield "⛔ Not authenticated — reach this service through Google sign-in (IAP)."
        return
    if not company:
        yield "Pick a ranked company above, or type a company name, then Prepare."
        return
    yield "⏳ Researching the company (grounded Gemini)… up to ~1 minute."
    result = pipeline.prep(company, (role or "this role").strip())
    q = result.get("questions", {})
    caveat = ""
    if not result.get("grounded"):
        caveat = "\n\n> ⚠️ Research was thin — these are general questions; verify company specifics yourself."
    elif result.get("depth") == "shallow":
        caveat = "\n\n> ℹ️ Based on limited sources — verify specifics before relying on them."
    questions_md = "\n".join(f"- **{cat}:** {q.get(cat, '')}" for cat in ["Trends", "Insights", "Advice", "Resources", "Assignments"])
    yield f"### {_md_escape(company)} — informational brief\n\n{result.get('brief','')}\n\n### TIARA questions\n{questions_md}{caveat}"


def build_app() -> gr.Blocks:
    """Construct the wizard Blocks (no network until launched)."""
    with gr.Blocks(theme=advocate_theme(), css=ADVOCATE_CSS, title="Advocate", analytics_enabled=False) as demo:
        step = gr.State(0)
        records_state = gr.State([])   # sourced full org records
        ranked_state = gr.State([])    # ranked Active-Five (carries motivation); read by _on_draft to enforce the gate
        meta_state = gr.State({})      # {company, contact} for the approved outreach

        gr.Markdown("# Advocate\nYour 2-Hour Job Search, guided — source, rank, reach out, follow up.")

        rail_buttons: list[gr.Button] = []
        with gr.Row(elem_id="rail"):
            for i, s in enumerate(STEPS):
                rail_buttons.append(
                    gr.Button(f"{i} · {s.title}", variant=("primary" if i == 0 else "secondary"),
                              size="sm", elem_classes=["rail-btn"])
                )

        groups: list[gr.Group] = []

        # --- Step 0: Connect ---
        with gr.Group(visible=True) as g0:
            gr.Markdown(f"## Step 0 — Connect\n\n{STEPS[0].description}")
            with gr.Row():
                industry_in = gr.Textbox(label="Target industry / sector", placeholder="e.g. climate technology")
                geography_in = gr.Textbox(label="Target geography", placeholder="e.g. New York")
                function_in = gr.Textbox(label="Target function / role", placeholder="e.g. product management")
            background_in = gr.Textbox(label="One line about you (used to personalize drafts)",
                                       placeholder="e.g. a Columbia MBA moving from consulting into climate product")
            alumni_csv = gr.File(label="Alumni / contacts CSV (optional for the demo — seeded data is used)",
                                 file_types=[".csv"])
            connect_status = gr.Markdown("")
        groups.append(g0)

        # --- Step 1: Source ---
        with gr.Group(visible=False) as g1:
            gr.Markdown(f"## Step 1 — Source\n\n{STEPS[1].description}")
            source_btn = gr.Button("Find target employers", variant="primary")
            source_status = gr.Markdown("")
        groups.append(g1)

        # --- Step 2: Rate ---
        with gr.Group(visible=False) as g2:
            gr.Markdown(f"## Step 2 — Rate\n\n{STEPS[2].description}")
            # Only the rating column (index 4) is editable — editing identity columns would
            # mis-key the rate-10 gate (a finding from review); lock columns 0-3.
            rate_df = gr.Dataframe(headers=_RATE_HEADERS, datatype=["str", "str", "number", "str", "number"],
                                   type="array", interactive=True, static_columns=[0, 1, 2, 3],
                                   label="Gut-rate each company (1–5) in the last column")
            rank_btn = gr.Button("Lock in ratings & rank", variant="primary")
            gate_status = gr.Markdown("")
        groups.append(g2)

        # --- Step 3: Rank ---
        with gr.Group(visible=False) as g3:
            gr.Markdown(f"## Step 3 — Rank\n\n{STEPS[3].description}")
            ranked_df = gr.Dataframe(headers=_RANK_HEADERS, type="array", interactive=False,
                                     label="Your Active Five (Motivation → Posting → Alumni)")
            outreach_company = gr.Dropdown(label="Pick a company to reach out to", choices=[], interactive=True)
        groups.append(g3)

        # --- Step 4: Outreach (the draft-approval gate) ---
        with gr.Group(visible=False) as g4:
            gr.Markdown(f"## Step 4 — Outreach\n\n{STEPS[4].description}")
            # Disabled until the rate-10 gate unlocks (set interactive by _on_rank).
            draft_btn = gr.Button("Draft outreach email", variant="primary", interactive=False)
            draft_status = gr.Markdown("")
            draft_box = gr.Textbox(label="Draft (editable) — review, edit, then approve", lines=14, interactive=True)
            with gr.Row():
                approve_btn = gr.Button("Approve & schedule follow-ups", variant="primary")
                regen_btn = gr.Button("Regenerate", variant="secondary")
                discard_btn = gr.Button("Discard", variant="secondary")
            approve_status = gr.Markdown("")
        groups.append(g4)

        # --- Step 5: 3B7 cadence ---
        with gr.Group(visible=False) as g5:
            gr.Markdown(f"## Step 5 — 3B7\n\n{STEPS[5].description}")
            cadence_view = gr.Markdown(_CADENCE_PLACEHOLDER)
        groups.append(g5)

        # --- Step 6: Prep (TIARA) ---
        with gr.Group(visible=False) as g6:
            gr.Markdown(f"## Step 6 — Prep\n\n{STEPS[6].description}")
            prep_company = gr.Dropdown(label="Company for the informational", choices=[],
                                       interactive=True, allow_custom_value=True)
            prep_role = gr.Textbox(label="Role / function you're exploring", placeholder="e.g. product management")
            prep_btn = gr.Button("Prepare TIARA questions", variant="primary")
            prep_view = gr.Markdown(_PREP_PLACEHOLDER)
        groups.append(g6)

        # ----- wiring -----
        # Connect: validate an uploaded CSV (display only; the demo flow uses the connected seed data).
        alumni_csv.change(_on_connect, inputs=[alumni_csv], outputs=[connect_status])

        nav_outputs = groups + rail_buttons + [step]
        for i, button in enumerate(rail_buttons):
            button.click(fn=functools.partial(_nav_updates, i), outputs=nav_outputs)

        source_btn.click(_on_source, inputs=[industry_in, geography_in, function_in],
                         outputs=[source_status, rate_df, records_state])
        rank_btn.click(_on_rank, inputs=[rate_df, records_state],
                       outputs=[gate_status, ranked_state, ranked_df, outreach_company, prep_company, draft_btn])
        draft_btn.click(_on_draft, inputs=[outreach_company, background_in, ranked_state],
                        outputs=[draft_status, draft_box, meta_state])
        regen_btn.click(_on_draft, inputs=[outreach_company, background_in, ranked_state],
                        outputs=[draft_status, draft_box, meta_state])
        approve_btn.click(_on_approve, inputs=[draft_box, meta_state], outputs=[approve_status, cadence_view])
        discard_btn.click(_on_discard, outputs=[draft_status, draft_box, meta_state, approve_status, cadence_view])
        prep_btn.click(_on_prep, inputs=[prep_company, prep_role], outputs=[prep_view])

    return demo


def launch() -> None:
    """Serve the wizard. Cloud Run provides $PORT; bind 0.0.0.0 for the container."""
    # Repo root (parent of the advocate package) — the app's own source + seeded CSVs.
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    build_app().launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", "7860")),
        show_api=False,
        max_file_size="5mb",  # cap untrusted CSV uploads (memory-exhaustion guard)
        # Authz for every route is Cloud Run + IAP. Defense-in-depth: refuse to serve the
        # app's own source / seeded CSVs via Gradio's /file= route. Uploads live under the
        # system temp dir (not repo_root), so they stay readable.
        blocked_paths=[repo_root],
    )


if __name__ == "__main__":
    launch()
