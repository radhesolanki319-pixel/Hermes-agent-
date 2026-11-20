from __future__ import annotations
"""Groq Cloud provider profile."""

from typing import Any
from providers import register_provider
from providers.base import ProviderProfile


class GroqProfile(ProviderProfile):
    """Groq Cloud — ultra-fast LPU inference via OpenAI-compatible endpoint."""

    def build_api_kwargs_extras(
        self, *, reasoning_config: dict | None = None, model: str | None = None, **context: Any
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        # Groq rejects session_id and unsupported reasoning_effort
        return {}, {}


groq = GroqProfile(
    name="groq",
    aliases=("groq-cloud", "groqcloud"),
    env_vars=("GROQ_API_KEY",),
    display_name="Groq Cloud",
    description="Groq LPU Inference",
    signup_url="https://console.groq.com/",
    fallback_models=("openai/gpt-oss-20b", "openai/gpt-oss-120b"),
    base_url="https://api.groq.com/openai/v1",
    default_aux_model="openai/gpt-oss-20b",
)

register_provider(groq)
