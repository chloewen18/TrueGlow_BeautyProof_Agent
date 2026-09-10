import pandas as pd
import streamlit as st

from backend.app.deliverables import DATASET, TRUFOR, dataset_records, trufor_results


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
    before.image(str(DATASET / row["original_path"]), caption="FFHQ 原图", use_container_width=True)
    after.image(str(DATASET / row["retouched_path"]), caption="FFHQR 专业修饰", use_container_width=True)
    st.caption(f"作者：{row['ffhq_author']} · 原图许可：{row['ffhq_license']} · 修饰图许可：{row['ffhqr_license']}")
    st.dataframe(selected, hide_index=True)

    st.subheader("TruFor 交付样例")
    st.warning("这4组评分和图片由模拟逻辑生成。交付包不含推理脚本、模型权重或输入原图，不能检测新上传图片。")
    threshold = st.slider("可疑分阈值", 0.0, 1.0, 0.65, 0.01)
    results = trufor_results(threshold)
    left, right = st.columns(2)
    left.metric("样例误报率", f"{results['false_positive_rate']:.0%}")
    right.metric("样例检出率", f"{results['true_positive_rate']:.0%}")
    st.dataframe(results["samples"], hide_index=True)
    sample = st.selectbox("结果样例", [r["sample"] for r in results["samples"]])
    left, right = st.columns(2)
    left.image(str(TRUFOR / f"{sample}_localization_map.png"), caption="交付定位图")
    right.image(str(TRUFOR / f"{sample}_confidence_map.png"), caption="交付置信度图")
    st.caption("按交付分数重新计算：阈值0.65时误报率为0%；原报告的50%为计算错误。以上不是模型实测性能。")
