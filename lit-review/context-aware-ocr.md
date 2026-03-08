# Context-Aware Handwriting Recognition & LLM-Augmented OCR: Structured Literature Review

**Use case**: Someone reads an article on a laptop and takes handwritten notes in GoodNotes. Notes contain abbreviations, shorthand, diagrams, messy handwriting. Goal: use the CONTEXT of what they're reading to improve recognition of what they wrote.

---

## 1. LLM-Augmented OCR

### 1A. Multimodal LLMs as Direct OCR Engines

**Greif, Griesshaber & Greif (2025). "Multimodal LLMs for OCR, OCR Post-Correction, and Named Entity Recognition in Historical Documents." arXiv:2504.00414**
- **Approach**: Benchmark mLLMs (GPT-4o, Gemini, Claude) against conventional OCR (Tesseract, Kraken) on German historical city directories. Introduces *multimodal* post-correction: feed both the image AND the initial OCR text to the mLLM, so it can cross-reference visual evidence with textual hypotheses.
- **Results**: Best mLLM significantly outperforms SOTA conventional OCR. Multimodal post-correction consistently produces <1% CER without any image preprocessing or fine-tuning.
- **Applicability**: The multimodal post-correction paradigm is directly transferable -- feed the GoodNotes page image + initial OCR output + reading context to an mLLM for correction.
- **Limitations**: Tested on printed historical text, not handwriting. Cost/latency of frontier model inference. No fine-tuning explored.

**CHURRO (Semnani et al., 2025). "Making History Readable with an Open-Weight Large Vision-Language Model." arXiv:2509.19768**
- **Approach**: 3B-parameter open-weight VLM fine-tuned on 155 historical corpora (99K pages, 46 language clusters). Specialized for historical text recognition.
- **Results**: 82.3% (printed) and 70.1% (handwritten) normalized Levenshtein similarity. Surpasses Gemini 2.5 Pro by 6.5% on handwritten text while being 15.5x more cost-effective.
- **Applicability**: Demonstrates that small fine-tuned VLMs can beat frontier models for specialized domains. A similar approach could work for note-specific fine-tuning.
- **Limitations**: Historical domain, not contemporary handwritten notes. No context-conditioning mechanism.

**Ocean-OCR (Chen et al., 2025). "Towards General OCR Application via a Vision-Language Model." arXiv:2501.15558**
- **Approach**: 3B MLLM with native variable-resolution ViT, trained on diverse OCR datasets covering documents, scene text, and handwriting.
- **Results**: First MLLM to outperform professional OCR models (TextIn, PaddleOCR) across document, scene, and handwriting benchmarks.
- **Applicability**: General-purpose VLM-OCR that handles handwriting. Could serve as the base recognition model in a pipeline.
- **Limitations**: No context-conditioning. Accuracy on messy/abbreviated notes unknown.

**Consensus Entropy (Zhang et al., 2025). "Harnessing Multi-VLM Agreement for Self-Verifying OCR." arXiv:2504.11101**
- **Approach**: Training-free method. Run multiple VLMs on the same image, compute consensus entropy to identify uncertain outputs, select best or fuse. Key insight: correct predictions converge in output space, errors diverge.
- **Results**: 15.2% higher F1 than VLM-as-judge, 6.0% accuracy gain on math tasks. Only 7.3% of inputs need rephrasing.
- **Applicability**: Ensemble approach could combine GoodNotes' on-device OCR with a cloud VLM, using consensus to flag uncertain recognitions for context-based disambiguation.
- **Limitations**: Requires multiple model calls. Latency overhead.

### 1B. LLM Post-Correction of OCR

**Kanerva et al. (2025). "OCR Error Post-Correction with LLMs: No Free Lunches." arXiv:2502.01205**
- **Approach**: Evaluates open-weight LLMs for post-correction of OCR in historical English/Finnish. Tests parameter optimization, quantization, segment length effects.
- **Results**: LLMs reduce CER in English but fail for Finnish (morphologically complex). Segment length matters -- too short loses context, too long causes hallucination.
- **Applicability**: Warns against naive LLM post-correction. Context window management is critical. For notes, the "segment" should include both the recognized text AND the source article context.
- **Limitations**: Highlights that LLMs can *introduce* errors (hallucinate plausible but incorrect text). Language-dependent performance.

**Do et al. (2024). "Reference-Based Post-OCR Processing with LLM for Precise Diacritic Text." arXiv:2410.13305**
- **Approach**: Uses available content-focused ebooks as a *reference base* to correct OCR output, supported by LLMs. The reference text constrains the LLM's correction space.
- **Results**: Mean grading score of 8.72/10, outperforming SOTA Vietnamese spell correction (7.03/10).
- **Applicability**: **This is the closest existing work to your use case.** The "ebook reference" is analogous to the article the student is reading. The reference constrains disambiguation. Direct architectural inspiration.
- **Limitations**: Focused on historical Vietnamese with diacritics. Requires page-level alignment between reference and OCR output. Not designed for abbreviations or diagrams.

**Springer Chapter (2025). "Post-correction of Handwriting Recognition Using Large Language Models."**
- Via SpringerLink: link.springer.com/chapter/10.1007/978-981-96-4285-4_9
- Directly addresses LLM post-correction of HTR output. (Could not access full text, but the title confirms active research in this exact space.)

### 1C. Benchmarks for VLM Handwriting

**FERMAT (Nath et al., 2025). "Can Vision-Language Models Evaluate Handwritten Math?" arXiv:2501.07244**
- **Approach**: Benchmark of 2,200+ handwritten math solutions across error detection, localization, and correction tasks.
- **Results**: Gemini-1.5-Pro achieves highest error correction rate (77%). Models struggle with handwritten vs. printed input -- accuracy improves when handwriting is replaced with printed text.
- **Applicability**: Confirms that current VLMs have a handwriting-specific deficit. Processing handwritten math remains hard.
- **Limitations**: Focused on error evaluation, not on improving recognition through context.

**DrawEduMath (Baral et al., 2025; Lucy et al., 2026). arXiv:2501.14877 / arXiv:2603.00925**
- **Approach**: 2,030 images of K-12 handwritten math responses with teacher QA annotations. Tests VLMs on understanding handwritten student work.
- **Results**: SOTA VLMs leave much room for improvement. Models underperform specifically on student error-related questions -- they are optimized as math solvers, not as readers of messy handwriting.
- **Applicability**: Validates that handwritten note understanding is an unsolved problem. The educational context is close to your use case.

**Benchmarking French PDF-to-Markdown (Rigal et al., 2026). arXiv:2602.11960**
- **Approach**: French-focused benchmark including handwritten forms, complex layouts, dense tables. 15 VLMs evaluated.
- **Results**: Strongest proprietary models show substantially higher robustness on handwriting and forms. Open-weight models competitive on printed layouts but not handwriting.
- **Applicability**: Confirms the handwriting gap persists in 2026. Proprietary models still lead.

---

## 2. Context-Aware Handwriting Recognition

### 2A. The Core Innovation Gap

**Key finding**: No paper found that specifically uses the *content the person is reading* (source article) to improve recognition of their handwritten notes. This is an open research problem.

The closest existing work:
1. **Do et al. (2024)** -- uses ebook references to constrain OCR correction (see 1B above)
2. **Cai et al. (2022)** -- uses conversation context to expand abbreviations (see Section 4)
3. **Language models in decoding** -- standard practice of using language models during beam search (see 2B)

The gap: nobody has combined (source document as context) + (handwriting recognition) + (LLM reasoning) into a single system.

### 2B. Language Models for Contextual Decoding

**Ferro et al. (2024). "Boosting CNN-based Handwriting Recognition with Learnable Relaxation Labeling." arXiv:2409.05699**
- **Approach**: Integrates trainable Relaxation Labeling (RL) processes with CNN architectures to model long-range contextual dependencies in handwriting recognition.
- **Results**: Improves generalization, surpassing transformer-based architectures in some cases.
- **Applicability**: Shows that explicit contextual constraint modeling improves HTR. Could be extended with domain-specific constraints derived from source material.

**Liu et al. (2020). "Effects of Implicit and Explicit Language Model Information for DBLSTM-CTC." arXiv:2008.01532**
- **Approach**: Studies implicit (learned by the network) vs. explicit (separate LM during decoding) language models for handwriting recognition.
- **Results**: Even with 1M training sentences, explicit LMs still help.
- **Applicability**: Confirms that external language models improve HTR. The source article could serve as a *domain-adaptive* language model.

**A Pipeline Approach to Context-Aware Handwritten Text Recognition (2022). Applied Sciences 12(4):1870**
- Via MDPI: mdpi.com/2076-3417/12/4/1870
- **Approach**: Pipeline that locates text on a page, recognizes text types, and understands context within detected regions. Uses NER-like classification to assign context (name, address, etc.) to recognized text.
- **Applicability**: Demonstrates that context-type classification improves downstream accuracy. For notes, context-type would be "notes about article X on topic Y."

### 2C. Transformer-Based Contextual HTR

**DANIEL (Constum et al., 2024). "A fast Document Attention Network for Information Extraction and Labelling." arXiv:2407.09103**
- **Approach**: Fully end-to-end architecture integrating a language model for layout recognition, handwriting recognition, and NER simultaneously. Convolutional encoder + autoregressive transformer decoder. Prompt-based ontology specification.
- **Results**: SOTA on RIMES 2009, M-POPP, IAM NER.
- **Applicability**: The prompt-based approach is interesting -- you could prompt with "these notes are about [article topic]" to condition recognition.
- **Limitations**: Not designed for external context injection. Trained on structured documents, not free-form notes.

---

## 3. Diagram and Sketch Recognition

### 3A. Foundational Models for Mixed Content

**InkFM (Fadeeva et al., 2025). "A Foundational Model for Full-Page Online Handwritten Note Understanding." arXiv:2503.23081**
- **Approach**: Foundation model for analyzing full pages of online (digital ink) handwritten content. Trained on 22K unique full-page notes with three-level hierarchical segmentation. Handles text (28 scripts), math expressions, and drawings in a single model.
- **Results**: SOTA text line segmentation (surpasses docTR). SOTA text recognition on DeepWriting, CASIA, SCUT, Mathwriting. SOTA sketch classification on QuickDraw.
- **Applicability**: **Directly relevant.** This is the state of the art for separating text from drawings in handwritten notes. Would serve as the segmentation/classification front-end in your pipeline. LoRA-tunable for domain adaptation.
- **Limitations**: Google internal work. Availability unclear. Online (stroke-based) input, not offline (image-based) -- though GoodNotes has stroke data.

**Representing Online Handwriting for Recognition in VLMs (Fadeeva et al., 2024). arXiv:2402.15307**
- **Approach**: Novel tokenized representation of digital ink that includes both stroke sequences as text AND rendered images. Applied to off-the-shelf VLMs without architecture changes.
- **Results**: Comparable to or better than SOTA online handwriting recognizers. Works with multiple VLM families.
- **Applicability**: GoodNotes stores stroke data. This dual representation (strokes + image) could be fed to a VLM along with article context. No architecture changes needed.
- **Limitations**: Tested on standard recognition benchmarks, not on messy notes with abbreviations.

**InkSight (Mitrevski et al., 2024). "Offline-to-Online Handwriting Conversion." arXiv:2402.05804**
- **Approach**: Converts offline (image) handwriting to online (stroke) representation using VLMs with reading and writing priors. 87% valid tracing rate.
- **Applicability**: If only images are available (e.g., photo of paper notes), this recovers stroke data for InkFM-style processing.

### 3B. Sketch Recognition Systems

**ViSketch-GPT (Federico et al., 2025). arXiv:2503.22374**
- **Approach**: Multi-scale context extraction for sketch recognition and generation. Ensemble-like mechanism combining features at multiple scales.
- **Results**: New benchmark on QuickDraw for both classification and generation.
- **Applicability**: Could classify diagram types in notes (graph, table, flowchart, etc.).

**Flowmind2Digital (Liu et al., 2024). arXiv:2401.03742**
- **Approach**: Converts hand-drawn flowcharts and mind maps to digital format using neural networks and keypoint detection.
- **Results**: 87.3% accuracy, surpassing previous methods by 11.9%.
- **Applicability**: Handles a common note-taking structure (mind maps, flowcharts). Could be a specialized module in the pipeline.

**Affordances of Sketched Notations for Multimodal UI Design (Ross et al., 2025). arXiv:2508.09342**
- **Approach**: Analyzes how users sketch without imposed rules, finding sketches are ambiguous in isolation but *interpretable in context within whole designs*.
- **Results**: Argues that element-based recognition fails; transformer-based and human-in-the-loop approaches are needed to understand context-rich notations.
- **Applicability**: **Critical insight for your system.** Individual handwritten elements (abbreviations, arrows, symbols) are ambiguous alone but interpretable given the page context and reading context. This validates the core hypothesis.

### 3C. Handwritten Circuit/Diagram Extraction

**Bayer et al. (2023, 2024). Instance/Modular Graph Extraction for Handwritten Circuit Diagrams. arXiv:2301.03155, arXiv:2402.11093**
- **Approach**: Instance segmentation + keypoint extraction to separate components, text, and connections in hand-drawn circuit diagrams.
- **Applicability**: Demonstrates that structured diagram extraction from handwriting is feasible with instance segmentation approaches.

---

## 4. Abbreviation Expansion

**Cai et al. (2022). "Context-Aware Abbreviation Expansion Using Large Language Models." NAACL 2022. arXiv:2205.03767**
- **Approach**: Phrases abbreviated as word-initial letters (e.g., "tmw" -> "tell me why"). LLM generates expansions conditioned on conversation context. Filtered to match abbreviation pattern.
- **Results**: 64B LLM exactly expands >70% of phrases (abbreviation length <= 10). **One turn of context more than doubles accuracy vs. no context.** Keystroke savings up to 77%.
- **Applicability**: **Directly applicable.** Replace "conversation context" with "article being read." The abbreviation pattern-matching filter is reusable. The doubling-with-context effect is the key evidence that your approach will work.
- **Limitations**: Tested on conversational text, not domain-specific academic notes. Abbreviation style is word-initial letters; handwritten notes use more diverse abbreviation strategies (truncation, symbols, domain shorthand).

**Gorman et al. (2021). "Structured Abbreviation Expansion in Context." arXiv:2110.01140**
- **Approach**: Studies ad hoc abbreviations in informal text (intentional, productive, not in dictionaries). Generates large open-source dataset.
- **Results**: Strong baselines for expansion. Characterizes abbreviation strategies.
- **Applicability**: Ad hoc abbreviation strategies map well to note-taking shorthand. Dataset and analysis of abbreviation patterns useful for system design.

**Ciosici et al. (2019). "Unsupervised Abbreviation Disambiguation." arXiv:1904.00929**
- **Approach**: Entirely unsupervised method. Learns abbreviation definitions from unstructured text, creates distinct tokens per meaning, uses word vectors for context representation.
- **Results**: High performance across domains. Scales to thousands of abbreviations.
- **Applicability**: Could pre-populate an abbreviation dictionary from the source article's domain.

**Wen et al. (2020). "MeDAL: Medical Abbreviation Disambiguation Dataset." arXiv:2012.13978**
- **Approach**: Large medical text dataset for abbreviation disambiguation. Pre-training on this improves downstream medical NLP.
- **Applicability**: Domain-specific abbreviation disambiguation is a solved-ish problem in medicine. Same approach for CS/physics/etc. notes.

**Jiang et al. (2024). "Evaluating ChatGPT-Based Abbreviation Expansion." arXiv:2410.23866**
- **Approach**: Tests ChatGPT on source code abbreviation expansion. Finds it underperforms SOTA heuristic approaches. Root causes: lack of context, inability to recognize abbreviations.
- **Results**: Adding surrounding source code context is the best fix. Iterative approach to mark missed abbreviations helps.
- **Applicability**: **Key lesson**: LLMs need explicit context to expand abbreviations well. Just feeding the abbreviation alone fails. The source article is that context.

---

## 5. Multimodal Note Understanding

### 5A. Benchmarks

**NoTeS-Bank (Pal et al., 2025). "Benchmarking Neural Transcription and Search for Scientific Notes Understanding." arXiv:2504.09249**
- **Approach**: First benchmark for handwritten scientific notes. Complex notes across multiple STEM domains with equations, diagrams, scientific notation. Two tasks: Evidence-Based VQA (localized answers with bounding boxes) and Open-Domain VQA (domain classification then retrieval).
- **Results**: Exposes structured transcription and reasoning limitations of SOTA VLMs. Demands vision-language fusion, retrieval, and multimodal reasoning.
- **Applicability**: **Directly relevant benchmark.** Evaluates exactly the capabilities your system would need. Current models struggle -- opportunity for a context-conditioned approach to outperform.
- **Limitations**: Benchmark only -- no proposed solution that uses source material context.

**ICDAR 2025 Handwritten Notes Understanding Challenge**
- 2,000+ real academic note images, 1,000 curated STEM questions. Multi-phase evaluation requiring answer correctness AND grounded reasoning (localize visual evidence).
- Results underscore that SOTA VLMs face serious obstacles in multimodal reasoning over handwritten content.

### 5B. Document Understanding Models

**Uni-MuMER (Li et al., 2025). "Unified Multi-Task Fine-Tuning of VLM for Handwritten Math Expression Recognition." arXiv:2505.23566**
- **Approach**: Fine-tunes VLM for handwritten math with three tasks: Tree-Aware Chain-of-Thought for spatial reasoning, Error-Driven Learning for similar-character confusion, Symbol Counting for long expressions.
- **Results**: SOTA on CROHME and HME100K. Outperforms SSAN by 16.31% and Gemini 2.5-flash by 24.42% zero-shot.
- **Applicability**: Tree-CoT for structured spatial reasoning could be adapted for note layout understanding.

**MathWriting (Gervais et al., 2024). arXiv:2404.10690**
- 230K human-written + 400K synthetic handwritten math expressions. Largest online HME dataset. Baseline VLM results included.
- **Applicability**: Training data source for math-heavy notes.

---

## 6. Vision-Language Models for Document Understanding

### 6A. General VLM OCR Capabilities

**Current SOTA rankings (as of early 2026)**:
- **Handwriting**: GPT-5 > olmOCR-2-7B > Gemini 2.5 Pro (per aimultiple.com benchmark)
- **Printed**: Gemini 2.5 Pro ~ Google Vision ~ Claude Sonnet 4.5
- **Cost-effective**: CHURRO (3B, open-weight) beats Gemini 2.5 Pro on handwriting at 1/15th cost
- **On-device**: GoodNotes uses proprietary on-device model, >95% accuracy on clean handwriting, supports 12 languages

### 6B. VLMs for Handwriting Verification/Analysis

**Chauhan et al. (2024). "VLM Based Handwriting Verification." arXiv:2407.21788**
- GPT-4o achieves 70% accuracy on handwriting verification using 0-shot CoT. Fine-tuned PaliGemma: 71%. CNN ResNet-18: 84%.
- Key finding: VLMs provide interpretability but still lag specialized models on handwriting-specific tasks.

**Levchenko (2025). "Evaluating LLMs for Historical Document OCR." arXiv:2510.06743**
- 12 multimodal LLMs evaluated. Gemini and Qwen outperform traditional OCR but exhibit "over-historicization" (inserting archaic characters from wrong periods). Post-OCR correction *degrades* performance in some cases.
- **Key lesson**: LLMs bring their own biases. Domain context must be carefully managed to avoid introducing errors.

---

## Synthesis: Architecture for Context-Aware Note Recognition

Based on the literature, no existing system combines all components. Here is what the SOTA suggests as a pipeline:

### Proposed Architecture

```
[GoodNotes stroke data + page image]
         |
    [InkFM-style segmentation]
    /        |          \
[Text]   [Math]     [Diagrams/Sketches]
   |        |              |
[VLM-OCR] [Uni-MuMER]  [ViSketch-GPT / Flowmind2Digital]
   |        |              |
   v        v              v
[Raw recognition hypotheses (N-best)]
         |
[Context-Conditioned Post-Correction]
   - Input: N-best hypotheses + source article text + topic
   - Method: LLM re-ranking/correction (Greif et al. multimodal approach)
   - Abbreviation expansion (Cai et al. pattern-matching + context)
   - Reference-based correction (Do et al. paradigm)
         |
[Structured output: recognized text, expanded abbreviations,
 diagram descriptions, linked to source material sections]
```

### Key Design Principles from Literature

1. **Context more than doubles accuracy** (Cai et al.): A single turn of context doubles abbreviation expansion. Source article = rich context.
2. **Multimodal post-correction beats text-only** (Greif et al.): Feed both image and text to the LLM corrector.
3. **Reference-based correction constrains hallucination** (Do et al.): The source article limits the space of plausible expansions.
4. **Segmentation first** (InkFM): Separate text, math, and drawings before specialized recognition.
5. **Consensus for uncertainty** (Zhang et al.): Use agreement between on-device OCR and cloud VLM to identify which words need context-based disambiguation.
6. **Small fine-tuned models can beat frontier** (CHURRO): A 3B model fine-tuned on your domain may outperform GPT-5 zero-shot.
7. **Elements ambiguous alone are interpretable in context** (Ross et al.): The whole-page + source-article context is necessary for disambiguation.

### Open Research Questions

1. **How much source article context is optimal?** Full text? Summary? Key terms? (Kanerva et al. warn about segment length tradeoffs.)
2. **What abbreviation strategies do note-takers actually use?** Word-initial (Cai)? Truncation (Gorman)? Domain-specific symbols? Empirical study needed.
3. **How to align notes to source material sections?** Temporal (what was on screen when note was written)? Semantic (topic matching)?
4. **Hallucination risk**: LLMs may "recognize" text that wasn't written, influenced by the source article. Need verification mechanisms.
5. **Latency vs. accuracy tradeoff**: On-device recognition is instant but context-unaware. Cloud VLM with context is slow but more accurate. When to invoke each?
6. **Personalization**: Handwriting styles, abbreviation habits, and domain knowledge are person-specific. Few-shot adaptation needed.

### What's Novel About Your Approach

The literature reveals a clear gap: **nobody has used the source material a person is reading as context for recognizing their handwritten notes about that material.** The closest work is Do et al. (reference-based post-OCR), Cai et al. (context-aware abbreviation expansion), and the InkFM/NoTeS-Bank work on note understanding. Your system would be the first to combine all three: source-context-conditioned handwriting recognition with abbreviation expansion and diagram understanding.

---

## Source URLs

- Greif et al. (2025): https://arxiv.org/pdf/2504.00414v1
- CHURRO (2025): https://arxiv.org/pdf/2509.19768v1
- Ocean-OCR (2025): https://arxiv.org/pdf/2501.15558v1
- Consensus Entropy (2025): https://arxiv.org/pdf/2504.11101v2
- Kanerva et al. (2025): https://arxiv.org/pdf/2502.01205v1
- Do et al. (2024): https://arxiv.org/pdf/2410.13305v3
- FERMAT (2025): https://arxiv.org/pdf/2501.07244v2
- DrawEduMath (2025/2026): https://arxiv.org/pdf/2501.14877v1 / https://arxiv.org/pdf/2603.00925v1
- Rigal et al. (2026): https://arxiv.org/pdf/2602.11960v1
- Ferro et al. (2024): https://arxiv.org/pdf/2409.05699v1
- DANIEL (2024): https://arxiv.org/pdf/2407.09103v1
- InkFM (2025): https://arxiv.org/pdf/2503.23081v1
- Fadeeva et al. (2024): https://arxiv.org/pdf/2402.15307v1
- InkSight (2024): https://arxiv.org/pdf/2402.05804v4
- ViSketch-GPT (2025): https://arxiv.org/pdf/2503.22374v1
- Flowmind2Digital (2024): https://arxiv.org/pdf/2401.03742v1
- Ross et al. (2025): https://arxiv.org/pdf/2508.09342v1
- Bayer et al. (2023/2024): https://arxiv.org/pdf/2301.03155v2 / https://arxiv.org/pdf/2402.11093v1
- Cai et al. (2022): https://aclanthology.org/2022.naacl-main.91/
- Gorman et al. (2021): https://arxiv.org/pdf/2110.01140v1
- Ciosici et al. (2019): https://arxiv.org/pdf/1904.00929v2
- MeDAL (2020): https://arxiv.org/pdf/2012.13978v1
- Jiang et al. (2024): https://arxiv.org/pdf/2410.23866v1
- NoTeS-Bank (2025): https://arxiv.org/pdf/2504.09249v1
- Uni-MuMER (2025): https://arxiv.org/pdf/2505.23566v4
- MathWriting (2024): https://arxiv.org/pdf/2404.10690v2
- Chauhan et al. (2024): https://arxiv.org/pdf/2407.21788v1
- Levchenko (2025): https://arxiv.org/pdf/2510.06743v1
- Pipeline HTR (2022): https://www.mdpi.com/2076-3417/12/4/1870
- LLM Post-correction of HTR (Springer, 2025): https://link.springer.com/chapter/10.1007/978-981-96-4285-4_9
- GoodNotes engineering blog: https://www.goodnotes.com/blog/machine-learning-engineer-handwriting-recognition
- Handwriting OCR comparison: https://www.handwritingocr.com/blog/chatgpt-claude-and-ai-for-ocr
- ICDAR 2025 HNU Challenge: https://rrc.cvc.uab.cat/?ch=33
- OCR trends 2026: https://photes.io/blog/posts/ocr-research-trend
- Benchmark rankings: https://research.aimultiple.com/handwriting-recognition/
- Visual Sketchpad (NeurIPS 2024): https://arxiv.org/abs/2406.09403