"""GoodNotes screen capture + frame differencing.

Captures the GoodNotes window every N seconds, computes frame diffs
to detect new ink, and triggers OCR on changed regions.

Uses macOS `screencapture` CLI for window-level capture and PIL/numpy
for image differencing.
"""

from __future__ import annotations

import io
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image


def find_goodnotes_window_id() -> Optional[str]:
    """Find the window ID of the GoodNotes application on macOS.

    Uses `osascript` to query running application windows.
    Returns the window ID string or None if GoodNotes is not running.
    """
    script = '''
    tell application "System Events"
        set windowList to {}
        repeat with proc in (every process whose name contains "GoodNotes")
            repeat with win in (every window of proc)
                set end of windowList to (id of win as text)
            end repeat
        end repeat
        if (count of windowList) > 0 then
            return item 1 of windowList
        else
            return ""
        end if
    end tell
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=5
        )
        window_id = result.stdout.strip()
        return window_id if window_id else None
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        return None


def capture_screen_region(output_path: Optional[str] = None) -> bytes:
    """Capture the full screen as PNG bytes.

    For window-specific capture, macOS screencapture with -l flag
    requires the CGWindowID (not the AS window id). Falls back to
    full screen capture and crops to GoodNotes region.
    """
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name

    subprocess.run(
        ["screencapture", "-x", "-t", "png", tmp_path],
        check=True, timeout=10
    )

    with open(tmp_path, "rb") as f:
        data = f.read()

    Path(tmp_path).unlink(missing_ok=True)

    if output_path:
        Path(output_path).write_bytes(data)

    return data


def capture_goodnotes_window() -> Optional[bytes]:
    """Capture just the GoodNotes window using CGWindowListCreateImage approach.

    Uses `screencapture -l <windowid>` which takes a CGWindowID.
    We get CGWindowIDs via the Quartz API.
    """
    try:
        # Get CGWindowID for GoodNotes via Python Quartz bindings
        result = subprocess.run(
            ["python3", "-c", """
import Quartz
windows = Quartz.CGWindowListCopyWindowInfo(
    Quartz.kCGWindowListOptionOnScreenOnly,
    Quartz.kCGNullWindowID
)
for w in windows:
    owner = w.get('kCGWindowOwnerName', '')
    if 'GoodNotes' in owner:
        print(w['kCGWindowNumber'])
        break
"""],
            capture_output=True, text=True, timeout=5
        )
        window_id = result.stdout.strip()
        if not window_id:
            return None

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        subprocess.run(
            ["screencapture", "-x", "-l", window_id, "-t", "png", tmp_path],
            check=True, timeout=10
        )

        with open(tmp_path, "rb") as f:
            data = f.read()
        Path(tmp_path).unlink(missing_ok=True)
        return data

    except (subprocess.SubprocessError, Exception):
        return None


class FrameDiffer:
    """Detects new ink in GoodNotes by comparing consecutive screenshots.

    Uses grayscale differencing with a threshold to find regions where
    new content has appeared. Returns bounding boxes of changed regions.
    """

    def __init__(self, threshold: int = 30, min_area: int = 100):
        self.threshold = threshold
        self.min_area = min_area
        self.previous_frame: Optional[np.ndarray] = None

    def detect_changes(self, current_bytes: bytes) -> Optional[dict]:
        """Compare current frame against previous.

        Returns dict with bounding box {x, y, width, height} of changed region,
        or None if no significant change detected.
        """
        current = Image.open(io.BytesIO(current_bytes)).convert("L")
        current_arr = np.array(current)

        if self.previous_frame is None:
            self.previous_frame = current_arr
            return None

        # Compute absolute difference
        diff = np.abs(current_arr.astype(int) - self.previous_frame.astype(int))
        mask = diff > self.threshold

        self.previous_frame = current_arr

        # Find bounding box of changed pixels
        changed_pixels = np.argwhere(mask)
        if len(changed_pixels) < self.min_area:
            return None

        y_min, x_min = changed_pixels.min(axis=0)
        y_max, x_max = changed_pixels.max(axis=0)

        return {
            "x": int(x_min),
            "y": int(y_min),
            "width": int(x_max - x_min),
            "height": int(y_max - y_min),
            "changed_pixels": int(len(changed_pixels)),
        }

    def reset(self):
        self.previous_frame = None


class GoodNotesCaptureLoop:
    """Continuous capture loop for GoodNotes screen monitoring."""

    def __init__(
        self,
        session_id: str,
        interval: float = 3.0,
        output_dir: Optional[str] = None,
    ):
        self.session_id = session_id
        self.interval = interval
        self.output_dir = Path(output_dir) if output_dir else None
        self.differ = FrameDiffer()
        self.frame_number = 0
        self.running = False
        self.captures: list[dict] = []

        if self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)

    def capture_once(self) -> dict:
        """Capture a single frame and check for changes.

        Returns a ScreenCapture-compatible dict.
        """
        self.frame_number += 1
        timestamp = datetime.utcnow()

        # Try window-specific capture first, fall back to full screen
        image_bytes = capture_goodnotes_window()
        if image_bytes is None:
            image_bytes = capture_screen_region()

        # Save frame if output dir is set
        screenshot_path = None
        if self.output_dir:
            screenshot_path = str(
                self.output_dir / f"frame-{self.frame_number:04d}.png"
            )
            Path(screenshot_path).write_bytes(image_bytes)

        # Detect changes
        diff = self.differ.detect_changes(image_bytes)

        result = {
            "timestamp": timestamp.isoformat(),
            "session_id": self.session_id,
            "frame_number": self.frame_number,
            "screenshot_path": screenshot_path,
            "diff_detected": diff is not None,
            "new_ink_region": diff,
            "image_bytes": image_bytes,
        }

        self.captures.append(result)
        return result

    def run(self, duration: Optional[float] = None, on_diff=None):
        """Run the capture loop.

        Args:
            duration: Max seconds to run. None = run until stopped.
            on_diff: Callback function called with (frame_dict, image_bytes)
                     when new ink is detected.
        """
        self.running = True
        start = time.time()

        while self.running:
            if duration and (time.time() - start) > duration:
                break

            result = self.capture_once()

            if result["diff_detected"] and on_diff:
                on_diff(result, result.pop("image_bytes"))
            else:
                result.pop("image_bytes", None)

            time.sleep(self.interval)

    def stop(self):
        self.running = False
