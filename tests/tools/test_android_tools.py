import json
import pytest
from tools.android_tools import (
    android_torch_tool,
    android_battery_tool,
    android_clipboard_tool,
    android_vibrate_tool,
    android_camera_tool,
    android_media_tool,
)
from tools.registry import registry


def test_android_tools_registered():
    """Verify that all 6 android tools are registered in the central registry."""
    tools = registry._merged_tools()
    for tool_name in (
        "android_torch",
        "android_battery",
        "android_clipboard",
        "android_vibrate",
        "android_camera",
        "android_media",
    ):
        assert tool_name in tools, f"Tool {tool_name} should be in registry"
        reg = tools[tool_name]
        assert reg.toolset == "android"


def test_android_torch_validation():
    """Torch rejects invalid actions."""
    res = json.loads(android_torch_tool("invalid_action"))
    assert res.get("success") is False
    assert "Invalid action" in res.get("error", "")


def test_android_torch_mocked(monkeypatch):
    """Torch executes termux-torch on/off."""
    monkeypatch.setattr("shutil.which", lambda cmd: "/data/data/com.termux/files/usr/bin/" + cmd)
    monkeypatch.setattr("tools.android_tools._run_cmd", lambda cmd, timeout=5.0: (0, "", ""))

    res = json.loads(android_torch_tool("on"))
    assert res.get("success") is True
    assert "ON" in res.get("status", "")

    res_off = json.loads(android_torch_tool("off"))
    assert res_off.get("success") is True
    assert "OFF" in res_off.get("status", "")


def test_android_battery_mocked(monkeypatch):
    """Battery reports status properly."""
    monkeypatch.setattr("shutil.which", lambda cmd: "/data/data/com.termux/files/usr/bin/" + cmd)
    sample_data = json.dumps({
        "percentage": 85,
        "status": "DISCHARGING",
        "health": "GOOD",
        "temperature": 32.5,
        "plugged": "UNPLUGGED",
    })
    monkeypatch.setattr("tools.android_tools._run_cmd", lambda cmd, timeout=5.0: (0, sample_data, ""))

    res = json.loads(android_battery_tool(detailed=False))
    assert res.get("success") is True
    assert res.get("percentage") == 85
    assert res.get("status") == "DISCHARGING"


def test_android_clipboard_get_and_set(monkeypatch):
    """Clipboard reads and writes text."""
    monkeypatch.setattr("shutil.which", lambda cmd: "/data/data/com.termux/files/usr/bin/" + cmd)
    monkeypatch.setattr("tools.android_tools._run_cmd", lambda cmd, timeout=5.0: (0, "Hello clipboard", ""))

    res_get = json.loads(android_clipboard_tool("get"))
    assert res_get.get("success") is True
    assert res_get.get("clipboard_content") == "Hello clipboard"

    # Set requires text argument
    res_err = json.loads(android_clipboard_tool("set", text=None))
    assert res_err.get("success") is False


def test_android_vibrate_bounds(monkeypatch):
    """Vibrate clamps duration to safe range."""
    monkeypatch.setattr("shutil.which", lambda cmd: "/data/data/com.termux/files/usr/bin/" + cmd)
    recorded = []
    monkeypatch.setattr("tools.android_tools._run_cmd", lambda cmd, timeout=5.0: (recorded.append(cmd) or (0, "", "")))

    # Out of bounds high -> clamped to 3000
    res = json.loads(android_vibrate_tool(duration_ms=10000))
    assert res.get("success") is True
    assert recorded[-1] == ["termux-vibrate", "-d", "3000"]

    # Out of bounds low -> clamped to 50
    res_low = json.loads(android_vibrate_tool(duration_ms=5))
    assert res_low.get("success") is True
    assert recorded[-1] == ["termux-vibrate", "-d", "50"]


def test_android_camera_ids(monkeypatch, tmp_path):
    """Camera properly selects back vs front camera ID."""
    monkeypatch.setattr("shutil.which", lambda cmd: "/data/data/com.termux/files/usr/bin/" + cmd)
    recorded = []

    def fake_run(cmd, timeout=15.0):
        recorded.append(cmd)
        target_file = tmp_path / "shot.jpg"
        target_file.write_bytes(b"dummy image data")
        return (0, "", "")

    monkeypatch.setattr("tools.android_tools._run_cmd", fake_run)

    # Front camera
    res_front = json.loads(android_camera_tool(camera="front", output_path=str(tmp_path / "shot.jpg")))
    assert res_front.get("success") is True
    assert res_front.get("camera") == "front"
    assert recorded[-1][2] == "1"


def test_android_media_actions(monkeypatch):
    """Media handles YouTube URL formatting cleanly."""
    monkeypatch.setattr("shutil.which", lambda cmd: "/data/data/com.termux/files/usr/bin/" + cmd)
    monkeypatch.setattr("tools.android_tools._run_cmd", lambda cmd, timeout=5.0: (0, "", ""))

    res_yt = json.loads(android_media_tool("open_youtube", "kesariya song"))
    assert res_yt.get("success") is True
    assert "youtube.com" in res_yt.get("url", "")
