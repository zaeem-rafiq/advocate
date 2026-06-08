"""Assembled Advocate "Guided Sprint" wizard (Gradio), set as an editorial product.

A single gr.Blocks: a hairline step "ledger" (one button per step, keyboard-reachable)
+ seven step panels toggled by a `step` gr.State. The visual language lives in theme.py
(Fraunces/Newsreader/Inter, oxblood-on-paper); the adk-free in-process pipeline (grounded
LLM + pure core) in pipeline.py. Handlers are thin wrappers over pipeline.* so the logic
stays unit-tested; this module is the Gradio glue + the custom gr.HTML rendering.

The Rate step is NOT a spreadsheet: it's a custom HTML roster of hairline rows, each with a
segmented 1–5 rater. Clicking a rater has no Gradio binding, so a load-time JS bridge (in
theme.ADVOCATE_JS) writes the {company: score} map into a hidden field that _on_rank reads.

DRAFT-ONLY guarantee: there is no send capability anywhere in the system. "Approve" means
"I've sent this myself" and only schedules the 3B7 reminders — nothing is ever sent for the user.
"""
from __future__ import annotations

import functools
import html
import logging
import os
import tempfile
from datetime import date

import gradio as gr

from advocate.ui import pipeline
from advocate.ui.steps import NUM_STEPS, STEPS, visibility_for
from advocate.ui.theme import ADVOCATE_CSS, ADVOCATE_HEAD, ADVOCATE_JS, advocate_theme

_LOG = logging.getLogger("advocate.ui")

_CADENCE_PLACEHOLDER = "_Approve an outreach on the Outreach step to schedule the 3B7 reminders._"
_PREP_PLACEHOLDER = "_Rank your companies first (or type a company above), then prepare TIARA questions._"
_OUTREACH_GOAL = 10  # mirrors gate.OUTREACH_RATING_THRESHOLD; shown in the Rate progress copy

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


def _esc(s) -> str:
    """HTML-escape any value bound into our gr.HTML markup (text or attribute)."""
    return html.escape(str(s if s is not None else ""), quote=True)


def _on_connect(f):
    """Validate an uploaded contacts CSV (display only; demo sourcing uses the seeded data)."""
    if not f:
        return "Using the **seeded** connected data for the demo. Set your targets above, then go to **Source**."
    from advocate.data.loaders import load_contacts
    path = f if isinstance(f, str) else f.name
    if not _is_safe_upload(path):
        return "That upload couldn’t be read from the expected location. Please re-upload your CSV."
    try:
        n = len(load_contacts(path))
    except Exception:  # noqa: BLE001 — never surface a stack trace or an internal path
        _LOG.exception("failed to read uploaded contacts CSV")
        return "Couldn't read that CSV. Expected columns like company, contact_name, is_cbs_alum."
    if n == 0:
        return "That CSV had no contact rows. Check it has a header row plus at least one contact."
    return f"Read **{n}** contacts from your CSV. (Demo sourcing uses the seeded connected data.)"


# ----- editorial HTML builders (rendered into gr.HTML blocks) -----

def _masthead_html() -> str:
    return (
        '<header class="masthead"><div class="masthead-top">'
        '<h1 class="wordmark"><span class="glyph-a">A</span>dvocate<span class="dot">.</span></h1>'
        '<div class="masthead-meta"><div class="issue">The two-hour job search</div>'
        '<div class="vol">A guided sprint</div></div></div>'
        '<p class="tagline">Stop applying into the void. We help you find the few employers worth your '
        'time — then write to a <em>real person</em> inside them. You decide. You send. Nothing leaves '
        'your hands automatically.</p></header>'
    )


def _sec_head(rule_no: str, num: str, title: str, sub: str) -> str:
    return (
        f'<div class="sec-head"><div class="sec-index"><span class="rule-no">{_esc(rule_no)}</span>{_esc(num)}</div>'
        f'<div><h2 class="sec-title">{_esc(title)}</h2><p class="sec-sub">{_esc(sub)}</p></div></div>'
    )


def _posting_signal(score) -> tuple[str, str]:
    """Map a 1–3 posting score to a strength class + label (typographic bars, not a pill)."""
    s = int(score or 0)
    if s >= 3:
        return "s-strong", "Strong"
    if s == 2:
        return "s-some", "Some"
    return "s-few", "Few"


def _rate_html(records: list, ratings: dict | None = None) -> str:
    """The Rate hero: a progress masthead + a roster of hairline rows with 1–5 raters.

    `ratings` (company -> 1..5) pre-fills raters when re-rendering; live clicks are handled
    by the JS bridge (theme.ADVOCATE_JS), which keeps the hidden #ratings-json field current.
    """
    ratings = ratings or {}
    if not records:
        return ('<div class="roster-empty">No employers yet — head to <b>Source</b> and we’ll '
                'surface around forty for you to rate.</div>')
    rated = sum(1 for r in records if ratings.get(r["company"]) in (1, 2, 3, 4, 5))
    total = len(records)
    pct = min(100, rated / _OUTREACH_GOAL * 100)
    head = (
        '<div class="rate-progress">'
        f'<div class="count"><b class="c-rated">{rated}</b><span class="of"> / {_OUTREACH_GOAL} rated</span></div>'
        '<div class="unlock">'
        f'<div class="line">Rate <b>{_OUTREACH_GOAL}</b> to unlock Outreach — you’ve rated '
        f'<b class="l-count">{rated}</b> of {total}.</div>'
        f'<div class="measure"><span style="width:{pct:.0f}%"></span></div>'
        '</div></div>'
    )
    rows = []
    cursor_placed = False  # the first unrated row gets the .empty "your turn" focal cue
    for i, r in enumerate(records, 1):
        co = _esc(r["company"])
        sector = _esc(r.get("sector", ""))
        pcls, plabel = _posting_signal(r.get("posting_score"))
        if r.get("has_alumni"):
            alum = '<span class="alum yes">In your network · <span class="who">warm intro</span></span>'
        else:
            alum = '<span class="alum no">No alum yet · <span class="who">cold intro</span></span>'
        val = ratings.get(r["company"])
        # Per-row radios so the chosen score is exposed to assistive tech (aria-checked);
        # the cumulative oxblood fill is CSS (data-val + nth-child), this is the parallel a11y state.
        buttons = "".join(
            f'<button role="radio" aria-checked="{"true" if val == n else "false"}" '
            f'aria-label="{n} out of 5">{n}</button>'
            for n in range(1, 6)
        )
        if val in (1, 2, 3, 4, 5):
            rater_cls, data_val, cell_cls, hint = "rater", f' data-val="{val}"', " done", ("Top pick" if val >= 5 else "Rated")
        elif not cursor_placed:
            rater_cls, data_val, cell_cls, hint, cursor_placed = "rater empty", "", "", "Your turn", True
        else:
            rater_cls, data_val, cell_cls, hint = "rater", "", "", "Your turn"
        rows.append(
            '<article class="row">'
            f'<div class="rank">{i:02d}</div>'
            f'<div class="body"><div class="co">{co}</div><div class="sector">{sector}</div>'
            '<div class="signals"><span class="sig">Postings '
            f'<span class="bars {pcls}"><i></i><i></i><i></i></span><span class="val">{plabel}</span></span>'
            f'{alum}</div></div>'
            f'<div class="rate-cell{cell_cls}">'
            f'<div class="{rater_cls}" data-company="{co}"{data_val} role="radiogroup" aria-label="Rate {co}">{buttons}</div>'
            f'<div class="hint">{hint}</div></div></article>'
        )
    return head + '<div class="roster">' + "".join(rows) + '</div>'


def _ranked_html(ranked: list) -> str:
    """The Active Five as a read-only editorial list (Motivation → Posting → Alumni)."""
    if not ranked:
        return '<div class="roster-empty">Lock in your ratings to reveal your Active Five.</div>'
    rows = []
    for i, o in enumerate(ranked[:5], 1):
        co = _esc(o["company"])
        sector = _esc(o.get("sector", ""))
        alum = "In your network" if o.get("has_alumni") else "No alum yet"
        mot = o.get("motivation")
        mot_disp = _esc(mot) if mot is not None else "—"
        lenses = "".join(f'<span class="lens">{_esc(l)}</span>' for l in (o.get("lenses") or []))
        lenses_html = f'<div class="lenses">{lenses}</div>' if lenses else ""
        rows.append(
            '<article class="row">'
            f'<div class="rank">{i:02d}</div>'
            f'<div class="body"><div class="co">{co}</div>'
            f'<div class="sector">{sector} · {alum}</div>{lenses_html}</div>'
            f'<div class="mot">{mot_disp}<span class="lbl">Motivation</span></div></article>'
        )
    return '<div class="ranked roster">' + "".join(rows) + '</div>'


_DRAFT_HEAD_PLACEHOLDER = (
    '<div class="draft-head"><div class="to">A note to your strongest match — draft it below.</div>'
    '<div class="editable">Draft-only</div></div>'
)


def _draft_head_html(contact: str, title: str, company: str, word_count=None) -> str:
    t = f" — {_esc(title)}" if title else ""
    wc = f" · {int(word_count)} words, passed compliance" if word_count else ""
    return (
        f'<div class="draft-head"><div class="to">To <b>{_esc(contact)}</b>{t}, {_esc(company)}{wc}</div>'
        '<div class="editable">Editable draft</div></div>'
    )


def _draft_note(text: str) -> str:
    """A head card that carries a status/refusal line (keeps the letter card visually complete)."""
    return f'<div class="draft-head"><div class="to">{_esc(text)}</div></div>'


def _colophon_html() -> str:
    return (
        '<div class="colophon"><div class="mark"><span class="glyph-a">A</span>dvocate<span class="dot">.</span></div>'
        '<div>A guided sprint, after Steve Dalton’s method · You stay in the driver’s seat</div></div>'
    )


def _nav_updates(target: int) -> list:
    """Updates for all step-panel visibilities + rail-button state (current vs done) + step."""
    group_updates = [gr.update(visible=v) for v in visibility_for(target)]
    button_updates = []
    for i in range(NUM_STEPS):
        if i == target:
            button_updates.append(gr.update(variant="primary", elem_classes=["rail-btn", "primary"]))
        elif i < target:
            button_updates.append(gr.update(variant="secondary", elem_classes=["rail-btn", "step-done"]))
        else:
            button_updates.append(gr.update(variant="secondary", elem_classes=["rail-btn"]))
    return group_updates + button_updates + [target]


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
    """Grounded sourcing with streamed status; renders the custom roster + resets ratings."""
    if _iap_blocked(request):
        yield ("Not authenticated — reach this service through Google sign-in (IAP).", gr.update(), [], "{}")
        return
    industry = (industry or "").strip()
    function = (function or "").strip()
    if not industry or not function:
        yield ("Enter at least a target **industry / sector** and **function** on the Connect step first.",
               gr.update(), [], "{}")
        return
    yield ("Searching the web for target employers across the four LAMP lenses… "
           "this runs grounded Gemini and can take about a minute.", gr.update(), [], "{}")
    result = pipeline.source_targets(industry, geography or "", function)
    orgs = result["organizations"]
    note = ("Live search was unavailable, so these are the **seeded** target companies "
            "(the flow still works end-to-end)." if result.get("fallback") else
            f"Sourced **{result['count']}** employers"
            + ("" if result.get("met_minimum") else " (below the 40 target, but all grounded)") + ".")
    yield (note + "  \nNow go to **Rate** and gut-rate each 1–5.",
           gr.update(value=_rate_html(orgs)), orgs, "{}")


def _on_rank(ratings_json, records):
    """Parse the hidden ratings field, apply the rate-10 gate, rank M→P→A, gate outreach.

    Ranking always previews (gate.py never gates the ranking). Only the outreach affordance is
    gated: when locked, the Draft button is disabled and no company is pre-selected, so the
    announced lock is real, not cosmetic. The actual draft refusal is enforced again in _on_draft.
    """
    motivations = pipeline.parse_ratings(ratings_json)
    gate = pipeline.gate_status(records, motivations)
    ranked = pipeline.rank_and_activate(records, motivations)
    choices = [o["company"] for o in ranked[:5]]
    if gate["unlocked"]:
        msg = (f"Outreach unlocked — **{gate['rated']}** rated. Your Active Five is below; "
               "pick the one to reach out to.")
        selected = choices[0] if choices else None
    else:
        msg = (f"Outreach locked — you’ve rated **{gate['rated']}/{gate['threshold']}**. "
               f"Rate **{gate['remaining']}** more to unlock drafting. (Your Active Five still previews below.)")
        selected = None  # don't pre-select an outreach target while locked
    return (
        msg,
        ranked,
        gr.update(value=_ranked_html(ranked)),
        gr.update(choices=choices, value=selected),                          # outreach_company
        gr.update(choices=[o["company"] for o in ranked], value=selected),   # prep_company
        gr.update(interactive=gate["unlocked"]),                             # draft_btn
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
        return (_draft_note("Not authenticated — reach this service through Google sign-in (IAP)."),
                gr.update(value=""), {})
    if not pipeline.gate_status(ranked or [], _ranked_motivations(ranked))["unlocked"]:
        rated = sum(1 for o in (ranked or []) if o.get("motivation") is not None)
        return (_draft_note(f"Outreach is locked — rate at least {pipeline.OUTREACH_RATING_THRESHOLD} "
                            f"companies on the Rate step first (you’ve rated {rated})."), gr.update(value=""), {})
    if not company:
        return (_draft_note("Pick a company on the Rank step first."), gr.update(value=""), {})
    contact = pipeline.starter_contact(company)
    if not contact.get("found"):
        return (_draft_note(f"No connected contact found at {company} — pick another company or add a "
                            "contact to your alumni CSV. Advocate never invents a contact."),
                gr.update(value=""), {})
    result = pipeline.draft_email(contact["contact_name"], company, background or "a job seeker", contact["connection"])
    if not result.get("passed"):
        return (_draft_note(f"Couldn’t produce a compliant draft for {contact['contact_name']} at {company}: "
                            f"{result.get('error', 'unknown error')}. Try Regenerate."), gr.update(value=""), {})
    meta = {"company": company, "contact": contact["contact_name"]}
    head = _draft_head_html(contact["contact_name"], contact.get("title", ""), company, result.get("word_count"))
    return (head, gr.update(value=result["email"]), meta)


def _on_approve(draft_text, meta):
    """Approve = the user sends it themselves; we only schedule the 3B7 reminders."""
    if not (draft_text or "").strip() or not meta:
        return ("Nothing to approve yet — draft an email first.", _CADENCE_PLACEHOLDER)
    plan = pipeline.schedule_3b7(date.today().isoformat())
    company, contact = meta.get("company", ""), meta.get("contact", "")
    msg = (f"Logged your outreach to **{contact}** at **{company}**. "
           f"3B7 reminders scheduled: follow-up #1 **{plan['followup_3b']}** (3 business days), "
           f"follow-up #2 **{plan['followup_7b']}** (7 business days). "
           f"_Nothing was sent automatically — Advocate is draft-only._")
    cadence_md = (f"**Active thread:** {contact} at {company}\n\n"
                  f"- Follow-up #1 (advance to next contact if no reply): **{plan['followup_3b']}**\n"
                  f"- Follow-up #2 (gentle nudge to contact #1): **{plan['followup_7b']}**\n\n"
                  f"Use **Prep** to get TIARA questions once someone replies.")
    return (msg, cadence_md)


def _on_discard():
    """Discard the draft AND revert the downstream Outreach/3B7 surfaces (no stale schedule)."""
    return (_DRAFT_HEAD_PLACEHOLDER, "", {}, "", _CADENCE_PLACEHOLDER)


def _on_prep(company, role, request: gr.Request = None):
    """Cited research brief + five TIARA questions for an informational interview."""
    if _iap_blocked(request):
        yield "Not authenticated — reach this service through Google sign-in (IAP)."
        return
    if not company:
        yield "Pick a ranked company above, or type a company name, then prepare."
        return
    yield "Researching the company (grounded Gemini)… up to about a minute."
    result = pipeline.prep(company, (role or "this role").strip())
    q = result.get("questions", {})
    caveat = ""
    if not result.get("grounded"):
        caveat = "\n\n> Research was thin — these are general questions; verify company specifics yourself."
    elif result.get("depth") == "shallow":
        caveat = "\n\n> Based on limited sources — verify specifics before relying on them."
    questions_md = "\n".join(f"- **{cat}:** {q.get(cat, '')}"
                             for cat in ["Trends", "Insights", "Advice", "Resources", "Assignments"])
    # _md_escape the user-typed company so it can't inject Markdown/links into the heading.
    yield (f"### {_md_escape(company)} — informational brief\n\n{result.get('brief','')}"
           f"\n\n### TIARA questions\n{questions_md}{caveat}")


def build_app() -> gr.Blocks:
    """Construct the wizard Blocks (no network until launched)."""
    with gr.Blocks(theme=advocate_theme(), css=ADVOCATE_CSS, js=ADVOCATE_JS, head=ADVOCATE_HEAD,
                   title="Advocate", analytics_enabled=False) as demo:
        step = gr.State(0)
        records_state = gr.State([])   # sourced full org records
        ranked_state = gr.State([])    # ranked Active-Five (carries motivation); read by _on_draft
        meta_state = gr.State({})      # {company, contact} for the approved outreach

        gr.HTML(_masthead_html(), elem_id="adv-masthead")

        rail_buttons: list[gr.Button] = []
        with gr.Row(elem_id="rail"):
            for i, s in enumerate(STEPS):
                rail_buttons.append(
                    gr.Button(s.title, variant=("primary" if i == 0 else "secondary"),
                              size="sm", elem_classes=(["rail-btn", "primary"] if i == 0 else ["rail-btn"]))
                )

        groups: list[gr.Group] = []

        # --- Step 0: Connect ---
        with gr.Group(visible=True, elem_classes=["adv-bare"]) as g0:
            gr.HTML(_sec_head("Step One", "01", "Tell us where you’re pointed.",
                              "Four lines set the whole sprint. The sharper your aim, the better the "
                              "employers we surface for you to rate."))
            with gr.Group(elem_id="adv-connect-panel"):
                industry_in = gr.Textbox(label="Target industry / sector", placeholder="e.g. climate & clean energy",
                                         max_lines=1, elem_classes=["adv-field"])
                geography_in = gr.Textbox(label="Target geography", placeholder="e.g. New York & remote (US)",
                                          max_lines=1, elem_classes=["adv-field"])
                function_in = gr.Textbox(label="Target function / role", placeholder="e.g. product management",
                                         max_lines=1, elem_classes=["adv-field"])
                background_in = gr.Textbox(label="One line about you",
                                           placeholder="e.g. a Columbia MBA moving from consulting into climate product",
                                           max_lines=1, elem_classes=["adv-field"])
                alumni_csv = gr.File(label="Bring your alumni network — upload a CSV (optional; seeded data backs the demo)",
                                     file_types=[".csv"], elem_id="adv-upload")
            connect_status = gr.Markdown("", elem_classes=["adv-status"])
        groups.append(g0)

        # --- Step 1: Source ---
        with gr.Group(visible=False, elem_classes=["adv-bare"]) as g1:
            gr.HTML(_sec_head("Step Two", "02", "Find the forty.",
                              "One grounded pass across the four LAMP lenses surfaces around forty employers "
                              "worth your attention. It runs live and can take about a minute."))
            source_btn = gr.Button("Find target employers", variant="primary", elem_classes=["adv-btn", "primary"])
            source_status = gr.Markdown("", elem_classes=["adv-status"])
        groups.append(g1)

        # --- Step 2: Rate (custom roster, no spreadsheet) ---
        with gr.Group(visible=False, elem_classes=["adv-bare"]) as g2:
            gr.HTML(_sec_head("Step Three", "03", "Rate the forty. Trust your gut.",
                              "One pass, one to five — would you be glad to work here? Rate ten and we’ll "
                              "open outreach on your strongest match."))
            rate_roster = gr.HTML(_rate_html([]), elem_id="adv-rate")
            # The rater JS bridge writes {company: score} JSON into this field. It is hidden via
            # CSS (NOT visible=False) so its <textarea> stays in the DOM for the bridge to target.
            ratings_json = gr.Textbox(value="{}", elem_id="ratings-json")
            rank_btn = gr.Button("Lock in ratings & rank", variant="primary", elem_classes=["adv-btn", "primary"])
            gate_status = gr.Markdown("", elem_classes=["adv-status"])
        groups.append(g2)

        # --- Step 3: Rank ---
        with gr.Group(visible=False, elem_classes=["adv-bare"]) as g3:
            gr.HTML(_sec_head("Step Four", "04", "Your Active Five.",
                              "Ranked deterministically — Motivation first, then live postings, then who you "
                              "already know. These five get your energy."))
            ranked_view = gr.HTML(_ranked_html([]), elem_id="adv-ranked")
            outreach_company = gr.Dropdown(label="Reach out to", choices=[], interactive=True, elem_classes=["adv-field"])
        groups.append(g3)

        # --- Step 4: Outreach (the draft-approval gate) ---
        with gr.Group(visible=False, elem_classes=["adv-bare"]) as g4:
            gr.HTML(_sec_head("Step Five", "05", "A note to a real person.",
                              "Connection first — you’re not asking for a job, just fifteen honest minutes. "
                              "Edit every word; it’s yours."))
            draft_btn = gr.Button("Draft outreach email", variant="primary", interactive=False,
                                  elem_classes=["adv-btn", "primary"])
            draft_status = gr.HTML(_DRAFT_HEAD_PLACEHOLDER, elem_id="adv-draft-head")
            draft_box = gr.Textbox(
                show_label=False, lines=12, interactive=True, elem_id="adv-letter",
                placeholder="Your draft appears here after you click “Draft outreach email”. You can edit "
                            "every word before approving — then send it yourself.",
            )
            gr.HTML('<div class="reassure"><span class="seal">✓</span>Nothing is ever sent for you. '
                    'You copy it out and send it yourself.</div>')
            with gr.Row(elem_id="action-row"):
                approve_btn = gr.Button("Approve & schedule follow-ups", variant="primary", elem_classes=["adv-btn", "primary"])
                regen_btn = gr.Button("Regenerate", variant="secondary", elem_classes=["adv-btn", "secondary"])
                discard_btn = gr.Button("Discard", variant="secondary", elem_classes=["adv-btn", "secondary"])
            approve_status = gr.Markdown("", elem_classes=["adv-status"])
        groups.append(g4)

        # --- Step 5: 3B7 cadence ---
        with gr.Group(visible=False, elem_classes=["adv-bare"]) as g5:
            gr.HTML(_sec_head("Step Six", "06", "The follow-up cadence.",
                              "Reminders at three and seven business days. Persistence is the whole game — "
                              "most replies come on the second touch."))
            cadence_view = gr.Markdown(_CADENCE_PLACEHOLDER, elem_classes=["adv-status"])
        groups.append(g5)

        # --- Step 6: Prep (TIARA) ---
        with gr.Group(visible=False, elem_classes=["adv-bare"]) as g6:
            gr.HTML(_sec_head("Step Seven", "07", "Prepare to listen.",
                              "Five cited TIARA questions so your fifteen minutes land. Curiosity, not a pitch."))
            prep_company = gr.Dropdown(label="Company for the informational", choices=[],
                                       interactive=True, allow_custom_value=True, elem_classes=["adv-field"])
            prep_role = gr.Textbox(label="Role you’re exploring", placeholder="e.g. product management",
                                   max_lines=1, elem_classes=["adv-field"])
            prep_btn = gr.Button("Prepare TIARA questions", variant="primary", elem_classes=["adv-btn", "primary"])
            prep_view = gr.Markdown(_PREP_PLACEHOLDER, elem_classes=["adv-status"])
        groups.append(g6)

        gr.HTML(_colophon_html(), elem_id="adv-colophon")

        # ----- wiring (handlers are module-level for testability) -----
        alumni_csv.change(_on_connect, inputs=[alumni_csv], outputs=[connect_status])

        nav_outputs = groups + rail_buttons + [step]
        for i, button in enumerate(rail_buttons):
            button.click(fn=functools.partial(_nav_updates, i), outputs=nav_outputs)

        source_btn.click(_on_source, inputs=[industry_in, geography_in, function_in],
                         outputs=[source_status, rate_roster, records_state, ratings_json])
        rank_btn.click(_on_rank, inputs=[ratings_json, records_state],
                       outputs=[gate_status, ranked_state, ranked_view, outreach_company, prep_company, draft_btn])
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
        # Authz for every route is Cloud Run + IAP. Defense-in-depth: refuse to serve the app's
        # own source / seeded CSVs via Gradio's /file= route. Uploads live under the system temp
        # dir (not repo_root), so they stay readable.
        blocked_paths=[repo_root],
    )


if __name__ == "__main__":
    launch()
