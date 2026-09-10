import json
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile

from api.mock_api import get_mock_response, get_mock_review_response

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"


app = FastAPI(
    title="BeautyProof Demo API",
    version="0.1.0",
    description="Mock-compatible routes for the BeautyProof hackathon demo.",
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "beautyproof-demo-api"}


def _load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


@app.post("/verify")
async def verify_content(
    image: UploadFile = File(...),
    text: str = Form(...),
    product_name: str = Form(""),
    user_need: str = Form(""),
    case_id: str = Form("case_b"),
):
    response = get_mock_response(case_id)
    response["input_summary"] = {
        "image_filename": image.filename,
        "text_chars": len(text),
        "product_name": product_name,
        "user_need": user_need,
    }
    return response


@app.post("/creator/evidence")
async def submit_creator_evidence(
    content_id: str = Form(...),
    original_request_id: str = Form(...),
    original_file: UploadFile = File(...),
    filter_info: str = Form(""),
):
    response = get_mock_review_response()
    response["creator_submission"] = {
        "content_id": content_id,
        "original_request_id": original_request_id,
        "original_filename": original_file.filename,
        "filter_info": filter_info,
    }
    return response


@app.get("/dataset/manifest")
def dataset_manifest():
    return _load_json(DATA_DIR / "dataset_manifest.json")


@app.get("/benchmark/summary")
def benchmark_summary():
    return _load_json(DATA_DIR / "benchmark_summary.json")
