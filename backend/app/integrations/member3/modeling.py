from __future__ import annotations

from pathlib import Path

import torch
from PIL import Image
from torch import nn
from torchvision import models
from torchvision.transforms import InterpolationMode
from torchvision.transforms import functional as TF

OPERATIONS = ["whitening", "smoothing", "facelifting", "eyeenlarging"]
OPERATION_ZH = {"whitening": "美白/提亮", "smoothing": "磨皮/纹理平滑", "facelifting": "瘦脸/脸型变形", "eyeenlarging": "放大眼睛"}
LEVELS = [0, 30, 60, 90]
PARAMETERS = ["exposure", "temperature", "tint", "contrast", "highlights", "shadows", "whites", "blacks", "clarity", "saturation", "vibrance", "texture"]
CHANGE_GROUPS = ["exposure_changed", "white_balance_changed", "tone_changed"]


class MultiTaskRetouchModel(nn.Module):
    def __init__(self):
        super().__init__()
        network = models.resnet18(weights=None)
        feature_size = network.fc.in_features
        network.fc = nn.Identity()
        self.backbone = network
        self.binary_head = nn.Linear(feature_size, 2)
        self.operation_head = nn.Linear(feature_size, 4)
        self.strength_heads = nn.ModuleList([nn.Linear(feature_size, 4) for _ in OPERATIONS])

    def forward(self, images):
        features = self.backbone(images)
        return {
            "features": features,
            "binary": self.binary_head(features),
            "presence": self.operation_head(features),
            "strength": torch.stack([head(features) for head in self.strength_heads], dim=1),
        }


class ConditionHead(nn.Module):
    def __init__(self, input_size: int, parameter_count: int):
        super().__init__()
        self.shared = nn.Sequential(nn.Linear(input_size, 512), nn.ReLU(), nn.Dropout(0.2), nn.Linear(512, 256), nn.ReLU(), nn.Dropout(0.1))
        self.regression = nn.Linear(256, parameter_count)
        self.change = nn.Linear(256, len(CHANGE_GROUPS))

    def forward(self, x):
        hidden = self.shared(x)
        return self.regression(hidden), self.change(hidden)


def choose_device(name: str = "auto") -> torch.device:
    if name != "auto": return torch.device(name)
    if torch.cuda.is_available(): return torch.device("cuda")
    if torch.backends.mps.is_available(): return torch.device("mps")
    return torch.device("cpu")


def load_rgb(path: str | Path) -> Image.Image:
    with Image.open(path) as image: return image.convert("RGB")


def normalize(raw: torch.Tensor) -> torch.Tensor:
    return TF.normalize(raw, [0.485, 0.456, 0.406], [0.229, 0.224, 0.225])


def prepare_stage1(image: Image.Image, image_size: int) -> torch.Tensor:
    image = TF.resize(image, image_size + 32, antialias=True)
    image = TF.center_crop(image, [image_size, image_size])
    return normalize(TF.to_tensor(image))


def prepare_stage2_single(image: Image.Image, image_size: int) -> torch.Tensor:
    image = TF.resize(image, [image_size + 32, image_size + 32], antialias=True)
    image = TF.center_crop(image, [image_size, image_size])
    return normalize(TF.to_tensor(image))


def prepare_pair(image: Image.Image, mask: Image.Image | None, image_size: int):
    image = TF.resize(image, image_size + 32, antialias=True)
    image = TF.center_crop(image, [image_size, image_size])
    raw = TF.to_tensor(image)
    if mask is None:
        mask_tensor = torch.ones((image_size, image_size), dtype=torch.bool)
    else:
        mask = TF.resize(mask.convert("L"), image_size + 32, interpolation=InterpolationMode.NEAREST)
        mask_tensor = TF.to_tensor(TF.center_crop(mask, [image_size, image_size]))[0] >= 0.5
    luma = 0.2126 * raw[0] + 0.7152 * raw[1] + 0.0722 * raw[2]
    grad = torch.zeros_like(luma)
    grad[:, :-1] += torch.abs(luma[:, 1:] - luma[:, :-1])
    grad[:-1, :] += torch.abs(luma[1:, :] - luma[:-1, :])
    stats = []
    for region in (mask_tensor, ~mask_tensor):
        if region.sum() < 16: region = torch.ones_like(region)
        stats.extend(raw[channel][region].mean() for channel in range(3))
        stats.extend([luma[region].std(), grad[region].mean()])
    return normalize(raw), torch.stack(stats)
