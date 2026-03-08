# ContextNotes

**Multimodal reading-to-notes learning trace system: linking reading context to handwritten annotations.**

## The Problem

When you read an article on your laptop and take handwritten notes in GoodNotes, the link between *what you're reading* and *what you write* is lost. No existing system:

1. Captures reading context at the paragraph level (what's visible, where you're looking)
2. Links that context temporally to handwritten annotations
3. Uses the article content to improve recognition of messy/abbreviated handwriting
4. Stores the progression of thought in a format useful for learning analytics

## Why This Matters

The literature review in this repository reveals an unoccupied intersection across three research areas:

- **Context-aware handwriting recognition**: Do et al. (2024) showed reference-based OCR correction works; Cai et al. (2022) showed context more than doubles abbreviation expansion accuracy; Ross et al. (2025) showed sketched elements ambiguous alone become interpretable in context. Nobody has combined these for note-taking during reading.
- **Multimodal learning analytics**: No standard data format exists for multimodal learning traces (Chango et al., 2025). xAPI handles events, W3C WADM handles document anchoring, but nothing unifies reading context + handwriting + gaze + temporal thought progression.
- **Note-taking cognitive science**: The encoding benefit of note-taking depends on *generative processing* (Wittrock, 1974; Fiorella & Mayer, 2016), not the input modality (Mueller & Oppenheimer replication failures: Morehead 2019, Urry 2021). Anchored annotations linked to source passages predict learning outcomes (List & Lin, 2023).

## Repository Structure

```
contextnotes/
├── lit-review/              # Literature review (~70 papers)
│   ├── cognitive-science.md # Note-taking + reading comprehension
│   ├── data-formats.md      # Standards: xAPI, WADM, Caliper, MMLA
│   ├── context-aware-ocr.md # LLM-augmented handwriting recognition
│   ├── annotated-pdfs/      # Key papers from arXiv
│   └── references.bib       # BibTeX
├── schema/                  # Learning trace format
│   ├── learning-trace.schema.json
│   ├── examples/            # Example trace files
│   ├── supabase-migrations/ # Database schema
│   └── DESIGN.md            # Design rationale linked to literature
├── capture/                 # Data capture (v2)
├── recognition/             # Context-aware OCR (v2)
├── trace/                   # Storage + viewer (v2)
└── analysis/                # Thought progression analysis (v2)
```

## Architecture

Three-layer learning trace format:

1. **Behavioral Events** (xAPI-compatible + W3C WADM selectors): reading scrolls, paragraph focus, annotation creation — each anchored to specific article text via TextQuoteSelector
2. **Sensor Streams**: webcam gaze coordinates (WebGazer.js) + scroll position, GoodNotes screen capture diffs with timestamps
3. **Derived Analytics**: reading patterns, annotation classification (generative vs. surface), thought progression narratives

### Data Pipeline

```
Chrome (reading)  ──→  Reading context snapshots (paragraph, scroll, selection)
                           │
                           ├──→  Timestamp alignment  ──→  Supabase
                           │
GoodNotes (notes) ──→  Screen capture → Frame diff → Context-aware OCR
                           │
WebGazer.js (gaze) ──→  Gaze stream (x, y, confidence)
```

### Context-Aware Recognition

The core innovation: use the article being read as context for recognizing handwritten notes.

```
[GoodNotes screenshot diff] + [Raw OCR] + [Article paragraphs at that timestamp]
                    ↓
            Claude API (multimodal)
                    ↓
[Corrected text, expanded abbreviations, diagram descriptions, motivation classification]
```

Grounded in: Do et al. (2024) reference-based correction, Cai et al. (2022) context-aware abbreviation expansion, Greif et al. (2025) multimodal LLM post-correction.

## Status

- [x] Literature review (3 reviews, ~70 papers)
- [x] Learning trace schema (JSON Schema + Supabase migrations)
- [ ] Chrome reading context capture
- [ ] GoodNotes screen capture + frame diff
- [ ] Context-aware OCR pipeline
- [ ] WebGazer.js gaze integration
- [ ] Trace viewer
- [ ] Thought progression analysis

## License

MIT
