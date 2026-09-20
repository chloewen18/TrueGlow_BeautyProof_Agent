"""Check required runtime and evaluation resources.

注意：member2 的大体积演示资产已移出版本库（见 .gitignore）。
在未单独获取这些资产的环境（CI / 云端 / 新克隆）中，相关断言会被跳过而非失败。
"""
import unittest

from backend.app.paths import (
    PROJECT_ROOT, MEMBER2_CURRENT, MEMBER2_LEGACY, MEMBER3_CURRENT,
    MEMBER4_CURRENT, MEMBER4_LEGACY,
)

HAS_MEMBER2_ASSETS = (MEMBER2_CURRENT / "_Output/npz").is_dir()


class ProjectStructureTests(unittest.TestCase):
    def test_delivery_roots_stay_inside_project(self):
        for folder in (MEMBER2_CURRENT, MEMBER2_LEGACY, MEMBER3_CURRENT,
                       MEMBER4_CURRENT, MEMBER4_LEGACY):
            with self.subTest(folder=folder):
                self.assertTrue(folder.resolve().is_relative_to(PROJECT_ROOT))

    @unittest.skipUnless(HAS_MEMBER2_ASSETS, "member2 演示资产未随仓库分发")
    def test_member2_delivered_npz_count(self):
        self.assertEqual(len(list((MEMBER2_CURRENT / "_Output/npz").glob("*.npz"))), 35)

    def test_member3_and_member4_assets(self):
        self.assertTrue((MEMBER3_CURRENT / "MODEL_MANIFEST.json").is_file())
        self.assertTrue((MEMBER4_CURRENT / "demo/test.PNG").is_file())
        self.assertTrue((MEMBER4_LEGACY / "30条盲测题.xlsx").is_file())

    @unittest.skipUnless(HAS_MEMBER2_ASSETS, "member2 演示资产未随仓库分发")
    def test_member2_evaluation_reads_relocated_outputs(self):
        from scripts.evaluate_integrated import member2_delivered
        result = member2_delivered()
        self.assertEqual(result["metrics"]["attempted"], 33)
        self.assertEqual(result["metrics"]["errors"], 0)


if __name__ == "__main__":
    unittest.main()
