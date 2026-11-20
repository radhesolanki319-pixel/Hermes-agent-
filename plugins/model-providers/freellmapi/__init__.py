"""FreeLLM API Unified Flagship Provider Profile.

Connects Hermes Agent CLI directly to Boss's 158 Flagship SOTA AI models
with fastest-first bandit routing and ultra-low latency.
"""

from __future__ import annotations

import os
from typing import Any

from agent.reasoning_effort import OPENAI_COMPAT_WIRE_EFFORTS, clamp_effort
from providers import register_provider
from providers.base import ProviderProfile

FREELLM_DEFAULT_BASE_URL = "https://freellmapi-backup.onrender.com/v1"
FREELLM_DEFAULT_API_KEY = "freellmapi-c7bf396fcf0351dbba9546933a8881054c627e6f78875206"

# Core Flagship Models for instant autocomplete, fallback and picker
FREELLM_FLAGSHIP_MODELS = (
    "auto",
    "gemini-3.8-flash",
    "claude-haiku-4.5",
    "gpt-5.1-codex",
    "qwen-3.8-27b",
    "llama-3.1-8b-instant",
    "claude-opus-5",
    "claude-sonnet-5.5",
    "gpt-5.5-fast",
    "grok-4.20-reasoning",
    "glm-5.3-flash",
    "deepseek-v4-flash",
    "deepseek-v4-pro",
    "command-a-03-2025",
    "Meta-Llama-3.3-70B-Instruct",
)


class FreeLLMProfile(ProviderProfile):
    """FreeLLM API Unified Flagship provider profile."""

    def supported_reasoning_efforts(self, model: str | None) -> tuple[str, ...]:
        return OPENAI_COMPAT_WIRE_EFFORTS

    def default_reasoning_config(self, model: str | None = None) -> dict | None:
        return {"enabled": True, "effort": "medium"}

    def build_api_kwargs_extras(
        self, *, reasoning_config: dict | None = None, **ctx: Any
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        extra_body: dict[str, Any] = {}
        top_level: dict[str, Any] = {}
        if reasoning_config and isinstance(reasoning_config, dict):
            effort = (reasoning_config.get("effort") or "").strip().lower()
            if effort == "none" or reasoning_config.get("enabled", True) is False:
                top_level["reasoning_effort"] = "none"
            elif effort:
                top_level["reasoning_effort"] = clamp_effort(effort, OPENAI_COMPAT_WIRE_EFFORTS)
        return extra_body, top_level

    def fetch_models(
        self, *, api_key: str | None = None, base_url: str | None = None, timeout: float = 8.0
    ) -> list[str] | None:
        url = base_url or self.base_url or FREELLM_DEFAULT_BASE_URL
        key = api_key or os.getenv("FREELLM_API_KEY") or os.getenv("UNIFIED_API_KEY") or FREELLM_DEFAULT_API_KEY
        fetched = super().fetch_models(api_key=key, base_url=url, timeout=timeout)
        if fetched:
            return fetched
        return list(FREELLM_FLAGSHIP_MODELS)


freellmapi = FreeLLMProfile(
    name="freellmapi",
    display_name="FreeLLM API (Flagship Router)",
    description="Boss's Unified 158 Flagship SOTA Models Gateway with Fastest-First Routing",
    aliases=("freeapi", "freellm", "omniroute", "flagship", "boss-router"),
    env_vars=("FREELLM_API_KEY", "UNIFIED_API_KEY"),
    base_url=FREELLM_DEFAULT_BASE_URL,
    fallback_models=FREELLM_FLAGSHIP_MODELS,
)

register_provider(freellmapi)
