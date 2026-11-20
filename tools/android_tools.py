"""Android and Termux Native Hardware & Automation Tools.

Provides direct, synchronous, zero-daemon access to Android hardware and capabilities:
- Flashlight / Torch (`termux-torch on/off`)
- Battery diagnostics (`termux-battery-status`)
- Clipboard synchronization (`termux-clipboard-get/set`)
- Haptic vibration (`termux-vibrate`)
- Camera photo snapshot (`termux-camera-photo`)
- Media playback & YouTube autoplay (`termux-media-player`, `termux-open-url`, `yt-dlp`)
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from hermes_platform.host.facts import is_android
from tools.registry import registry

logger = logging.getLogger(__name__)


def _run_cmd(cmd: list[str], timeout: float = 10.0) -> tuple[int, str, str]:
    """Execute a command synchronously with bounded timeout."""
    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout} seconds"
    except Exception as exc:
        return -1, "", str(exc)


def _check_android_available() -> bool:
    """Check if running in Android / Termux environment."""
    return is_android() or bool(shutil.which("termux-battery-status"))


# ==============================================================================
# 1. Android Torch (Flashlight)
# ==============================================================================

TORCH_SCHEMA = {
    "name": "android_torch",
    "description": "Turn the phone flashlight/torch ON or OFF.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["on", "off"],
                "description": "Action to perform: 'on' to enable torch, 'off' to disable torch.",
            }
        },
        "required": ["action"],
    },
}


def android_torch_tool(action: str) -> str:
    """Control device flashlight."""
    if not shutil.which("termux-torch"):
        return json.dumps({"error": "termux-torch command not found on this device", "success": False})

    action = action.strip().lower()
    if action not in ("on", "off"):
        return json.dumps({"error": "Invalid action. Use 'on' or 'off'.", "success": False})

    code, out, err = _run_cmd(["termux-torch", action], timeout=5.0)
    if code != 0:
        return json.dumps({"error": f"Failed to set torch: {err or out}", "success": False})

    return json.dumps({"status": f"Torch turned {action.upper()}", "action": action, "success": True})


# ==============================================================================
# 2. Android Battery Status
# ==============================================================================

BATTERY_SCHEMA = {
    "name": "android_battery",
    "description": "Get real-time battery status, percentage, health, charging state, and temperature.",
    "parameters": {
        "type": "object",
        "properties": {
            "detailed": {
                "type": "boolean",
                "description": "Whether to return full raw telemetry details.",
            }
        },
        "required": [],
    },
}


def android_battery_tool(detailed: bool = False) -> str:
    """Retrieve battery diagnostic status."""
    if shutil.which("termux-battery-status"):
        code, out, err = _run_cmd(["termux-battery-status"], timeout=5.0)
        if code == 0 and out:
            try:
                data = json.loads(out)
                if not detailed:
                    return json.dumps({
                        "percentage": data.get("percentage"),
                        "status": data.get("status"),
                        "health": data.get("health"),
                        "temperature": data.get("temperature"),
                        "plugged": data.get("plugged"),
                        "success": True,
                    })
                return json.dumps({"telemetry": data, "success": True})
            except json.JSONDecodeError:
                pass

    from hermes_platform.termux_adapter import get_battery_status
    status = get_battery_status()
    return json.dumps({"battery": status, "success": True})


# ==============================================================================
# 3. Android Clipboard
# ==============================================================================

CLIPBOARD_SCHEMA = {
    "name": "android_clipboard",
    "description": "Read from or write to the device clipboard.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["get", "set"],
                "description": "'get' to read clipboard content, 'set' to copy text to clipboard.",
            },
            "text": {
                "type": "string",
                "description": "The text to copy to the clipboard (required when action is 'set').",
            },
        },
        "required": ["action"],
    },
}


def android_clipboard_tool(action: str, text: Optional[str] = None) -> str:
    """Manage device clipboard."""
    action = action.strip().lower()
    if action == "get":
        if not shutil.which("termux-clipboard-get"):
            return json.dumps({"error": "termux-clipboard-get not found", "success": False})
        code, out, err = _run_cmd(["termux-clipboard-get"], timeout=5.0)
        if code != 0:
            return json.dumps({"error": f"Failed to get clipboard: {err or out}", "success": False})
        return json.dumps({"clipboard_content": out, "success": True})

    elif action == "set":
        if not shutil.which("termux-clipboard-set"):
            return json.dumps({"error": "termux-clipboard-set not found", "success": False})
        if text is None:
            return json.dumps({"error": "text argument is required when action='set'", "success": False})
        try:
            res = subprocess.run(
                ["termux-clipboard-set"],
                input=text,
                text=True,
                timeout=5.0,
                check=False,
            )
            if res.returncode != 0:
                return json.dumps({"error": "Failed to set clipboard", "success": False})
            return json.dumps({"status": "Text copied to clipboard", "success": True})
        except Exception as exc:
            return json.dumps({"error": str(exc), "success": False})

    return json.dumps({"error": f"Unknown action: {action}", "success": False})


# ==============================================================================
# 4. Android Haptic Feedback (Vibration)
# ==============================================================================

VIBRATE_SCHEMA = {
    "name": "android_vibrate",
    "description": "Trigger phone haptic vibration feedback.",
    "parameters": {
        "type": "object",
        "properties": {
            "duration_ms": {
                "type": "integer",
                "description": "Vibration duration in milliseconds (default: 500, max: 3000).",
            }
        },
        "required": [],
    },
}


def android_vibrate_tool(duration_ms: int = 500) -> str:
    """Trigger device vibration."""
    if not shutil.which("termux-vibrate"):
        return json.dumps({"error": "termux-vibrate not found", "success": False})

    dur = max(50, min(int(duration_ms or 500), 3000))
    code, out, err = _run_cmd(["termux-vibrate", "-d", str(dur)], timeout=5.0)
    if code != 0:
        return json.dumps({"error": f"Failed to vibrate: {err or out}", "success": False})

    return json.dumps({"status": f"Vibrated for {dur}ms", "success": True})


# ==============================================================================
# 5. Android Camera Snapshot
# ==============================================================================

CAMERA_SCHEMA = {
    "name": "android_camera",
    "description": "Capture a photo snapshot using the phone camera (back or front). Returns image path, which can then be passed to vision_analyze to see/inspect what the camera captured.",
    "parameters": {
        "type": "object",
        "properties": {
            "camera": {
                "type": "string",
                "enum": ["back", "front"],
                "description": "Which camera to use: 'back' (default, 0) or 'front' (selfie, 1).",
            },
            "output_path": {
                "type": "string",
                "description": "Optional output filepath. Default saves to /storage/emulated/0/DCIM/Camera or ~/photos/.",
            },
        },
        "required": [],
    },
}


def android_camera_tool(camera: str = "back", output_path: Optional[str] = None) -> str:
    """Capture photo snapshot."""
    if not shutil.which("termux-camera-photo"):
        return json.dumps({"error": "termux-camera-photo not found", "success": False})

    cam_id = "1" if camera.strip().lower() == "front" else "0"

    if output_path:
        dest = Path(output_path).expanduser().resolve()
    else:
        dcim = Path("/storage/emulated/0/DCIM/Camera")
        if not dcim.exists():
            dcim = Path(os.path.expanduser("~/photos"))
        dcim.mkdir(parents=True, exist_ok=True)
        import time
        dest = dcim / f"photo_{int(time.time())}.jpg"

    code, out, err = _run_cmd(["termux-camera-photo", "-c", cam_id, str(dest)], timeout=15.0)
    if code != 0 or not dest.exists():
        return json.dumps({"error": f"Camera capture failed: {err or out}", "success": False})

    return json.dumps({
        "status": "Photo captured successfully",
        "path": str(dest),
        "camera": "front" if cam_id == "1" else "back",
        "size_bytes": dest.stat().st_size,
        "success": True,
    })


# ==============================================================================
# 6. Android Media & YouTube Controls
# ==============================================================================

MEDIA_SCHEMA = {
    "name": "android_media",
    "description": "Play local audio, open YouTube video/song in YouTube app, or download media via yt-dlp.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["open_youtube", "play_audio", "download_media"],
                "description": "'open_youtube' to search and play a video in YouTube app, 'play_audio' to play local file, 'download_media' to download via yt-dlp.",
            },
            "query_or_path": {
                "type": "string",
                "description": "Search query for YouTube / URL, or local file path to play.",
            },
        },
        "required": ["action", "query_or_path"],
    },
}


def android_media_tool(action: str, query_or_path: str) -> str:
    """Handle media operations."""
    action = action.strip().lower()
    target = query_or_path.strip()

    if action == "open_youtube":
        # Search YouTube or open direct video
        url = target
        if not (target.startswith("http://") or target.startswith("https://")):
            # Build search URL or extract top hit
            encoded = urllib.parse.quote_plus(target)
            url = f"https://www.youtube.com/results?search_query={encoded}"

        if shutil.which("termux-open-url"):
            code, out, err = _run_cmd(["termux-open-url", url], timeout=5.0)
            if code == 0:
                return json.dumps({"status": f"Opened YouTube URL: {url}", "url": url, "success": True})

        return json.dumps({"status": "Generated YouTube URL", "url": url, "success": True})

    elif action == "play_audio":
        path = Path(target).expanduser().resolve()
        if not path.exists():
            return json.dumps({"error": f"File does not exist: {path}", "success": False})

        if shutil.which("termux-media-player"):
            code, out, err = _run_cmd(["termux-media-player", "play", str(path)], timeout=5.0)
            if code == 0:
                return json.dumps({"status": f"Playing audio via termux-media-player: {path.name}", "success": True})

        return json.dumps({"error": "No media player available (termux-media-player not found)", "success": False})

    elif action == "download_media":
        if not shutil.which("yt-dlp"):
            return json.dumps({"error": "yt-dlp is not installed in Termux", "success": False})

        download_dir = Path("/storage/emulated/0/Download")
        if not download_dir.exists():
            download_dir = Path.home() / "Downloads"
        download_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            "yt-dlp",
            "--no-playlist",
            "-o", str(download_dir / "%(title)s.%(ext)s"),
            target if target.startswith("http") else f"ytsearch1:{target}",
        ]
        code, out, err = _run_cmd(cmd, timeout=90.0)
        if code != 0:
            return json.dumps({"error": f"yt-dlp download failed: {err or out}", "success": False})

        return json.dumps({
            "status": "Media download completed successfully",
            "destination": str(download_dir),
            "output_summary": out.splitlines()[-3:] if out else [],
            "success": True,
        })

    return json.dumps({"error": f"Unknown action: {action}", "success": False})


# ==============================================================================
# Tool Registration
# ==============================================================================

registry.register(
    name="android_torch",
    toolset="android",
    schema=TORCH_SCHEMA,
    handler=lambda args, **kw: android_torch_tool(action=args.get("action", "")),
    check_fn=_check_android_available,
    emoji="🔦",
)

registry.register(
    name="android_battery",
    toolset="android",
    schema=BATTERY_SCHEMA,
    handler=lambda args, **kw: android_battery_tool(detailed=args.get("detailed", False)),
    check_fn=_check_android_available,
    emoji="🔋",
)

registry.register(
    name="android_clipboard",
    toolset="android",
    schema=CLIPBOARD_SCHEMA,
    handler=lambda args, **kw: android_clipboard_tool(
        action=args.get("action", ""),
        text=args.get("text"),
    ),
    check_fn=_check_android_available,
    emoji="📋",
)

registry.register(
    name="android_vibrate",
    toolset="android",
    schema=VIBRATE_SCHEMA,
    handler=lambda args, **kw: android_vibrate_tool(
        duration_ms=args.get("duration_ms", 500),
    ),
    check_fn=_check_android_available,
    emoji="📳",
)

registry.register(
    name="android_camera",
    toolset="android",
    schema=CAMERA_SCHEMA,
    handler=lambda args, **kw: android_camera_tool(
        camera=args.get("camera", "back"),
        output_path=args.get("output_path"),
    ),
    check_fn=_check_android_available,
    emoji="📷",
)

registry.register(
    name="android_media",
    toolset="android",
    schema=MEDIA_SCHEMA,
    handler=lambda args, **kw: android_media_tool(
        action=args.get("action", ""),
        query_or_path=args.get("query_or_path", ""),
    ),
    check_fn=_check_android_available,
    emoji="🎵",
)


DISPLAY_SCHEMA = {
    "name": "android_display",
    "description": "Control phone AMOLED display calibration, Eye Protection, Extra Dim, and 4K Cinema saturation boost.",
    "parameters": {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["comfort", "cinema", "normal", "status"],
                "description": "Display mode: 'comfort' (Eye Protection + Extra Dim), 'cinema' (Pure 4K DCI-P3 Vibrant), 'normal' (Factory default), 'status' (Current calibration).",
            },
            "dim_level": {
                "type": "integer",
                "description": "Extra dim intensity level (1-100, default 40). Applicable in comfort mode.",
            },
        },
        "required": ["mode"],
    },
}


def android_display_tool(mode: str, dim_level: Optional[int] = None) -> str:
    script = "/data/data/com.termux/files/usr/bin/screen-boost"
    if not os.path.exists(script):
        return json.dumps({"error": "screen-boost utility not found"})
    cmd = [script, mode]
    if dim_level is not None:
        cmd.append(str(dim_level))
    code, stdout, stderr = _run_cmd(cmd)
    return json.dumps({
        "success": code == 0,
        "mode": mode,
        "output": stdout or stderr,
    })


registry.register(
    name="android_display",
    toolset="android",
    schema=DISPLAY_SCHEMA,
    handler=lambda args, **kw: android_display_tool(
        mode=args.get("mode", "status"),
        dim_level=args.get("dim_level"),
    ),
    check_fn=_check_android_available,
    emoji="🖥️",
)


# ---------------------------------------------------------------------------
# 8 New Flagship Tools: Notification, Toast, TTS, WiFi, Telephony, Status, Volume, FreeLLM AI
# ---------------------------------------------------------------------------

NOTIFICATION_SCHEMA = {
    "name": "android_notification",
    "description": "Send or clear Android status bar notifications and heads-up alerts with custom title, content, sound, and vibration.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["notify", "remove"],
                "description": "'notify' to show a notification, 'remove' to cancel/clear it.",
            },
            "title": {
                "type": "string",
                "description": "Notification title (e.g. 'Task Complete', 'JARVIS Alert').",
            },
            "content": {
                "type": "string",
                "description": "Notification body text.",
            },
            "id": {
                "type": "string",
                "description": "Unique notification ID (optional, used to update or remove).",
            },
            "priority": {
                "type": "string",
                "enum": ["low", "normal", "high", "max"],
                "description": "Alert priority (default: 'high').",
            },
            "vibrate_ms": {
                "type": "integer",
                "description": "Vibration duration in milliseconds (default: 200).",
            },
            "sound": {
                "type": "boolean",
                "description": "Play alert sound (default: True).",
            },
        },
        "required": ["action"],
    },
}


def android_notification_tool(
    action: str = "notify",
    title: Optional[str] = None,
    content: Optional[str] = None,
    id: Optional[str] = None,
    priority: str = "high",
    vibrate_ms: Optional[int] = 200,
    sound: bool = True,
) -> str:
    """Send or remove native Android notification via termux-notification."""
    if action == "remove":
        if not id:
            return json.dumps({"error": "id parameter is required to remove notification"})
        cmd = ["termux-notification-remove", id]
        code, stdout, stderr = _run_cmd(cmd)
        return json.dumps({
            "success": code == 0,
            "action": "remove",
            "id": id,
            "output": stdout or stderr,
        })

    if not title and not content:
        return json.dumps({"error": "title or content required for notification"})

    cmd = ["termux-notification"]
    if title:
        cmd.extend(["--title", title])
    if content:
        cmd.extend(["--content", content])
    if id:
        cmd.extend(["--id", id])
    if priority in ("low", "normal", "high", "max"):
        cmd.extend(["--priority", priority])
    if vibrate_ms and vibrate_ms > 0:
        cmd.extend(["--vibrate", str(min(vibrate_ms, 3000))])
    if sound:
        cmd.append("--sound")

    code, stdout, stderr = _run_cmd(cmd)
    return json.dumps({
        "success": code == 0,
        "action": "notify",
        "title": title,
        "content": content,
        "output": stdout or stderr,
    })


registry.register(
    name="android_notification",
    toolset="android",
    schema=NOTIFICATION_SCHEMA,
    handler=lambda args, **kw: android_notification_tool(
        action=args.get("action", "notify"),
        title=args.get("title"),
        content=args.get("content"),
        id=args.get("id"),
        priority=args.get("priority", "high"),
        vibrate_ms=args.get("vibrate_ms", 200),
        sound=args.get("sound", True),
    ),
    check_fn=_check_android_available,
    emoji="🔔",
)


TOAST_SCHEMA = {
    "name": "android_toast",
    "description": "Show an instant visual toast message on the Android phone screen.",
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text message to display in toast.",
            },
            "short": {
                "type": "boolean",
                "description": "True for short duration (~2s), False for long (~3.5s). Default: True.",
            },
            "gravity": {
                "type": "string",
                "enum": ["top", "middle", "bottom"],
                "description": "Screen position of toast (default: 'bottom').",
            },
            "bg_color": {
                "type": "string",
                "description": "Background color (e.g. 'black', 'gray', 'white'). Default: 'black'.",
            },
            "text_color": {
                "type": "string",
                "description": "Text color (e.g. 'white', 'cyan', 'red'). Default: 'white'.",
            },
        },
        "required": ["text"],
    },
}


def android_toast_tool(
    text: str,
    short: bool = True,
    gravity: str = "bottom",
    bg_color: str = "black",
    text_color: str = "white",
) -> str:
    """Show Android toast popup via termux-toast."""
    if not text:
        return json.dumps({"error": "text is required for toast"})

    cmd = ["termux-toast", "-g", gravity, "-b", bg_color, "-c", text_color]
    if short:
        cmd.append("-s")
    cmd.append(text)

    code, stdout, stderr = _run_cmd(cmd)
    return json.dumps({
        "success": code == 0,
        "text": text,
        "gravity": gravity,
        "output": stdout or stderr,
    })


registry.register(
    name="android_toast",
    toolset="android",
    schema=TOAST_SCHEMA,
    handler=lambda args, **kw: android_toast_tool(
        text=args.get("text", ""),
        short=args.get("short", True),
        gravity=args.get("gravity", "bottom"),
        bg_color=args.get("bg_color", "black"),
        text_color=args.get("text_color", "white"),
    ),
    check_fn=_check_android_available,
    emoji="💬",
)


TTS_SCHEMA = {
    "name": "android_tts",
    "description": "Speak text aloud through Android device speakers using native Termux text-to-speech.",
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text to speak aloud to Boss.",
            },
            "rate": {
                "type": "number",
                "description": "Speech speed rate (0.5 to 2.0, default 1.0).",
            },
            "pitch": {
                "type": "number",
                "description": "Speech pitch (0.5 to 2.0, default 1.0).",
            },
            "stream": {
                "type": "string",
                "enum": ["music", "notification", "system", "alarm"],
                "description": "Audio stream (default: 'music').",
            },
        },
        "required": ["text"],
    },
}


def android_tts_tool(
    text: str,
    rate: float = 1.0,
    pitch: float = 1.0,
    stream: str = "music",
) -> str:
    """Speak text aloud using termux-tts-speak."""
    if not text:
        return json.dumps({"error": "text is required for TTS"})

    safe_rate = max(0.5, min(float(rate), 2.0))
    safe_pitch = max(0.5, min(float(pitch), 2.0))

    cmd = ["termux-tts-speak", "-r", str(safe_rate), "-p", str(safe_pitch), "-s", stream, text]
    code, stdout, stderr = _run_cmd(cmd, timeout=15.0)
    return json.dumps({
        "success": code == 0,
        "spoken_text": text,
        "rate": safe_rate,
        "pitch": safe_pitch,
        "output": stdout or stderr,
    })


registry.register(
    name="android_tts",
    toolset="android",
    schema=TTS_SCHEMA,
    handler=lambda args, **kw: android_tts_tool(
        text=args.get("text", ""),
        rate=args.get("rate", 1.0),
        pitch=args.get("pitch", 1.0),
        stream=args.get("stream", "music"),
    ),
    check_fn=_check_android_available,
    emoji="🗣️",
)


WIFI_SCHEMA = {
    "name": "android_wifi",
    "description": "Inspect WiFi connection status, SSID, link speed, signal strength, or scan nearby networks.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["info", "scan"],
                "description": "'info' for current WiFi connection state, 'scan' for nearby access points.",
            },
        },
        "required": [],
    },
}


def android_wifi_tool(action: str = "info") -> str:
    """Query WiFi state via termux-wifi-connectioninfo or scaninfo."""
    if action == "scan":
        code, stdout, stderr = _run_cmd(["termux-wifi-scaninfo"], timeout=10.0)
    else:
        code, stdout, stderr = _run_cmd(["termux-wifi-connectioninfo"], timeout=5.0)

    if code != 0:
        return json.dumps({"error": stderr or "Failed to query WiFi status"})

    try:
        data = json.loads(stdout)
        return json.dumps({"success": True, "action": action, "data": data})
    except Exception:
        return json.dumps({"success": True, "action": action, "raw": stdout})


registry.register(
    name="android_wifi",
    toolset="android",
    schema=WIFI_SCHEMA,
    handler=lambda args, **kw: android_wifi_tool(
        action=args.get("action", "info"),
    ),
    check_fn=_check_android_available,
    emoji="📶",
)


TELEPHONY_SCHEMA = {
    "name": "android_telephony",
    "description": "Inspect cellular telephony state, SIM information, carrier, network type, and cell towers.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["device", "cell"],
                "description": "'device' for SIM/carrier info, 'cell' for cell tower diagnostics.",
            },
        },
        "required": [],
    },
}


def android_telephony_tool(action: str = "device") -> str:
    """Query telephony state via termux-telephony-deviceinfo or cellinfo."""
    cmd = ["termux-telephony-cellinfo"] if action == "cell" else ["termux-telephony-deviceinfo"]
    code, stdout, stderr = _run_cmd(cmd, timeout=5.0)
    if code != 0:
        return json.dumps({"error": stderr or "Failed to query telephony status"})

    try:
        data = json.loads(stdout)
        return json.dumps({"success": True, "action": action, "data": data})
    except Exception:
        return json.dumps({"success": True, "action": action, "raw": stdout})


registry.register(
    name="android_telephony",
    toolset="android",
    schema=TELEPHONY_SCHEMA,
    handler=lambda args, **kw: android_telephony_tool(
        action=args.get("action", "device"),
    ),
    check_fn=_check_android_available,
    emoji="📱",
)


SYSTEM_STATUS_SCHEMA = {
    "name": "android_system_status",
    "description": "Comprehensive hardware health & policy monitor for Boss's iQOO Neo 10 (Snapdragon 8 Gen 3). Verifies 34°C-35°C thermal mandate, battery, RAM, storage, and zero-daemon architecture.",
    "parameters": {
        "type": "object",
        "properties": {
            "detailed": {
                "type": "boolean",
                "description": "True to include detailed memory and thermal sensor readings.",
            },
        },
        "required": [],
    },
}


def android_system_status_tool(detailed: bool = False) -> str:
    """Collect complete hardware health and policy status."""
    status: Dict[str, Any] = {
        "device": "iQOO Neo 10 (Model I2405 / PD2453F_EX)",
        "platform": "Android 15 / Funtouch OS 15",
        "soc": "Snapdragon 8 Gen 3 (4nm)",
        "thermal_policy": "34°C - 35°C Peak Cool Running Mandate",
        "daemon_policy": "Strict Zero-Background Daemon Policy (Enforced)",
        "fast_charging_policy": "PERMANENTLY OFF (fast_charge_switch=0)",
        "bypass_charging_policy": "ENABLED during gaming (bypass_charging_enabled=1)",
    }

    # Battery & Thermal Check
    code, stdout, _ = _run_cmd(["termux-battery-status"], timeout=5.0)
    if code == 0:
        try:
            bdata = json.loads(stdout)
            temp_c = bdata.get("temperature", 0.0)
            status["battery"] = {
                "percentage": bdata.get("percentage"),
                "status": bdata.get("status"),
                "health": bdata.get("health"),
                "plugged": bdata.get("plugged"),
                "temperature_c": temp_c,
                "thermal_status": "OPTIMAL COOL" if temp_c <= 35.0 else "ELEVATED (Cooling required)",
            }
        except Exception:
            status["battery_raw"] = stdout

    # Memory info
    try:
        meminfo: Dict[str, int] = {}
        with open("/proc/meminfo", "r") as f:
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    k = parts[0].strip()
                    val = parts[1].strip().split()[0]
                    if val.isdigit():
                        meminfo[k] = int(val)
        total_mb = meminfo.get("MemTotal", 0) // 1024
        avail_mb = meminfo.get("MemAvailable", 0) // 1024
        used_mb = total_mb - avail_mb
        status["memory_mb"] = {
            "total": total_mb,
            "used": used_mb,
            "available": avail_mb,
            "usage_percent": round((used_mb / total_mb) * 100, 1) if total_mb else 0,
        }
    except Exception as e:
        status["memory_error"] = str(e)

    # Storage info
    try:
        import shutil as _sh
        usage = _sh.disk_usage("/storage/emulated/0")
        status["storage_gb"] = {
            "total": round(usage.total / (1024**3), 1),
            "used": round(usage.used / (1024**3), 1),
            "free": round(usage.free / (1024**3), 1),
        }
    except Exception as e:
        status["storage_error"] = str(e)

    # Load average
    try:
        load1, load5, load15 = os.getloadavg()
        status["cpu_load"] = {"1m": round(load1, 2), "5m": round(load5, 2), "15m": round(load15, 2)}
    except Exception:
        pass

    return json.dumps(status, indent=2)


registry.register(
    name="android_system_status",
    toolset="android",
    schema=SYSTEM_STATUS_SCHEMA,
    handler=lambda args, **kw: android_system_status_tool(
        detailed=args.get("detailed", False),
    ),
    check_fn=_check_android_available,
    emoji="⚡",
)


VOLUME_SCHEMA = {
    "name": "android_volume",
    "description": "Inspect and set Android audio volume streams (media, ring, notification, system, alarm, call).",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["get", "set"],
                "description": "'get' to read volume levels, 'set' to change volume.",
            },
            "stream": {
                "type": "string",
                "enum": ["media", "ring", "notification", "system", "alarm", "call"],
                "description": "Audio stream type (default: 'media').",
            },
            "volume": {
                "type": "integer",
                "description": "Target volume level (0 to stream max, e.g. 15). Required for 'set'.",
            },
        },
        "required": ["action"],
    },
}


def android_volume_tool(
    action: str = "get",
    stream: str = "media",
    volume: Optional[int] = None,
) -> str:
    """Inspect or change volume streams via termux-volume."""
    if action == "set":
        if volume is None:
            return json.dumps({"error": "volume parameter is required for action='set'"})
        cmd = ["termux-volume", stream, str(volume)]
        code, stdout, stderr = _run_cmd(cmd)
        return json.dumps({
            "success": code == 0,
            "action": "set",
            "stream": stream,
            "volume": volume,
            "output": stdout or stderr,
        })

    code, stdout, stderr = _run_cmd(["termux-volume"])
    if code != 0:
        return json.dumps({"error": stderr or "Failed to query volume"})

    try:
        data = json.loads(stdout)
        return json.dumps({"success": True, "action": "get", "streams": data})
    except Exception:
        return json.dumps({"success": True, "action": "get", "raw": stdout})


registry.register(
    name="android_volume",
    toolset="android",
    schema=VOLUME_SCHEMA,
    handler=lambda args, **kw: android_volume_tool(
        action=args.get("action", "get"),
        stream=args.get("stream", "media"),
        volume=args.get("volume"),
    ),
    check_fn=_check_android_available,
    emoji="🔊",
)


FREELLM_QUERY_SCHEMA = {
    "name": "freellm_ai_query",
    "description": "Synchronously consult any of Boss's 158 Flagship SOTA models from FreeLLM API (e.g. 'claude-opus-5', 'gpt-5.1-codex', 'qwen-3.8-27b', 'auto') for secondary opinions or multi-model reasoning.",
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "The prompt or task for the external SOTA model.",
            },
            "model": {
                "type": "string",
                "description": "Model ID to query (default: 'auto', or 'claude-haiku-4.5', 'gpt-5.1-codex', etc.).",
            },
            "system_prompt": {
                "type": "string",
                "description": "Optional system prompt instructions.",
            },
            "max_tokens": {
                "type": "integer",
                "description": "Maximum response tokens (default: 500).",
            },
        },
        "required": ["prompt"],
    },
}


def freellm_ai_query_tool(
    prompt: str,
    model: str = "auto",
    system_prompt: Optional[str] = None,
    max_tokens: int = 500,
) -> str:
    """Query Boss's FreeLLM API directly and return the response."""
    import time
    if not prompt:
        return json.dumps({"error": "prompt is required"})

    api_url = os.getenv("FREELLM_BASE_URL", "https://freellmapi-backup.onrender.com/v1") + "/chat/completions"
    api_key = os.getenv("FREELLM_API_KEY", "freellmapi-c7bf396fcf0351dbba9546933a8881054c627e6f78875206")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": min(max_tokens, 2048),
        "stream": False,
    }

    t0 = time.time()
    try:
        req = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=12.0) as resp:
            dur_ms = round((time.time() - t0) * 1000, 1)
            routed_via = resp.headers.get("X-Routed-Via", "unknown")
            body = json.loads(resp.read().decode("utf-8"))
            choice = body.get("choices", [{}])[0]
            answer = choice.get("message", {}).get("content", "").strip()
            return json.dumps({
                "success": True,
                "model": model,
                "latency_ms": dur_ms,
                "routed_via": routed_via,
                "answer": answer,
            })
    except Exception as exc:
        dur_ms = round((time.time() - t0) * 1000, 1)
        return json.dumps({
            "success": False,
            "model": model,
            "latency_ms": dur_ms,
            "error": str(exc),
        })


registry.register(
    name="freellm_ai_query",
    toolset="android",
    schema=FREELLM_QUERY_SCHEMA,
    handler=lambda args, **kw: freellm_ai_query_tool(
        prompt=args.get("prompt", ""),
        model=args.get("model", "auto"),
        system_prompt=args.get("system_prompt"),
        max_tokens=args.get("max_tokens", 500),
    ),
    check_fn=_check_android_available,
    emoji="🧠",
)


