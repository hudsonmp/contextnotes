"""Pydantic models for the ContextNotes learning trace schema.

Three-layer architecture:
- Layer 1: Behavioral events (reading context + annotations)
- Layer 2: Sensor streams (gaze + screen captures)
- Layer 3: Derived analytics (thought progression, learning indicators)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --- Enums ---

class SessionStatus(str, Enum):
    active = "active"
    paused = "paused"
    completed = "completed"


class EventType(str, Enum):
    reading_scroll = "reading.scroll"
    reading_focus_paragraph = "reading.focus_paragraph"
    reading_selection = "reading.selection"
    reading_navigate = "reading.navigate"
    annotation_create = "annotation.create"
    annotation_update = "annotation.update"
    gaze_fixation = "gaze.fixation"
    session_start = "session.start"
    session_pause = "session.pause"
    session_resume = "session.resume"
    session_end = "session.end"


class ContentType(str, Enum):
    text = "text"
    math = "math"
    diagram = "diagram"
    mixed = "mixed"


class Motivation(str, Enum):
    """Annotation motivation, adapted from think-aloud coding schemes.

    Generative: paraphrasing, elaborating, questioning, summarizing, connecting, evaluating
    Surface: copying, highlighting
    Metacognitive: monitoring

    See: Fiorella & Mayer (2016), Hamzah et al. (2024)
    """
    paraphrasing = "paraphrasing"
    elaborating = "elaborating"
    questioning = "questioning"
    summarizing = "summarizing"
    connecting = "connecting"
    evaluating = "evaluating"
    copying = "copying"
    highlighting = "highlighting"
    monitoring = "monitoring"

    @property
    def cognitive_level(self) -> str:
        if self in (
            Motivation.paraphrasing, Motivation.elaborating,
            Motivation.questioning, Motivation.summarizing,
            Motivation.connecting, Motivation.evaluating
        ):
            return "generative"
        elif self in (Motivation.copying, Motivation.highlighting):
            return "surface"
        else:
            return "metacognitive"


# --- W3C WADM Selector ---

class TextQuoteSelector(BaseModel):
    """W3C Web Annotation Data Model TextQuoteSelector.

    Robust to minor document edits via prefix/suffix context matching.
    See: https://www.w3.org/TR/annotation-model/#text-quote-selector
    """
    type: str = "TextQuoteSelector"
    exact: str
    prefix: Optional[str] = None
    suffix: Optional[str] = None


# --- Layer 1: Behavioral Events ---

class VisibleParagraph(BaseModel):
    index: int
    text: str = Field(max_length=200)


class Viewport(BaseModel):
    scroll_y: float
    scroll_progress: float = Field(ge=0, le=1)
    viewport_height: Optional[float] = None
    document_height: Optional[float] = None
    visible_paragraphs: list[VisibleParagraph] = Field(default_factory=list)


class ReadingSource(BaseModel):
    """Reading context at the time of an event."""
    url: str
    title: Optional[str] = None
    selector: Optional[TextQuoteSelector] = None
    viewport: Optional[Viewport] = None
    selection: Optional[str] = None


class AbbreviationExpansion(BaseModel):
    original: str
    expanded: str
    confidence: float = Field(ge=0, le=1)


class Annotation(BaseModel):
    """Handwritten annotation captured from GoodNotes, with context-aware recognition."""
    raw_ocr: Optional[str] = None
    context_corrected: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    content_type: Optional[ContentType] = None
    goodnotes_page: Optional[int] = None
    screenshot_ref: Optional[str] = None
    motivation: Optional[Motivation] = None
    source_paragraph_link: Optional[TextQuoteSelector] = None
    abbreviations_expanded: list[AbbreviationExpansion] = Field(default_factory=list)
    diagram_description: Optional[str] = None


class Event(BaseModel):
    """A single behavioral event in a reading + annotation session."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    timestamp: datetime
    event_type: EventType
    source: Optional[ReadingSource] = None
    annotation: Optional[Annotation] = None


class Session(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime
    ended_at: Optional[datetime] = None
    article_url: str
    article_title: Optional[str] = None
    notebook_name: Optional[str] = None
    status: SessionStatus = SessionStatus.active


# --- Layer 2: Sensor Streams ---

class GazeSample(BaseModel):
    """Single gaze + scroll sample from WebGazer.js and Chrome."""
    timestamp: datetime
    session_id: str
    gaze_x: Optional[float] = None
    gaze_y: Optional[float] = None
    gaze_confidence: Optional[float] = Field(default=None, ge=0, le=1)
    scroll_y: Optional[float] = None
    scroll_progress: Optional[float] = Field(default=None, ge=0, le=1)


class InkRegion(BaseModel):
    x: float
    y: float
    width: float
    height: float


class ScreenCapture(BaseModel):
    """A screen capture frame from the GoodNotes window."""
    timestamp: datetime
    session_id: str
    frame_number: int
    screenshot_url: Optional[str] = None
    diff_detected: bool = False
    new_ink_region: Optional[InkRegion] = None


# --- Layer 3: Derived Analytics ---

class ReadingSegment(BaseModel):
    section: str
    start_time: datetime
    end_time: datetime
    dwell_seconds: float
    re_reads: int = 0


class AnnotationEntry(BaseModel):
    timestamp: datetime
    text: str
    motivation: str
    source_section: str
    cognitive_level: str


class Concept(BaseModel):
    name: str
    from_source: bool = False
    from_notes: bool = False


class ConceptLink(BaseModel):
    from_concept: str = Field(alias="from")
    to_concept: str = Field(alias="to")
    relation: str

    model_config = {"populate_by_name": True}


class ConceptMap(BaseModel):
    concepts: list[Concept] = Field(default_factory=list)
    links: list[ConceptLink] = Field(default_factory=list)


class LearningIndicators(BaseModel):
    generative_ratio: float = Field(ge=0, le=1)
    concept_coverage: float = Field(ge=0, le=1)
    cross_references: int = 0
    total_annotations: int = 0
    total_reading_minutes: float = 0


class SessionAnalytics(BaseModel):
    """Post-session derived analytics computed by Claude API."""
    reading_path: list[ReadingSegment] = Field(default_factory=list)
    annotation_timeline: list[AnnotationEntry] = Field(default_factory=list)
    thought_progression: Optional[str] = None
    concept_map: Optional[ConceptMap] = None
    learning_indicators: Optional[LearningIndicators] = None
    computed_at: datetime = Field(default_factory=datetime.utcnow)


# --- Full Trace ---

class LearningTrace(BaseModel):
    """Complete learning trace for a reading + annotation session."""
    session: Session
    events: list[Event]
    gaze_stream: list[GazeSample] = Field(default_factory=list)
    screen_captures: list[ScreenCapture] = Field(default_factory=list)
    analytics: Optional[SessionAnalytics] = None
