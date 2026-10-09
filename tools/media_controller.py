"""On-demand audio playback and media controller for Termux & Linux.

Executes 100% synchronously on-demand with zero background daemons.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional


def play_audio(file_path: str | Path) -> Dict[str, Any]:
    """Play audio file using available on-demand player (mpv or termux-media-player)."""
    p = Path(file_path).expanduser().resolve()
    if not p.is_file():
        return {"success": False, "error": f"Audio file not found: {p}"}

    # Preference 1: mpv (terminates after playback)
    if shutil.which("mpv"):
        try:
            res = subprocess.run(
                ["mpv", "--no-video", "--really-quiet", str(p)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            return {"success": res.returncode == 0, "player": "mpv"}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Playback timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # Preference 2: termux-media-player
    if shutil.which("termux-media-player"):
        try:
            res = subprocess.run(
                ["termux-media-player", "play", str(p)],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return {"success": res.returncode == 0, "player": "termux-media-player"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    return {"success": False, "error": "No audio player available (install mpv or termux-api)"}
