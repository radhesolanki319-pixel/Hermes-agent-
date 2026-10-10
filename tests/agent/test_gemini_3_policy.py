import pytest
from run_agent import AIAgent


def test_gemini_3_policy_enforcement_flash(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    agent = AIAgent(
        model="gemini-2.5-flash",
        provider="gemini",
    )
    assert agent.model == "gemini-3.8-flash"


def test_gemini_3_policy_enforcement_pro(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    agent = AIAgent(
        model="gemini-2.5-pro",
        provider="gemini",
    )
    assert agent.model == "gemini-3-pro-preview"


def test_gemini_3_policy_enforcement_prefix(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    agent = AIAgent(
        model="google/gemini-2.5-flash",
        provider="gemini",
    )
    assert agent.model in ("gemini-3.8-flash", "google/gemini-3.8-flash")


def test_gemini_3_preserves_3_series(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    agent = AIAgent(
        model="gemini-3.8-flash",
        provider="gemini",
    )
    assert agent.model == "gemini-3.8-flash"
