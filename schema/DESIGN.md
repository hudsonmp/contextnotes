# Schema Design Rationale

Every design decision in the ContextNotes learning trace schema is grounded in the literature. This document maps schema elements to the research that motivated them.

## Three-Layer Architecture

**Decision**: Separate behavioral events (Layer 1), sensor streams (Layer 2), and derived analytics (Layer 3) into distinct data structures.

**Rationale**: The MMLA field has no unified standard (Chango et al., 2025). The closest systems use hybrid approaches:
- EZ-MMLA (Worsley et al., 2022) uses CSV with video frame numbers as the universal join key
- xAPI handles discrete behavioral events but is unsuitable for high-frequency sensor data (60Hz gaze = millions of statements per session)
- W3C WADM handles document anchoring but has no concept of temporal event streams

The three-layer split lets each layer use the format best suited to its data type while maintaining temporal alignment via ISO 8601 timestamps.

## Layer 1: Behavioral Events

### Event Envelope (xAPI-compatible)

**Decision**: Use Actor-Verb-Object-style events with timestamps, compatible with xAPI but not dependent on an LRS.

**Rationale**: xAPI (IEEE 9274.1.1-2023) is the established standard for learning activity tracking. Its extensions mechanism allows custom payloads. However, xAPI has no pre-built reading or annotation profile — these must be community-defined. We define our own event types (`reading.scroll`, `annotation.create`, etc.) that could be mapped to xAPI verbs if interoperability is needed later.

### Document Anchoring (W3C WADM TextQuoteSelector)

**Decision**: Anchor reading context and annotations to specific article text using W3C Web Annotation Data Model TextQuoteSelector with `exact` + `prefix` + `suffix` fields.

**Rationale**: The WADM defines 8 selector types. TextQuoteSelector is the most robust for web content because:
- It survives minor page edits (unlike TextPositionSelector which uses character offsets)
- The prefix/suffix context enables fuzzy re-anchoring if the exact text changes
- Hypothes.is has proven this approach at scale with their "fuzzy anchoring" system
- Marshall (1997) established that annotations are spatially anchored to source material — digital systems must preserve this relationship

We store the most-centered visible paragraph as the likely reading focus, following the viewport-center heuristic.

### Annotation Motivation Vocabulary

**Decision**: Use a 9-category motivation vocabulary: paraphrasing, elaborating, questioning, summarizing, connecting, evaluating, copying, highlighting, monitoring.

**Rationale**: This vocabulary synthesizes two sources:

1. **W3C WADM motivation vocabulary** (commenting, highlighting, questioning, etc.) — the established standard for annotation intent
2. **Think-aloud protocol coding schemes** — the closest research paradigm for capturing thought progression during reading. Categories from Hamzah et al. (2024) and the comprehension monitoring literature: paraphrase, elaboration, prediction, monitoring, questioning, summarizing, connecting, evaluating, visualizing, rereading.

We collapsed these into 9 categories mapped to three cognitive levels:
- **Generative** (paraphrasing, elaborating, questioning, summarizing, connecting, evaluating) — the activities that Fiorella & Mayer (2016) identified as promoting deep learning through reorganization and integration with prior knowledge
- **Surface** (copying, highlighting) — activities that Dunlosky et al. (2013) rated as "low utility" as commonly practiced
- **Metacognitive** (monitoring) — comprehension monitoring ("I don't understand this"), which is a regulatory process distinct from encoding

This classification scheme operationalizes Wittrock's (1974) generative learning theory: learning occurs when learners generate connections between new information and prior knowledge. The generative/surface distinction lets us quantify the depth of engagement.

## Layer 2: Sensor Streams

### Dual Gaze Capture (Scroll Proxy + WebGazer.js)

**Decision**: Capture both scroll position (as attention proxy) and WebGazer.js gaze coordinates simultaneously.

**Rationale**:
- **Scroll proxy**: Jarodzka & Brand-Gruwel (2017) advocated for moving beyond lab-based eye tracking toward real-world reading environments. Scroll position + dwell time per section correlates with reading attention in naturalistic settings. This is the reliable baseline signal.
- **WebGazer.js**: Provides paragraph-level gaze estimation (~100-200px accuracy) via webcam. Not research-grade, but Shubi et al. (2024) showed reading goals are decodable from gaze patterns — even coarse gaze data adds signal. Self-calibrating through user clicks.
- **Dual capture**: Running both allows comparing signals and falling back to scroll-only when gaze confidence is low.

Gaze data is stored as time-series samples (`gaze_x`, `gaze_y`, `gaze_confidence`, `scroll_y`, `scroll_progress`) rather than as behavioral events, following the EZ-MMLA frame-based alignment pattern.

### GoodNotes Screen Capture + Frame Diff

**Decision**: Screenshot the GoodNotes window every 2-3 seconds, compute frame diffs to detect new ink, and OCR diff regions.

**Rationale**: GoodNotes has no real-time API — no stroke streaming, no webhooks, no plugin system. The `.goodnotes` file format stores strokes as proprietary protobuf (undocumented). The three viable capture strategies:
1. File system watching (coarse timing, depends on iCloud sync interval)
2. Screen capture + frame diff (2-3 second resolution, computationally feasible)
3. Custom note surface (full control but loses GoodNotes UX)

Screen capture preserves the GoodNotes writing experience while achieving sufficient temporal resolution to align notes with reading context.

## Context-Aware Recognition

### Multimodal Post-Correction with Article Context

**Decision**: Feed GoodNotes screenshot + raw OCR + article paragraphs to Claude API for context-conditioned correction.

**Rationale**: Three papers establish the components:
- **Greif et al. (2025)**: Multimodal post-correction (image + OCR text to mLLM) achieves <1% CER on historical documents. Feeding both modalities lets the model cross-reference visual evidence with textual hypotheses.
- **Do et al. (2024)**: Reference-based post-OCR correction using ebook content as a reference constrains the LLM's correction space. Mean grading score 8.72/10 vs. 7.03 for SOTA spell correction. The article being read is our reference.
- **Cai et al. (2022)**: One turn of conversation context more than doubles abbreviation expansion accuracy. A 64B LLM expands >70% of word-initial-letter abbreviations with context. The source article provides rich context for expanding note-taking shorthand.

### Consensus for Uncertainty Detection

**Decision**: Compare Apple Vision OCR (from GoodNotes MCP) with Claude Vision OCR, flag disagreements.

**Rationale**: Zhang et al. (2025) showed that consensus entropy across multiple VLMs identifies uncertain outputs without any training. Correct predictions converge; errors diverge. By comparing on-device OCR with cloud VLM OCR, we can flag words that need context-based disambiguation — focusing expensive LLM processing where it matters most.

### Hallucination Guard

**Decision**: Flag low-confidence corrections. Require corrections to be grounded in visual evidence.

**Rationale**: Kanerva et al. (2025) demonstrated that LLMs can *introduce* errors when post-correcting OCR — hallucinating plausible but incorrect text. Levchenko (2025) found "over-historicization" where models insert incorrect period-specific characters. Context must be carefully managed: too much context or wrong-domain context increases hallucination risk.

## Layer 3: Derived Analytics

### Thought Progression Narrative

**Decision**: Use Claude API post-session to generate a narrative of how understanding evolved.

**Rationale**: The temporal dynamics of note-taking within a reading session are almost entirely unstudied empirically (identified as a gap in the cognitive science review). Forte's (2022) progressive summarization framework proposes layered distillation but has no controlled evidence base. Our system generates the data that could support or challenge this framework.

The think-aloud protocol (Hamzah et al., 2024) provides the coding scheme: paraphrase, elaboration, monitoring, questioning, etc. We apply these labels to annotations automatically, creating a time-indexed record of cognitive processes during reading.

### Learning Indicators

**Decision**: Compute generative ratio, concept coverage, cross-references per session.

**Rationale**:
- **Generative ratio**: Wittrock (1974, 1992) and Fiorella & Mayer (2016) establish that generative processing drives learning. The proportion of generative vs. surface annotations operationalizes this.
- **Concept coverage**: List & Lin (2023) found that both content quality and quantity of annotations predict learning from digital texts. Concept coverage measures breadth.
- **Cross-references**: List & Lin (2023) also found that annotations linking concepts across texts were particularly valuable. Cross-section references indicate integrative processing.

## Storage: Supabase

**Decision**: Supabase (PostgreSQL + real-time subscriptions + Storage) from the start.

**Rationale**: Cross-device access, real-time subscriptions for live session monitoring, Supabase Storage for screenshot files. Already configured (project ref: nhttyppkcajodocrnqhi). The JSONB columns for `source_data` and `annotation_data` provide schema flexibility without sacrificing queryability.

## What This Schema Does NOT Capture (Known Limitations)

1. **Stroke-level pen data**: GoodNotes' proprietary protobuf format is not parsed. We capture screenshots, not vectors.
2. **Character-level gaze**: WebGazer.js accuracy (~100-200px) supports paragraph-level analysis, not character or word-level fixation analysis (Rayner 1998).
3. **Real-time note streaming**: Screen capture introduces 2-3 second latency. Stroke-by-stroke capture would require a custom note surface.
4. **Audio/think-aloud**: No audio capture in v1. Could be added as a Layer 2 stream.
5. **Multi-user/social annotation**: Single-user system. Kalir et al. (2020) showed social annotation enhances learning, but this is out of v1 scope.
