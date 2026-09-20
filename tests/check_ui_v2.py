"""Render saved real report through Streamlit's real app, without injecting model signals."""
import json
from pathlib import Path
from streamlit.testing.v1 import AppTest

root = Path(__file__).resolve().parents[1]
result = json.loads((root / "data/evaluation_runs/live_http/verify.json").read_text(encoding="utf-8"))
app = AppTest.from_file(str(root / "app.py"))
app.session_state["active_report"] = result
app.run(timeout=60)
assert not app.exception, app.exception
assert any("通用专业修饰" in element.value for element in app.markdown)
app.sidebar.radio[0].set_value("评测工作台").run(timeout=60)
assert not app.exception, app.exception
assert any("73 / 100" == str(element.value) for element in app.metric)
print("Real report and evaluation UI rendered without exceptions")
