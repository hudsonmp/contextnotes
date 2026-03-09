"""Chrome reading context capture loop via AppleScript.

Polls the active Chrome tab every N seconds:
1. Gets the active tab URL + title via AppleScript
2. Injects chrome_capture.js via Chrome's `execute javascript`
3. Parses the returned JSON reading context
4. Feeds it to SessionCoordinator.update_reading_context()

No MCP dependency — uses AppleScript's direct Chrome automation.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

JS_PATH = Path(__file__).parent / "chrome_capture.js"


def get_active_tab_info() -> Optional[dict]:
    """Get the active Chrome tab's URL and title via AppleScript.

    Returns dict with {url, title} or None if Chrome isn't running.
    """
    script = '''
    tell application "System Events"
        if not (exists process "Google Chrome") then return "NOT_RUNNING"
    end tell
    tell application "Google Chrome"
        set tabUrl to URL of active tab of first window
        set tabTitle to title of active tab of first window
        return tabUrl & "|||" & tabTitle
    end tell
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=5,
        )
        output = result.stdout.strip()
        if output == "NOT_RUNNING" or "|||" not in output:
            return None
        url, title = output.split("|||", 1)
        return {"url": url, "title": title}
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        return None


_JS_PERMISSION_ERROR_SHOWN = False


def inject_capture_js() -> Optional[dict]:
    """Inject chrome_capture.js into the active Chrome tab and return the reading context.

    Uses AppleScript to read the JS file and execute it in Chrome.
    Returns the parsed reading context dict, or None on failure.
    """
    global _JS_PERMISSION_ERROR_SHOWN

    # Write a wrapped version that returns JSON
    js_source = JS_PATH.read_text()
    wrapped_js = f"JSON.stringify({js_source})"

    # Write to temp file so AppleScript can read it (avoids escaping issues)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as tmp:
        tmp.write(wrapped_js)
        tmp_path = tmp.name

    script = f'''
    set jsContent to read POSIX file "{tmp_path}"
    tell application "Google Chrome"
        set result to execute front window's active tab javascript jsContent
        return result
    end tell
    '''

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10,
        )
        Path(tmp_path).unlink(missing_ok=True)

        # Check for the JS permission error
        if "JavaScript through AppleScript is turned off" in result.stderr:
            if not _JS_PERMISSION_ERROR_SHOWN:
                _JS_PERMISSION_ERROR_SHOWN = True
                print("\n[chrome] Enable JavaScript from Apple Events (one-time):")
                print("         Chrome → View → Developer → Allow JavaScript from Apple Events\n")
            return None

        output = result.stdout.strip()
        if not output or output == "missing value":
            return None
        return json.loads(output)

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, json.JSONDecodeError):
        Path(tmp_path).unlink(missing_ok=True)
        return None


class ChromeReadingLoop:
    """Polls Chrome for reading context at regular intervals."""

    def __init__(self, interval: float = 5.0):
        self.interval = interval
        self.running = False
        self.poll_count = 0
        self.last_context: Optional[dict] = None

    def poll_once(self) -> Optional[dict]:
        """Single poll: inject JS, return reading context."""
        self.poll_count += 1
        context = inject_capture_js()
        if context:
            self.last_context = context
        return context

    def run(self, on_context: Optional[Callable] = None, duration: Optional[float] = None):
        """Run the polling loop.

        Args:
            on_context: Callback called with (context_dict) on each successful capture.
            duration: Max seconds to run. None = run until stopped.
        """
        self.running = True
        start = time.time()

        while self.running:
            if duration and (time.time() - start) > duration:
                break

            context = self.poll_once()
            if context and on_context:
                on_context(context)

            time.sleep(self.interval)

    def stop(self):
        self.running = False
