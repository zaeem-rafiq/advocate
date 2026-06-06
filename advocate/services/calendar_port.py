"""Calendar port + a draft-only in-memory fallback.

The agent NEVER sends email, but it does create calendar reminders. To keep the
demo robust if Google Calendar auth is unstable, the cadence works against this
port; InMemoryCalendar records reminders locally (the draft-only fallback) and is
also the unit-test double. A Google Calendar (MCP) adapter can implement the same
port without changing the scheduler.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import List


@dataclass(frozen=True)
class CalendarEvent:
    """A created reminder."""

    event_id: str
    summary: str
    due_date: date
    description: str = ""


class CalendarPort(ABC):
    """Boundary for creating calendar reminders."""

    @abstractmethod
    def create_reminder(self, summary: str, due_date: date, description: str = "") -> CalendarEvent:
        """Create a reminder and return the resulting event (with an id)."""


class InMemoryCalendar(CalendarPort):
    """Draft-only fallback: records reminders in memory, performs no external call."""

    def __init__(self) -> None:
        self.events: List[CalendarEvent] = []

    def create_reminder(self, summary: str, due_date: date, description: str = "") -> CalendarEvent:
        event = CalendarEvent(
            event_id=f"mem-{len(self.events) + 1}",
            summary=summary,
            due_date=due_date,
            description=description,
        )
        self.events.append(event)
        return event
