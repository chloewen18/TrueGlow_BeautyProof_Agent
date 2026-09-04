"""证据层持久化：每次核验的证据与报告落盘为 JSON，供数据集回流与审计。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import settings
from ..schemas.evidence import EvidenceLayer


class EvidenceStore:
    def __init__(self, evidence_dir: Path | None = None) -> None:
        self.dir = evidence_dir or settings.evidence_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, request_id: str) -> Path:
        safe = request_id.replace("/", "_").replace("\\", "_")
        return self.dir / f"{safe}.json"

    def save_evidence(self, request_id: str, layer: EvidenceLayer | dict[str, Any]) -> Path:
        data = layer if isinstance(layer, dict) else layer.model_dump(exclude_none=False)
        path = self._path(request_id)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load_evidence(self, request_id: str) -> dict[str, Any] | None:
        path = self._path(request_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))


evidence_store = EvidenceStore()
