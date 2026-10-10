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
    "description": "Capture a photo snapshot using the phone camera (back or front). Returns image path.",
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
