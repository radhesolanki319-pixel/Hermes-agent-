"""Two-Tier Context Compressor and Prompt Hygiene for Hermes Core."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("hermes_core.compressor")


class ContextCompressor:
    """Manages context window budgets, deterministic tool output trimming, and milestone summarization."""

    def __init__(
        self,
        context_window_tokens: int = 128000,
        compression_threshold: float = 0.50,
        max_tool_output_chars: int = 2000,
        summary_model_client: Optional[Callable[[str], str]] = None,
    ):
        self.context_window_tokens = context_window_tokens
        self.compression_threshold = compression_threshold
        self.max_tool_output_chars = max_tool_output_chars
        self.summary_model_client = summary_model_client

    def prune_tool_results(
        self, messages: List[Dict[str, Any]], keep_recent_turns: int = 2
    ) -> List[Dict[str, Any]]:
        """Tier 1: Deterministic zero-cost trimming of older verbose tool results."""
        if not messages:
            return []

        pruned: List[Dict[str, Any]] = []
        total_msgs = len(messages)

        for idx, msg in enumerate(messages):
            # Don't trim the most recent messages
            is_recent = (total_msgs - idx) <= (keep_recent_turns * 2)

            if msg.get("role") == "tool" and not is_recent:
                content = str(msg.get("content") or "")
                if len(content) > self.max_tool_output_chars:
                    head_len = self.max_tool_output_chars // 2
                    tail_len = min(head_len, 20)
                    head = content[:head_len]
                    tail = content[-tail_len:] if tail_len > 0 else ""
                    trimmed = f"{head}\n... [Output truncated: {len(content)} chars] ...\n{tail}"
                    m_copy = dict(msg)
                    m_copy["content"] = trimmed
                    pruned.append(m_copy)
                    continue

            pruned.append(msg)

        return pruned

    def should_compress(self, current_token_count: int) -> bool:
        """Check if current context length exceeds the compression threshold."""
        return current_token_count >= int(self.context_window_tokens * self.compression_threshold)

    def compact_history(
        self, messages: List[Dict[str, Any]], keep_recent_count: int = 4
    ) -> tuple[List[Dict[str, Any]], Optional[str]]:
        """Tier 2: Synthesize older conversation history into a structured milestone summary."""
        if len(messages) <= keep_recent_count:
            return messages, None

        # Split into historical slice to summarize and active recent slice
        to_summarize = messages[:-keep_recent_count]
        recent = messages[-keep_recent_count:]

        # Extract text for summary
        transcript_lines = []
        for m in to_summarize:
            role = m.get("role", "user")
            content = m.get("content") or ""
            transcript_lines.append(f"[{role.upper()}]: {content[:500]}")

        transcript_text = "\n".join(transcript_lines)

        if self.summary_model_client:
            summary = self.summary_model_client(transcript_text)
        else:
            # Deterministic fallback milestone summary
            summary = (
                f"### [Automated Milestone Context Summary]\n"
                f"- Compacted {len(to_summarize)} earlier conversation messages.\n"
                f"- Transcript excerpt:\n"
                f"{transcript_text[:1200]}\n"
                f"... [End of compacted milestone summary]"
            )

        compacted_messages: List[Dict[str, Any]] = [
            {"role": "user", "content": f"[Previous Conversation Context Summary]:\n{summary}"},
            {"role": "assistant", "content": "Understood. I have absorbed the prior conversation context. How may I continue?"},
        ]
        compacted_messages.extend(recent)

        return compacted_messages, summary
