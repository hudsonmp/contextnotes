"""iPad mirroring automation — start QuickTime mirroring via AppleScript UI automation.

Attempts to programmatically open QuickTime Player and select the iPad
as a video recording source, giving us a capturable window on Mac.

This uses System Events UI automation (accessibility scripting), which:
- Requires "Accessibility" permission for the terminal app
- Takes ~10-20 seconds to complete
- Is fragile to macOS UI changes

If automation fails, falls back to iCloud OCR polling.
"""

from __future__ import annotations

import subprocess
import time
from typing import Optional


def find_ipad_name() -> Optional[str]:
    """Find the name of a connected iPad via system_profiler."""
    try:
        result = subprocess.run(
            ["system_profiler", "SPUSBDataType", "-json"],
            capture_output=True, text=True, timeout=10,
        )
        import json
        data = json.loads(result.stdout)
        for controller in data.get("SPUSBDataType", []):
            for item in controller.get("_items", []):
                name = item.get("_name", "")
                if "iPad" in name:
                    return name
                # Check nested hubs
                for sub in item.get("_items", []):
                    if "iPad" in sub.get("_name", ""):
                        return sub["_name"]
    except Exception:
        pass

    # Also check via AppleScript for paired devices
    try:
        result = subprocess.run(
            ["osascript", "-e", '''
            tell application "System Events"
                set deviceList to name of every process whose name contains "iPad"
                if (count of deviceList) > 0 then
                    return item 1 of deviceList
                end if
            end tell
            return ""
            '''],
            capture_output=True, text=True, timeout=5,
        )
        name = result.stdout.strip()
        if name:
            return name
    except Exception:
        pass

    return None


def is_mirror_window_open() -> bool:
    """Check if an iPad mirror window (QuickTime or macOS Mirroring) already exists."""
    try:
        import Quartz
        windows = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly,
            Quartz.kCGNullWindowID,
        )
        for w in windows:
            owner = w.get("kCGWindowOwnerName", "").lower()
            name = w.get("kCGWindowName", "").lower()
            combined = f"{owner} {name}"
            bounds = w.get("kCGWindowBounds", {})
            h = bounds.get("Height", 0)
            width = bounds.get("Width", 0)

            # QuickTime with a recording window (not just the app)
            if "quicktime" in owner and h > 400 and width > 300:
                return True
            # macOS built-in mirroring
            if "iphone mirroring" in combined or "ipad" in combined:
                if h > 400 and width > 300:
                    return True
        return False
    except Exception:
        return False


def start_quicktime_mirror(device_name: Optional[str] = None, timeout: float = 25.0) -> bool:
    """Attempt to start iPad mirroring via QuickTime UI automation.

    This uses System Events to:
    1. Open QuickTime Player
    2. Create a new Movie Recording
    3. Click the device selector dropdown
    4. Select the iPad

    Requires Accessibility permission for the terminal app.
    Returns True if a mirror window was successfully created.
    """
    device_hint = device_name or "iPad"

    # AppleScript that automates QuickTime device selection
    script = f'''
    tell application "QuickTime Player"
        activate
        delay 1
        -- Create new movie recording
        set newDoc to new movie recording
        delay 2
    end tell

    -- Now use System Events to click the device selector
    tell application "System Events"
        tell process "QuickTime Player"
            set frontmost to true
            delay 0.5

            -- Find the recording window
            set recWindow to front window

            -- Look for the dropdown button near the record button
            -- The device selector is typically a pop up button or menu button
            set allButtons to every button of recWindow
            repeat with btn in allButtons
                try
                    set btnDesc to description of btn
                    if btnDesc contains "arrow" or btnDesc contains "device" or btnDesc contains "menu" then
                        click btn
                        delay 1

                        -- Look for iPad in the menu items
                        set menuItems to every menu item of menu 1 of btn
                        repeat with mi in menuItems
                            if name of mi contains "{device_hint}" then
                                click mi
                                delay 1
                                return "OK"
                            end if
                        end repeat
                    end if
                end try
            end repeat

            -- Alternative: try the pop-up button approach
            set allPopups to every pop up button of recWindow
            repeat with pu in allPopups
                try
                    click pu
                    delay 1
                    set menuItems to every menu item of menu 1 of pu
                    repeat with mi in menuItems
                        if name of mi contains "{device_hint}" then
                            click mi
                            delay 1
                            return "OK"
                        end if
                    end repeat
                end try
            end repeat
        end tell
    end tell
    return "FAILED"
    '''

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=timeout,
        )
        output = result.stdout.strip()

        if output == "OK":
            # Verify the window appeared
            time.sleep(2)
            return is_mirror_window_open()
        return False

    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        return False


def ensure_mirror(device_name: Optional[str] = None) -> bool:
    """Ensure an iPad mirror window is available.

    1. Check if one already exists → return True
    2. Try to start via QuickTime automation → return True/False
    """
    if is_mirror_window_open():
        return True

    print("[mirror] No iPad mirror window found. Attempting QuickTime automation...")
    print("[mirror] This requires Accessibility permission for your terminal.")

    success = start_quicktime_mirror(device_name)

    if success:
        print("[mirror] iPad mirror started via QuickTime.")
    else:
        print("[mirror] QuickTime automation failed. Falling back to iCloud OCR.")
        print("[mirror] For manual setup: QuickTime Player → File → New Movie Recording → select iPad")

    return success
