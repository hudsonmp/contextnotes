"""Context-aware handwriting recognition using Claude API.

Core innovation: uses the article being read as context to improve
recognition of handwritten notes. Combines three approaches:

1. Multimodal post-correction (Greif et al., 2025):
   Feed both page image AND OCR text to the mLLM.

2. Reference-based correction (Do et al., 2024):
   Article constrains the space of plausible interpretations.

3. Context-aware abbreviation expansion (Cai et al., 2022):
   Source article provides context for expanding shorthand.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Optional

import anthropic


@dataclass
class RecognitionResult:
    """Result of context-aware handwriting recognition."""
    corrected_text: str
    content_type: str  # text, math, diagram, mixed
    motivation: str  # paraphrasing, questioning, etc.
    confidence: float
    abbreviations: list[dict]  # [{original, expanded, confidence}]
    diagram_description: Optional[str] = None
    source_paragraph_match: Optional[str] = None


RECOGNITION_PROMPT = """You are analyzing handwritten notes taken while reading an article. Your job is to:

1. RECOGNIZE: Correct the raw OCR output using both the handwriting image and the article context.
2. EXPAND: Expand any abbreviations or shorthand using the article as context.
3. CLASSIFY: Determine what type of content this is (text, math, diagram, or mixed).
4. CATEGORIZE: Classify the cognitive motivation of the annotation.

## Article Context (what the reader was looking at when they wrote this note)
{article_context}

## Raw OCR Output (from Apple Vision - may contain errors)
{raw_ocr}

## Instructions
- The handwriting image is attached. Cross-reference the image with the OCR text.
- Use the article context to disambiguate unclear handwriting and expand abbreviations.
- Common note-taking abbreviations: arrows (→, ←), shorthand (w/ = with, b/c = because, etc.)
- Be conservative: only correct what you can verify from the image. Flag uncertainty.
- Do NOT hallucinate text that isn't visible in the image.

## Response Format (JSON)
{{
  "corrected_text": "the corrected and expanded text",
  "content_type": "text|math|diagram|mixed",
  "motivation": "paraphrasing|elaborating|questioning|summarizing|connecting|evaluating|copying|highlighting|monitoring",
  "confidence": 0.0-1.0,
  "abbreviations": [
    {{"original": "abbr", "expanded": "abbreviation", "confidence": 0.95}}
  ],
  "diagram_description": "description of any diagrams/sketches, or null",
  "source_paragraph_match": "the specific article paragraph this note most relates to, or null"
}}

Respond with ONLY the JSON object, no other text."""


class ContextCorrector:
    """Recognizes handwritten notes using article context.

    Uses Claude API with vision to process handwriting images
    alongside the article text the reader was viewing.
    """

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic()
        self.model = model

    def recognize(
        self,
        image_bytes: bytes,
        raw_ocr: Optional[str],
        article_context: str,
        media_type: str = "image/png",
    ) -> RecognitionResult:
        """Run context-aware recognition on a handwriting image.

        Args:
            image_bytes: PNG/JPEG of the handwritten notes region.
            raw_ocr: Initial OCR output from Apple Vision (may be None for diagrams).
            article_context: The article text visible when this note was written.
            media_type: MIME type of the image.

        Returns:
            RecognitionResult with corrected text, classifications, and expansions.
        """
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        prompt = RECOGNITION_PROMPT.format(
            article_context=article_context or "(no article context available)",
            raw_ocr=raw_ocr or "(no OCR output - likely a diagram or sketch)",
        )

        message = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        )

        response_text = message.content[0].text

        # Parse JSON response
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            if start >= 0 and end > start:
                result = json.loads(response_text[start:end])
            else:
                return RecognitionResult(
                    corrected_text=raw_ocr or response_text,
                    content_type="text",
                    motivation="copying",
                    confidence=0.3,
                    abbreviations=[],
                )

        return RecognitionResult(
            corrected_text=result.get("corrected_text", raw_ocr or ""),
            content_type=result.get("content_type", "text"),
            motivation=result.get("motivation", "copying"),
            confidence=result.get("confidence", 0.5),
            abbreviations=result.get("abbreviations", []),
            diagram_description=result.get("diagram_description"),
            source_paragraph_match=result.get("source_paragraph_match"),
        )

    def recognize_with_consensus(
        self,
        image_bytes: bytes,
        ocr_apple: Optional[str],
        article_context: str,
    ) -> RecognitionResult:
        """Recognition with consensus check between Apple Vision and Claude.

        When Apple Vision OCR and Claude Vision disagree, flags the result
        with lower confidence. Based on Zhang et al. (2025) consensus entropy.
        """
        # Run Claude-based recognition
        result = self.recognize(image_bytes, ocr_apple, article_context)

        # Compare with Apple Vision OCR if available
        if ocr_apple and result.corrected_text:
            # Simple word-level agreement check
            ocr_words = set(ocr_apple.lower().split())
            corrected_words = set(result.corrected_text.lower().split())

            if ocr_words and corrected_words:
                overlap = len(ocr_words & corrected_words)
                total = len(ocr_words | corrected_words)
                agreement = overlap / total if total > 0 else 0

                # Low agreement = high uncertainty, reduce confidence
                if agreement < 0.3:
                    result.confidence = min(result.confidence, 0.5)

        return result
