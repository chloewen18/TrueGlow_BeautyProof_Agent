import argparse
import json
import tempfile
import shutil
from pathlib import Path

from .claim_extractor import (
    ClaimExtractor,
    MockSemanticLayer,
    merge_rule_and_mock,
    resolve_claim_conflicts,
)


def add_bridge_rules(text, claims, consumer_meaning):
    present = {c["canonical_claim"] for c in claims}

    if any(p in text for p in ["没有干卡", "没干卡", "不干卡"]):
        if "不卡粉" not in present:
            phrase = next(p for p in ["没有干卡", "没干卡", "不干卡"] if p in text)
            claims.append({
                "canonical_claim": "不卡粉",
                "matched_text": phrase,
                "polarity": "positive",
                "strength": "medium",
                "duration": None,
                "is_slang": True,
                "is_exaggerated": False,
                "consumer_meaning": consumer_meaning.get(
                    "不卡粉",
                    "底妆不容易出现明显卡粉、结块或干燥感。"
                )
            })
    return claims


def run_ocr(image_path, subtitle_crop=False):
    import cv2
    import numpy as np
    from .ocr_paddle_v2_1 import make_variants, run_one, clean
    from paddleocr import PaddleOCR
    image = cv2.imdecode(np.fromfile(str(image_path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Cannot read image: {image_path}")

    variants, _ = make_variants(image) if subtitle_crop else ({"original": image}, None)

    model_root = Path(__file__).resolve().parents[4] / "data/models"
    local_models = {}
    for kind, name in [("detection", "PP-OCRv5_mobile_det"), ("recognition", "PP-OCRv5_mobile_rec")]:
        if (model_root / name / "inference.yml").is_file():
            # Paddle's Windows native loader cannot reliably open Unicode model paths.
            runtime_dir = Path(tempfile.gettempdir()) / "trueglow_ocr_models" / name
            shutil.copytree(model_root / name, runtime_dir, dirs_exist_ok=True)
            local_models[f"text_{kind}_model_dir"] = str(runtime_dir)
    ocr = PaddleOCR(
        **local_models,
        enable_mkldnn=False,
        device="cpu",
        text_detection_model_name="PP-OCRv5_mobile_det",
        text_recognition_model_name="PP-OCRv5_mobile_rec",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False
    )

    with tempfile.TemporaryDirectory() as td:
        lines = []
        for name in variants:
            lines.extend(run_one(ocr, variants[name], name, td))

    cleaned = clean(lines)
    return "\n".join(x["text"] for x in cleaned), cleaned


def run_claim(text, dictionary_path):
    extractor = ClaimExtractor(str(dictionary_path))
    mock_layer = MockSemanticLayer(extractor.consumer_meaning)

    base = extractor.extract_claims(text)
    rule_claims = base["output"]["claims"]

    mock_claims = mock_layer.analyze(text, rule_claims)
    merged = merge_rule_and_mock(rule_claims, mock_claims)
    cleaned = resolve_claim_conflicts(text, merged)
    cleaned = add_bridge_rules(text, cleaned, extractor.consumer_meaning)

    return cleaned


def load_evidence(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def evidence_matches_for_claim(evidence_db, claim_name, product=None):
    matches = []

    for product_item in evidence_db.get("products", []):
        product_name = product_item.get("product_name", "")

        if not product or product.strip().casefold() != product_name.strip().casefold():
            continue

        for item in product_item.get("claims", []):
            if item.get("canonical_claim") == claim_name and item.get("supports_claim") is True:
                matches.append({
                    "product_name": product_name,
                    **item
                })

    return matches


def explain_claim(claim, evidence_matches):
    claim_name = claim["canonical_claim"]

    if evidence_matches:
        strongest = sorted(
            evidence_matches,
            key=lambda x: {
                "High": 4,
                "Medium-High": 3,
                "Medium": 2,
                "Low": 1
            }.get(x.get("evidence_strength", ""), 0),
            reverse=True
        )[0]

        strength = strongest.get("evidence_strength", "Unknown")
        detail = strongest.get("evidence_detail", "")

        return {
            "status": "evidence_found",
            "evidence_strength": strength,
            "consumer_explanation": (
                f"这条内容提到「{claim_name}」。目前在证据库里找到了相关资料，"
                f"证据强度为 {strength}。{detail}"
                f" 这说明这个说法有一定依据，但仍不代表每个人都会得到完全一样的效果。"
            )
        }

    return {
        "status": "no_matching_evidence",
        "evidence_strength": "None",
        "consumer_explanation": (
            f"这条内容提到「{claim_name}」，但目前这个 Demo 证据库里还没有找到"
            f"与它直接对应的证据。更适合先把它当作个人使用体验或内容中的功效表达，"
            f"不要直接理解成已经被验证的产品结论。"
        )
    }


def main():
    parser = argparse.ArgumentParser(
        description="Member 4 Full Demo Pipeline v1"
    )
    parser.add_argument("--image", required=True)
    parser.add_argument(
        "--dictionary",
        default=str(Path(__file__).resolve().parents[4] / "data/deliverables/member4/Claim Dictionary V2.2.xlsx")
    )
    parser.add_argument(
        "--evidence",
        default=str(Path(__file__).resolve().parents[4] / "data/deliverables/member4/Mini功效证据JSON.json")
    )
    parser.add_argument(
        "--product",
        default=None,
        help="Optional product name filter. If omitted, search all demo products."
    )
    parser.add_argument(
        "--out",
        default="Member4_Full_Result_v1.json"
    )

    args = parser.parse_args()

    script_dir = Path(__file__).parent

    image_path = Path(args.image)
    dictionary_path = Path(args.dictionary)
    evidence_path = Path(args.evidence)

    if not dictionary_path.exists():
        dictionary_path = script_dir / args.dictionary
    if not evidence_path.exists():
        evidence_path = script_dir / args.evidence

    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    if not dictionary_path.exists():
        raise FileNotFoundError(f"Dictionary not found: {dictionary_path}")
    if not evidence_path.exists():
        raise FileNotFoundError(f"Evidence library not found: {evidence_path}")

    ocr_text, ocr_lines = run_ocr(image_path)
    claims = run_claim(ocr_text, dictionary_path)
    evidence_db = load_evidence(evidence_path)

    final_claims = []

    for claim in claims:
        matches = evidence_matches_for_claim(
            evidence_db,
            claim["canonical_claim"],
            args.product
        )
        if claim.get("polarity") != "positive":
            matches = []

        explanation = explain_claim(claim, matches)

        final_claims.append({
            **claim,
            "evidence_matches": matches,
            "audience_explanation": explanation
        })

    result = {
        "pipeline_name": "member4_full_demo",
        "version": "v1",
        "input": {
            "image_path": str(image_path),
            "product_filter": args.product
        },
        "ocr": {
            "extracted_text": ocr_text,
            "lines": ocr_lines
        },
        "claims": final_claims
    }

    Path(args.out).write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(json.dumps({
        "status": "success",
        "ocr_text": ocr_text,
        "claim_count": len(final_claims),
        "claims": [c["canonical_claim"] for c in final_claims],
        "evidence_found_for": [
            c["canonical_claim"]
            for c in final_claims
            if c["audience_explanation"]["status"] == "evidence_found"
        ],
        "output_file": args.out
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
