"""Editorial "ink-on-paper" design system for the Advocate wizard (Gradio).

A magazine-grade, Apple-bar visual language: a Fraunces serif masthead, a hairline
step "ledger", warm near-monochrome paper surfaces, a single oxblood accent, and a
muted-forest affirmative. The Rate step is a custom-rendered roster of hairline rows
with a segmented 1–5 rater (NOT a spreadsheet); the draft reads as a typeset letter.

Exports:
  - advocate_theme()  — a Gradio Base theme so native widgets inherit paper/ink/oxblood.
  - ADVOCATE_HEAD     — <link> tags loading Fraunces / Newsreader / Inter.
  - ADVOCATE_CSS      — the full stylesheet (our custom gr.HTML markup + Gradio chrome).
  - ADVOCATE_JS       — a load-time bridge: clicking a rater writes JSON to a hidden field.

Accessibility: AA-contrast tokens (ink #1c1a17 on paper ~12:1; oxblood #9a2b1e on
paper ~6.4:1), a never-suppressed :focus-visible ring, and prefers-reduced-motion honored.
"""
from __future__ import annotations

import gradio as gr

_ACCENT = gr.themes.colors.red
_NEUTRAL = gr.themes.colors.stone


def advocate_theme() -> gr.themes.Base:
    """A light, warm-paper Base theme so Gradio's own widgets inherit the palette."""
    return gr.themes.Base(
        primary_hue=_ACCENT,
        neutral_hue=_NEUTRAL,
        font=(gr.themes.GoogleFont("Fraunces"), "Georgia", "serif"),
        font_mono=(gr.themes.GoogleFont("Inter"), "ui-sans-serif", "sans-serif"),
    ).set(
        body_background_fill="#f7f4ee",
        body_background_fill_dark="#f7f4ee",
        background_fill_primary="#fdfbf6",
        background_fill_secondary="#f1ede4",
        body_text_color="#1c1a17",
        body_text_color_subdued="#4a463f",
        block_title_text_color="#1c1a17",
        block_label_text_color="#4a463f",
        block_border_color="#e2dccf",
        block_background_fill="#fdfbf6",
        input_background_fill="#fdfbf6",
        input_background_fill_focus="#fdfbf6",
        input_border_color="#e2dccf",
        input_border_color_focus="#9a2b1e",
        button_primary_background_fill="#9a2b1e",
        button_primary_background_fill_hover="#7d2218",
        button_primary_text_color="#fdf6f4",
        button_secondary_background_fill="#fdfbf6",
        button_secondary_background_fill_hover="#f1ede4",
        button_secondary_text_color="#1c1a17",
        button_secondary_border_color="#cfc7b6",
        border_color_accent="#9a2b1e",
    )


# Injected verbatim into <head> — the three families the design is set in.
ADVOCATE_HEAD = (
    '<link rel="preconnect" href="https://fonts.googleapis.com" />'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    'family=Fraunces:ital,opsz,wght@0,9..144,300..600;1,9..144,400&'
    'family=Newsreader:ital,opsz@0,6..72;1,6..72&'
    'family=Inter:wght@400;450;500;600&display=swap" />'
)


# Clicking a rater <button> (rendered inside our gr.HTML) has no Gradio binding, so this
# load-time delegate captures it: it sets the row's data-val, recomputes the {company:score}
# map from the DOM, writes JSON into the hidden #ratings-json field, and fires `input` so
# Gradio syncs it to the backend. Stateless (reads the DOM) so it survives roster re-renders.
# Live count/measure updates use textContent + style only (never innerHTML) — the .c-rated /
# .l-count nodes are pre-rendered server-side, so there is no HTML injection surface.
ADVOCATE_JS = r"""
() => {
  function syncRatings() {
    const map = {};
    document.querySelectorAll('#adv-rate .rater[data-company]').forEach(function (r) {
      const v = r.getAttribute('data-val');
      if (v) map[r.getAttribute('data-company')] = Number(v);
    });
    const field = document.querySelector('#ratings-json textarea, #ratings-json input');
    if (field) {
      field.value = JSON.stringify(map);
      field.dispatchEvent(new Event('input', { bubbles: true }));
    }
    return map;
  }
  function updateProgress(map) {
    const rated = Object.keys(map).length;
    const goal = 10;
    const c = document.querySelector('#adv-rate .c-rated'); if (c) c.textContent = String(rated);
    const lc = document.querySelector('#adv-rate .l-count'); if (lc) lc.textContent = String(rated);
    const m = document.querySelector('#adv-rate .measure > span');
    if (m) m.style.width = Math.min(100, (rated / goal) * 100) + '%';
  }
  document.addEventListener('click', function (e) {
    const btn = e.target.closest('#adv-rate .rater button');
    if (!btn) return;
    const rater = btn.closest('.rater');
    const idx = Array.prototype.indexOf.call(rater.querySelectorAll('button'), btn) + 1;
    if (idx < 1) return;
    rater.classList.remove('empty');
    rater.setAttribute('data-val', String(idx));
    rater.querySelectorAll('button').forEach(function (b, i) {
      b.setAttribute('aria-checked', (i + 1) === idx ? 'true' : 'false');
    });
    const cell = rater.closest('.rate-cell');
    if (cell) {
      cell.classList.add('done');
      const hint = cell.querySelector('.hint');
      if (hint) hint.textContent = idx >= 5 ? 'Top pick' : 'Rated';
    }
    updateProgress(syncRatings());
  });
}
"""


ADVOCATE_CSS = r"""
:root {
  --paper: #f7f4ee; --paper-card: #fdfbf6; --paper-sunk: #f1ede4;
  --ink: #1c1a17; --ink-soft: #4a463f; --ink-faint: #68635c; --ink-ghost: #736e67;
  --rule: #e2dccf; --rule-strong: #cfc7b6;
  --accent: #9a2b1e; --accent-deep: #7d2218; --accent-tint: #f0e3df; --accent-bright: #d8704f;
  --cover-ink: #211b16;
  --affirm: #3f6149; --affirm-tint: #e6ece6;
  --shadow-card: 0 1px 2px rgba(40,33,22,.05), 0 16px 38px -20px rgba(40,33,22,.30);
  --shadow-lift: 0 2px 5px rgba(40,33,22,.06), 0 30px 60px -26px rgba(40,33,22,.36);
  --sheen: inset 0 1px 0 rgba(255,255,255,.8);
  --serif: "Fraunces", Georgia, "Times New Roman", serif;
  --read: "Newsreader", Georgia, serif;
  --sans: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

/* ---------- canvas + centered column ---------- */
body, gradio-app, .gradio-container {
  background: radial-gradient(120% 80% at 50% -8%, #fbf8f2 0%, var(--paper) 55%) fixed !important;
}
.gradio-container {
  width: min(1040px, 100vw) !important;
  margin: 0 auto !important;
  padding: 0 56px 48px !important;
  overflow-x: hidden;
  color: var(--ink);
  font-family: var(--sans);
}
main.fillable, .gradio-container > main { width: 100% !important; max-width: 100% !important; min-width: 0 !important; }
footer { display: none !important; }
::selection { background: var(--accent-tint); color: var(--accent-deep); }

/* a fine, fixed paper grain over the whole canvas — tactile tooth, never blocks input */
.gradio-container::after {
  content: ""; position: fixed; inset: 0; z-index: 2; pointer-events: none; opacity: .05;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Cfilter id='pg'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='2' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23pg)'/%3E%3C/svg%3E");
}

/* neutralize Gradio's default block chrome where we want bare editorial surfaces */
.gradio-container .gap { gap: 0 !important; }
.adv-bare, .adv-bare > .styler { background: transparent !important; border: none !important; box-shadow: none !important; padding: 0 !important; }
/* the rater bridge's backing field — kept in the DOM (so JS can write it) but never shown */
#ratings-json { display: none !important; }

/* ---------- MASTHEAD (dark "cover plate", full column width) ---------- */
/* the full-bleed band (margin:0 -56px) is wider than the gr.HTML wrapper, which defaults to
   overflow-x:auto → a stray horizontal scrollbar. overflow:visible lets it bleed; the centered
   .gradio-container (overflow-x:hidden) clips it at the column edge. */
#adv-masthead { overflow: visible !important; }
/* the masthead is a nav/handler OUTPUT, so Gradio flashes its grey "generating" overlay + a "0.0s"
   timer on it. Suppress that chrome — the agent's state is shown by the seal, not a Gradio spinner. */
#adv-masthead .progress-text { display: none !important; }
#adv-masthead .masthead { margin: 0 -56px; padding: 30px 56px 22px; background: radial-gradient(135% 150% at 26% -32%, rgba(255,238,214,.07) 0%, transparent 58%), linear-gradient(168deg, #2b231b 0%, var(--cover-ink) 60%, #161009 100%); box-shadow: inset 0 1px 0 rgba(255,245,232,.10), inset 0 -1px 0 rgba(0,0,0,.35), 0 14px 30px -20px rgba(20,15,10,.55); }
/* a dateline band, ruled top + bottom in cream hairlines, tracked small caps */
.dateline { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 11px 2px; border-top: 1px solid rgba(247,244,238,.30); border-bottom: 1px solid rgba(247,244,238,.30); font-family: var(--sans); font-size: 11px; font-weight: 600; letter-spacing: .17em; text-transform: uppercase; }
.dateline span { color: rgba(247,244,238,.66); }
.dateline .fleuron { color: var(--accent-bright); font-family: var(--serif); font-size: 21px; letter-spacing: 0; line-height: 1; }
/* the nameplate — plain inline text (no flex), so the leading A never blockifies/displaces */
.nameplate-row { display: flex; align-items: center; justify-content: space-between; gap: 24px; margin: 14px 0 0; }
.wordmark { font-family: var(--serif); font-optical-sizing: auto; font-weight: 450; font-size: clamp(48px, 7vw, 80px); letter-spacing: -.03em; color: var(--paper); line-height: .96; margin: 0; white-space: nowrap; text-shadow: 0 1px 2px rgba(0,0,0,.4); }
.wordmark::first-letter { font-weight: 540; }
.wordmark .dot { color: var(--accent-bright); font-weight: 540; }
/* the wax seal — reversed for the dark plate (cream contents on a bright-oxblood disc) */
.seal { flex: 0 0 auto; width: 96px; height: 96px; filter: drop-shadow(0 3px 9px rgba(0,0,0,.5)); }
.seal-svg { width: 96px; height: 96px; display: block; }
.seal-disc { fill: var(--accent-bright); }
.seal-ringline { fill: none; stroke: rgba(247,244,238,.92); stroke-width: 0.6; opacity: .85; }
.seal-ring { fill: var(--paper); font-family: var(--sans); font-size: 6.5px; font-weight: 600; letter-spacing: 0.7px; }
.seal-mono { fill: var(--paper); font-family: var(--serif); font-optical-sizing: auto; font-size: 40px; font-weight: 500; }
.seal-fleuron { fill: var(--paper); font-family: var(--serif); font-size: 9px; }
.tagline { margin: 12px 0 0; font-family: var(--read); font-size: 18px; line-height: 1.45; color: rgba(247,244,238,.82); max-width: 605px; }
.tagline em { color: var(--accent-bright); font-style: italic; }
.tagline .dropcap { float: left; font-family: var(--serif); font-optical-sizing: auto; font-weight: 430; font-size: 58px; line-height: .78; padding: 6px 11px 0 0; color: var(--accent-bright); text-shadow: 0 1px 2px rgba(0,0,0,.35); }
/* a cream thick + thin double rule closes the cover plate, cleared past the drop cap float */
#adv-masthead .masthead::after { content: ""; display: block; clear: both; height: 3px; margin-top: 16px; border-top: 2px solid var(--paper); border-bottom: 1px solid rgba(247,244,238,.5); }

/* ---------- DOCK — the cover plate compacted to a standing-agent header (steps 1–6) ---------- */
#adv-masthead .masthead.mast-compact { margin: 0 -56px; padding: 0 56px; background: linear-gradient(168deg, #271f19 0%, var(--cover-ink) 70%, #161009 100%); box-shadow: inset 0 -1px 0 rgba(0,0,0,.4), 0 10px 24px -18px rgba(20,15,10,.5); }
#adv-masthead .masthead.mast-compact::after { display: none; }
.dock { display: flex; align-items: center; gap: 16px; min-height: 64px; padding: 11px 0; }
.dock-seal { width: 42px; height: 42px; flex: 0 0 auto; filter: drop-shadow(0 2px 5px rgba(0,0,0,.4)); }
.dock-seal .seal-svg { width: 42px; height: 42px; }
.dock-seal .seal-ring { display: none; }   /* ring micro-type is illegible at 42px — disc + monogram only */
.dock-id { display: flex; align-items: baseline; gap: 14px; min-width: 0; }
.dock-name { font-family: var(--serif); font-optical-sizing: auto; font-weight: 480; font-size: 22px; letter-spacing: -.02em; color: var(--paper); line-height: 1; }
.dock-name .dot { color: var(--accent-bright); }
.dock-brief { font-family: var(--read); font-style: italic; font-size: 13.5px; color: rgba(247,244,238,.64); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.dock-chron { margin-left: auto; flex: 0 0 auto; font-family: var(--sans); font-size: 10.5px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; color: rgba(247,244,238,.55); }
/* the agent AT WORK: a slow oxblood arc sweeps the seal during a grounded call; the dock narrates it */
.dock-seal { position: relative; }
.dock-seal[data-state="working"]::after { content: ""; position: absolute; inset: -5px; border-radius: 50%; border: 1.6px solid transparent; border-top-color: var(--accent-bright); animation: dock-sweep .9s linear infinite; }
@keyframes dock-sweep { to { transform: rotate(360deg); } }
.dock-status { font-family: var(--read); font-style: italic; font-size: 13.5px; color: rgba(247,244,238,.84); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
@media (prefers-reduced-motion: reduce) {
  .dock-seal[data-state="working"]::after { animation: none; border: 1.6px solid var(--accent-bright); opacity: .5; }
}

/* ---------- STEP LEDGER (the 7 nav buttons, restyled) ---------- */
#rail {
  counter-reset: advstep 0;
  display: flex !important; gap: 0 !important; flex-wrap: nowrap !important;
  border-bottom: 1px solid var(--rule); padding: 20px 0 0 !important; margin: 0 0 6px !important; overflow-x: auto;
}
#rail.unequal-height { align-items: stretch; }
#rail > * { flex: 1 1 0 !important; min-width: 0 !important; }
.rail-btn {
  counter-increment: advstep;
  display: flex !important; flex-direction: column; align-items: flex-start !important; gap: 5px;
  background: transparent !important; border: none !important; box-shadow: none !important;
  border-radius: 0 !important; border-bottom: 2.5px solid transparent !important;
  padding: 0 14px 15px 0 !important; min-width: 0 !important;
  text-align: left !important; white-space: nowrap; cursor: pointer; transition: border-color .2s, color .2s;
  font-family: var(--sans) !important; font-size: 14px !important; font-weight: 500 !important; color: var(--ink-ghost) !important; letter-spacing: -.01em;
}
.rail-btn::before {
  content: counter(advstep, decimal-leading-zero);
  font-family: var(--serif); font-size: 13px; font-weight: 500; letter-spacing: .02em; color: var(--ink-ghost); font-feature-settings: "tnum" 1;
}
.rail-btn:hover { color: var(--ink-soft) !important; }
.rail-btn.primary { color: var(--ink) !important; font-weight: 600 !important; border-bottom-color: var(--accent) !important; }
.rail-btn.primary::before { color: var(--accent); }
.rail-btn.step-done { color: var(--ink-soft) !important; border-bottom-color: var(--rule-strong) !important; }
.rail-btn.step-done::before { color: var(--ink-faint); }

/* ---------- EDITORIAL SECTION HEADS ---------- */
.sec-head { display: grid; grid-template-columns: 140px 1fr; gap: 0; align-items: start; margin: 30px 0 22px; }
.sec-index { font-family: var(--serif); font-optical-sizing: auto; font-size: 68px; font-weight: 380; color: var(--accent); line-height: .8; letter-spacing: -.015em; padding-top: 0; text-shadow: 0 1px 0 rgba(255,255,255,.5); }
.sec-index .rule-no { display: block; font-family: var(--sans); font-size: 10px; font-weight: 600; letter-spacing: .2em; text-transform: uppercase; color: var(--ink-faint); margin-bottom: 11px; }
.sec-title { font-family: var(--serif); font-optical-sizing: auto; font-weight: 420; font-size: 36px; line-height: 1.06; letter-spacing: -.02em; color: var(--ink); margin: 0; }
.sec-sub { margin-top: 9px; font-family: var(--read); font-size: 16px; line-height: 1.5; color: var(--ink-soft); max-width: 560px; }

/* ---------- CONNECT = the cover's "brief": a slim prompt + a 2×2 field grid ---------- */
.brief-prompt { font-family: var(--read); font-size: 16px; color: var(--ink-soft); margin: 20px 0 14px; }
.brief-prompt .bp-eyebrow { font-family: var(--sans); font-size: 10px; font-weight: 600; letter-spacing: .2em; text-transform: uppercase; color: var(--accent); margin-right: 14px; }
/* Gradio's gr.Row is display:grid — set explicit equal columns for a true side-by-side 2×2 */
#adv-connect-panel .brief-row { display: grid !important; grid-template-columns: 1fr 1fr !important; gap: 28px !important; }
#adv-connect-panel .brief-row > * { min-width: 0 !important; }
#adv-connect-panel { background: var(--paper-card) !important; border: 1px solid var(--rule) !important; border-radius: 10px !important; box-shadow: var(--shadow-card), var(--sheen) !important; padding: 8px 18px !important; overflow: hidden; }
#adv-connect-panel .block, #adv-connect-panel .form, #adv-connect-panel > .styler { background: transparent !important; border: none !important; box-shadow: none !important; }
.adv-field, .adv-field > .styler, .adv-field .block, .adv-field .form { background: transparent !important; border: none !important; box-shadow: none !important; }
.adv-field label > span, .adv-field span[data-testid="block-info"] { font-family: var(--sans) !important; font-size: 12px !important; font-weight: 600 !important; letter-spacing: .04em !important; color: var(--ink-soft) !important; margin-bottom: 8px !important; }
.adv-field input[type="text"], .adv-field textarea {
  background: transparent !important; border: none !important; border-radius: 0 !important;
  border-bottom: 1.5px solid var(--rule-strong) !important; box-shadow: none !important;
  font-family: var(--serif) !important; font-weight: 380 !important; font-size: 19px !important;
  letter-spacing: -.01em !important; color: var(--ink) !important; padding: 2px 0 9px !important; transition: border-color .3s cubic-bezier(.2,.7,.2,1);
}
.adv-field input::placeholder, .adv-field textarea::placeholder { color: var(--ink-ghost) !important; font-style: italic; }
.adv-field input:focus, .adv-field textarea:focus { border-bottom-color: var(--accent) !important; outline: none !important; }
/* the alumni-CSV upload as a single slim editorial line (gr.UploadButton, not a tall dropzone) */
#adv-upload.adv-upload-btn { background: var(--paper-sunk) !important; color: var(--ink-faint) !important; border: 1px dashed var(--rule-strong) !important; border-radius: 8px !important; box-shadow: none !important; font-family: var(--read) !important; font-style: italic !important; font-size: 13.5px !important; font-weight: 400 !important; letter-spacing: 0 !important; padding: 11px 16px !important; min-height: 0 !important; height: auto !important; width: 100% !important; justify-content: flex-start !important; margin: 6px 0 2px !important; transition: border-color .2s, color .2s !important; }
#adv-upload.adv-upload-btn:hover { border-color: var(--ink-faint) !important; color: var(--ink-soft) !important; }

/* ---------- RATE — the hero roster ---------- */
.rate-progress { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; padding: 0 2px 18px; border-bottom: 1.5px solid var(--ink); margin-bottom: 4px; }
.rate-progress .count { font-family: var(--serif); font-weight: 380; font-size: 34px; letter-spacing: -.02em; color: var(--ink); line-height: 1; font-feature-settings: "tnum" 1; }
.rate-progress .count b { font-weight: 560; color: var(--accent); }
.rate-progress .count .of { color: var(--ink-ghost); font-weight: 380; }
.rate-progress .unlock { text-align: right; max-width: 340px; }
.rate-progress .unlock .line { font-family: var(--read); font-size: 15px; line-height: 1.4; color: var(--ink-soft); }
.rate-progress .unlock .line b { color: var(--ink); font-weight: 600; }
.measure { margin-top: 10px; height: 3px; background: var(--rule); border-radius: 2px; overflow: hidden; }
.measure > span { display: block; height: 100%; width: 0; background: var(--accent); border-radius: 2px; transition: width .4s cubic-bezier(.2,.7,.2,1); }

.roster { padding: 0; }
/* the ~40-row Rate roster scrolls INTERNALLY so the page itself never scrolls (no-scroll shell);
   the progress masthead + dock stay pinned above it. Rank's 5-row list is short, so it's unscoped. */
#adv-rate .roster { max-height: calc(100vh - 358px); overflow-y: auto; scrollbar-width: thin; scrollbar-color: var(--rule-strong) transparent; padding-right: 6px; -webkit-overflow-scrolling: touch; }
#adv-rate .roster::-webkit-scrollbar { width: 7px; }
#adv-rate .roster::-webkit-scrollbar-thumb { background: var(--rule-strong); border-radius: 4px; }
.row { display: grid; grid-template-columns: 36px 1fr auto; align-items: center; gap: 22px; padding: 22px 4px; border-bottom: 1px solid var(--rule); transition: background .18s; }
.row:last-child { border-bottom: none; }
.row .rank { font-family: var(--serif); font-optical-sizing: auto; font-size: 22px; font-weight: 420; color: var(--ink-faint); text-align: right; }
.row .body { min-width: 0; }
.row .co { font-family: var(--serif); font-optical-sizing: auto; font-weight: 470; font-size: 25px; letter-spacing: -.02em; color: var(--ink); line-height: 1.1; }
.row .sector { font-family: var(--read); font-size: 15px; color: var(--ink-faint); margin-top: 2px; }
.signals { display: flex; align-items: center; gap: 14px; margin-top: 11px; flex-wrap: wrap; }
.sig { display: inline-flex; align-items: baseline; gap: 7px; font-size: 11px; letter-spacing: .12em; text-transform: uppercase; color: var(--ink-faint); font-weight: 600; }
.sig .val { font-family: var(--read); font-style: normal; font-size: 13px; letter-spacing: 0; text-transform: none; font-weight: 500; color: var(--ink-soft); }
.bars { display: inline-flex; gap: 3px; align-items: center; }
.bars i { width: 14px; height: 4px; border-radius: 1px; background: var(--rule-strong); display: inline-block; }
.bars.s-strong i:nth-child(-n+3) { background: var(--ink-soft); }
.bars.s-some i:nth-child(-n+2) { background: var(--ink-soft); }
.bars.s-few i:nth-child(-n+1) { background: var(--ink-soft); }
.alum { display: inline-flex; align-items: baseline; gap: 7px; font-size: 11px; letter-spacing: .12em; text-transform: uppercase; font-weight: 600; }
.alum.yes { color: var(--affirm); }
.alum.no { color: var(--ink-ghost); }
.alum .who { font-family: var(--read); font-style: italic; font-weight: 400; font-size: 13.5px; letter-spacing: 0; text-transform: none; }
/* the agent's receipt — why this employer surfaced + which LAMP lens(es). Shown only when grounded. */
.receipt { margin-top: 9px; display: flex; align-items: baseline; gap: 11px; max-width: 560px; }
.receipt .r-lens { flex: 0 0 auto; font-family: var(--sans); font-size: 9.5px; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; color: var(--accent); white-space: nowrap; padding-top: 1px; }
.receipt .r-why { font-family: var(--read); font-style: italic; font-size: 13px; line-height: 1.42; color: var(--ink-faint); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }

.rater { display: inline-flex; align-items: stretch; border: 1px solid var(--rule-strong); border-radius: 9px; overflow: hidden; background: var(--paper-card); box-shadow: inset 0 1px 0 rgba(255,255,255,.6); }
.rater button { appearance: none; border: none; background: transparent; border-left: 1px solid var(--rule); width: 38px; height: 42px; font-family: var(--serif); font-weight: 440; font-size: 17px; color: var(--ink-faint); cursor: pointer; font-feature-settings: "tnum" 1; transition: background .15s, color .15s; }
.rater button:first-child { border-left: none; }
.rater button:hover { background: var(--paper-sunk); color: var(--ink); }
.rater[data-val="5"] button:nth-child(-n+5),
.rater[data-val="4"] button:nth-child(-n+4),
.rater[data-val="3"] button:nth-child(-n+3),
.rater[data-val="2"] button:nth-child(-n+2),
.rater[data-val="1"] button:nth-child(-n+1) { color: #fff; background: var(--accent); border-left-color: var(--accent-deep); font-weight: 500; }
.rater[data-val] button:first-child { border-left: none; }
.rater.empty { border-color: var(--accent); box-shadow: inset 0 1px 0 rgba(255,255,255,.6), 0 0 0 3px var(--accent-tint); }
.rater.empty button { color: var(--accent-deep); }
.row:has(.rater.empty) { background: linear-gradient(90deg, rgba(154,43,30,.045), transparent 70%); }
.rate-cell { display: flex; flex-direction: column; align-items: flex-end; gap: 7px; }
.rate-cell .hint { font-family: var(--read); font-style: italic; font-size: 12.5px; color: var(--ink-ghost); }
.rate-cell.done .hint { color: var(--affirm); font-style: normal; font-weight: 500; font-family: var(--sans); font-size: 11px; letter-spacing: .1em; text-transform: uppercase; }
.roster-empty { font-family: var(--read); font-style: italic; font-size: 16px; color: var(--ink-faint); padding: 34px 4px; }

/* ---------- RANK — active five (read-only editorial list) ---------- */
.ranked .row { grid-template-columns: 30px 1fr auto; }
.ranked .badge { font-family: var(--sans); font-size: 11px; letter-spacing: .1em; text-transform: uppercase; font-weight: 600; color: var(--accent); }
.ranked .mot { font-family: var(--serif); font-size: 26px; font-weight: 470; color: var(--ink); line-height: 1; font-feature-settings: "tnum" 1; text-align: right; }
.ranked .mot .lbl { display: block; font-family: var(--sans); font-size: 10px; letter-spacing: .12em; text-transform: uppercase; color: var(--ink-ghost); font-weight: 600; margin-top: 5px; }
.lenses { margin-top: 8px; display: flex; gap: 7px; flex-wrap: wrap; }
.lens { font-family: var(--sans); font-size: 10.5px; letter-spacing: .08em; text-transform: uppercase; font-weight: 600; color: var(--ink-faint); border: 1px solid var(--rule-strong); border-radius: 999px; padding: 3px 9px; }

/* ---------- OUTREACH — the letter ---------- */
#adv-draft-head .draft-head { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; padding: 18px 24px; border: 1px solid var(--rule); border-bottom: none; border-radius: 12px 12px 0 0; background: var(--paper-sunk); }
.draft-head .to { font-family: var(--read); font-size: 15px; color: var(--ink-soft); }
.draft-head .to b { color: var(--ink); font-weight: 600; font-family: var(--sans); font-size: 14px; }
.draft-head .editable { font-size: 11px; letter-spacing: .14em; text-transform: uppercase; color: var(--ink-faint); font-weight: 600; white-space: nowrap; }
#adv-letter { background: var(--paper-card) !important; border: 1px solid var(--rule) !important; border-top: none !important; border-radius: 0 0 12px 12px !important; box-shadow: var(--shadow-lift), var(--sheen) !important; }
#adv-letter textarea { background: transparent !important; border: none !important; box-shadow: none !important; font-family: var(--read) !important; font-size: 18px !important; line-height: 1.62 !important; color: var(--ink) !important; padding: 26px 32px !important; letter-spacing: -.003em; }
#adv-letter textarea::placeholder { color: var(--ink-ghost) !important; font-style: italic; }
.reassure { display: inline-flex; align-items: center; gap: 9px; font-family: var(--read); font-style: italic; font-size: 14px; color: var(--ink-soft); padding: 16px 2px 0; }
.reassure .seal { font-family: var(--serif); font-weight: 560; font-style: normal; color: var(--accent); font-size: 13px; border: 1.5px solid var(--accent); border-radius: 50%; width: 22px; height: 22px; display: inline-flex; align-items: center; justify-content: center; flex: 0 0 auto; }

/* ---------- BUTTONS (Gradio, restyled) ---------- */
.adv-btn { width: fit-content !important; min-width: 0 !important; }
.adv-btn button, button.adv-btn {
  font-family: var(--sans) !important; font-size: 14px !important; font-weight: 600 !important; letter-spacing: .005em !important;
  border-radius: 8px !important; padding: 11px 22px !important; min-width: 0 !important;
  width: fit-content !important; white-space: nowrap !important;
  box-shadow: none !important; transition: transform .12s, box-shadow .2s, background .2s, border-color .2s !important;
}
.adv-btn.primary button, button.adv-btn.primary { background: var(--accent) !important; color: #fdf6f4 !important; border: 1px solid transparent !important; box-shadow: 0 1px 2px rgba(122,34,24,.3), 0 8px 18px -10px rgba(122,34,24,.5) !important; }
.adv-btn.primary button:hover { background: var(--accent-deep) !important; transform: translateY(-1px); }
.adv-btn.secondary button, button.adv-btn.secondary { background: var(--paper-card) !important; color: var(--ink) !important; border: 1px solid var(--rule-strong) !important; }
.adv-btn.secondary button:hover { border-color: var(--ink-soft) !important; transform: translateY(-1px); }
.adv-btn button[disabled] { background: var(--paper-sunk) !important; color: var(--ink-ghost) !important; border-color: var(--rule) !important; box-shadow: none !important; cursor: not-allowed !important; transform: none !important; }
/* the Approve / Regenerate / Discard row reads as one tight, left-aligned group.
   Gradio's Row is display:grid, which distributes columns unevenly — force flex. */
#action-row { display: flex !important; gap: 10px !important; justify-content: flex-start !important; margin-top: 12px; }
#action-row > * { flex: 0 0 auto !important; min-width: 0 !important; width: fit-content !important; }

/* editorial dropdowns (Reach out to / Prep company) — paper, hairline, no grey block */
.adv-bare .form { background: transparent !important; border: none !important; box-shadow: none !important; }
.adv-field .wrap, .adv-field .secondary-wrap, .adv-field .container { background: transparent !important; }
.adv-field input[role="listbox"], .adv-field .wrap-inner {
  background: var(--paper-card) !important; border: 1px solid var(--rule-strong) !important; border-radius: 8px !important;
  font-family: var(--read) !important; font-size: 16px !important; color: var(--ink) !important;
}
.adv-field ul.options { background: var(--paper-card) !important; border: 1px solid var(--rule-strong) !important; font-family: var(--read) !important; }
.adv-field ul.options li.item.selected, .adv-field ul.options li.item:hover { background: var(--accent-tint) !important; color: var(--accent-deep) !important; }

/* status / markdown copy */
.adv-status p, .adv-status { font-family: var(--read) !important; color: var(--ink-soft) !important; font-size: 15px !important; }
.adv-status b, .adv-status strong { color: var(--ink) !important; font-family: var(--sans) !important; }

/* ---------- COLOPHON ---------- */
#adv-colophon .colophon { margin-top: 22px; padding-top: 14px; border-top: 1.5px solid var(--ink); display: flex; justify-content: space-between; align-items: baseline; font-size: 12px; color: var(--ink-faint); letter-spacing: .02em; }
.colophon .mark { font-family: var(--serif); font-weight: 500; color: var(--ink-soft); }
.colophon .mark .dot { color: var(--accent); }

/* ---------- a11y + responsive ---------- */
*:focus-visible { outline: 2.5px solid var(--accent) !important; outline-offset: 2px !important; border-radius: 3px; }
@media (max-width: 880px) {
  .gradio-container { padding: 0 24px 80px !important; }
  .sec-head { grid-template-columns: 1fr; gap: 4px; }
  .sec-index { padding-top: 0; }
  .row { grid-template-columns: 24px 1fr; }
  .rate-cell { grid-column: 1 / -1; align-items: flex-start; margin-top: 10px; }
  /* on mobile, don't full-bleed the cover band — keep it within the column, cleanly aligned */
  #adv-masthead .masthead { margin: 0; padding: 28px 24px 24px; border-radius: 4px; }
  .wordmark { font-size: 38px; }
  .seal, .seal-svg { width: 60px; height: 60px; }
  .nameplate-row { gap: 14px; }
  .sec-index { font-size: 44px; }
  .sec-title { font-size: 27px; }
  /* the ledger scrolls horizontally on mobile — steps keep natural width, never collide */
  #rail > * { flex: 0 0 auto !important; }
  .rail-btn { padding-right: 22px !important; }
  .rate-progress { flex-direction: column; align-items: flex-start; gap: 12px; }
  .rate-progress .unlock { text-align: left; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: .001ms !important; transition-duration: .001ms !important; }
}

/* oldstyle figures + ligatures on the serif display type — numerals set like proper type.
   Placed last so it overrides the earlier tabular (tnum) settings on these elements. */
.wordmark, .sec-index, .sec-index .rule-no, .rail-btn::before, .ranked .mot, .row .rank { font-feature-settings: "onum" 1, "pnum" 1, "liga" 1, "calt" 1; }
"""
