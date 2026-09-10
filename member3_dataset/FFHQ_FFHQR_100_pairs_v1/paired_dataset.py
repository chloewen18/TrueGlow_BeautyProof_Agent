"""Minimal PyTorch loader for the FFHQ–FFHQR paired prototype dataset."""

from __future__ import annotations

import csv
from pathlib import Path

from PIL import Image
from torch.utils.data import Dataset


class FFHQFFHQRPairedDataset(Dataset):
    def __init__(self, root, split="train", transform=None):
        self.root = Path(root)
        self.transform = transform
        with (self.root / "paired_manifest.csv").open(encoding="utf-8-sig", newline="") as handle:
            self.rows = [row for row in csv.DictReader(handle) if row["split"] == split]

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        original = Image.open(self.root / row["original_path"]).convert("RGB")
        retouched = Image.open(self.root / row["retouched_path"]).convert("RGB")
        if self.transform is not None:
            original = self.transform(original)
            retouched = self.transform(retouched)
        return {
            "original": original,
            "retouched": retouched,
            "pair_id": row["pair_id"],
            "retouch_type": row["retouch_type"],
            "retouch_level": row["retouch_level"],
        }


if __name__ == "__main__":
    dataset = FFHQFFHQRPairedDataset(Path(__file__).parent, split="train")
    first = dataset[0]
    print(f"train pairs: {len(dataset)}")
    print(first["pair_id"], first["original"].size, first["retouched"].size)
