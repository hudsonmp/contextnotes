"""Post-session thought progression analysis using Claude API.

Analyzes a completed learning trace to generate:
1. Reading path with dwell times
2. Annotation timeline with cognitive level classification
3. Thought progression narrative
4. Concept map (source concepts + note concepts + links)
5. Learning indicators (generative ratio, coverage, cross-refs)

Based on think-aloud protocol coding schemes (Hamzah et al., 2024)
and generative learning theory (Fiorella & Mayer, 2016).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic

sys.path.insert(0, str(Path(__file__).parent.parent))

from trace.models import SessionAnalytics
from trace.store import TraceStore


ANALYSIS_PROMPT = """You are analyzing a learning trace from a reading + note-taking session. The trace contains reading events (what article sections were viewed and when) and annotation events (handwritten notes taken during reading, with their OCR'd content and the article context they were anchored to).

## Session Data
{session_json}

## Your Task

Analyze this trace and produce a comprehensive learning analysis. For each annotation, classify its cognitive level using this scheme (from think-aloud protocol and generative learning theory):

**Generative** (deep processing — reorganizes/integrates with prior knowledge):
- paraphrasing: Restating in own words
- elaborating: Adding prior knowledge or examples
- questioning: Generating questions about the content
- summarizing: Condensing information
- connecting: Linking ideas across sections or to external knowledge
- evaluating: Judging content quality or validity

**Surface** (shallow processing — records without transformation):
- copying: Verbatim transcription
- highlighting: Marking without comment

**Metacognitive** (self-regulation):
- monitoring: Checking own comprehension ("I don't understand this")

## Response Format (JSON)
{{
  "reading_path": [
    {{
      "section": "section name or description",
      "start_time": "ISO timestamp",
      "end_time": "ISO timestamp",
      "dwell_seconds": 120,
      "re_reads": 0
    }}
  ],
  "annotation_timeline": [
    {{
      "timestamp": "ISO timestamp",
      "text": "annotation content",
      "motivation": "paraphrasing|elaborating|questioning|summarizing|connecting|evaluating|copying|highlighting|monitoring",
      "source_section": "which article section this relates to",
      "cognitive_level": "generative|surface|metacognitive"
    }}
  ],
  "thought_progression": "A 2-4 sentence narrative of how the reader's understanding evolved across the session. What did they focus on? When did key insights emerge? What patterns of engagement are visible?",
  "concept_map": {{
    "concepts": [
      {{"name": "concept name", "from_source": true, "from_notes": true}}
    ],
    "links": [
      {{"from": "concept A", "to": "concept B", "relation": "relationship description"}}
    ]
  }},
  "learning_indicators": {{
    "generative_ratio": 0.0-1.0,
    "concept_coverage": 0.0-1.0,
    "cross_references": 0,
    "total_annotations": 0,
    "total_reading_minutes": 0.0
  }}
}}

Respond with ONLY the JSON object."""


class ThoughtProgressionAnalyzer:
    """Analyzes completed sessions to extract learning insights."""

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic()
        self.model = model

    def analyze_session(self, session_id: str, store: Optional[TraceStore] = None) -> SessionAnalytics:
        """Analyze a completed session and return SessionAnalytics.

        Args:
            session_id: The session to analyze.
            store: TraceStore instance. Creates one if not provided.

        Returns:
            SessionAnalytics with reading path, annotations, narrative, etc.
        """
        store = store or TraceStore()
        trace = store.get_full_trace(session_id)

        # Build condensed session data for the prompt
        session_json = self._prepare_session_data(trace)

        message = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": ANALYSIS_PROMPT.format(session_json=session_json),
                }
            ],
        )

        response_text = message.content[0].text

        # Parse JSON
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            result = json.loads(response_text[start:end])

        analytics = SessionAnalytics(
            reading_path=[
                {
                    "section": r["section"],
                    "start_time": r["start_time"],
                    "end_time": r["end_time"],
                    "dwell_seconds": r["dwell_seconds"],
                    "re_reads": r.get("re_reads", 0),
                }
                for r in result.get("reading_path", [])
            ],
            annotation_timeline=[
                {
                    "timestamp": a["timestamp"],
                    "text": a["text"],
                    "motivation": a["motivation"],
                    "source_section": a["source_section"],
                    "cognitive_level": a["cognitive_level"],
                }
                for a in result.get("annotation_timeline", [])
            ],
            thought_progression=result.get("thought_progression"),
            concept_map=result.get("concept_map"),
            learning_indicators=result.get("learning_indicators"),
        )

        # Save to store
        store.save_analytics(session_id, analytics)

        return analytics

    def analyze_trace_file(self, trace_path: str) -> dict:
        """Analyze a trace from a JSON file (for testing without Supabase).

        Args:
            trace_path: Path to a learning trace JSON file.

        Returns:
            Raw analysis dict from Claude.
        """
        with open(trace_path) as f:
            trace = json.load(f)

        session_json = json.dumps(trace, indent=2, default=str)

        message = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": ANALYSIS_PROMPT.format(session_json=session_json),
                }
            ],
        )

        response_text = message.content[0].text

        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            return json.loads(response_text[start:end])

    def _prepare_session_data(self, trace: dict) -> str:
        """Condense trace data for the prompt, keeping it within token limits."""
        condensed = {
            "session": trace.get("session", {}),
            "events": [],
        }

        for event in trace.get("events", []):
            entry = {
                "timestamp": event.get("timestamp"),
                "event_type": event.get("event_type"),
            }

            # Include source data for reading events
            source = event.get("source_data")
            if source:
                entry["article_section"] = source.get("selector", {}).get("exact", "")[:200] if source.get("selector") else None
                entry["scroll_progress"] = source.get("viewport", {}).get("scroll_progress")

            # Include annotation data
            ann = event.get("annotation_data")
            if ann:
                entry["annotation"] = {
                    "raw_ocr": ann.get("raw_ocr"),
                    "corrected": ann.get("context_corrected"),
                    "content_type": ann.get("content_type"),
                    "motivation": ann.get("motivation"),
                }

            condensed["events"].append(entry)

        return json.dumps(condensed, indent=2, default=str)
