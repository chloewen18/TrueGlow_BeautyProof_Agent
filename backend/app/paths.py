"""Stable locations for team deliveries; runtime data remains under data/."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MEMBER2_LEGACY = PROJECT_ROOT / "member2_forensics/deliverables/legacy_simulated"
MEMBER2_CURRENT = PROJECT_ROOT / "member2_forensics/deliverables/v2"
MEMBER3_CURRENT = PROJECT_ROOT / "member3_dataset/deliverables/v1_1"
MEMBER4_LEGACY = PROJECT_ROOT / "member4_text/deliverables/v1"
MEMBER4_CURRENT = PROJECT_ROOT / "member4_text/deliverables/v2"
