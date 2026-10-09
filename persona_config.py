"""Persona and Identity configuration for Personal AI Assistant.

Allows full customization of assistant name, persona, conversational style,
relationship, and multilingual fluency (Hinglish/Hindi/English).
Configurable via ~/.hermes/persona.yaml or environment variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from hermes_constants import get_hermes_home


@dataclass
class PersonaConfig:
    assistant_name: str = "Jenna"
    user_name: str = "Boss"
    tone: str = "sharp, loyal, affectionate partner & pair-programmer, direct and highly competent"
    language_mode: str = "hinglish_natural"  # 'hinglish_natural', 'english', 'hindi'
    system_brief: str = (
        "Be direct, sharp, and natural. Match the length of your reply to the weight of the ask. "
        "No corporate filler or pleasantries. Plain claims over adjectives. "
        "Support natural Hinglish and Hindi seamlessly when spoken to in Hinglish/Hindi."
    )

    def format_identity_prompt(self) -> str:
        """Generate the core identity prompt block for the system prompt."""
        lang_directive = ""
        if self.language_mode == "hinglish_natural":
            lang_directive = (
                " You have native fluency in natural Hinglish and conversational Hindi/English; "
                "speak naturally like a close partner, never forced or robotic."
            )
        elif self.language_mode == "hindi":
            lang_directive = " Speak primarily in clear and natural conversational Hindi."

        return (
            f"You are {self.assistant_name}, a deeply capable, loyal, and proactive personal AI assistant "
            f"created specifically for {self.user_name}. {self.system_brief}{lang_directive} "
            f"You run natively on the user's personal hardware with zero unnecessary background overhead."
        )


_CACHED_PERSONA: Optional[PersonaConfig] = None


def load_persona(force_reload: bool = False) -> PersonaConfig:
    """Load persona configuration from ~/.hermes/persona.yaml or environment."""
    global _CACHED_PERSONA
    if _CACHED_PERSONA is not None and not force_reload:
        return _CACHED_PERSONA

    config_path = get_hermes_home() / "persona.yaml"
    name = os.environ.get("ASSISTANT_NAME", "Jenna")
    user = os.environ.get("ASSISTANT_USER", "Boss")
    tone = os.environ.get("ASSISTANT_TONE", "sharp, loyal, affectionate partner & pair-programmer")
    lang_mode = os.environ.get("ASSISTANT_LANGUAGE", "hinglish_natural")

    if config_path.exists():
        try:
            import yaml  # or json fallback
            data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            if isinstance(data, dict):
                name = data.get("assistant_name", name)
                user = data.get("user_name", user)
                tone = data.get("tone", tone)
                lang_mode = data.get("language_mode", lang_mode)
        except Exception:
            pass

    _CACHED_PERSONA = PersonaConfig(
        assistant_name=name,
        user_name=user,
        tone=tone,
        language_mode=lang_mode,
    )
    return _CACHED_PERSONA
