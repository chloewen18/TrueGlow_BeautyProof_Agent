# Member 4 Integration

All 11 original deliveries are preserved under `data/deliverables/member4/`.
Active code lives under `backend/app/integrations/member4/` with normalized
imports and project-relative asset paths. Originals are not modified.

The Main Agent's `text_integrity` tool now uses the delivered dictionary,
deterministic semantic rules and local product evidence. Explicit mock
signals still support legacy fixtures. The structured analysis is retained
under `member4_analysis` in the report's raw text evidence.

The "文案与功效证据" frontend tab supports editable text, optional OCR,
exact product selection, claim extraction, brand evidence references,
repeated-comment signals, explanation templates and evaluated test cases.
Comment rules and explanation templates remain visible as human reference
tables; the implemented comment detector only counts exact repetitions.

API routes: `/api/v1/member4/analyze`, `/resources`, `/ocr`.
OCR accepts an uploaded media reference from `/api/v1/upload`.
Default OCR uses the full image; subtitle mode retains the delivered crop
(58%-78% height, 3%-97% width). Chinese input paths are supported.
The integrated pipeline uses PP-OCRv5 mobile detection/recognition on CPU,
with MKL-DNN disabled for compatibility with this Windows runtime.
Downloaded model copies are stored in `data/models/` (ignored by Git).
An actual generated Chinese-text image passed recognition verification.

Core install: `python -m pip install -r requirements.txt`.
OCR install: `python -m pip install -r requirements-ocr.txt`.
PaddleOCR needs model files at first initialization. Missing dependencies
or unavailable models produce an explicit service error, not simulated text.

Evaluation: `python -m backend.app.integrations.member4.evaluate`.
Results go to `data/member4_evaluation.json`; source workbooks stay unchanged.
Predictions are produced before comparing with answer keys, which are never
loaded by the extraction service. This is a rerun of supplied tests, not an
independent unseen benchmark. Metrics cover canonical claim sets only.
Current rerun: Test Set 20/20 exact, micro F1=1.0; Blind Test 20/30 exact,
micro F1=0.90625. Seven integration/regression tests passed.

Product evidence requires an exact product name and canonical claim match.
No product means no supporting match. Positive brand evidence does not
validate negative or mixed experiences. Evidence is the delivered local
snapshot, not freshly verified web research or independent scientific proof.
The dictionary/semantic layer remains rule-based and may miss paraphrases.

Checks: `python -m unittest discover -s tests`.
