"""Session coordinator: orchestrates all capture streams.

Manages the lifecycle of a reading + annotation session:
1. Starts/stops GoodNotes screen capture
2. Polls Chrome reading context (via MCP)
3. Collects gaze/scroll data
4. Triggers context-aware OCR on new ink
5. Stores everything to Supabase
"""

from __future__ import annotations

import json
import sys
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from trace.models import (
    Session, Event, EventType, ReadingSource, Annotation,
    GazeSample, ScreenCapture, InkRegion, Viewport,
    VisibleParagraph, TextQuoteSelector, SessionStatus,
    ContentType, Motivation,
)
from trace.store import TraceStore
from capture.goodnotes_screen_capture import GoodNotesCaptureLoop
from recognition.context_corrector import ContextCorrector, RecognitionResult


class SessionCoordinator:
    """Orchestrates a complete reading + annotation capture session."""

    def __init__(
        self,
        article_url: str,
        article_title: Optional[str] = None,
        notebook_name: Optional[str] = None,
        capture_interval: float = 3.0,
        output_dir: Optional[str] = None,
    ):
        self.store = TraceStore()
        self.corrector = ContextCorrector()

        # Create session
        self.session = Session(
            started_at=datetime.utcnow(),
            article_url=article_url,
            article_title=article_title,
            notebook_name=notebook_name,
        )
        self.store.create_session(self.session)

        # GoodNotes capture
        self.gn_capture = GoodNotesCaptureLoop(
            session_id=self.session.id,
            interval=capture_interval,
            output_dir=output_dir,
        )

        # State
        self.latest_reading_context: Optional[dict] = None
        self.running = False
        self._threads: list[threading.Thread] = []

        # Emit session start event
        self._emit_event(EventType.session_start)

    def update_reading_context(self, context: dict):
        """Update the current reading context from Chrome.

        Called externally (e.g., by the MCP javascript_tool polling loop)
        with the output of chrome_capture.js.
        """
        self.latest_reading_context = context

        # Emit reading event
        source = self._parse_reading_source(context)
        self._emit_event(
            EventType.reading_focus_paragraph,
            source=source,
        )

    def update_gaze(self, gaze_x: Optional[float], gaze_y: Optional[float],
                    confidence: Optional[float], scroll_y: float, scroll_progress: float):
        """Record a gaze + scroll sample."""
        sample = GazeSample(
            timestamp=datetime.utcnow(),
            session_id=self.session.id,
            gaze_x=gaze_x,
            gaze_y=gaze_y,
            gaze_confidence=confidence,
            scroll_y=scroll_y,
            scroll_progress=scroll_progress,
        )
        # Buffer and batch-insert (TODO: add buffering)
        self.store.insert_gaze_batch([sample])

    def _on_new_ink(self, frame_dict: dict, image_bytes: bytes):
        """Callback when GoodNotes frame diff detects new ink.

        1. Upload screenshot to Supabase
        2. Run context-aware OCR with current reading context
        3. Store annotation event
        """
        # Upload screenshot
        screenshot_url = self.store.upload_screenshot(
            self.session.id,
            frame_dict["frame_number"],
            image_bytes,
        )

        # Store screen capture record
        capture = ScreenCapture(
            timestamp=datetime.fromisoformat(frame_dict["timestamp"]),
            session_id=self.session.id,
            frame_number=frame_dict["frame_number"],
            screenshot_url=screenshot_url,
            diff_detected=True,
            new_ink_region=InkRegion(**frame_dict["new_ink_region"]) if frame_dict.get("new_ink_region") else None,
        )
        self.store.insert_screen_capture(capture)

        # Build article context from latest reading state
        article_context = self._get_article_context()

        # Run context-aware OCR
        # TODO: also get raw OCR from GoodNotes MCP for consensus check
        result = self.corrector.recognize(
            image_bytes=image_bytes,
            raw_ocr=None,  # Will be filled by GoodNotes MCP OCR
            article_context=article_context,
        )

        # Build annotation
        annotation = Annotation(
            raw_ocr=None,
            context_corrected=result.corrected_text,
            confidence=result.confidence,
            content_type=ContentType(result.content_type) if result.content_type in ContentType.__members__ else ContentType.text,
            goodnotes_page=None,
            screenshot_ref=screenshot_url,
            motivation=Motivation(result.motivation) if result.motivation in Motivation.__members__ else None,
            diagram_description=result.diagram_description,
            abbreviations_expanded=[
                {"original": a["original"], "expanded": a["expanded"], "confidence": a["confidence"]}
                for a in result.abbreviations
            ] if result.abbreviations else [],
        )

        # Build reading source from latest context
        source = self._parse_reading_source(self.latest_reading_context) if self.latest_reading_context else None

        # Link to source paragraph
        if result.source_paragraph_match:
            annotation.source_paragraph_link = TextQuoteSelector(
                exact=result.source_paragraph_match[:500],
            )

        # Emit annotation event
        self._emit_event(
            EventType.annotation_create,
            source=source,
            annotation=annotation,
        )

        print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] New annotation detected:")
        print(f"  Content: {result.corrected_text[:80]}...")
        print(f"  Type: {result.content_type} | Motivation: {result.motivation}")
        if result.abbreviations:
            for a in result.abbreviations:
                print(f"  Abbr: {a['original']} -> {a['expanded']}")

    def _get_article_context(self) -> str:
        """Build article context string from latest reading state."""
        if not self.latest_reading_context:
            return "(no reading context available)"

        parts = []
        ctx = self.latest_reading_context

        if ctx.get("title"):
            parts.append(f"Article: {ctx['title']}")

        if ctx.get("focus_paragraph"):
            fp = ctx["focus_paragraph"]
            parts.append(f"\nFocused paragraph:\n{fp.get('text', '')}")

        if ctx.get("visible_paragraphs"):
            parts.append("\nVisible paragraphs:")
            for vp in ctx["visible_paragraphs"][:5]:
                parts.append(f"  - {vp.get('text', '')}")

        if ctx.get("selection"):
            parts.append(f"\nSelected text: {ctx['selection']}")

        return "\n".join(parts)

    def _parse_reading_source(self, context: Optional[dict]) -> Optional[ReadingSource]:
        """Parse chrome_capture.js output into a ReadingSource model."""
        if not context:
            return None

        selector = None
        if context.get("selector"):
            s = context["selector"]
            selector = TextQuoteSelector(
                exact=s.get("exact", ""),
                prefix=s.get("prefix"),
                suffix=s.get("suffix"),
            )

        viewport = None
        if context.get("viewport"):
            v = context["viewport"]
            visible = []
            for vp in context.get("visible_paragraphs", []):
                visible.append(VisibleParagraph(
                    index=vp.get("index", 0),
                    text=vp.get("text", "")[:200],
                ))
            viewport = Viewport(
                scroll_y=v.get("scroll_y", 0),
                scroll_progress=v.get("scroll_progress", 0),
                viewport_height=v.get("viewport_height"),
                document_height=v.get("document_height"),
                visible_paragraphs=visible,
            )

        return ReadingSource(
            url=context.get("url", ""),
            title=context.get("title"),
            selector=selector,
            viewport=viewport,
            selection=context.get("selection"),
        )

    def _emit_event(
        self,
        event_type: EventType,
        source: Optional[ReadingSource] = None,
        annotation: Optional[Annotation] = None,
    ):
        event = Event(
            session_id=self.session.id,
            timestamp=datetime.utcnow(),
            event_type=event_type,
            source=source,
            annotation=annotation,
        )
        self.store.insert_event(event)

    def start(self, duration: Optional[float] = None):
        """Start all capture streams.

        Args:
            duration: Max seconds to run. None = run until stop() is called.
        """
        self.running = True

        # Start GoodNotes capture in a background thread
        gn_thread = threading.Thread(
            target=self.gn_capture.run,
            kwargs={"duration": duration, "on_diff": self._on_new_ink},
            daemon=True,
        )
        gn_thread.start()
        self._threads.append(gn_thread)

        print(f"Session started: {self.session.id}")
        print(f"Article: {self.session.article_url}")
        print(f"GoodNotes capture: every {self.gn_capture.interval}s")
        print("Waiting for reading context updates and new ink...")

    def stop(self):
        """Stop all capture streams and finalize session."""
        self.running = False
        self.gn_capture.stop()

        # Wait for threads
        for t in self._threads:
            t.join(timeout=5)

        # Emit session end
        self._emit_event(EventType.session_end)
        self.store.end_session(self.session.id)

        print(f"\nSession ended: {self.session.id}")
        print(f"Total captures: {len(self.gn_capture.captures)}")
        diffs = sum(1 for c in self.gn_capture.captures if c.get("diff_detected"))
        print(f"Ink changes detected: {diffs}")
