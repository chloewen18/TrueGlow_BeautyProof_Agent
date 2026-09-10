# BeautyProof Member 5 Delivery

## Scope

Member 5 owns the runnable demo surface, dataset operations, benchmark execution view, and demo deployment path.

## Streamlit Demo

The MVP Streamlit app includes four areas:

- Consumer Trust Card: runs the three required demo cases with mock Tool outputs.
- Creator Evidence Review: accepts original material notes and shows the updated verdict.
- Dataset and Annotation: displays folder layout, required labels, split policy, and version checklist.
- Benchmark Evaluation: visualizes model, Agent, and user-test metrics for the demo report.

## Local API Routes

Run the mock-compatible backend with:

```powershell
uvicorn api.server:app --reload
```

Then set:

```powershell
$env:BEAUTYPROOF_USE_MOCK = "false"
```

The Streamlit client will call the local API instead of reading mock JSON files directly.

## Dataset Layout

Use this layout for the first deliverable:

- `data/raw/original`: authorized original camera images and videos.
- `data/raw/edited`: retouched, relit, compressed, and locally edited variants.
- `data/processed/cases`: demo-ready cases with normalized metadata.
- `data/annotations`: label sheets, split files, reviewer notes, and disagreement logs.

The starter manifest is in `data/dataset_manifest.json`; the first annotation sheet is `data/annotations/label_template.csv`.

## Benchmark View

The benchmark summary lives in `data/benchmark_summary.json`. It tracks:

- Retouching detection F1.
- Suspicious-region pixel F1.
- Before/After consistency accuracy.
- Hard-negative false-positive safety.
- Agent traceability agreement.

## Demo Script

1. Open the Streamlit app.
2. Run Case A to show "evidence insufficient" without over-judging missing metadata.
3. Run Case B to show retouching, exposure shift, and Beauty Effect Attribution.
4. Open Creator Evidence Review and submit original-material notes.
5. Show Case C updated verdict.
6. Open Benchmark Evaluation to show measurable progress and remaining risk.
