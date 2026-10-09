"""Cached facts about the machine running this Python process.

Facts use hardware sources without environment-variable input or subprocesses.
Runtime-environment predicates live in ``hermes_platform.host.runtime``.
"""

from hermes_platform.host.facts import interactive_session
from hermes_platform.host.runtime import is_android, is_container, is_termux, is_wsl

__all__ = [
    "interactive_session",
    "is_android",
    "is_container",
    "is_termux",
    "is_wsl",
]
