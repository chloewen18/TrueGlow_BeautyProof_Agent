"""Opt-in private evaluation collection, separate from public upload routes."""
from datetime import datetime, timedelta, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import secrets
import shutil
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image, ImageOps
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2] / "data/volunteers"
router = APIRouter(prefix="/api/v1/volunteers", tags=["volunteers"])
CONSENT_VERSION = "2026-09-17-v1"


def clean_expired():
    ROOT.mkdir(parents=True, exist_ok=True)
    for record in ROOT.glob("*/record.json"):
        data = json.loads(record.read_text(encoding="utf-8"))
        if datetime.fromisoformat(data["expires_at"]) < datetime.now(timezone.utc):
            remove_record(record.parent)


def remove_record(directory):
    if directory.resolve().parent != ROOT.resolve():
        raise ValueError("Invalid collection directory")
    shutil.rmtree(directory)


@router.get("/status")
def status():
    clean_expired()
    records = list(ROOT.glob("*/record.json"))
    return {"consented_pairs": len(records), "consent_version": CONSENT_VERSION,
            "storage": "local_private", "public_sharing": False, "training_use": False}


def decode(upload):
    raw = upload.file.read(12 * 1024 * 1024 + 1)
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(413, "单张图片不得超过12MB")
    try:
        with Image.open(BytesIO(raw)) as source:
            if source.width * source.height > 16_000_000:
                raise ValueError("Image exceeds 16 megapixels")
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.load()
            # Keep pixels, remove identifying EXIF/GPS and original filenames.
            image.info.clear()
            return image
    except Exception as exc:
        raise HTTPException(422, "请提供有效且不超过1600万像素的图片") from exc


@router.post("/submit")
def submit(before: UploadFile = File(...), after: UploadFile = File(...),
           consent: bool = Form(False), adult_self: bool = Form(False),
           condition: str = Form(...), edits: str = Form(...)):
    if not consent or not adult_self:
        raise HTTPException(422, "仅接收本人、已成年且明确同意用于内部评测的素材")
    if condition not in ("same_conditions", "lighting_changed", "makeup_changed", "compression_only", "other"):
        raise HTTPException(422, "Unknown condition")
    if len(edits) > 1000:
        raise HTTPException(422, "操作说明过长")
    clean_expired()
    first, second = decode(before), decode(after)
    sample_id, token = uuid.uuid4().hex, secrets.token_urlsafe(32)
    directory = ROOT / sample_id
    directory.mkdir()
    try:
        first.save(directory / "before.png")
        second.save(directory / "after.png")
        now = datetime.now(timezone.utc)
        data = {"sample_id": sample_id, "consent_version": CONSENT_VERSION,
                "consent": True, "adult_self": True, "use": "internal_evaluation_only",
                "created_at": now.isoformat(), "expires_at": (now+timedelta(days=30)).isoformat(),
                "condition_self_report": condition, "edits_self_report": edits,
                "label_status": "pending_two_person_review", "split": "unassigned_subject_group",
                "withdrawal_token_hash": hashlib.sha256(token.encode()).hexdigest()}
        (directory / "record.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        remove_record(directory)
        raise
    return {"sample_id": sample_id, "withdrawal_token": token, "expires_at": data["expires_at"]}


class Withdrawal(BaseModel):
    sample_id: str
    token: str


@router.post("/withdraw")
def withdraw(payload: Withdrawal):
    if not re.fullmatch(r"[a-f0-9]{32}", payload.sample_id):
        raise HTTPException(404, "Record not found")
    directory = ROOT / payload.sample_id
    path = directory / "record.json"
    if not path.is_file():
        raise HTTPException(404, "Record not found")
    record = json.loads(path.read_text(encoding="utf-8"))
    if not secrets.compare_digest(record["withdrawal_token_hash"], hashlib.sha256(payload.token.encode()).hexdigest()):
        raise HTTPException(403, "撤回码不匹配")
    remove_record(directory)
    return {"status": "withdrawn", "sample_id": payload.sample_id}
