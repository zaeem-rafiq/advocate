"""Thin HTTP client for the deployed Advocate ADK service + event parsing.

Talks to the Cloud Run FastAPI surface that `advocate/app.py` serves
(`get_fast_api_app`): create a session, then POST `/run` and read back the
agent's events. Nothing here knows about pytest — the budget guard is injected
(duck-typed) so this module stays importable and unit-reasonable on its own.

Two error classes draw the flaky/failing line the suite reports on:
- `FlakyTransport` — a timeout, connection drop, 429, or 5xx that survived the
  retry budget. This is infrastructure noise, NOT a product bug.
- `AdkHttpError` — a 4xx (other than 429). The request itself was wrong; that is
  a real contract/usage failure and is raised immediately, never retried.
"""
from __future__ import annotations

import os
import subprocess
import time
from typing import Any, Callable, Dict, Iterable, List, Optional

import httpx

DEFAULT_BASE_URL = "https://advocate-964730889018.us-central1.run.app"
DEFAULT_APP = "advocate_app"


class FlakyTransport(Exception):
    """Transport-level failure that outlived the retry budget (treat as flaky)."""


class AdkHttpError(Exception):
    """A non-retryable 4xx from the service (a real request/contract error)."""


# ---------------------------------------------------------------------------
# Identity-token resolution: env override first (CI), gcloud fallback (local).
# ---------------------------------------------------------------------------
def resolve_id_token() -> str:
    """Return a Cloud Run identity token.

    Prefers `ADVOCATE_E2E_ID_TOKEN` (CI injects it); otherwise shells out to
    `gcloud auth print-identity-token` (the dev's Application Default creds),
    mirroring the README's documented call exactly.
    """
    injected = os.environ.get("ADVOCATE_E2E_ID_TOKEN")
    if injected and injected.strip():
        return injected.strip()
    try:
        proc = subprocess.run(
            ["gcloud", "auth", "print-identity-token"],
            capture_output=True, text=True, timeout=30,
        )
    except FileNotFoundError as exc:  # gcloud not installed and no token injected
        raise RuntimeError(
            "No identity token available: set ADVOCATE_E2E_ID_TOKEN or install gcloud."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("gcloud auth print-identity-token timed out") from exc
    if proc.returncode != 0:
        raise RuntimeError(
            "gcloud auth print-identity-token failed "
            f"(rc={proc.returncode}): {proc.stderr.strip() or 'no stderr'}"
        )
    token = proc.stdout.strip()
    if not token:
        raise RuntimeError("gcloud returned an empty identity token")
    return token


class AdkClient:
    """Minimal client over the ADK run/session API with retry + budget hooks."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        app_name: str = DEFAULT_APP,
        *,
        token_provider: Callable[[], str] = resolve_id_token,
        timeout: float = 180.0,
        max_retries: int = 3,
        budget: Any = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.app_name = app_name
        self._token_provider = token_provider
        self._token: Optional[str] = None
        self._http = httpx.Client(timeout=timeout)
        self.max_retries = max_retries
        self.budget = budget
        self._sleep = sleep

    # -- lifecycle ---------------------------------------------------------
    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "AdkClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- auth --------------------------------------------------------------
    def _headers(self) -> Dict[str, str]:
        if self._token is None:
            self._token = self._token_provider()
        # Content-Type is REQUIRED by the ADK session endpoint (422 without it).
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    def _refresh_token(self) -> None:
        self._token = self._token_provider()

    # -- transport ---------------------------------------------------------
    def _post(self, path: str, body: Dict[str, Any]) -> httpx.Response:
        url = f"{self.base_url}{path}"
        last: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._http.post(url, json=body, headers=self._headers())
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last = exc
                self._backoff(attempt)
                continue
            if resp.status_code == 401 and attempt == 0:
                # Token may have expired between suite construction and now.
                self._refresh_token()
                continue
            if resp.status_code == 429 or 500 <= resp.status_code < 600:
                last = FlakyTransport(f"{resp.status_code} on {path}: {resp.text[:200]}")
                self._backoff(attempt)
                continue
            if resp.status_code >= 400:
                raise AdkHttpError(f"{resp.status_code} on {path}: {resp.text[:400]}")
            return resp
        raise FlakyTransport(
            f"{path} failed after {self.max_retries} retries; last error: {last}"
        )

    def _backoff(self, attempt: int) -> None:
        self._sleep(min(1.5 * (2 ** attempt), 12.0))

    # -- API ---------------------------------------------------------------
    def create_session(
        self, user_id: str, session_id: str, state: Optional[Dict[str, Any]] = None
    ) -> None:
        """Create a session. An already-existing session id is treated as OK."""
        path = f"/apps/{self.app_name}/users/{user_id}/sessions/{session_id}"
        try:
            self._post(path, state or {})
        except AdkHttpError as exc:
            # A 409/400 "already exists" is benign for our reuse-the-session flow.
            if "exist" in str(exc).lower() or str(exc).startswith("409"):
                return
            raise

    def run(self, user_id: str, session_id: str, text: str) -> List[Dict[str, Any]]:
        """Send one user turn and return the agent's events (list of dicts).

        Charges the injected budget for every grounded tool call observed, so the
        suite fails fast before blowing the cost ceiling.
        """
        body = {
            "app_name": self.app_name,
            "user_id": user_id,
            "session_id": session_id,
            "new_message": {"role": "user", "parts": [{"text": text}]},
        }
        resp = self._post("/run", body)
        events = _coerce_events(resp.json())
        if self.budget is not None:
            self.budget.charge_run(events)
        return events

    def new_session(self, user_id: str, prefix: str = "s") -> str:
        """Mint a unique session id, create it, and return it."""
        import uuid

        sid = f"{prefix}-{uuid.uuid4().hex[:10]}"
        self.create_session(user_id, sid)
        return sid

    def run_until_tool(
        self,
        user_id: str,
        session_id: str,
        text: str,
        tool_name: str,
        *,
        retries: int = 1,
        nudge: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Run a turn and ensure `tool_name` fired; re-nudge up to `retries` times.

        A tool that never fires after the nudges is an elicitation flake, surfaced
        as AssertionError by the caller's `require_tool_response`. Re-tries past the
        first attempt print a [FLAKY-RETRY] line so the console separates
        "passed first try" from "passed only after a retry".
        """
        events = self.run(user_id, session_id, text)
        if tool_responses(events, tool_name):
            return events
        followup = nudge or f"Please call the {tool_name} tool now to proceed."
        for attempt in range(1, retries + 1):
            print(f"[FLAKY-RETRY] {tool_name} not called on attempt {attempt}; re-nudging.")
            events = self.run(user_id, session_id, followup)
            if tool_responses(events, tool_name):
                return events
        return events  # caller asserts; absence becomes a clear failure message


# ---------------------------------------------------------------------------
# Event parsing — robust to camelCase/snake_case and the {'result': ...} wrap.
# ADK serializes google-genai Parts; field spelling varies by version, so we
# accept both and normalize.
# ---------------------------------------------------------------------------
def _coerce_events(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("events", "result", "data"):
            if isinstance(payload.get(key), list):
                return payload[key]
    raise AdkHttpError(f"Unexpected /run payload shape: {type(payload).__name__}")


def _iter_parts(events: Iterable[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    for ev in events:
        content = ev.get("content") or {}
        for part in content.get("parts") or []:
            if isinstance(part, dict):
                yield part


def _function_response(part: Dict[str, Any]):
    fr = part.get("functionResponse") or part.get("function_response")
    if not isinstance(fr, dict):
        return None
    name = fr.get("name")
    response = fr.get("response")
    # ADK wraps a non-dict tool return as {"result": value}; unwrap that single key.
    if isinstance(response, dict) and set(response.keys()) == {"result"}:
        response = response["result"]
    return name, response


def _function_call(part: Dict[str, Any]):
    fc = part.get("functionCall") or part.get("function_call")
    if not isinstance(fc, dict):
        return None
    return fc.get("name"), (fc.get("args") or {})


def tool_responses(events: Iterable[Dict[str, Any]], name: Optional[str] = None) -> List[Any]:
    """All function-response payloads (optionally filtered to one tool name)."""
    out: List[Any] = []
    for part in _iter_parts(events):
        parsed = _function_response(part)
        if parsed and (name is None or parsed[0] == name):
            out.append(parsed[1])
    return out


def function_call_names(events: Iterable[Dict[str, Any]]) -> List[str]:
    """Names of every tool the agent *called* this turn (for budget accounting)."""
    names: List[str] = []
    for part in _iter_parts(events):
        parsed = _function_call(part)
        if parsed and parsed[0]:
            names.append(parsed[0])
    return names


def final_text(events: Iterable[Dict[str, Any]]) -> str:
    """Concatenated text parts across the turn (the agent's prose to the user)."""
    chunks: List[str] = []
    for part in _iter_parts(events):
        text = part.get("text")
        if isinstance(text, str) and text.strip():
            chunks.append(text.strip())
    return "\n".join(chunks)


def require_tool_response(events: Iterable[Dict[str, Any]], name: str) -> Any:
    """Return the (single) response payload for `name`, asserting it fired.

    Raises AssertionError with the agent's prose when the tool never ran, so a
    failure message shows what the agent did instead of calling the tool.
    """
    events = list(events)
    matches = tool_responses(events, name)
    if not matches:
        called = function_call_names(events) or ["<none>"]
        raise AssertionError(
            f"Expected tool {name!r} to be called, but it was not. "
            f"Tools called: {called}. Agent said: {final_text(events)[:300]!r}"
        )
    return matches[-1]
