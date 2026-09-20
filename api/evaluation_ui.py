import json
from pathlib import Path
import subprocess
import sys
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]


def render_evaluation():
    path = ROOT / "data/integrated_evaluation.json"
    if st.button("重新运行真实评测", icon=":material/play_arrow:"):
        with st.spinner("正在运行100对修饰检测、同图控制、文案测试与TruFor输出复算……"):
            try:
                process = subprocess.run([sys.executable, str(ROOT / "scripts/evaluate_integrated.py"), "--member3-pairs", "100", "--trufor-live"],
                    cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
                if process.returncode:
                    st.error("评测失败，保留上次成功记录；未将失败计为零风险。")
                    st.code(process.stderr[-3000:])
                else:
                    st.success("本次评测与逐样本输出已保存。")
            except subprocess.TimeoutExpired:
                st.error("评测超时，本次未生成完整报告。")
    if not path.exists():
        st.info("尚无本地集成评测记录")
        return
    report = json.loads(path.read_text(encoding="utf-8"))
    st.caption(f"运行批次：{report['run_id']} · 数据来源与局限随结果保留")
    m3 = report["member3"]
    if m3.get("metrics"):
        st.subheader("成员三 · 本地真实复测")
        m = m3["metrics"]
        a,b,c = st.columns(3)
        a.metric("修饰图检出", f"{m['tp']} / {m['tp']+m['fn']}")
        b.metric("原图误报", f"{m['fp']} / {m['fp']+m['tn']}")
        c.metric("运行失败", f"{m['errors']} / {m['attempted']}")
        for note in m3["limitations"]:
            st.caption(note)
        with st.expander("逐样本结果"):
            st.dataframe([{k:v for k,v in r.items() if k != "output"} for r in m3["rows"]], hide_index=True)
    st.subheader("成员二 · 交付输出复算")
    m2 = report["member2"]
    st.dataframe([{"分组": group, "样本数": values["completed"], "误报数": values["fp"],
                   "误报率": f"{values['fpr']:.1%}" if values['fpr'] is not None else "未评测", "阈值": values["threshold"]}
                  for group,values in m2["groups"].items() if group != "tampered"], hide_index=True)
    for note in m2["limitations"]:
        st.caption(note)
    for row in report.get("trufor_live", []):
        output = row.get("output", {})
        st.write(f"本机TruFor新推理 · {row['sample']} · " + (f"可疑分 {output['trufor_score']:.3f}" if output else f"失败：{row.get('error')}"))
    st.download_button("导出完整评测与原始结果", path.read_bytes(), "integrated-evaluation.json", "application/json", icon=":material/download:")
