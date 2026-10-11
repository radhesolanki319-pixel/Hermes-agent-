"""Turn context, budgeting, and execution telemetry for Hermes Core."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Callable, Dict, List, Optional


@dataclass
class TurnBudget:
    """Manages iteration budgets and token caps for an agent turn."""
    max_iterations: int = 25
    remaining_iterations: int = 25
    max_tokens: Optional[int] = None
    grace_calls_allowed: int = 1
    grace_calls_used: int = 0

    def can_continue(self) -> bool:
        if self.remaining_iterations > 0:
            return True
        return self.grace_calls_used < self.grace_calls_allowed

    def consume_iteration(self) -> None:
        if self.remaining_iterations > 0:
            self.remaining_iterations -= 1
        else:
            self.grace_calls_used += 1


@dataclass
class TurnTelemetry:
    """Tracks timing and token metrics for a single turn."""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0
    tool_calls_count: int = 0
    api_calls_count: int = 0

    @property
    def duration_seconds(self) -> float:
        end = self.end_time or time.time()
        return max(0.0, end - self.start_time)


class TurnContext:
    """Context object passing state between turn execution phases."""

    def __init__(
        self,
        session_id: str,
        turn_index: int = 0,
        budget: Optional[TurnBudget] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
    ):
        self.session_id = session_id
        self.turn_index = turn_index
        self.budget = budget or TurnBudget()
        self.stream_callback = stream_callback
        self.telemetry = TurnTelemetry()
        self.tool_results: List[Dict[str, Any]] = []
        self.interrupted: bool = False
        self.final_response: Optional[str] = None

    def emit_stream(self, token: str) -> None:
        if self.stream_callback:
            self.stream_callback(token)

    def mark_interrupted(self) -> None:
        self.interrupted = True
