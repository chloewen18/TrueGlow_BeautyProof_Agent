import requests
import streamlit as st
from api.client import API_BASE_URL


def show_artifact(reference, caption):
    value = (reference or {}).get("value", "")
    if not value.startswith("/api/v1/artifacts/"):
        st.caption(f"{caption}：未生成真实图像")
        return
    try:
        response = requests.get(API_BASE_URL+value, timeout=30)
        response.raise_for_status()
        st.image(response.content, caption=caption, width="stretch")
    except requests.RequestException:
        st.warning(f"{caption}暂不可读取，原始报告仍保留引用。")


def render_evidence(report):
    calls = report.get("tool_calls", [])
    labels = {"mock": "模拟", "real": "真实模型", "real_exif": "真实解析", "real_rules": "真实规则", "unavailable": "未完成"}
    st.markdown("#### 检测来源")
    for mode in sorted({c.get("model", "unavailable") for c in calls}):
        st.badge(labels.get(mode, mode), icon=":material/science:" if mode == "mock" else ":material/verified:",
                 color="orange" if mode in ("mock", "unavailable") else "green")
    st.dataframe([{"模块": c["tool"], "来源": labels.get(c.get("model"), "见原始记录"),
                   "状态": c["status"], "耗时(秒)": round(c.get("latency_ms", 0)/1000, 2),
                   "错误": str(c.get("error") or "")} for c in calls], hide_index=True, width="stretch")
    evidence = report.get("evidence", {})
    visual = evidence.get("visual_evidence", {}).get("raw", {})
    for row in visual.get("per_image", []):
        with st.expander(f"图像证据 · {row['media_ref']}", expanded=True):
            tf, member3 = row.get("trufor", {}), row.get("member3", {})
            if tf.get("status") == "success":
                a, b = st.columns(2)
                a.metric("TruFor 可疑分", f"{tf['trufor_score']:.3f}")
                b.metric("完整性参考分", f"{tf['integrity_score']:.3f}")
                st.caption("真实推理 · 完整性参考分 = 1 − 可疑分；不是造假概率。图例：黑色0 → 红色1，固定色阶。")
                with a:
                    show_artifact(tf.get("manipulation_map"), "异常定位图")
                with b:
                    show_artifact(tf.get("reliability_map"), "定位置信度图（不是异常图）")
                for note in tf.get("limitations", []):
                    st.caption(note)
            else:
                st.warning(f"TruFor 未完成：{tf.get('error', '无结果')}")
            if member3.get("status") == "ok":
                st.caption("成员三 · 真实模型 · 操作信号仅供辅助，未经跨域概率校准")
                generic = member3["result"]["generic_retouch"]
                st.write(f"通用修饰分 {generic['score']:.3f} / 模型阈值 {generic['threshold']:.3f}")
                st.dataframe([{"操作": o["name_zh"], "模型分数": o["score"], "阈值": o["threshold"],
                               "提示": "触发辅助信号" if o["detected"] else "未触发（不等于没有）"}
                              for o in member3["result"]["operations"].values()], hide_index=True)
            else:
                st.warning(f"修饰模型未完成：{member3.get('error', '无结果')}")
    pair = evidence.get("before_after_evidence", {}).get("raw", {})
    if pair.get("member3_analysis"):
        st.markdown("#### 前后条件与差异")
        st.write(pair.get("attribution_summary"))
        st.caption(f"可比较性：{pair.get('comparison_reliability')} · 产品归因：未知")
        delta = pair["member3_analysis"]["result"]["parameter_deltas"]
        st.dataframe([{"参数": k, "模型估计差": v} for k, v in delta.items()], hide_index=True)
        difference = pair.get("difference", {})
        if difference.get("status") == "success":
            show_artifact(difference.get("map"), "对齐后像素差异（非修饰操作真值）")
        else:
            st.info(difference.get("reason", "未生成差异图"))
        for note in pair.get("limitations", []):
            st.caption(note)


def render_collection():
    st.subheader("志愿者内部评测采集")
    st.info("仅收集已成年志愿者本人的两张图片，用于本团队内部评测，不用于训练或公开展示。不填写姓名、联系方式或其他人的信息。人脸本身仍可识别个人；图片去除EXIF/GPS后保存在本机，30天到期后在采集服务下次访问时清理。可凭撤回码提前删除。")
    try:
        response = requests.get(API_BASE_URL+"/api/v1/volunteers/status", timeout=10)
        response.raise_for_status()
        st.metric("已同意提交的图片对", response.json()["consented_pairs"])
    except requests.RequestException:
        st.warning("采集服务暂不可用")
    with st.form("volunteer_consent"):
        a, b = st.columns(2)
        before = a.file_uploader("前图", type=["png", "jpg", "jpeg"], key="vol_before", max_upload_size=12)
        after = b.file_uploader("后图", type=["png", "jpg", "jpeg"], key="vol_after", max_upload_size=12)
        conditions = {"same_conditions": "同条件不同帧", "lighting_changed": "仅光照变化", "makeup_changed": "真实底妆变化", "compression_only": "仅压缩/缩放", "other": "其他"}
        condition = st.selectbox("拍摄条件（本人声明）", list(conditions), format_func=conditions.get)
        edits = st.text_area("使用的滤镜、美颜和编辑操作；没有请填无")
        adult = st.checkbox("我已成年，图片仅包含我本人，且有权提交")
        consent = st.checkbox("我已阅读并同意上述内部评测用途、存储与撤回方式")
        submit = st.form_submit_button("同意并提交", icon=":material/upload:")
    if submit:
        if not before or not after or not consent or not adult or not edits.strip():
            st.warning("请补齐两张图片、操作说明并明确同意。")
        else:
            try:
                response = requests.post(API_BASE_URL+"/api/v1/volunteers/submit",
                    files={"before": ("before.png", before.getvalue(), before.type), "after": ("after.png", after.getvalue(), after.type)},
                    data={"consent": "true", "adult_self": "true", "condition": condition, "edits": edits}, timeout=60)
                response.raise_for_status()
                st.session_state["volunteer_receipt"] = response.json()
            except requests.RequestException as exc:
                st.error(f"提交未完成：{exc}")
    if st.session_state.get("volunteer_receipt"):
        import json
        receipt = st.session_state["volunteer_receipt"]
        st.success("素材已收件，标签等待双人复核。请保留撤回凭据。")
        st.download_button("下载撤回凭据", json.dumps(receipt, ensure_ascii=False, indent=2), "withdrawal-receipt.json", icon=":material/download:")
        st.code(json.dumps(receipt, ensure_ascii=False), language="json")
    with st.expander("撤回已提交素材"):
        sid = st.text_input("素材编号")
        token = st.text_input("撤回码", type="password")
        if st.button("确认撤回并删除", icon=":material/delete:"):
            try:
                response = requests.post(API_BASE_URL+"/api/v1/volunteers/withdraw", json={"sample_id": sid, "token": token}, timeout=30)
                if response.ok:
                    st.session_state.pop("volunteer_receipt", None)
                    st.success("已删除本次提交的图片与记录。")
                else:
                    st.error("撤回失败，请核对编号和撤回码。")
            except requests.RequestException:
                st.error("服务暂不可用，撤回尚未完成，请稍后重试。")
