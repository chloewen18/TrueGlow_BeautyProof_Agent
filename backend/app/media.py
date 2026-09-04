"""素材上传与回流（已冻结的前端对接方案）。

对接约定（见 docs/API_SPEC.md §6.4）：
  方式一（推荐，冻结主路径）：
    1) POST /api/v1/upload 上传图片/视频（multipart/form-data）
    2) 拿回 media_ref / media_url
    3) 把 media_ref 填进 /verify 的 content.media[].ref（或 /creators/review 中补证文件的 ref）
  方式二（Demo 便利）：
    直接 multipart/form-data 调 POST /api/v1/verify，表单字段 payload(JSON) + files，
    后端自动保存文件并把 media_ref 注入 content.media。

上传后可用 GET /api/v1/uploads/{path} 回流原始文件用于前端预览。
"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .config import settings

router = APIRouter(prefix="/api/v1", tags=["media"])


class UploadedMedia(BaseModel):
    """单条上传素材的回流信息。"""

    media_ref: str = Field(..., description="回填到 /verify 的引用，如 uploads/up_xxx_0.jpg")
    media_url: str = Field(..., description="可直接用于 <img>/<video> 预览的回流地址")
    kind: str = Field(..., description="image | video")
    filename: str = Field(..., description="原始文件名")
    size_bytes: int = Field(..., description="字节数")


def _uploads_dir() -> Path:
    d = settings.resolved_data_dir / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_upload(upload: UploadFile, batch_id: str) -> UploadedMedia:
    """保存单个上传文件，返回可被 /verify 引用的 media_ref。"""
    data = upload.file.read()
    content_type = upload.content_type or ""
    kind = "video" if content_type.startswith("video") else "image"
    suffix = Path(upload.filename or "blob").suffix or (".mp4" if kind == "video" else ".jpg")
    # 同批次顺序编号，避免文件名冲突
    existing = [p.name for p in _uploads_dir().glob(f"{batch_id}_*")]
    safe_name = f"{batch_id}_{len(existing)}{suffix}"
    path = _uploads_dir() / safe_name
    path.write_bytes(data)
    return UploadedMedia(
        media_ref=f"uploads/{safe_name}",
        media_url=f"/api/v1/uploads/{safe_name}",
        kind=kind,
        filename=upload.filename or safe_name,
        size_bytes=len(data),
    )


@router.post("/upload", summary="上传素材（图片/视频），返回 media_ref")
def upload(files: list[UploadFile] = File(...)) -> dict:
    """接收一个或多个文件，返回批量 id 与每条素材的 media_ref。

    示例返回：
    {
      "batch_id": "up_abc1234567",
      "uploaded": [
        {"media_ref": "uploads/up_abc1234567_0.jpg", "media_url": "/api/v1/uploads/up_abc1234567_0.jpg",
         "kind": "image", "filename": "before.jpg", "size_bytes": 12345}
      ]
    }
    """
    if not files:
        raise HTTPException(status_code=400, detail="未收到任何文件")
    batch_id = f"up_{uuid.uuid4().hex[:10]}"
    uploaded = [save_upload(f, batch_id).model_dump() for f in files]
    return {"batch_id": batch_id, "uploaded": uploaded}


@router.get("/uploads/{path:path}", summary="回流已上传素材（预览用）")
def serve(path: str):
    """按 media_ref 回流原始文件（路径穿越防护）。"""
    root = _uploads_dir().resolve()
    target = (root / path).resolve()
    if target != root and root not in target.parents:
        raise HTTPException(status_code=403, detail="非法的文件路径")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="未找到素材")
    return FileResponse(target)


def inject_uploads_into_payload(payload: dict, uploaded: list[UploadedMedia]) -> dict:
    """把上传素材注入 /verify 的 content.media（Demo 便利路径用）。"""
    if not uploaded:
        return payload
    content = payload.setdefault("content", {})
    media = content.get("media") or []
    for m in uploaded:
        media.append({"kind": m.kind, "ref": m.media_ref, "note": m.filename})
    content["media"] = media
    return payload


async def parse_multipart_verify(request: Request) -> tuple[dict, list[UploadedMedia]]:
    """解析 multipart/form-data 的 /verify 请求（payload 表单字段 + files）。"""
    import json

    form = await request.form()
    payload = json.loads(form.get("payload") or "{}")
    batch_id = f"up_{uuid.uuid4().hex[:10]}"
    uploaded: list[UploadedMedia] = []
    for f in form.getlist("files"):
        if isinstance(f, UploadFile):
            uploaded.append(save_upload(f, batch_id))
    return inject_uploads_into_payload(payload, uploaded), uploaded
