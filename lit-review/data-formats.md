# Technical Review: Data Formats, Standards, and Systems for Storing Multimodal Learning Traces

## Purpose

Structured review of how to capture and store the progression of a learner's thoughts during a reading + note-taking session. Covers standards, schemas, academic literature, and their relevance to a system linking reading context + handwritten notes + eye gaze.

---

## 1. xAPI (Experience API / Tin Can API)

### Specification
- **Standard**: IEEE 9274.1.1-2023 (xAPI 2.0), released October 2023
- **Origin**: ADL (Advanced Distributed Learning), evolved from SCORM
- **Spec source**: [github.com/adlnet/xAPI-Spec](https://github.com/adlnet/xAPI-Spec/blob/master/xAPI-Data.md)
- **Registry**: [xapi.com/registry](https://xapi.com/registry/)

### JSON Schema (core structure)
```json
{
  "actor": {
    "name": "Learner Name",
    "mbox": "mailto:learner@example.com"
  },
  "verb": {
    "id": "http://adlnet.gov/expapi/verbs/experienced",
    "display": { "en-US": "experienced" }
  },
  "object": {
    "id": "http://example.com/activity/chapter-3",
    "definition": {
      "name": { "en-US": "Chapter 3: Thermodynamics" },
      "type": "http://adlnet.gov/expapi/activities/module"
    }
  },
  "result": {
    "completion": false,
    "duration": "PT45M",
    "extensions": { "http://example.com/ext/highlight-count": 12 }
  },
  "context": {
    "contextActivities": {
      "parent": [{ "id": "http://example.com/course/physics-101" }]
    },
    "extensions": {
      "http://example.com/ext/reading-position": { "page": 47, "paragraph": 3 }
    }
  },
  "timestamp": "2026-03-08T14:30:00.000Z"
}
```

### What It Captures
- Actor-Verb-Object triple: "who did what to which thing"
- Temporal data via ISO 8601 timestamps
- Result data (scores, completion, duration, custom extensions)
- Context (parent activities, instructor, platform, extensions)
- Attachments (binary data like signatures)

### Key Verbs (ADL published)
experienced, attended, attempted, completed, passed, failed, answered, interacted, imported, created, shared, voided

### Reading/Annotation Relevance
- No pre-built "reading profile" with verbs like highlighted/bookmarked/commented -- these must be community-defined via the xAPI Registry
- Extensions mechanism (URI-keyed JSON) provides unlimited flexibility for custom data (gaze coordinates, annotation content, ink strokes)
- Statements are atomic events, not continuous streams -- need to decompose reading sessions into discrete events

### Limitations
- **No streaming**: Designed for discrete events, not continuous sensor data (eye tracking at 60Hz would generate massive statement volumes)
- **No document anchoring**: No built-in selector mechanism to point at specific text ranges (must be encoded in extensions)
- **Vocabulary fragmentation**: Without agreed-upon verb/extension vocabularies for reading+annotation, interoperability is theoretical
- **Flat structure**: No native concept of hierarchical or nested events (reading session > page view > highlight > annotation)
- **No multimodal fusion**: Just a transport/storage format, no alignment mechanism across modalities

### Relevance to Our System: MEDIUM-HIGH
Best used as the **event envelope** -- each user action (highlight, annotation, page turn, gaze fixation) becomes an xAPI statement. Custom extensions carry the domain-specific payload. But for high-frequency sensor data (eye tracking, pen pressure), xAPI introduces overhead. Hybrid approach: xAPI for behavioral events, raw time-series for sensor streams, linked by timestamps.

---

## 2. Caliper Analytics (1EdTech / IMS Global)

### Specification
- **Standard**: Caliper Analytics 1.2 (current), maintained by 1EdTech (formerly IMS Global)
- **Spec source**: [imsglobal.org/spec/caliper/v1p2](https://www.imsglobal.org/spec/caliper/v1p2)
- **GitHub**: [github.com/1EdTech/caliper-spec](https://github.com/IMSGlobal/caliper-spec)

### JSON-LD Event Structure
```json
{
  "@context": "http://purl.imsglobal.org/ctx/caliper/v1p2",
  "id": "urn:uuid:...",
  "type": "AnnotationEvent",
  "actor": {
    "id": "https://example.edu/users/554433",
    "type": "Person"
  },
  "action": "Highlighted",
  "object": {
    "id": "https://example.edu/etexts/201/chapter-3",
    "type": "Document"
  },
  "generated": {
    "id": "urn:uuid:...",
    "type": "HighlightAnnotation",
    "annotated": "https://example.edu/etexts/201/chapter-3",
    "selection": {
      "type": "TextPositionSelector",
      "start": 2300,
      "end": 2370
    }
  },
  "eventTime": "2026-03-08T14:30:15.432Z"
}
```

### Metric Profiles (15 total)
1. **Annotation Profile**: Bookmarked, Highlighted, Shared, Tagged actions + corresponding Annotation subtypes
2. **Reading Profile**: NavigationEvent (NavigatedTo) and ViewEvent (Viewed) for tracking document navigation
3. **Assessment Profile**: Started, Submitted, Paused, Resumed, Completed, Reset
4. **Media Profile**: Started, Paused, Resumed, Ended for media playback
5. **Session Profile**: LoggedIn, LoggedOut, TimedOut
6. + 10 more (Forum, Grading, Survey, Tool Launch, Tool Use, etc.)

### 69 Entity Types
Person, Organization, Document, DigitalResource, Assessment, AssessmentItem, Attempt, Response, Score, Message, Forum, Thread, Annotation subtypes (BookmarkAnnotation, HighlightAnnotation, SharedAnnotation, TagAnnotation), etc.

### Caliper vs xAPI Comparison

| Dimension | xAPI | Caliper |
|-----------|------|---------|
| Data model | Actor-Verb-Object (freeform) | Actor-Action-Object (profile-constrained) |
| Strictness | Loose (any verb URI) | Tight (must implement metric profiles) |
| Certification | None required | Consortium membership + profile compliance |
| Interoperability | Theoretical (vocab fragmentation) | Higher (standardized profiles) |
| Reading support | No built-in profile | Annotation + Reading profiles |
| Serialization | JSON | JSON-LD |
| Storage target | LRS | Event Store (any) |
| Extensibility | Extensions via URI keys | Extensions property |
| Adoption | Broader (corporate, military, ed-tech) | Higher-ed, LMS vendors |
| Standard body | IEEE (formerly ADL) | 1EdTech (formerly IMS Global) |

### Limitations
- **ReadingEvent deprecated** in recent spec versions -- reading tracking now via ViewEvent/NavigationEvent (less granular)
- **No sensor data profiles**: No profiles for eye tracking, physiological data, pen input
- **Consortium lock-in**: Certification requires 1EdTech membership
- **Limited community verbs**: Cannot extend verb vocabulary as freely as xAPI

### Relevance to Our System: HIGH
Caliper's Annotation Profile is the closest pre-built standard to what we need. It already models Highlighted, Bookmarked, Shared, Tagged with document anchoring via selectors. The Reading Profile captures navigation. Main gap: no support for handwriting/ink data, eye tracking, or think-aloud audio.

---

## 3. Learning Record Stores (LRS)

### What They Are
Server systems that receive, validate, store, and serve xAPI statements. Required component of any xAPI ecosystem.

### Key Implementations
| LRS | Type | Notes |
|-----|------|-------|
| Learning Locker | Open source | MongoDB-backed, widely used |
| Watershed | Commercial | Owned by Rustici Software |
| Veracity | Commercial | Cloud-hosted |
| Yet Analytics | Commercial | Enterprise, SQL-backed |
| SCORM Cloud | Commercial | Rustici, also supports SCORM |

### Data Format
- **Input**: xAPI Statements (JSON)
- **Validation**: LRS validates statement structure, required fields, JSON correctness
- **Storage**: Implementation-dependent (MongoDB, PostgreSQL, etc.)
- **Query**: xAPI Statement API with filtering by actor, verb, activity, date range

### Limitations
- **xAPI-only**: LRS stores only xAPI statements, not raw sensor streams
- **No fusion**: No built-in mechanism for combining with non-xAPI data
- **Query limitations**: Statement API not designed for complex analytics queries

### Relevance to Our System: MEDIUM
An LRS could store the behavioral event layer (annotations, page views, reading events) but not the sensor layer (eye tracking, pen data). We'd need a parallel time-series database for high-frequency data, with the LRS handling the semantically-rich event stream.

---

## 4. Multimodal Learning Analytics (MMLA)

### Key Survey
- Chango et al. (2025). "A review on data fusion in multimodal learning analytics and educational data mining." arXiv:2511.20871
- Crescenzi-Lanna (2020). "Multimodal Data Fusion in Learning Analytics: A Systematic Review." PMC7729570.

### Data Modalities Identified
1. **Digital space**: Log data, clickstream, mouse movements, keystrokes, text, handwriting
2. **Physical space**: Eye tracking, facial expressions, body posture, gestures
3. **Physiological space**: EEG, ECG, skin conductance, heart rate
4. **Psychometric space**: Self-report questionnaires
5. **Environmental space**: Ambient conditions

### Fusion Approaches
- **Many-to-one**: Multiple modalities measure a single construct (e.g., engagement)
- **Many-to-many**: Multiple modalities map to multiple indicators
- **Triangulation**: Independent parallel analysis for validation

### The Standardization Gap
This is the critical finding: **there is no unified standard for multimodal learning data.** The systematic review explicitly notes that "fusion lies at the conceptual heart of MMLA, yet it remains one of the least standardized components." Each research group uses ad-hoc schemas. Common patterns:
- JSON with ISO 8601 timestamps
- CSV with frame numbers as alignment keys
- Proprietary sensor formats converted to tabular data

### Key Systems/Toolkits

**OpenMMLA** (LAK 2025)
- IoT-based toolkit for multimodal data collection
- Toolkit approach with prebuilt pipelines
- Addresses privacy, flexibility, scalability
- No published standard schema

**EZ-MMLA** (Worsley et al., 2021/2022)
- Browser-based, uses TensorFlow.js for local processing
- Captures: eye tracking, pose detection, hand tracking, emotion detection, heart rate, object detection
- **Data format**: CSV files with frame-based organization. Each row: frame number, timestamp, per-joint (x, y, confidence) for pose; equivalent structures for other modalities
- **Temporal sync**: Video frame number as universal join key
- Privacy-preserving: all processing in-browser

**M2LADS** (Becerra, Cukurova et al., 2023, arXiv:2305.12561)
- System for multimodal LA dashboards in open education
- Integrates EEG, heart rate, video, MOOC logs
- Uses edBB platform for data collection

**MOSAIC-F** (Becerra et al., 2025, arXiv:2506.08634)
- Framework for multimodal feedback on oral presentations
- Integrates video, audio, gaze, physiology, behavioral interactions
- Four-step pipeline: assessment, data collection, AI feedback generation, self-review

**Platform mBox** (LAK 2024)
- Open MMLA platform for field deployments
- Designed for ecological validity

### Key Researchers
- **Marcelo Worsley** (Northwestern): Pioneer of MMLA (coined with Blikstein, 2009). Focus: process-oriented multimodal data in maker/hands-on learning. Editor of special issue on MMLA in ecological settings.
- **Xavier Ochoa** (NYU): Co-editor of The Multimodal Learning Analytics Handbook (Springer, 2022). Focus: low-cost sensors for collaboration, RAP system for oral presentation feedback.
- **Mutlu Cukurova** (UCL): Collaborative problem-solving via multimodal data (verbal, audio, screen). Recent work on LLM-based CPS diagnosis (arXiv:2504.15093). Shows multimodal transformers outperform unimodal for social-cognitive CPS indicators.
- **Bertrand Schneider** (Harvard), **Roberto Martinez-Maldonado** (Monash), **Gautam Biswas** (Vanderbilt): Co-editors of MMLA in ecological settings special issue.

### Relevance to Our System: VERY HIGH
MMLA is the closest research community to what we're building. The critical gap: no standard data model for multimodal traces. We would be contributing to the field by defining one for reading+annotation+gaze. The EZ-MMLA frame-number alignment pattern is directly applicable.

---

## 5. Knowledge Tracing Models

### BKT (Bayesian Knowledge Tracing)

**Input format** (standard-bkt):
```
observation	student	problem_step	skill(s)
2	student_001	unit1-problem5-step1	addition~multiplication
1	student_001	unit1-problem5-step2	multiplication
```
- 4 tab-separated columns
- Observation: 1=correct, 2=incorrect, .=missing
- Multiple skills delimited by custom character (e.g., ~)
- pyBKT accepts: -1 (no response), 0 (incorrect), 1 (correct)

**Parameters**: P(L0) init knowledge, P(T) transition/learn, P(G) guess, P(S) slip

### DKT (Deep Knowledge Tracing)

**Input format**: 3-column space-delimited file
```
student_id  skill_id  correct
1  5  1
1  3  0
1  5  1
```
- Sequential: order of rows encodes temporal progression
- Binary outcomes (0/1)
- One-hot encoding of skill_id as input vector

**Key papers**:
- Piech et al. (2015). "Deep Knowledge Tracing." NeurIPS. (Original DKT)
- Khajah et al. (2016). "How deep is knowledge tracing?" arXiv:1604.02416 (Shows extended BKT matches DKT -- depth not always needed)
- Pandey & Karypis (2019). "SAKT: Self-Attentive Knowledge Tracing." arXiv:1907.06837 (Attention-based, handles sparsity)
- Zhou et al. (2025). "DKT2: Revisiting Applicable and Comprehensive Knowledge Tracing." arXiv:2501.14256 (xLSTM architecture, Rasch model input, IRT output)

### SPARFA (Sparse Factor Analysis)

**Input format**: Binary matrix (correct/incorrect) of learner responses to questions
- Rows: learners, Columns: questions
- Can handle partial observability (not all learners answer all questions)
- SPARFA-Trace (Lan et al., 2013, arXiv:1312.5734): extends to time-varying by adding action logs (what learner does at each timestep: answer question or study resource)
- Ordinal SPARFA-Tag (Lan et al., 2014, arXiv:1412.5967): extends to partial credit (ordinal scale) and question tags

**What SPARFA estimates**:
1. Question-concept association matrix (W)
2. Learner concept-knowledge profiles (C)
3. Question intrinsic difficulties (mu)

### Limitations for Our Use Case
- **All KT models assume discrete assessment events**: correct/incorrect on questions
- **No support for continuous processes**: reading, note-taking, thinking are not binary-outcome events
- **No multimodal input**: designed for clickstream/response data only
- **Temporal granularity**: per-question or per-session, not sub-second

### Relevance to Our System: LOW-MEDIUM
KT models are designed for a fundamentally different data type (assessment responses). They could potentially consume *derived* features from our system (e.g., "did the learner demonstrate understanding of concept X based on their annotations?"), but they cannot directly ingest reading traces, eye tracking, or handwritten notes. The SPARFA-Trace idea of modeling knowledge state transitions based on learning resource interactions is conceptually relevant -- our system could feed higher-level events (read section, annotated concept, reviewed notes) into a modified KT framework.

---

## 6. Annotation Standards

### W3C Web Annotation Data Model (WADM)
- **Status**: W3C Recommendation (stable standard)
- **Spec**: [w3.org/TR/annotation-model/](https://www.w3.org/TR/annotation-model/)
- **Serialization**: JSON-LD

**Core structure**:
```json
{
  "@context": "http://www.w3.org/ns/anno.jsonld",
  "id": "http://example.org/anno1",
  "type": "Annotation",
  "body": {
    "type": "TextualBody",
    "value": "This contradicts the second law",
    "format": "text/plain"
  },
  "target": {
    "source": "http://example.org/textbook/chapter3.pdf",
    "selector": {
      "type": "TextQuoteSelector",
      "exact": "entropy always decreases",
      "prefix": "In closed systems, ",
      "suffix": " over time."
    }
  },
  "creator": "http://example.org/user/hudson",
  "created": "2026-03-08T14:30:00Z",
  "motivation": "commenting"
}
```

**8 Selector Types**:
1. **TextQuoteSelector**: exact text + prefix/suffix context (most robust for text)
2. **TextPositionSelector**: character start/end offsets (fragile to edits)
3. **FragmentSelector**: media-type-specific fragment IDs
4. **CssSelector**: CSS selectors for DOM nodes
5. **XPathSelector**: XPath expressions for XML/HTML
6. **DataPositionSelector**: byte-range offsets for binary data
7. **SvgSelector**: SVG shapes for spatial regions (useful for handwriting on page images)
8. **RangeSelector**: combines two selectors for start/end boundaries

**Refinement**: Selectors can be nested via `refinedBy` for multi-level targeting (e.g., FragmentSelector to identify a page, then TextQuoteSelector within that page).

**Motivations** (why the annotation was made): bookmarking, classifying, commenting, describing, editing, highlighting, identifying, linking, moderating, questioning, replying, reviewing, tagging.

### Hypothes.is Data Format
- Implements W3C WADM
- **API**: RESTful, JSON responses
- **Target structure** uses triple-redundant selectors for robustness:
  ```json
  "target": [{
    "source": "https://example.com/article",
    "selector": [
      {
        "type": "RangeSelector",
        "startContainer": "/div[1]/p[3]",
        "startOffset": 12,
        "endContainer": "/div[1]/p[3]",
        "endOffset": 48
      },
      {
        "type": "TextPositionSelector",
        "start": 546,
        "end": 587
      },
      {
        "type": "TextQuoteSelector",
        "exact": "entropy always decreases",
        "prefix": "In closed systems, ",
        "suffix": " over time."
      }
    ]
  }]
  ```
- **Fuzzy anchoring**: If exact text changes, falls back to prefix/suffix context matching
- **API fields**: id, uri, text, tags, user, group, permissions, created, updated, document (title, metadata), references (for replies), target (with selectors)

### Open Annotation (predecessor to WADM)
- W3C Open Annotation Community Group specification
- Superseded by WADM in 2017
- Introduced SpecificResource / Selector pattern that WADM adopted

### Relevance to Our System: VERY HIGH
The W3C WADM is the right standard for linking annotations to specific document locations. Key insights:
- **SvgSelector** can describe handwritten annotation regions on page images
- **TextQuoteSelector** anchors text highlights robustly
- **Motivation** vocabulary maps directly to learning activities (highlighting, commenting, questioning)
- **Missing**: No built-in concept of temporal sequence or learning progression -- annotations are individual objects, not a stream
- **Missing**: No ink/handwriting body type -- would need extension for stroke data (pressure, tilt, coordinates)

---

## 7. Think-Aloud Protocol Data

### Traditional Format
- **Audio recording** of concurrent verbalization during task
- **Transcription**: Full verbatim, including pauses (marked with dots), interruptions, meta-comments
- **Segmentation**: Divide transcript into analyzable units (utterances, sentences, episodes)
- **Coding**: Apply coding scheme to each segment

### Common Coding Schemes for Reading Comprehension

| Code Category | Description | Example |
|---------------|-------------|---------|
| Paraphrase | Restating text content | "So it's saying that..." |
| Elaboration | Adding prior knowledge | "That's like how..." |
| Prediction | Anticipating text content | "I think next they'll..." |
| Monitoring | Checking comprehension | "Wait, I don't get this" |
| Questioning | Generating questions | "Why would that happen?" |
| Summarizing | Condensing information | "The main point is..." |
| Connecting | Linking ideas | "This relates to..." |
| Evaluating | Judging content | "That argument is weak" |
| Visualizing | Creating mental images | "I picture this as..." |
| Rereading | Going back to re-process | "Let me read that again" |

### Automated Approaches
- Hamzah et al. (2024, MDPI Applied Sciences 14/2/858): Uses sentence embeddings to automatically identify reading comprehension impairment from think-aloud transcripts
- Traditional NLP pipeline: speech-to-text -> segmentation -> embedding -> classification

### Data Structure (typical research format)
```
participant_id, timestamp, segment_id, utterance_text, code, page, paragraph
P001, 2026-03-08T14:30:05, 1, "So this is about entropy...", paraphrase, 47, 3
P001, 2026-03-08T14:30:12, 2, "Wait that doesn't make sense", monitoring, 47, 3
P001, 2026-03-08T14:30:18, 3, "Let me read that again", rereading, 47, 3
```

### Limitations
- **Manual transcription**: Extremely time-consuming
- **Coding reliability**: Subjective interpretation, requires multiple coders and inter-rater reliability
- **Reactivity**: Thinking aloud alters the cognitive process being measured
- **No standard format**: Every research group uses ad-hoc schemas

### Relevance to Our System: HIGH
Think-aloud data is the closest existing paradigm to what we want to capture -- the temporal progression of a learner's thoughts while reading. Our system could capture something analogous automatically: annotation text as externalized thought, annotation timing and sequence as the temporal dimension, annotation location as the reading context. The coding scheme categories (paraphrase, elaboration, monitoring, questioning) could become classification labels for annotations.

---

## 8. Timestamped Event Logs for Learning

### Common Formats

**LMS Log Format** (Moodle, Canvas, etc.):
```
timestamp, user_id, event_type, resource_id, metadata
2026-03-08T14:30:00Z, u001, page_view, /course/101/page/5, {duration: 45}
2026-03-08T14:30:45Z, u001, highlight, /course/101/page/5, {start: 200, end: 250}
```

**Process Mining (XES format)**:
- IEEE standard for event logs (used in business process mining)
- XML-based, each event has: case_id, activity, timestamp, resources, attributes
- Could model learning as a process: reading -> highlighting -> annotating -> reviewing

**STREAMS** (Structured TRansactional Event Analysis of Multimodal Streams):
- Tool for integrating log data into multimodal streams
- Mentioned in Crescenzi-Lanna's systematic review

**Sensor Data (Time-Series)**:
- Eye tracking: timestamp, gaze_x, gaze_y, pupil_diameter, fixation_id, saccade_id (typically 60-120Hz)
- Pen/stylus: timestamp, x, y, pressure, tilt_x, tilt_y, stroke_id (typically 100-240Hz)
- No standard schema for learning-specific sensor data

### Eye Tracking Specific
- **Fixation data**: fixation_id, start_time, end_time, x, y, duration, AOI_label
- **Scanpath data**: ordered sequence of fixations with saccade metrics
- **Key metrics**: First Fixation Duration, Total Dwell Time, Fixation Count per AOI, Regression Count
- **Tools**: PyTrack, Tobii Pro SDK, iMotions -- each exports proprietary CSV formats
- No universal standard for gaze data in learning contexts

### Relevance to Our System: HIGH
The temporal event log is the backbone data structure we need. Key design decision: what granularity? Options:
1. **Event-level**: Each discrete action (page turn, highlight, annotation) is a log entry -- aligns with xAPI
2. **Sample-level**: Each sensor sample (gaze point, pen point) is a row -- aligns with time-series DBs
3. **Hybrid**: Event stream for behavioral data, time-series for sensor data, linked by timestamps

---

## Synthesis: Architecture Recommendation

### The Gap
No existing standard or system fully captures what we need: **the temporal progression of reading + annotation + thinking, anchored to document locations, enriched with eye gaze and handwriting data.** We're at the intersection of:
- xAPI/Caliper (behavioral events)
- W3C Web Annotation (document anchoring)
- MMLA toolkits (sensor fusion)
- Think-aloud protocols (thought progression)
- Knowledge tracing (learning state modeling)

### Proposed Hybrid Schema

Three data layers, linked by shared timestamps and session IDs:

**Layer 1: Behavioral Events (xAPI-compatible)**
- Reading events: page_view, scroll, navigate, search
- Annotation events: highlight, comment, question, tag, connect
- Each event carries W3C WADM selectors for document anchoring
- Stored in LRS or event database

**Layer 2: Sensor Streams (Time-series)**
- Eye tracking: gaze position, fixation/saccade classification, pupil diameter
- Pen input: stroke coordinates, pressure, tilt
- Audio (optional): for think-aloud capture
- Stored in time-series database (InfluxDB, TimescaleDB, or just Parquet files)
- Indexed by timestamp, aligned to Layer 1 events

**Layer 3: Derived Analytics**
- Reading patterns: dwell time per section, re-reading episodes, reading order
- Annotation patterns: annotation density, temporal clustering, concept coverage
- Comprehension indicators: derived from layers 1+2, potentially fed into modified KT models
- Stored as computed features, updateable

### Key Design Principles from the Literature
1. **Frame-number alignment** (from EZ-MMLA): Use a universal timestamp or frame counter as join key across modalities
2. **Triple-redundant anchoring** (from Hypothes.is): Store TextQuoteSelector + TextPositionSelector + RangeSelector for robust document linking
3. **Motivation vocabulary** (from WADM): Use standardized annotation motivations as event types
4. **Extension mechanism** (from xAPI): URI-keyed extensions for domain-specific data
5. **Profile-based semantics** (from Caliper): Define a "Reading+Annotation Profile" that constrains the vocabulary

### Open Questions for Our System
1. Do we emit xAPI statements to an LRS, or define our own event store? (Tradeoff: interoperability vs. simplicity)
2. How do we handle handwritten annotation body content? (Options: ink serialization format like InkML, stroke coordinates as JSON, or rendered image)
3. What temporal resolution for gaze data? (Full 60Hz stream vs. fixation-level summaries)
4. How do we model "learning progression" from the event stream? (Sequence analysis, KT adaptation, or LLM-based interpretation)

---

## Sources

### Standards & Specifications
- [xAPI Specification (GitHub)](https://github.com/adlnet/xAPI-Spec/blob/master/xAPI-Data.md)
- [xAPI Overview](https://xapi.com/overview/)
- [xAPI Statements 101](https://xapi.com/statements-101/)
- [xAPI Registry](https://xapi.com/registry/)
- [xAPI Wikipedia](https://en.wikipedia.org/wiki/Experience_API)
- [Caliper Analytics 1.2 Spec](https://www.imsglobal.org/spec/caliper/v1p2)
- [Caliper Spec (GitHub)](https://github.com/IMSGlobal/caliper-spec/blob/master/caliper-spec.md)
- [xAPI/Caliper Comparison (IMS Global)](https://www.imsglobal.org/initial-xapicaliper-comparison)
- [W3C Web Annotation Data Model](https://www.w3.org/TR/annotation-model/)
- [W3C Web Annotation Working Group](https://www.w3.org/annotation/)
- [Standard BKT Specification](https://iedms.github.io/standard-bkt/)
- [Learning Record Store (xapi.com)](https://xapi.com/learning-record-store/)
- [LRS Wikipedia](https://en.wikipedia.org/wiki/Learning_Record_Store)

### Hypothes.is
- [Hypothes.is API Blueprint (Draft)](https://gist.github.com/BigBlueHat/e7bff9b2b7c7336edf010f11aa28eb87)
- [Fuzzy Anchoring (Hypothes.is blog)](https://web.hypothes.is/blog/fuzzy-anchoring/)
- [Jon Udell: Notes for an Annotation SDK](https://blog.jonudell.net/2021/09/03/notes-for-an-annotation-sdk/)

### Academic Papers (arxiv)
- Chango et al. (2025). "A review on data fusion in multimodal learning analytics and educational data mining." arXiv:2511.20871
- Khalil (2020). "MOLAM: A Mobile Multimodal Learning Analytics Conceptual Framework." arXiv:2012.14308
- Cukurova et al. (2022). "AI-driven LA for CPS from a Complex Adaptive Systems Perspective." arXiv:2210.16059
- Cukurova et al. (2025). "Rethinking Multimodality in CPS Diagnosis with LLMs." arXiv:2504.15093
- Becerra, Cukurova et al. (2023). "M2LADS: MultiModal LA Dashboards." arXiv:2305.12561
- Becerra, Cukurova et al. (2025). "AI-based Multimodal Biometrics for Detecting Smartphone Distractions." arXiv:2506.17364
- Becerra et al. (2025). "MOSAIC-F: Multimodal Feedback Framework." arXiv:2506.08634
- Lan et al. (2013). "SPARFA: Sparse Factor Analysis for Learning and Content Analytics." arXiv:1303.5685
- Lan et al. (2013). "SPARFA-Trace: Time-varying Learning and Content Analytics." arXiv:1312.5734
- Lan et al. (2014). "Tag-Aware Ordinal SPARFA." arXiv:1412.5967
- Khajah et al. (2016). "How deep is knowledge tracing?" arXiv:1604.02416
- Pandey & Karypis (2019). "SAKT: Self-Attentive Knowledge Tracing." arXiv:1907.06837
- Zhou et al. (2025). "DKT2: Revisiting Knowledge Tracing." arXiv:2501.14256
- Sinha, Bai, Cassell (2022). "Multimodal Approach for Studying Dynamics of Curiosity." arXiv:2204.00545

### Academic Papers (other venues)
- Crescenzi-Lanna (2020). "Multimodal Data Fusion in Learning Analytics: A Systematic Review." Sensors, PMC7729570.
- Worsley & Blikstein (2012). "Multimodal Learning Analytics." ACM ICMI.
- Giannakos, Spikol, Di Mitri, Sharma, Ochoa, Hammad (2022). The Multimodal Learning Analytics Handbook. Springer.
- EZ-MMLA Toolkit (2022). Sensors 22(2):568. PMC8780387.
- OpenMMLA (2025). LAK '25.
- Platform mBox (2024). LAK '24.
- Hamzah et al. (2024). "Automated Think-Aloud Protocol for Identifying Students with Reading Comprehension Impairment." Applied Sciences 14(2):858.

### MMLA Researchers
- [Marcelo Worsley (Northwestern)](https://sites.northwestern.edu/marceloworsley/)
- [Xavier Ochoa (NYU)](https://xaoch.com/research)
- [Mutlu Cukurova (UCL)](https://www.researchgate.net/profile/Xavier-Ochoa)
- [Multimodal Learning Analytics Handbook](https://link.springer.com/book/10.1007/978-3-031-08076-0)

### Eye Tracking
- [PyTrack Toolkit](https://link.springer.com/article/10.3758/s13428-020-01392-6)
- [Eye Tracking Metrics (iMotions)](https://imotions.com/blog/learning/10-terms-metrics-eye-tracking/)
- [Comprehensive Eye Tracking Framework (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12564957/)