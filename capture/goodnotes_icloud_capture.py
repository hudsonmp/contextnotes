"""GoodNotes iCloud capture — polls notebook OCR for new handwriting.

This is the iPad-compatible capture path. Instead of screenshotting a
GoodNotes window on Mac, it reads the .goodnotes file from iCloud Drive
(which syncs from iPad) and runs Apple Vision OCR to detect new text.

Uses the same Vision OCR engine as the goodnotes-mcp server.

Two modes:
  - Thumbnail mode: reads the first-page thumbnail from the .goodnotes zip.
    Only covers page 1, but no export needed.
  - PDF mode: if the user has exported the notebook as PDF to iCloud Drive,
    OCRs all pages. This is the preferred mode for multi-page notebooks.

The capture loop diffs OCR text between polls to detect new writing.
"""

from __future__ import annotations

import difflib
import io
import os
import sys
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

# Import Vision OCR directly from the goodnotes MCP server
GOODNOTES_MCP_PATH = Path.home() / "mcp-servers" / "goodnotes-mcp"
sys.path.insert(0, str(GOODNOTES_MCP_PATH))

from server import (
    find_goodnotes_files,
    find_notebook,
    vision_ocr_image_bytes,
    pdf_page_to_image_bytes,
    get_pdf_page_count,
)


class GoodNotesICloudCapture:
    """Polls GoodNotes notebooks via iCloud for new handwriting.

    Detects new text by diffing Apple Vision OCR output between polls.
    Works with GoodNotes on iPad — no mirroring or Mac app required.
    """

    def __init__(
        self,
        notebook_name: str,
        session_id: str,
        poll_interval: float = 15.0,
        max_pages: int = 5,
    ):
        self.notebook_name = notebook_name
        self.session_id = session_id
        self.poll_interval = poll_interval
        self.max_pages = max_pages
        self.running = False

        # State for diffing
        self.previous_ocr: dict[int, str] = {}  # page_index -> ocr_text
        self.poll_count = 0

        # Resolve notebook
        self.notebook = find_notebook(notebook_name)
        if not self.notebook:
            available = [nb["name"] for nb in find_goodnotes_files()]
            raise ValueError(
                f"No notebook matching '{notebook_name}'. "
                f"Available: {available}"
            )

        # Check for exported PDF
        self.export_pdf = Path(self.notebook["dir"]) / f"{self.notebook['name']}.pdf"
        self.use_pdf = self.export_pdf.exists()

        if self.use_pdf:
            self.total_pages = min(get_pdf_page_count(str(self.export_pdf)), max_pages)
        else:
            self.total_pages = 1  # thumbnail only

    @property
    def mode(self) -> str:
        return "pdf" if self.use_pdf else "thumbnail"

    def ocr_once(self) -> dict[int, str]:
        """Run OCR on the notebook, return {page_index: text}."""
        results = {}

        if self.use_pdf:
            for page_idx in range(self.total_pages):
                img_bytes = pdf_page_to_image_bytes(
                    str(self.export_pdf), page_idx, scale=2.0
                )
                if img_bytes is None:
                    continue
                observations = vision_ocr_image_bytes(
                    img_bytes, upscale=1, language_correction=False
                )
                text = "\n".join(
                    obs["text"] for obs in observations if obs["confidence"] > 0.1
                )
                results[page_idx] = text
        else:
            # Thumbnail mode — read from .goodnotes zip
            try:
                with zipfile.ZipFile(self.notebook["path"]) as zf:
                    if "thumbnail.jpg" in zf.namelist():
                        thumb_bytes = zf.read("thumbnail.jpg")
                        observations = vision_ocr_image_bytes(
                            thumb_bytes, upscale=3, language_correction=False
                        )
                        text = "\n".join(
                            obs["text"] for obs in observations
                            if obs["confidence"] > 0.1
                        )
                        results[0] = text
            except Exception:
                pass

        return results

    def detect_changes(self, current_ocr: dict[int, str]) -> list[dict]:
        """Diff current OCR against previous to find new text.

        Returns list of {page, new_lines, full_text} for pages with changes.
        """
        changes = []

        for page_idx, current_text in current_ocr.items():
            prev_text = self.previous_ocr.get(page_idx, "")

            if current_text == prev_text:
                continue

            # Line-level diff to find new content
            prev_lines = prev_text.splitlines()
            curr_lines = current_text.splitlines()

            diff = difflib.unified_diff(prev_lines, curr_lines, lineterm="")
            new_lines = [
                line[1:] for line in diff
                if line.startswith("+") and not line.startswith("+++")
            ]

            if new_lines:
                changes.append({
                    "page": page_idx + 1,
                    "new_lines": new_lines,
                    "new_text": "\n".join(new_lines),
                    "full_text": current_text,
                    "timestamp": datetime.utcnow().isoformat(),
                    "session_id": self.session_id,
                })

        return changes

    def poll_once(self) -> list[dict]:
        """Single poll cycle: OCR + diff. Returns list of detected changes."""
        self.poll_count += 1
        current_ocr = self.ocr_once()
        changes = self.detect_changes(current_ocr)
        self.previous_ocr = current_ocr
        return changes

    def run(self, duration: Optional[float] = None, on_change=None):
        """Run the polling loop.

        Args:
            duration: Max seconds to run. None = run until stopped.
            on_change: Callback called with (change_dict) for each detected change.
        """
        self.running = True
        start = time.time()

        # Initial OCR baseline
        self.previous_ocr = self.ocr_once()
        print(f"[iCloud] Baseline OCR: {sum(len(t) for t in self.previous_ocr.values())} chars across {len(self.previous_ocr)} page(s)")

        while self.running:
            if duration and (time.time() - start) > duration:
                break

            time.sleep(self.poll_interval)
            changes = self.poll_once()

            for change in changes:
                if on_change:
                    on_change(change)
                else:
                    print(f"[iCloud] New text on page {change['page']}: {change['new_text'][:80]}")

    def stop(self):
        self.running = False
