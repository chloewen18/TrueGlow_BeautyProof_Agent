from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

import torch
from PIL import Image
from torch import nn
from torchvision import models

from .modeling import (
    CHANGE_GROUPS, LEVELS, OPERATION_ZH, OPERATIONS, PARAMETERS,
    ConditionHead, MultiTaskRetouchModel, choose_device, load_rgb,
    prepare_pair, prepare_stage1, prepare_stage2_single,
)


def level(score: float, low: float, high: float) -> str:
    return "low" if score < low else "medium" if score < high else "high"


class BeautyProofTool:
    """Member-3 evidence tool. It reports signals, never deceptive intent."""

    schema_version = "1.1.0"
    engine_version = "1.1.1"

    def __init__(self, model_dir: str | Path | None = None, device: str = "auto"):
        root = Path(model_dir) if model_dir else Path(__file__).resolve().parents[1] / "models"
        package_root = root.parent
        manifest = json.loads((package_root / "MODEL_MANIFEST.json").read_text(encoding="utf-8"))
        verified_hashes = {}
        for item in manifest["models"]:
            model_path = package_root / item["file"]
            digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
            if digest != item["sha256"]:
                raise RuntimeError(f"Model integrity check failed: {item['file']}")
            verified_hashes[item["role"]] = digest
        self.model_provenance = {
            "model_manifest": "MODEL_MANIFEST.json",
            "model_integrity": "verified",
            "model_sha256": verified_hashes,
            "content_provenance": "not_checked",
            "content_provenance_owner": "image_forensics",
        }
        self.device = choose_device(device)
        stage1_ckpt = torch.load(root / "stage1_ffhqr_best_model.pth", map_location="cpu", weights_only=True)
        self.stage1 = models.resnet18(weights=None); self.stage1.fc = nn.Linear(self.stage1.fc.in_features, 2)
        self.stage1.load_state_dict(stage1_ckpt["model_state"]); self.stage1 = self.stage1.to(self.device).eval()
        self.stage1_size = int(stage1_ckpt.get("image_size", 224)); self.stage1_threshold = float(stage1_ckpt.get("decision_threshold", 0.731))

        stage2_ckpt = torch.load(root / "stage2_mixed_rehearsal_best_model.pth", map_location="cpu", weights_only=True)
        self.stage2 = MultiTaskRetouchModel(); self.stage2.load_state_dict(stage2_ckpt["model_state"]); self.stage2 = self.stage2.to(self.device).eval()
        self.stage2_size = int(stage2_ckpt.get("image_size", 224)); self.operation_thresholds = stage2_ckpt.get("thresholds", {}).get("operations", {name: 0.5 for name in OPERATIONS})

        stage3_ckpt = torch.load(root / "stage3_ppr10k_balanced_best_model.pth", map_location="cpu", weights_only=True)
        self.stage3 = ConditionHead(int(stage3_ckpt["input_size"]), len(PARAMETERS)); self.stage3.load_state_dict(stage3_ckpt["model_state"]); self.stage3 = self.stage3.to(self.device).eval()
        self.means = stage3_ckpt["target_means"]; self.stds = stage3_ckpt["target_stds"]

    def _engine(self, routes: list[str]) -> dict:
        return {
            "name": "BeautyProof Member3 Beauty Effect Attribution",
            "version": self.engine_version,
            "device": str(self.device),
            "routes": routes,
        }

    def _single_models(self, images: list[Image.Image]):
        first = torch.stack([prepare_stage1(image, self.stage1_size) for image in images]).to(self.device)
        second = torch.stack([prepare_stage2_single(image, self.stage2_size) for image in images]).to(self.device)
        with torch.inference_mode():
            generic = torch.softmax(self.stage1(first), 1)[:, 1].cpu()
            detailed = self.stage2(second)
            presence = torch.sigmoid(detailed["presence"]).cpu()
            strengths = detailed["strength"].argmax(2).cpu()
        return generic, presence, strengths

    def analyze_single(self, image_path: str | Path, request_id: str | None = None) -> dict:
        image = load_rgb(image_path); generic, presence, strengths = self._single_models([image]); score = float(generic[0])
        operations = {}
        evidence = []
        for i, name in enumerate(OPERATIONS):
            probability = float(presence[0, i]); threshold = float(self.operation_thresholds[name]); detected = probability >= threshold
            operations[name] = {"name_zh": OPERATION_ZH[name], "score": round(probability, 4), "threshold": round(threshold, 4), "detected": detected, "estimated_level": LEVELS[int(strengths[0, i])]}
            if detected: evidence.append({"type": "retouch_operation", "label": name, "score": round(probability, 4), "reliability": "auxiliary"})
        return {
            "schema_version": self.schema_version, "tool": "beauty_effect_attribution", "request_id": request_id or str(uuid.uuid4()), "status": "ok",
            "mode": "single_image",
            "engine": self._engine(["stage1_ffhqr", "stage2_retouchingffhq"]),
            "provenance": self.model_provenance,
            "result": {"comparison_reliability": "Unknown", "generic_retouch": {"score": round(score, 4), "threshold": round(self.stage1_threshold, 4), "detected": score >= self.stage1_threshold, "risk_level": level(score, self.stage1_threshold - 0.15, self.stage1_threshold + 0.10), "model_route": "stage1_ffhqr"}, "operations": operations},
            "evidence": evidence,
            "limitations": ["Operation probabilities were trained on RetouchingFFHQ and are auxiliary outside that domain.", "A detection is not proof of deceptive intent."],
        }

    def analyze_pair(self, before_path: str | Path, after_path: str | Path, mask_path: str | Path | None = None, request_id: str | None = None) -> dict:
        before, after = load_rgb(before_path), load_rgb(after_path)
        mask = None
        if mask_path:
            with Image.open(mask_path) as loaded: mask = loaded.convert("L")
        before_tensor, before_stats = prepare_pair(before, mask, self.stage2_size)
        after_tensor, after_stats = prepare_pair(after, mask, self.stage2_size)
        pair_images = torch.stack([before_tensor, after_tensor]).to(self.device)
        with torch.inference_mode():
            features = self.stage2.backbone(pair_images).cpu(); first, second = features
            combined = torch.cat([first, second, second - first, torch.abs(second - first), before_stats, after_stats, after_stats - before_stats]).unsqueeze(0).to(self.device)
            regression, logits = self.stage3(combined)
            deltas = regression.cpu()[0] * self.stds + self.means; probabilities = torch.sigmoid(logits.cpu()[0])
        delta = {name: round(float(value), 3) for name, value in zip(PARAMETERS, deltas)}
        changes = {name: {"score": round(float(value), 4), "use_as": "auxiliary_signal_only"} for name, value in zip(CHANGE_GROUPS, probabilities)}
        cues = []
        if abs(delta["exposure"]) >= 0.25: cues.append("曝光差异")
        if abs(delta["temperature"]) >= 400 or abs(delta["tint"]) >= 5: cues.append("白平衡差异")
        if max(abs(delta[name]) for name in ["contrast", "highlights", "shadows", "whites", "blacks", "saturation", "vibrance"]) >= 15: cues.append("色调差异")
        reliability = "Low" if len(cues) >= 2 else "Medium" if cues else "High"
        return {
            "schema_version": self.schema_version, "tool": "beauty_effect_attribution", "request_id": request_id or str(uuid.uuid4()), "status": "ok",
            "mode": "before_after_pair",
            "engine": self._engine(["stage2_pair_backbone", "stage3_ppr10k_condition"]),
            "provenance": self.model_provenance,
            "result": {"parameter_deltas": delta, "change_probabilities": changes, "comparison_reliability": reliability, "reliability_rule_cues": cues, "mask_used": mask_path is not None},
            "consumer_explanation": "Before/After 存在多项拍摄或调色条件差异，观察到的妆效不宜全部归因于产品。" if reliability == "Low" else "未发现多项强条件差异，但仍需结合原文、光线与原始素材复核。",
            "evidence": [{"type": "condition_delta", "label": cue, "reliability": "model_estimate"} for cue in cues],
            "limitations": ["PPR10K predicts editing/photographic parameter differences, not product causality or deceptive intent.", "Change probabilities are not calibrated for real-world negative pairs; use continuous deltas and rules first.", "Without a foreground mask, foreground/background statistics are less reliable."],
        }
