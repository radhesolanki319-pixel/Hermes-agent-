"""Modular Turn Execution Engine for Hermes Core."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from hermes_core.persistence.session_db import SessionDB
from hermes_core.turn.context import TurnBudget, TurnContext

logger = logging.getLogger("hermes_core.turn.engine")


class TurnEngine:
    """Orchestrates single-turn conversational execution with tool dispatch and persistence."""

    def __init__(
        self,
        session_db: SessionDB,
        model_client: Any,
        tool_executor: Optional[Callable[[str, Dict[str, Any]], str]] = None,
        tool_schemas: Optional[List[Dict[str, Any]]] = None,
    ):
        self.db = session_db
        self.model_client = model_client
        self.tool_executor = tool_executor or (lambda name, args: json.dumps({"status": "no executor"}))
        self.tool_schemas = tool_schemas or []

    def _enforce_role_alternation(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Ensure strict OpenAI role alternation without consecutive duplicate roles."""
        if not messages:
            return []

        cleaned: List[Dict[str, Any]] = []
        for msg in messages:
            if not cleaned:
                cleaned.append(msg)
                continue

            last = cleaned[-1]
            if last["role"] == msg["role"] and msg["role"] == "user":
                # Merge consecutive user messages
                last["content"] = f"{last.get('content', '')}\n\n{msg.get('content', '')}"
            else:
                cleaned.append(msg)
        return cleaned

    def execute_turn(
        self,
        session_id: str,
        user_message: str,
        stream_callback: Optional[Callable[[str], None]] = None,
        max_iterations: int = 15,
    ) -> Dict[str, Any]:
        """Execute a full agent turn from user prompt to final response."""
        context = TurnContext(
            session_id=session_id,
            budget=TurnBudget(max_iterations=max_iterations, remaining_iterations=max_iterations),
            stream_callback=stream_callback,
        )

        # 1. Record incoming user message in DB
        self.db.add_message(session_id=session_id, role="user", content=user_message)

        # 2. Retrieve session and full message history
        session = self.db.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found.")

        # Build prompt messages array
        messages: List[Dict[str, Any]] = []
        if session.get("system_prompt"):
            messages.append({"role": "system", "content": session["system_prompt"]})

        history = self.db.get_messages(session_id)
        for h in history:
            m = {"role": h["role"], "content": h.get("content")}
            if h.get("tool_calls"):
                m["tool_calls"] = h["tool_calls"]
            if h.get("tool_name"):
                m["name"] = h["tool_name"]
            if h.get("tool_call_id"):
                m["tool_call_id"] = h["tool_call_id"]
            messages.append(m)

        messages = self._enforce_role_alternation(messages)

        final_text = ""

        # 3. Execution Loop
        while context.budget.can_continue():
            if context.interrupted:
                logger.info(f"Turn {session_id} received interrupt. Stopping.")
                break

            context.budget.consume_iteration()
            context.telemetry.api_calls_count += 1

            # Dispatch model call
            try:
                response = self.model_client(messages, tools=self.tool_schemas)
            except Exception as exc:
                logger.error(f"Model dispatch failed: {exc}")
                final_text = f"Error during model dispatch: {str(exc)}"
                break

            # Process response
            content = response.get("content") or ""
            tool_calls = response.get("tool_calls") or []

            # Stream text if provided
            if content and stream_callback:
                context.emit_stream(content)

            # If tool calls were generated
            if tool_calls:
                # Add assistant message with tool calls
                self.db.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=content,
                    tool_calls=tool_calls,
                )
                messages.append({
                    "role": "assistant",
                    "content": content,
                    "tool_calls": tool_calls,
                })

                # Execute each tool call
                for tc in tool_calls:
                    tc_id = tc.get("id", f"call_{int(time.time()*1000)}")
                    fn = tc.get("function", {})
                    name = fn.get("name") or tc.get("name", "")
                    raw_args = fn.get("arguments") or tc.get("args") or {}
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args

                    context.telemetry.tool_calls_count += 1
                    try:
                        result_str = self.tool_executor(name, args)
                    except Exception as t_err:
                        result_str = json.dumps({"error": str(t_err)})

                    # Record tool response
                    self.db.add_message(
                        session_id=session_id,
                        role="tool",
                        content=result_str,
                        tool_name=name,
                        tool_call_id=tc_id,
                    )
                    messages.append({
                        "role": "tool",
                        "name": name,
                        "tool_call_id": tc_id,
                        "content": result_str,
                    })

                # Loop continues for next model turn
                continue
            else:
                # Final response reached
                final_text = content
                self.db.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=final_text,
                )
                break

        # 4. Turn Finalization
        context.telemetry.end_time = time.time()
        context.final_response = final_text

        # Record metrics in DB
        self.db.record_usage(
            session_id=session_id,
            input_tokens=context.telemetry.input_tokens,
            output_tokens=context.telemetry.output_tokens,
        )

        return {
            "session_id": session_id,
            "final_response": final_text,
            "interrupted": context.interrupted,
            "api_calls": context.telemetry.api_calls_count,
            "tool_calls": context.telemetry.tool_calls_count,
            "duration_seconds": context.telemetry.duration_seconds,
        }
