"""C2PA 清单存在性检测的最小验证。

覆盖：JPEG APP11/c2pa 标记识别、无清单文件、以及 source_trace 真实路径的聚合行为。
注意：仅验证「存在性检测」，不涉及签名链验证。
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.app.config import settings
from backend.app.integrations.metadata_parser import detect_c2pa_manifest
from backend.app.schemas.common import ToolRequest
from backend.app.tools.source_trace import handler as source_trace_handler

# 带 APP11 段 + "c2pa\0" 标识符的最小 JPEG（非合法图片，仅用于字节级检测）
JPEG_WITH_C2PA = (
    b"\xff\xd8\xff\xe0" + b"JFIF\x00" + b"\x00\x01"
    + b"\xff\xeb\x00\x14" + b"c2pa\x00" + b"urn:uuid:demo-manifest"
    + b"\xff\xd9"
)
# 无任何清单标记的最小 PNG
PLAIN_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 13


class DetectFunctionTests(unittest.TestCase):
    def test_present_in_jpeg_app11(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "with_c2pa.jpg"
            p.write_bytes(JPEG_WITH_C2PA)
            result = detect_c2pa_manifest(str(p))
        self.assertEqual(result["status"], "present")
        self.assertTrue(result["markers"])

    def test_absent_in_plain_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "plain.png"
            p.write_bytes(PLAIN_PNG)
            result = detect_c2pa_manifest(str(p))
        self.assertEqual(result["status"], "absent")

    def test_unknown_when_file_missing(self):
        result = detect_c2pa_manifest("/nonexistent/file.jpg")
        self.assertEqual(result["status"], "unknown")


class SourceTraceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._created = []

    def tearDown(self):
        for ref in self._created:
            path = settings.resolved_data_dir / ref
            if path.is_file():
                path.unlink()
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _save(self, name: str, data: bytes) -> str:
        target = settings.resolved_data_dir / "uploads" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        ref = f"uploads/{name}"
        self._created.append(ref)
        return ref

    def _run(self, ref: str) -> dict:
        request = ToolRequest(tool="source_trace", request_id="c2pa-test",
                              payload={"files": [{"kind": "image", "ref": ref}]})
        return source_trace_handler.handle(request)

    def test_uploaded_jpeg_reports_present(self):
        result = self._run(self._save("c2pa_present.jpg", JPEG_WITH_C2PA))
        self.assertEqual(result["c2pa"]["status"], "present")
        self.assertIn("未验证签名链", result["c2pa"]["detail"])
        self.assertIn("存在性检测", result["conclusion"])

    def test_uploaded_png_reports_absent(self):
        result = self._run(self._save("c2pa_absent.png", PLAIN_PNG))
        self.assertEqual(result["c2pa"]["status"], "absent")
        self.assertIn("不代表伪造", result["conclusion"])


if __name__ == "__main__":
    unittest.main()
