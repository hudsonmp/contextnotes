"""Supabase storage layer for ContextNotes learning traces.

Handles writing events, gaze samples, screen captures, and session analytics
to the Supabase backend. Read operations support trace reconstruction.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Optional

from supabase import create_client, Client

from trace.models import (
    Session, Event, GazeSample, ScreenCapture,
    SessionAnalytics, LearningTrace, SessionStatus
)


def get_client() -> Client:
    """Create Supabase client from environment variables."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise ValueError(
            "Set SUPABASE_URL and SUPABASE_KEY environment variables. "
            "Find these in your Supabase project settings > API."
        )
    return create_client(url, key)


class TraceStore:
    """Read/write learning traces to Supabase."""

    def __init__(self, client: Optional[Client] = None):
        self.client = client or get_client()

    # --- Sessions ---

    def create_session(self, session: Session) -> Session:
        data = {
            "id": session.id,
            "started_at": session.started_at.isoformat(),
            "article_url": session.article_url,
            "article_title": session.article_title,
            "notebook_name": session.notebook_name,
            "status": session.status.value,
        }
        self.client.table("sessions").insert(data).execute()
        return session

    def end_session(self, session_id: str) -> None:
        self.client.table("sessions").update({
            "ended_at": datetime.utcnow().isoformat(),
            "status": SessionStatus.completed.value,
        }).eq("id", session_id).execute()

    def get_session(self, session_id: str) -> Optional[dict]:
        result = self.client.table("sessions").select("*").eq("id", session_id).execute()
        return result.data[0] if result.data else None

    # --- Events (Layer 1) ---

    def insert_event(self, event: Event) -> None:
        data = {
            "id": event.id,
            "session_id": event.session_id,
            "timestamp": event.timestamp.isoformat(),
            "event_type": event.event_type.value,
            "source_data": event.source.model_dump(mode="json") if event.source else None,
            "annotation_data": event.annotation.model_dump(mode="json") if event.annotation else None,
        }
        self.client.table("events").insert(data).execute()

    def insert_events_batch(self, events: list[Event]) -> None:
        rows = []
        for event in events:
            rows.append({
                "id": event.id,
                "session_id": event.session_id,
                "timestamp": event.timestamp.isoformat(),
                "event_type": event.event_type.value,
                "source_data": event.source.model_dump(mode="json") if event.source else None,
                "annotation_data": event.annotation.model_dump(mode="json") if event.annotation else None,
            })
        self.client.table("events").insert(rows).execute()

    def get_events(self, session_id: str) -> list[dict]:
        result = (
            self.client.table("events")
            .select("*")
            .eq("session_id", session_id)
            .order("timestamp")
            .execute()
        )
        return result.data

    # --- Gaze Stream (Layer 2) ---

    def insert_gaze_batch(self, samples: list[GazeSample]) -> None:
        rows = []
        for s in samples:
            rows.append({
                "session_id": s.session_id,
                "timestamp": s.timestamp.isoformat(),
                "gaze_x": s.gaze_x,
                "gaze_y": s.gaze_y,
                "gaze_confidence": s.gaze_confidence,
                "scroll_y": s.scroll_y,
                "scroll_progress": s.scroll_progress,
            })
        # Batch in chunks of 500 to avoid payload limits
        for i in range(0, len(rows), 500):
            self.client.table("gaze_stream").insert(rows[i:i+500]).execute()

    def get_gaze_stream(self, session_id: str) -> list[dict]:
        result = (
            self.client.table("gaze_stream")
            .select("*")
            .eq("session_id", session_id)
            .order("timestamp")
            .execute()
        )
        return result.data

    # --- Screen Captures (Layer 2) ---

    def insert_screen_capture(self, capture: ScreenCapture) -> None:
        data = {
            "id": capture.session_id + "-" + str(capture.frame_number),
            "session_id": capture.session_id,
            "timestamp": capture.timestamp.isoformat(),
            "frame_number": capture.frame_number,
            "screenshot_url": capture.screenshot_url,
            "diff_detected": capture.diff_detected,
            "new_ink_region": capture.new_ink_region.model_dump() if capture.new_ink_region else None,
        }
        self.client.table("screen_captures").insert(data).execute()

    def upload_screenshot(self, session_id: str, frame_number: int, image_bytes: bytes) -> str:
        """Upload screenshot to Supabase Storage, return public URL."""
        path = f"{session_id}/frame-{frame_number:04d}.png"
        self.client.storage.from_("screenshots").upload(path, image_bytes, {"content-type": "image/png"})
        return self.client.storage.from_("screenshots").get_public_url(path)

    def get_screen_captures(self, session_id: str, diffs_only: bool = False) -> list[dict]:
        query = (
            self.client.table("screen_captures")
            .select("*")
            .eq("session_id", session_id)
            .order("timestamp")
        )
        if diffs_only:
            query = query.eq("diff_detected", True)
        return query.execute().data

    # --- Session Analytics (Layer 3) ---

    def save_analytics(self, session_id: str, analytics: SessionAnalytics) -> None:
        data = {
            "session_id": session_id,
            "reading_path": [s.model_dump(mode="json") for s in analytics.reading_path],
            "annotation_timeline": [a.model_dump(mode="json") for a in analytics.annotation_timeline],
            "thought_progression": analytics.thought_progression,
            "concept_map": analytics.concept_map.model_dump(mode="json") if analytics.concept_map else None,
            "learning_indicators": analytics.learning_indicators.model_dump(mode="json") if analytics.learning_indicators else None,
            "computed_at": analytics.computed_at.isoformat(),
        }
        self.client.table("session_analytics").insert(data).execute()

    def get_analytics(self, session_id: str) -> Optional[dict]:
        result = (
            self.client.table("session_analytics")
            .select("*")
            .eq("session_id", session_id)
            .order("computed_at", desc=True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    # --- Full Trace Reconstruction ---

    def get_full_trace(self, session_id: str) -> dict:
        """Reconstruct the complete learning trace for a session."""
        session = self.get_session(session_id)
        events = self.get_events(session_id)
        gaze = self.get_gaze_stream(session_id)
        captures = self.get_screen_captures(session_id)
        analytics = self.get_analytics(session_id)

        return {
            "session": session,
            "events": events,
            "gaze_stream": gaze,
            "screen_captures": captures,
            "analytics": analytics,
        }
