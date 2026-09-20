import json
from pathlib import Path
import requests
import streamlit as st
from api.client import API_BASE_URL, _upload
from backend.app.integrations.member4.service import evidence_db, workbook_rows


def render_member4():
    st.header("文案与功效证据")
    st.caption("词典与规则提取；品牌资料来自交付证据库，未在线复核，不等同于独立科学验证。")
    product = st.selectbox("证据库产品", [""]+[p["product_name"] for p in evidence_db()["products"]],
                           format_func=lambda p:p or "未指定 / 其他产品", key="m4_product")
    image = st.file_uploader("含文字图片", type=["png","jpg","jpeg"], key="m4_image", max_upload_size=20)
    crop = st.checkbox("仅识别下方字幕区域", value=False)
    if st.button("识别图片文字", disabled=image is None):
        try:
            with st.spinner("正在识别图片文字……"):
                media = _upload(image)
                response = requests.post(f"{API_BASE_URL}/api/v1/member4/ocr",
                    json={"media_ref":media["ref"], "subtitle_crop":crop}, timeout=240)
                if not response.ok:
                    raise ValueError(response.json().get("detail", "OCR failed"))
                result = response.json()
                st.session_state["m4_text"] = result["text"]
                st.session_state["m4_ocr"] = result
        except Exception as exc:
            st.error(f"图片文字识别失败：{exc}")
    text = st.text_area("待分析文案", key="m4_text", height=140)
    comments = st.text_area("评论（每行一条）", key="m4_comments")
    if st.button("提取宣称与匹配证据", type="primary", disabled=not text.strip()):
        try:
            response = requests.post(f"{API_BASE_URL}/api/v1/member4/analyze",
                json={"text":text, "product":product, "comments":comments.splitlines()}, timeout=60)
            response.raise_for_status()
            st.session_state["m4_result"] = response.json()
        except Exception as exc:
            st.error(f"文案分析失败：{exc}")
    if "m4_result" in st.session_state:
        result = st.session_state["m4_result"]
        st.caption(f"上次分析产品：{result['product'] or '未指定'} · 文案：{result['text']}")
        st.dataframe([{"功效宣称":c["canonical_claim"],"原文":c["matched_text"],
            "表达倾向":{"positive":"正向","negative":"负向","mixed":"混合"}.get(c["polarity"],c["polarity"]),
            "时长":c["duration"] or "未提及","品牌资料支持":"有" if c["evidence_supported"] else "未匹配"}
            for c in result["claims"]],hide_index=True)
        for claim in result["claims"]:
            with st.expander(claim["canonical_claim"]):
                st.write(claim["consumer_meaning"])
                st.write(claim["audience_explanation"])
                for evidence in claim["evidence_matches"]:
                    st.caption(f"交付证据等级：{evidence.get('evidence_level_cn', evidence.get('evidence_strength', '未标注'))} · 品牌资料，未独立验证")
                    st.write(evidence.get("evidence_detail",""))
                    for limitation in evidence.get("limitations", []):
                        st.caption(limitation)
                    st.caption(evidence.get("consumer_explanation",""))
                    if evidence.get("source_url"):
                        st.link_button("查看资料来源",evidence["source_url"])
        comments_result=result["comment_analysis"]
        st.caption(f"评论数量：{comments_result['count']} · {comments_result['note']}")
        if comments_result["repeated_phrases"]:
            st.dataframe([{"重复表达":k,"次数":v} for k,v in comments_result["repeated_phrases"].items()],hide_index=True)
    with st.expander("解释模板与评论参考"):
        st.dataframe(workbook_rows("解释模版库.xlsx"), hide_index=True)
        st.dataframe(workbook_rows("评论区分析.xlsx"), hide_index=True)
    with st.expander("测试集复跑结果"):
        path = Path(__file__).resolve().parents[1] / "data/member4_evaluation.json"
        if path.exists():
            report = json.loads(path.read_text(encoding="utf-8"))
            st.caption("仅统计规范化宣称集合；不代表OCR、极性、时长或功效证据准确率。")
            for name, metrics in report["datasets"].items():
                st.write(f"{name}：{metrics['count']}条，完全匹配 {metrics['exact_match_count']}条，micro F1 {metrics['micro_f1']:.3f}")
                st.dataframe(metrics["cases"], hide_index=True)
