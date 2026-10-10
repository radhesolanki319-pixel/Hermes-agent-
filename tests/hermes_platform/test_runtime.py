from __future__ import annotations

from hermes_platform.host import runtime


def test_is_android_with_android_root(monkeypatch) -> None:
    monkeypatch.setattr(runtime.sys, "platform", "linux")
    monkeypatch.setenv("ANDROID_ROOT", "/system")
    monkeypatch.delenv("ANDROID_DATA", raising=False)

    assert runtime.is_android()


def test_is_android_with_android_data(monkeypatch) -> None:
    monkeypatch.setattr(runtime.sys, "platform", "linux")
    monkeypatch.delenv("ANDROID_ROOT", raising=False)
    monkeypatch.setenv("ANDROID_DATA", "/data")

    assert runtime.is_android()


def test_is_android_false_on_regular_linux(monkeypatch) -> None:
    monkeypatch.setattr(runtime.sys, "platform", "linux")
    monkeypatch.delenv("ANDROID_ROOT", raising=False)
    monkeypatch.delenv("ANDROID_DATA", raising=False)

    assert not runtime.is_android()


def test_is_android_false_outside_linux(monkeypatch) -> None:
    monkeypatch.setattr(runtime.sys, "platform", "darwin")
    monkeypatch.setenv("ANDROID_ROOT", "/system")

    assert not runtime.is_android()


def test_termux_detection_remains_separate(monkeypatch) -> None:
    monkeypatch.setenv("ANDROID_ROOT", "/system")
    monkeypatch.delenv("ANDROID_DATA", raising=False)
    monkeypatch.delenv("TERMUX_VERSION", raising=False)
    monkeypatch.setenv("PREFIX", "/usr")

    assert runtime.is_android()
    assert not runtime.is_termux()


def test_is_android_with_android_sys_platform(monkeypatch) -> None:
    monkeypatch.setattr(runtime.sys, "platform", "android")
    monkeypatch.delenv("ANDROID_ROOT", raising=False)
    monkeypatch.delenv("ANDROID_DATA", raising=False)

    assert runtime.is_android()

