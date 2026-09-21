#!/usr/bin/env python3
"""一键部署到 Hugging Face Spaces。

用法：
    export HF_TOKEN=hf_xxxxxxxx        # 在 https://huggingface.co/settings/tokens 创建（需 write 权限）
    export HF_SPACE_ID=你的用户名/trueglow
    python deploy/hf_deploy.py --dry-run   # 先试跑，只看会传哪些文件
    python deploy/hf_deploy.py             # 真正创建并上传

说明：
  * 只上传 git 已跟踪的文件（约 9MB），大体积演示资产不会进入 Space。
  * 自动把 deploy/huggingface-README.md 写成 Space 的 README.md，
    其中的 `sdk: docker` / `app_port: 7860` frontmatter 是 Docker 构建的必要条件。
  * 上传完成后仍需到 Space 的 Settings → Variables and secrets 配置密钥，
    本脚本不会替你写密钥（避免密钥进入 git 历史）。
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HF_README = REPO_ROOT / "deploy" / "huggingface-README.md"


def stage_files(dest: Path) -> int:
    """用 git archive 导出已跟踪文件到 dest（天然排除 .gitignore 中的大资产）。"""
    archive = subprocess.run(
        ["git", "archive", "--format=tar", "HEAD"],
        cwd=REPO_ROOT, capture_output=True, check=True,
    ).stdout
    extract = subprocess.run(["tar", "-x", "-C", str(dest)], input=archive, check=True)
    if extract.returncode != 0:
        raise SystemExit("解压 git archive 失败")
    shutil.copy2(HF_README, dest / "README.md")
    return sum(1 for p in dest.rglob("*") if p.is_file())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只暂存并检查，不上传")
    parser.add_argument("--space-id", default=os.getenv("HF_SPACE_ID", ""))
    parser.add_argument("--private", action="store_true", help="创建为私有 Space")
    args = parser.parse_args()

    if not HF_README.is_file():
        raise SystemExit(f"缺少 {HF_README}，无法生成 Space README")

    token = os.getenv("HF_TOKEN", "").strip()
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / "space"
        stage.mkdir()
        count = stage_files(stage)
        size_mb = sum(p.stat().st_size for p in stage.rglob("*") if p.is_file()) / 1048576
        print(f"已暂存 {count} 个文件，共 {size_mb:.1f} MB → {stage}")

        if args.dry_run:
            print("\n[dry-run] 不会上传。以下是将要上传的顶层内容：")
            for item in sorted(stage.iterdir()):
                print("  ", item.name)
            return 0

        if not token:
            raise SystemExit("未设置 HF_TOKEN，无法上传。请先 export HF_TOKEN=hf_xxx")
        if not args.space_id:
            raise SystemExit("未设置 HF_SPACE_ID（形如 用户名/space名）。请 export HF_SPACE_ID=...")

        try:
            from huggingface_hub import HfApi
        except ImportError:
            raise SystemExit("缺少 huggingface_hub，请先 pip install huggingface_hub")

        api = HfApi(token=token)
        print(f"\n创建/复用 Space：{args.space_id}（docker SDK）")
        api.create_repo(
            repo_id=args.space_id, repo_type="space", space_sdk="docker",
            private=args.private, exist_ok=True,
        )
        print("上传文件中……")
        api.upload_folder(
            folder_path=str(stage), repo_id=args.space_id, repo_type="space",
            commit_message="deploy: TrueGlow 映真 演示站",
        )
        print(f"\n完成：https://huggingface.co/spaces/{args.space_id}")
        print("提醒：请到 Space 的 Settings → Variables and secrets 配置")
        print("      BEAUTYPROOF_API_KEY 与 BEAUTYPROOF_ACCESS_CODE（用 Secrets，不要写进仓库）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
