"""Read-only access to imported team artifacts."""
import csv
from pathlib import Path

from fastapi import APIRouter

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "data/datasets/FFHQ_FFHQR_100_pairs_v1"
TRUFOR = ROOT / "data/deliverables/TruFor_交付物"
router = APIRouter(prefix="/api/v1/deliverables", tags=["deliverables"])


@router.get("/dataset")
def dataset_records():
    with (DATASET / "paired_manifest.csv").open(encoding="utf-8-sig", newline="") as file:
        pairs = list(csv.DictReader(file))
    return {"pairs": pairs, "pair_count": len(pairs), "label_scope": "generic_professional_retouch"}


@router.get("/trufor")
def trufor_results(threshold: float = 0.65):
    if not 0 <= threshold <= 1:
        from fastapi import HTTPException
        raise HTTPException(422, "Threshold must be between 0 and 1")
    rows = []
    for file in sorted(TRUFOR.glob("*_integrity_score.txt")):
        sample = file.name.removesuffix("_integrity_score.txt")
        score = float(file.read_text().strip())
        rows.append({"sample": sample, "suspicion_score": score,
                     "label": int(sample.startswith("tampered")), "predicted": int(score >= threshold)})
    negatives = [r for r in rows if r["label"] == 0]
    positives = [r for r in rows if r["label"] == 1]
    return {"mode": "simulated_artifact", "threshold": threshold, "samples": rows,
            "false_positive_rate": sum(r["predicted"] for r in negatives) / len(negatives) if negatives else None,
            "true_positive_rate": sum(r["predicted"] for r in positives) / len(positives) if positives else None}
