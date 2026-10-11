"""Dual-Guard Interrupt and Real-Time Steering Control Bus for Hermes Core."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("hermes_core.interrupt")


class ApprovalGate:
    """Thread-safe gate allowing sensitive tool executions to pause and await explicit Boss confirmation."""

    def __init__(self, token: str, action_description: str, timeout_seconds: float = 60.0):
        self.token = token
        self.action_description = action_description
        self.timeout_seconds = timeout_seconds
        self._event = threading.Event()
        self._approved: Optional[bool] = None
        self._reason: Optional[str] = None

    def wait(self) -> bool:
        """Wait synchronously for user decision or timeout. Returns True if approved."""
        signaled = self._event.wait(timeout=self.timeout_seconds)
        if not signaled:
            self._approved = False
            self._reason = "Timeout waiting for user approval"
            return False
        return bool(self._approved)

    def resolve(self, approved: bool, reason: Optional[str] = None) -> None:
        """Resolve the gate with approval or denial."""
        self._approved = approved
        self._reason = reason or ("Approved by user" if approved else "Denied by user")
        self._event.set()

    @property
    def is_resolved(self) -> bool:
        return self._event.is_set()

    @property
    def reason(self) -> Optional[str]:
        return self._reason


class InterruptBus:
    """Dual-guard message router and real-time control bus."""

    def __init__(self):
        self._lock = threading.RLock()
        self._active_contexts: Dict[str, Any] = {}
        self._pending_queues: Dict[str, List[str]] = {}
        self._approval_gates: Dict[str, ApprovalGate] = {}

    def register_active_turn(self, session_id: str, context: Any) -> None:
        """Register active session context for real-time interrupt routing."""
        with self._lock:
            self._active_contexts[session_id] = context
            if session_id not in self._pending_queues:
                self._pending_queues[session_id] = []

    def unregister_active_turn(self, session_id: str) -> None:
        """Unregister active session when turn completes."""
        with self._lock:
            self._active_contexts.pop(session_id, None)

    def is_session_active(self, session_id: str) -> bool:
        with self._lock:
            return session_id in self._active_contexts

    def create_approval_gate(self, token: str, action_description: str, timeout: float = 60.0) -> ApprovalGate:
        """Create and register a pending approval gate."""
        with self._lock:
            gate = ApprovalGate(token=token, action_description=action_description, timeout_seconds=timeout)
            self._approval_gates[token] = gate
            return gate

    def dispatch_inbound_message(self, session_id: str, message: str) -> Dict[str, Any]:
        """Dispatch inbound message through the Dual-Guard pipeline.
        
        Guard 1 (Runner Control Interceptor):
          - `/stop`: Immediate execution halt.
          - `/approve <token>`: Grants permission on gate.
          - `/deny <token>`: Rejects permission on gate.
        
        Guard 2 (Session Queue):
          - If session is currently executing, enqueue for next turn.
          - If session is idle, admit immediately.
        """
        trimmed = message.strip()
        parts = trimmed.split(maxsplit=1)
        command = parts[0].lower() if parts else ""

        # --- GUARD 1: Control Command Interception (Bypasses Session Queue) ---
        if command in ("/stop", "/cancel", "/halt"):
            with self._lock:
                ctx = self._active_contexts.get(session_id)
                if ctx and hasattr(ctx, "mark_interrupted"):
                    ctx.mark_interrupted()
                    logger.info(f"Session {session_id} marked interrupted via {command}")
                    return {
                        "status": "interrupted",
                        "admitted": True,
                        "bypassed_queue": True,
                        "message": "Active turn interrupted successfully.",
                    }
                return {
                    "status": "idle",
                    "admitted": True,
                    "bypassed_queue": True,
                    "message": "No active turn to interrupt.",
                }

        if command == "/approve":
            token = parts[1].strip() if len(parts) > 1 else ""
            with self._lock:
                gate = self._approval_gates.get(token)
                if gate:
                    gate.resolve(approved=True)
                    self._approval_gates.pop(token, None)
                    return {
                        "status": "approved",
                        "token": token,
                        "admitted": True,
                        "bypassed_queue": True,
                        "message": f"Approved action '{gate.action_description}'.",
                    }
                return {
                    "status": "not_found",
                    "token": token,
                    "admitted": False,
                    "bypassed_queue": True,
                    "message": f"Approval token '{token}' not found or expired.",
                }

        if command == "/deny":
            token = parts[1].strip() if len(parts) > 1 else ""
            with self._lock:
                gate = self._approval_gates.get(token)
                if gate:
                    gate.resolve(approved=False)
                    self._approval_gates.pop(token, None)
                    return {
                        "status": "denied",
                        "token": token,
                        "admitted": True,
                        "bypassed_queue": True,
                        "message": f"Denied action '{gate.action_description}'.",
                    }
                return {
                    "status": "not_found",
                    "token": token,
                    "admitted": False,
                    "bypassed_queue": True,
                    "message": f"Approval token '{token}' not found or expired.",
                }

        # --- GUARD 2: Session Active Queue ---
        with self._lock:
            if session_id in self._active_contexts:
                # Active session: Queue message
                self._pending_queues[session_id].append(trimmed)
                queue_pos = len(self._pending_queues[session_id])
                return {
                    "status": "queued",
                    "admitted": False,
                    "bypassed_queue": False,
                    "queue_position": queue_pos,
                    "message": f"Agent is busy. Message queued (position {queue_pos}).",
                }

            # Idle session: Direct admission
            return {
                "status": "admitted",
                "admitted": True,
                "bypassed_queue": False,
                "message": "Message admitted for immediate turn execution.",
            }

    def pop_queued_message(self, session_id: str) -> Optional[str]:
        """Pop the next queued message for session."""
        with self._lock:
            q = self._pending_queues.get(session_id)
            if q and len(q) > 0:
                return q.pop(0)
            return None
