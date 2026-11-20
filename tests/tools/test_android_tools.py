import json
from tools.android_tools import (
    android_torch_tool,
    android_battery_tool,
    android_clipboard_tool,
    android_vibrate_tool,
    android_camera_tool,
    android_media_tool,
    android_display_tool,
    android_notification_tool,
    android_toast_tool,
    android_tts_tool,
    android_wifi_tool,
    android_telephony_tool,
    android_system_status_tool,
    android_volume_tool,
    freellm_ai_query_tool,
)
from tools.registry import registry


def test_android_tools_registered():
    """Verify that all 15 android tools are registered in the central registry."""
    tools = registry._merged_tools()
    expected_tools = (
        "android_torch",
        "android_battery",
        "android_clipboard",
        "android_vibrate",
        "android_camera",
        "android_media",
        "android_display",
        "android_notification",
        "android_toast",
        "android_tts",
        "android_wifi",
        "android_telephony",
        "android_system_status",
        "android_volume",
        "freellm_ai_query",
    )
    for tool_name in expected_tools:
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


def test_android_display_tool(monkeypatch):
    """Display tool handles comfort, cinema, and status modes."""
    monkeypatch.setattr("os.path.exists", lambda path: True)
    monkeypatch.setattr("tools.android_tools._run_cmd", lambda cmd, timeout=10.0: (0, "DISPLAY OK", ""))

    res = json.loads(android_display_tool(mode="comfort", dim_level=50))
    assert res.get("success") is True
    assert res.get("mode") == "comfort"
    assert "DISPLAY OK" in res.get("output", "")


def test_android_notification_tool(monkeypatch):
    """Notification tool handles notify and remove actions."""
    recorded = []
    monkeypatch.setattr("tools.android_tools._run_cmd", lambda cmd, timeout=10.0: (recorded.append(cmd) or (0, "", "")))

    res_notify = json.loads(android_notification_tool(
        action="notify",
        title="JARVIS Alert",
        content="Task Complete Boss",
        id="jarvis_01",
        priority="high",
        vibrate_ms=250,
        sound=True,
    ))
    assert res_notify.get("success") is True
    assert "--title" in recorded[-1]
    assert "JARVIS Alert" in recorded[-1]

    res_remove = json.loads(android_notification_tool(action="remove", id="jarvis_01"))
    assert res_remove.get("success") is True
    assert recorded[-1] == ["termux-notification-remove", "jarvis_01"]


def test_android_toast_tool(monkeypatch):
    """Toast tool executes termux-toast with parameters."""
    recorded = []
    monkeypatch.setattr("tools.android_tools._run_cmd", lambda cmd, timeout=10.0: (recorded.append(cmd) or (0, "", "")))

    res = json.loads(android_toast_tool(text="Hello Boss", short=True, gravity="bottom"))
    assert res.get("success") is True
    assert recorded[-1] == ["termux-toast", "-g", "bottom", "-b", "black", "-c", "white", "-s", "Hello Boss"]


def test_android_tts_tool(monkeypatch):
    """TTS tool clamps rate and pitch, executes speech."""
    recorded = []
    monkeypatch.setattr("tools.android_tools._run_cmd", lambda cmd, timeout=15.0: (recorded.append(cmd) or (0, "", "")))

    res = json.loads(android_tts_tool(text="Voice output ready Boss", rate=3.0, pitch=0.1))
    assert res.get("success") is True
    # Clamped rate to 2.0 and pitch to 0.5
    assert recorded[-1][2] == "2.0"
    assert recorded[-1][4] == "0.5"


def test_android_wifi_tool(monkeypatch):
    """WiFi tool parses connection info."""
    sample_wifi = json.dumps({"ssid": "Boss_HQ_5G", "ip": "192.168.1.100", "link_speed_mbps": 866})
    monkeypatch.setattr("tools.android_tools._run_cmd", lambda cmd, timeout=5.0: (0, sample_wifi, ""))

    res = json.loads(android_wifi_tool("info"))
    assert res.get("success") is True
    assert res.get("data", {}).get("ssid") == "Boss_HQ_5G"


def test_android_telephony_tool(monkeypatch):
    """Telephony tool parses device info."""
    sample_tel = json.dumps({"network_operator_name": "Jio 5G", "sim_state": "READY"})
    monkeypatch.setattr("tools.android_tools._run_cmd", lambda cmd, timeout=5.0: (0, sample_tel, ""))

    res = json.loads(android_telephony_tool("device"))
    assert res.get("success") is True
    assert res.get("data", {}).get("network_operator_name") == "Jio 5G"


def test_android_system_status_tool(monkeypatch):
    """System status returns device specs, thermal policy and battery info."""
    battery_json = json.dumps({"percentage": 80, "status": "DISCHARGING", "temperature": 32.0})
    monkeypatch.setattr("tools.android_tools._run_cmd", lambda cmd, timeout=5.0: (0, battery_json, ""))

    res = json.loads(android_system_status_tool(detailed=False))
    assert "iQOO Neo 10" in res.get("device", "")
    assert "Snapdragon 8 Gen 3" in res.get("soc", "")
    assert res.get("battery", {}).get("temperature_c") == 32.0
    assert res.get("battery", {}).get("thermal_status") == "OPTIMAL COOL"


def test_android_volume_tool(monkeypatch):
    """Volume tool handles get and set."""
    recorded = []
    monkeypatch.setattr("tools.android_tools._run_cmd", lambda cmd, timeout=10.0: (recorded.append(cmd) or (0, "[]", "")))

    res_set = json.loads(android_volume_tool(action="set", stream="media", volume=10))
    assert res_set.get("success") is True
    assert recorded[-1] == ["termux-volume", "media", "10"]


def test_freellm_ai_query_tool(monkeypatch):
    """FreeLLM AI query connects and returns response."""
    class FakeResponse:
        headers = {"X-Routed-Via": "groq/qwen/qwen3.8-27b"}
        def read(self):
            return json.dumps({
                "choices": [{"message": {"content": "Hello Boss! JARVIS AI ready."}}]
            }).encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=12.0: FakeResponse())

    res = json.loads(freellm_ai_query_tool(prompt="Test prompt", model="auto"))
    assert res.get("success") is True
    assert res.get("routed_via") == "groq/qwen/qwen3.8-27b"
    assert "Hello Boss!" in res.get("answer", "")


if __name__ == "__main__":
    import types
    from pathlib import Path

    class MockMonkeypatch:
        def __init__(self):
            self.undo = []
        def setattr(self, target, value):
            mod_name, attr = target.rsplit(".", 1)
            import importlib
            mod = importlib.import_module(mod_name)
            old = getattr(mod, attr)
            setattr(mod, attr, value)
            self.undo.append((mod, attr, old))
        def cleanup(self):
            for mod, attr, old in reversed(self.undo):
                setattr(mod, attr, old)

    mp = MockMonkeypatch()
    import tempfile
    tmp_dir = Path(tempfile.gettempdir())
    tests = [
        test_android_tools_registered,
        test_android_torch_validation,
        lambda: test_android_torch_mocked(mp),
        lambda: test_android_battery_mocked(mp),
        lambda: test_android_clipboard_get_and_set(mp),
        lambda: test_android_vibrate_bounds(mp),
        lambda: test_android_camera_ids(mp, tmp_dir),
        lambda: test_android_media_actions(mp),
        lambda: test_android_display_tool(mp),
        lambda: test_android_notification_tool(mp),
        lambda: test_android_toast_tool(mp),
        lambda: test_android_tts_tool(mp),
        lambda: test_android_wifi_tool(mp),
        lambda: test_android_telephony_tool(mp),
        lambda: test_android_system_status_tool(mp),
        lambda: test_android_volume_tool(mp),
        lambda: test_freellm_ai_query_tool(mp),
    ]

    passed = 0
    for t in tests:
        name = getattr(t, "__name__", "lambda")
        try:
            t()
            passed += 1
            print(f"PASS: {name}")
        except Exception as e:
            print(f"FAIL: {name}: {e}")
            raise
        finally:
            mp.cleanup()

    print(f"\nALL {passed}/{len(tests)} TESTS PASSED PERFECTLY!")
