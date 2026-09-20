import pandas as pd
import streamlit as st

from backend.app.deliverables import DATASET, dataset_records
from api.evidence_ui import show_artifact
import json
from pathlib import Path


def render_team_deliverables():
    st.header("成员交付数据")
    pairs = pd.DataFrame(dataset_records()["pairs"])
    st.metric("FFHQ / FFHQR 配对", len(pairs))
    st.caption("专业修饰二分类标签；没有磨皮、美白等单项操作或强度真值。80/10/10 为原型划分，未验证跨人物身份隔离。")
    split = st.selectbox("数据划分", ["train", "validation", "test"])
    selected = pairs[pairs["split"] == split]
    pair_id = st.selectbox("配对编号", selected["pair_id"].tolist())
    row = selected[selected["pair_id"] == pair_id].iloc[0]
    before, after = st.columns(2)
    before.image(str(DATASET / row["original_path"]), caption="FFHQ 原图", width="stretch")
    after.image(str(DATASET / row["retouched_path"]), caption="FFHQR 专业修饰", width="stretch")
    st.caption(f"作者：{row['ffhq_author']} · 原图许可：{row['ffhq_license']} · 修饰图许可：{row['ffhqr_license']}")
    st.dataframe(selected, hide_index=True)

    path = Path(__file__).resolve().parents[1] / "data/integrated_evaluation.json"
    if path.exists():
        st.subheader("本机 TruFor 真实推理样例")
        for item in json.loads(path.read_text(encoding="utf-8")).get("trufor_live", []):
            tf = item.get("output")
            if not tf:
                st.warning(item.get("error"))
                continue
            st.write(f"{item['sample']} · 可疑分 {tf['trufor_score']:.3f}")
            a,b = st.columns(2)
            with a:
                show_artifact(tf["manipulation_map"], "异常定位 · 黑0 / 红1")
            with b:
                show_artifact(tf["reliability_map"], "定位置信度 · 黑0 / 红1")
            st.caption("原始输出、权重哈希和输入哈希见评测导出。历史模拟包仅存档，不再作为评测数字展示。")
