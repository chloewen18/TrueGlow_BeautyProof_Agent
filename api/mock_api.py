import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MOCK_DIR = PROJECT_ROOT / "data" / "mock"

CASE_FILES = {
    "case_a": "case_a_response.json",
    "case_b": "case_b_response.json",
    "case_c_review": "case_c_review_response.json",
}


def _load_json(filename):
    path = MOCK_DIR / filename
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def get_mock_response(case_id="case_b"):
    filename = CASE_FILES.get(case_id, CASE_FILES["case_b"])
    return _load_json(filename)


def get_mock_review_response():
    return _load_json(CASE_FILES["case_c_review"])
