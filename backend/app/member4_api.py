from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from .config import settings
from .integrations.member4.service import analyze, evidence_db, workbook_rows

router = APIRouter(prefix="/api/v1/member4", tags=["member4"])

class AnalyzeInput(BaseModel):
    text: str = Field(min_length=1, max_length=30000)
    product: str = ""
    comments: list[str] = Field(default_factory=list)

class OCRInput(BaseModel):
    media_ref: str
    subtitle_crop: bool = False

@router.post("/analyze")
def analyze_text(payload: AnalyzeInput):
    return analyze(payload.text, payload.product, payload.comments)

@router.get("/resources")
def resources():
    return {"evidence": evidence_db(), "explanations": workbook_rows("解释模版库.xlsx"),
            "comment_rules": workbook_rows("评论区分析.xlsx")}

@router.post("/ocr")
def ocr(payload: OCRInput):
    root = (settings.resolved_data_dir / "uploads").resolve()
    target = (settings.resolved_data_dir / payload.media_ref).resolve()
    if root not in target.parents or not target.is_file():
        raise HTTPException(422, "Invalid uploaded media reference")
    try:
        from .integrations.member4.full_pipeline import run_ocr
        text, lines = run_ocr(target, payload.subtitle_crop)
    except (ImportError, ModuleNotFoundError) as exc:
        raise HTTPException(503, "OCR dependencies unavailable; install requirements-ocr.txt") from exc
    except Exception as exc:
        raise HTTPException(503, f"OCR initialization or inference failed: {exc}") from exc
    return {"text": text, "lines": lines, "mode": "paddleocr"}
