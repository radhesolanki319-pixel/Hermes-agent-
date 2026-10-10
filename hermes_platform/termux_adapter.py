"""Termux & Android platform adapter for Hermes personal AI assistant.

Provides platform detection, Android storage resolution, device battery/thermal
diagnostics, and enforces the STRICT ZERO-BACKGROUND PROCESS policy on mobile.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional


def is_android() -> bool:
    """Return True if running in Android environment (Termux, PRoot, etc.)."""
    return (
        sys.platform == "android"
        or "TERMUX_VERSION" in os.environ
        or "/data/data/com.termux" in os.environ.get("PREFIX", "")
        or os.path.exists("/system/build.prop")
    )


def is_termux() -> bool:
    """Return True if running directly within Termux userland."""
    return "TERMUX_VERSION" in os.environ or "/data/data/com.termux" in os.environ.get("PREFIX", "")


def get_android_storage() -> Path:
    """Return primary shared internal storage directory (/storage/emulated/0)."""
    candidates = [
        Path("/storage/emulated/0"),
        Path("/sdcard"),
        Path.home() / "storage" / "shared",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return Path("/storage/emulated/0")


def get_android_download_dir() -> Path:
    """Return the user-facing Download directory."""
    candidates = [
        Path("/storage/emulated/0/Download"),
        Path("/sdcard/Download"),
        Path.home() / "storage" / "downloads",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return get_android_storage() / "Download"


def has_termux_api() -> bool:
    """Return True if termux-api CLI utilities are installed and available."""
    return shutil.which("termux-battery-status") is not None


def get_battery_status() -> Dict[str, Any]:
    """Return current battery and thermal status safely and synchronously."""
    if not is_android():
        return {"status": "unsupported", "level": None}

    # Try termux-battery-status if available
    if has_termux_api():
        try:
            res = subprocess.run(
                ["termux-battery-status"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if res.returncode == 0:
                import json
                return json.loads(res.stdout)
        except Exception:
            pass

    # Fallback to sysfs thermal / battery readings
    status_info: Dict[str, Any] = {"status": "unknown", "level": None, "temperature": None}
    cap_path = Path("/sys/class/power_supply/battery/capacity")
    temp_path = Path("/sys/class/power_supply/battery/temp")
    if cap_path.exists():
        try:
            status_info["level"] = int(cap_path.read_text(encoding="utf-8").strip())
        except Exception:
            pass
    if temp_path.exists():
        try:
            raw_temp = int(temp_path.read_text(encoding="utf-8").strip())
            status_info["temperature"] = raw_temp / 10.0 if raw_temp > 100 else raw_temp
        except Exception:
            pass

    return status_info


def is_zero_daemon_required() -> bool:
    """Return True if background daemons are forbidden (always True on Android)."""
    return is_android() or os.environ.get("ZERO_DAEMON_MODE", "").strip().lower() in ("1", "true", "yes")
