from __future__ import annotations
"""Mistral AI provider profile."""

from typing import Any
from providers import register_provider
from providers.base import ProviderProfile


class MistralProfile(ProviderProfile):
    """Mistral AI — native OpenAI-compatible API without reasoning_effort for non-reasoning models."""

    def build_api_kwargs_extras(
        self, *, reasoning_config: dict | None = None, model: str | None = None, **context: Any
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        return {}, {}


mistral = MistralProfile(
    name="mistral",
    aliases=("mistralai", "mistral-ai"),
    env_vars=("MISTRAL_API_KEY",),
    display_name="Mistral AI",
    description="Mistral AI API",
    signup_url="https://console.mistral.ai/",
    fallback_models=("codestral-latest", "mistral-large-4", "ministral-8b-latest"),
    base_url="https://api.mistral.ai/v1",
    default_aux_model="codestral-latest",
)

register_provider(mistral)
