"""Local real-inference adapters; failures never fall back to mock results."""
from functools import lru_cache
import hashlib
import os
from pathlib import Path
import sys
import threading
import uuid

import numpy as np
from PIL import Image, ImageOps

from ..config import settings

ROOT = Path(__file__).resolve().parents[3]
INFERENCE_LOCK = threading.RLock()


def uploaded_path(ref):
    value = ref.get("ref", "") if isinstance(ref, dict) else str(ref or "")
    root = (settings.resolved_data_dir / "uploads").resolve()
    target = (settings.resolved_data_dir / value).resolve()
    if not value.startswith("uploads/") or root not in target.parents or not target.is_file():
        raise ValueError("Expected an existing uploads/ media reference")
    return target


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def artifact_dir():
    path = settings.resolved_data_dir / "artifacts" / uuid.uuid4().hex
    path.mkdir(parents=True)
    return path


def artifact_ref(path):
    relative = path.relative_to(settings.resolved_data_dir / "artifacts").as_posix()
    return {"kind": "path", "value": f"/api/v1/artifacts/{relative}"}


def heat_image(array, path):
    values = np.asarray(array, dtype=np.float32).squeeze()
    if values.ndim != 2 or not np.isfinite(values).all():
        raise ValueError("Invalid localization/confidence map")
    # Fixed 0..1 scale: never normalize a weak anomaly into a red hot spot.
    values = np.clip(values, 0, 1)
    rgb = np.stack([values, values * .25, values * .08], axis=-1)
    Image.fromarray((rgb * 255).astype(np.uint8)).save(path)
    return artifact_ref(path)


@lru_cache(maxsize=1)
def member3_engine():
    import torch
    from .member3.tool import BeautyProofTool
    torch.set_num_threads(int(os.getenv("TRUEGLOW_CPU_THREADS", "4")))
    return BeautyProofTool(ROOT / "data/models/member3", device="cpu")


@lru_cache(maxsize=1)
def trufor_engine():
    import torch
    vendor = ROOT / "vendor/trufor"
    sys.path.insert(0, str(vendor))
    from lib.config import config
    from lib.models.cmx.builder_np_conf import EncoderDecoder
    cfg = config.clone()
    cfg.defrost()
    cfg.merge_from_file(str(vendor / "lib/config/trufor_ph3.yaml"))
    cfg.MODEL.PRETRAINED = ""
    cfg.freeze()
    weights = ROOT / "data/models/trufor.pth.tar"
    torch.set_num_threads(int(os.getenv("TRUEGLOW_CPU_THREADS", "4")))
    with torch.serialization.safe_globals([
        (np._core.multiarray.scalar, "numpy.core.multiarray.scalar"),
        np.dtype, np.dtypes.Float64DType, np.dtypes.Float32DType,
    ]):
        checkpoint = torch.load(weights, map_location="cpu", weights_only=True)
    model = EncoderDecoder(cfg=cfg)
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    return model.eval(), sha256(weights)


def trufor(path):
    import torch
    with INFERENCE_LOCK:
        model, digest = trufor_engine()
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
        original_size = image.size
        max_size = int(os.getenv("TRUFOR_MAX_SIDE", "1024"))
        image.thumbnail((max_size, max_size))
        if min(image.size) < 32:
            raise ValueError("TruFor requires an image at least 32 pixels per side")
        tensor = torch.from_numpy(np.asarray(image).copy()).permute(2, 0, 1).float()[None] / 255
        with torch.inference_mode():
            pred, confidence, detection, _ = model(tensor)
            anomaly = torch.softmax(pred[0], dim=0)[1].cpu().numpy()
            conf = torch.sigmoid(confidence[0])[0].cpu().numpy()
            score = float(torch.sigmoid(detection).item())
    if not np.isfinite(score) or not 0 <= score <= 1:
        raise ValueError("TruFor returned an invalid score")
    directory = artifact_dir()
    np.savez_compressed(directory / "trufor.npz", map=anomaly, conf=conf, score=score, imgsize=anomaly.shape)
    return {"mode": "real", "status": "success", "engine": "TruFor/ae54475", "weight_sha256": digest,
            "input_sha256": sha256(path), "trufor_score": score, "integrity_score": 1 - score,
            "score_direction": "trufor_score=higher_suspicion; integrity_score=1-trufor_score",
            "original_size": original_size, "inference_size": image.size,
            "manipulation_map": heat_image(anomaly, directory / "anomaly.png"),
            "reliability_map": heat_image(conf, directory / "confidence.png"),
            "raw_output": artifact_ref(directory / "trufor.npz"),
            "limitations": ["分数未经美妆场景概率校准；低分不证明未经修饰。",
                            "热力图为异常定位，不区分拼接、生成或具体美颜操作。"] +
                           (["输入按最长边缩小，可能损失取证细节。"] if original_size != image.size else [])}


def single(path, request_id):
    with INFERENCE_LOCK:
        result = member3_engine().analyze_single(path, request_id=request_id)
    result["input_sha256"] = sha256(path)
    return result


def pair(before, after, request_id, mask=None):
    with INFERENCE_LOCK:
        result = member3_engine().analyze_pair(before, after, mask_path=mask, request_id=request_id)
    result["input_sha256"] = {"before": sha256(before), "after": sha256(after)}
    return result


def pair_difference(before, after):
    """Conservative geometric check; render only sufficiently aligned pairs."""
    import cv2
    def read(path):
        with Image.open(path) as source:
            im = ImageOps.exif_transpose(source).convert("RGB")
            im.thumbnail((768, 768))
            return np.asarray(im).copy()
    a, b = read(before), read(after)
    if a.shape != b.shape:
        return {"status": "unavailable", "reason": "图片尺寸或裁切比例不一致，未生成差异定位图。"}
    gray_a, gray_b = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY), cv2.cvtColor(b, cv2.COLOR_RGB2GRAY)
    if np.array_equal(a, b):
        aligned, quality = b, 1.0
    else:
        orb = cv2.ORB_create(2000)
        ka, da = orb.detectAndCompute(gray_a, None)
        kb, db = orb.detectAndCompute(gray_b, None)
        if da is None or db is None:
            return {"status": "unavailable", "reason": "缺少足够稳定的对应点。"}
        matches = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(db, da, k=2)
        good = [m[0] for m in matches if len(m) == 2 and m[0].distance < .7 * m[1].distance]
        if len(good) < 20:
            return {"status": "unavailable", "reason": "对应点不足，前后图不可可靠对齐。"}
        src = np.float32([kb[m.queryIdx].pt for m in good])
        dst = np.float32([ka[m.trainIdx].pt for m in good])
        matrix, inliers = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC)
        quality = float(inliers.mean()) if inliers is not None else 0
        if matrix is None or quality < .65:
            return {"status": "unavailable", "reason": "几何对齐不可靠；不能把错位当成修饰区域。"}
        scale = float(np.linalg.norm(matrix[0, :2]))
        if not .85 < scale < 1.18 or abs(matrix[0, 1]) > .15 or np.linalg.norm(matrix[:, 2]) > min(a.shape[:2]) * .15:
            return {"status": "unavailable", "reason": "拍摄角度、缩放或位移差异过大。"}
        aligned = cv2.warpAffine(b, matrix, (a.shape[1], a.shape[0]), borderMode=cv2.BORDER_REFLECT)
    difference = np.abs(a.astype(np.float32) - aligned.astype(np.float32)).mean(2) / 255
    directory = artifact_dir()
    return {"status": "success", "method": "ORB_RANSAC_affine_then_RGB_absolute_difference",
            "alignment_inlier_ratio": quality, "mean_absolute_difference": float(difference.mean()),
            "map": heat_image(difference, directory / "difference.png"),
            "limitations": ["差异图表示对齐后的像素变化，不是磨皮、美白定位真值，也不是产品因果证据。",
                            "非刚性表情、光照和压缩也会造成差异；边缘可能有配准误差。"]}
