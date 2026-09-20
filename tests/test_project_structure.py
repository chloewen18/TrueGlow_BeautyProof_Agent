"""Check required runtime and evaluation resources."""
import unittest

from backend.app.paths import (
    PROJECT_ROOT, MEMBER2_CURRENT, MEMBER2_LEGACY, MEMBER3_CURRENT,
    MEMBER4_CURRENT, MEMBER4_LEGACY,
)


class ProjectStructureTests(unittest.TestCase):
    def test_delivery_roots_and_required_assets(self):
        for folder in (MEMBER2_CURRENT, MEMBER2_LEGACY, MEMBER3_CURRENT,
                       MEMBER4_CURRENT, MEMBER4_LEGACY):
            with self.subTest(folder=folder):
                self.assertTrue(folder.is_dir())
                self.assertTrue(folder.resolve().is_relative_to(PROJECT_ROOT))
        self.assertEqual(len(list((MEMBER2_CURRENT / "_Output/npz").glob("*.npz"))), 35)
        self.assertTrue((MEMBER3_CURRENT / "MODEL_MANIFEST.json").is_file())
        self.assertTrue((MEMBER4_CURRENT / "demo/test.PNG").is_file())
        self.assertTrue((MEMBER4_LEGACY / "30条盲测题.xlsx").is_file())

    def test_member2_evaluation_reads_relocated_outputs(self):
        from scripts.evaluate_integrated import member2_delivered
        result = member2_delivered()
        self.assertEqual(result["metrics"]["attempted"], 33)
        self.assertEqual(result["metrics"]["errors"], 0)


if __name__ == "__main__":
    unittest.main()
