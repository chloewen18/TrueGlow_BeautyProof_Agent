import json
import os
from pathlib import Path
import streamlit as st
from PIL import Image
from api.client import submit_creator_evidence
from api.workbench_client import verify, demo, ocr
from api.member4_ui import render_member4
from api.deliverables_ui import render_team_deliverables
from api.evidence_ui import render_evidence, render_collection
from api.evaluation_ui import render_evaluation

ROOT = Path(__file__).resolve().parent
ACCESS_CODE = os.getenv("BEAUTYPROOF_ACCESS_CODE", "").strip()
st.set_page_config(page_title="TrueGlow 映真 · 内容信任工作台",page_icon=":material/verified_user:",layout="wide")
st.markdown(f"<style>{(ROOT/'styles/theme.css').read_text(encoding='utf-8')}\n{(ROOT/'styles/workbench.css').read_text(encoding='utf-8')}</style>",unsafe_allow_html=True)


def access_gate() -> bool:
    """公网部署时的访问口令门槛。未设置 BEAUTYPROOF_ACCESS_CODE 则不启用。"""
    if not ACCESS_CODE or st.session_state.get("_authorized"):
        return True
    st.title("TrueGlow 映真 · 内容信任工作台")
    st.caption("演示环境受访问口令保护，请向团队获取口令后进入。")
    with st.form("access_gate"):
        code = st.text_input("访问口令", type="password")
        submitted = st.form_submit_button("进入", type="primary")
    if submitted:
        if code.strip() == ACCESS_CODE:
            st.session_state["_authorized"] = True
            st.rerun()
        else:
            st.error("口令不正确。")
    return False


if not access_gate():
    st.stop()

PAGES = ["内容核验", "创作者复核", "证据档案", "文案与功效", "评测工作台"]


@st.cache_resource(show_spinner=False)
def real_models_ready() -> bool:
    """当前环境是否具备运行真实视觉模型的条件（权重存在且 torch 可用）。

    用 cache_resource 缓存是因为 Streamlit 每次交互都会重跑脚本，
    若 torch 可用则首次 import 需要数秒，不应重复付出。
    """
    if not (ROOT / "data/models").is_dir():
        return False
    try:
        import torch  # noqa: F401
    except ImportError:
        return False
    return True


def report_mode_caption(result, report) -> str:
    """报告顶部的模式说明：如实区分「模拟」「部分未完成」「真实处理」三种情况。"""
    calls = report.get("tool_calls", [])
    if result.get("demo_mode") or "mock" in {c.get("model") for c in calls}:
        return "模拟演示 · 不构成真实核验结论"
    degraded = [str(c.get("tool")) for c in calls if c.get("status") != "success"]
    if degraded:
        names = "、".join(dict.fromkeys(degraded))
        return f"部分模块未完成（{names}）：相关维度未参与判定，本次结论仅供演示参考"
    return "真实处理 · 模型信号仅供辅助，不能证明造假意图或产品因果"

def remember(response, simulated=False):
    response["demo_mode"] = simulated
    st.session_state["active_report"] = response
    history = st.session_state.setdefault("reports", {})
    history[response["request_id"]] = response

def bullets(items):
    for item in items:
        st.write(f"• {item}")

def render_report(result):
    report = result.get("report",{})
    card = report.get("trust_card",{})
    st.divider()
    st.caption("BEAUTY TRUST CARD / 内容信任报告")
    c1,c2 = st.columns([3,1])
    with c1:
        st.subheader(card.get("verdict_label","待核验"))
        st.caption(report_mode_caption(result, report))
    with c2:
        st.download_button("导出报告",json.dumps(result,ensure_ascii=False,indent=2),
            file_name=f"trueglow-{result['request_id']}.json",mime="application/json",icon=":material/download:")
    a,b = st.columns([1.3,1],gap="large")
    with a:
        st.markdown("#### 主要发现")
        bullets(card.get("main_findings",[]))
        if report.get("limitations"):
            st.caption("未核验范围：" + "；".join(report["limitations"]))
        for section in card.get("sections",[]):
            with st.expander(section.get("title","证据说明")):
                bullets(section.get("content",[]))
    with b:
        st.markdown("#### 建议补充的证据")
        bullets(card.get("creator_actions",[]))
        if result.get("review_summary"):
            st.info(result["review_summary"])
        st.caption("核验记录")
        st.code(result.get("request_id",""),language=None)
    render_evidence(report)
    with st.expander("证据链与检测状态"):
        st.dataframe(report.get("tool_calls",[]),hide_index=True)
        st.json(card.get("advanced",{}))

with st.sidebar:
    st.markdown('<div class="brand">TrueGlow <span>映真</span></div><p class="brand-sub">内容信任工作台</p>',unsafe_allow_html=True)
    page = st.radio("工作区",PAGES,label_visibility="collapsed")
    st.divider()
    st.caption("当前能力")
    model_line = "TruFor / 修饰模型　已接入" if real_models_ready() else "TruFor / 修饰模型　本环境未启用"
    st.markdown("EXIF / OCR　真实处理\n\n文案 / 功效　新版规则与资料库\n\n" + model_line
                + "\n\n前后条件　模型估计 + 差异图\n\nC2PA 认证　尚未接入")
    st.caption("运行成功与否以每次报告状态为准")
    st.divider()
    st.caption("信任守护师 · 创造者的 AI 卫士")
    st.link_button("赛道二", "https://tianchi.aliyun.com/competition/entrance/532496",icon=":material/open_in_new:")

st.markdown('<div class="topline"><span>TrueGlow 映真</span><span>美妆内容 · 多模态核验</span></div>',unsafe_allow_html=True)

if page == "内容核验":
    st.title("内容核验")
    st.caption("让每一条美妆内容，都有可追溯的判断依据。")
    mode = st.segmented_control("核验模式",["上传核验","演示案例"],default="上传核验",label_visibility="collapsed")
    left,right = st.columns([1.05,1],gap="large")
    with left:
        st.subheader("待核验内容")
        if mode == "演示案例":
            case = st.selectbox("案例",["A","B","C"],format_func=lambda x:{"A":"A · 来源缺失，证据不足","B":"B · 修饰与功效宣称冲突","C":"C · 创作者补证后复核"}[x])
            st.info("案例使用预设检测信号，结果仅用于展示核验与复核流程。")
            if st.button("运行案例",type="primary",icon=":material/play_arrow:"):
                try:
                    with st.spinner("正在生成案例报告……"):
                        remember(demo(case),True)
                except Exception as exc:
                    st.error(f"案例运行失败：{exc}")
        else:
            uploaded = st.file_uploader("图片 / 内容截图",type=["jpg","jpeg","png"],key="verify_image",max_upload_size=20)
            if st.button("提取图片文字",icon=":material/document_scanner:",disabled=uploaded is None):
                try:
                    with st.spinner("正在识别……"):
                        st.session_state["verify_text"] = ocr(uploaded)
                except Exception as exc:
                    st.error(f"识别失败：{exc}")
            text = st.text_area("文案",key="verify_text",height=110,placeholder="种草文案、产品宣称或图片中的文字")
            product = st.text_input("产品名称（可选）",placeholder="填写完整产品名以匹配功效资料")
            with st.expander("前后对比与评论"):
                before = st.file_uploader("使用前图片",type=["jpg","jpeg","png"],key="verify_before",max_upload_size=20)
                comments = st.text_area("评论（每行一条）",key="verify_comments")
            if st.button("开始核验",type="primary",icon=":material/fact_check:"):
                if not text.strip() and not uploaded:
                    st.warning("请添加图片或文案。")
                else:
                    try:
                        with st.spinner("分析内容、整理证据与建议……"):
                            remember(verify(text,product,uploaded,before,comments))
                    except Exception as exc:
                        st.error(f"核验失败：{exc}")
    with right:
        st.subheader("素材预览")
        if mode != "演示案例" and uploaded:
            try:
                st.image(Image.open(uploaded),width="stretch")
            except Exception:
                st.warning("图片无法解码，请更换有效图片。")
        else:
            one,two = st.columns(2)
            folder = ROOT / "data/datasets/FFHQ_FFHQR_100_pairs_v1"
            sample_before = folder/"originals/00001.png"
            sample_after = folder/"retouched/00001.png"
            if sample_before.is_file() and sample_after.is_file():
                one.image(str(sample_before),caption="原始素材",width="stretch")
                two.image(str(sample_after),caption="专业修饰",width="stretch")
                st.caption("FFHQ / FFHQR 配对样例 · Cyber Shaman · 原图 Attribution / 修饰 CC BY-NC-SA 4.0。样例不代表当前检测结果。")
            else:
                st.info("演示配对样例未随本环境分发（大体积素材已移出版本库），不影响核验流程。")
        st.markdown('<div class="scope"><b>核验关注</b><p>来源与元数据</p><p>画面修饰与前后条件</p><p>文案宣称与功效证据</p></div>',unsafe_allow_html=True)
        st.caption("元数据缺失不等于伪造。模型低分不证明原图真实，操作分数不代表产品功效。")
    if st.session_state.get("active_report"):
        render_report(st.session_state["active_report"])

elif page == "创作者复核":
    st.title("创作者复核")
    st.caption("补充原始素材，让结论随证据更新。")
    history = st.session_state.get("reports",{})
    source = st.selectbox("关联核验记录",[""]+list(history),format_func=lambda x:x or "手动填写记录编号")
    original = history.get(source,{})
    left,right = st.columns([1.2,1],gap="large")
    with left:
        rid = st.text_input("核验记录编号",value=source,key=f"rid_{source}")
        cid = st.text_input("内容编号",value=original.get("content_id",""),key=f"cid_{source}")
        file = st.file_uploader("原始图片",type=["jpg","jpeg","png"],key="review_file",max_upload_size=20)
        note = st.text_area("拍摄条件与滤镜说明",placeholder="设备、光线、滤镜参数、曝光调整")
        if st.button("提交复核",type="primary",icon=":material/assignment_turned_in:"):
            if not rid or not cid or not file:
                st.warning("请关联核验记录并上传原始图片。")
            else:
                try:
                    with st.spinner("正在复核补充材料……"):
                        result=submit_creator_evidence(cid,rid,file,note)
                        remember(result)
                        st.session_state["review_result"]=result
                except Exception as exc:
                    st.error(f"复核失败：{exc}")
    with right:
        st.subheader("证据要求")
        bullets(["未经平台压缩的原始素材","如实披露美颜、滤镜与曝光调整","保持前后画面光线与角度一致"])
        st.info("补证不保证改变结论。当前未接入C2PA认证，不签发真实可信凭证。")
    if st.session_state.get("review_result"):
        r=st.session_state["review_result"]
        a,b=st.columns(2)
        a.metric("补证前",r.get("before_verdict_label","未知"))
        b.metric("补证后",r.get("after_verdict_label","未知"))
        render_report(r)

elif page == "证据档案":
    st.title("证据档案")
    st.caption("本次会话的核验记录、工具调用与处理依据。")
    history=st.session_state.get("reports",{})
    if not history:
        st.info("暂无记录。完成一次内容核验后，报告会出现在这里。")
    else:
        chosen=st.selectbox("核验记录",list(history),format_func=lambda k:f"{history[k].get('report',{}).get('trust_card',{}).get('verdict_label','报告')} · {k}")
        render_report(history[chosen])
        with st.expander("完整结构化记录"):
            st.json(history[chosen])

elif page == "文案与功效":
    render_member4()

else:
    st.title("评测工作台")
    st.caption("可复跑的测试结果与数据边界。")
    test_tab,data_tab,collection_tab=st.tabs(["真实输出评测","配对数据与视觉样例","志愿者采集"])
    with test_tab:
        render_evaluation()
        path=ROOT/"data/member4_evaluation.json"
        if path.exists():
            report=json.loads(path.read_text(encoding="utf-8"))
            a,b,c=st.columns(3)
            test = report['datasets']['Test Set']
            blind = report['datasets']['Blind Test']
            a.metric("测试题完全匹配",f"{test['exact_match_count']} / {test['count']}")
            b.metric("原盲测题复测匹配",f"{blind['exact_match_count']} / {blind['count']}")
            c.metric("原盲测集复测 F1",f"{report['datasets']['Blind Test']['micro_f1']:.3f}")
            st.caption("这些题目已参与迭代，不是新的独立盲测；仅评价宣称集合，不涵盖OCR、极性、时长、证据支持或图像检测准确率。")
            for name,metrics in report["datasets"].items():
                with st.expander(name):
                    st.dataframe(metrics["cases"],hide_index=True)
        st.subheader("能力边界")
        st.dataframe([{"模块":k,"状态":v} for k,v in [("OCR / EXIF","本地真实处理"),("宣称提取","新版词典与确定性规则"),("功效资料","交付品牌资料，未在线复核"),("图像鉴伪 / 前后对比","真实模型；跨域性能及因果解释受限"),("C2PA","尚未接入")]],hide_index=True)
    with data_tab:
        render_team_deliverables()
        with st.expander("采集与标注模板"):
            labels = ROOT / "data/annotations/label_template.csv"
            st.download_button("下载标注模板",labels.read_bytes(),file_name="label_template.csv",mime="text/csv",icon=":material/download:")
            st.json(json.loads((ROOT/"data/dataset_manifest.json").read_text(encoding="utf-8")))
    with collection_tab:
        render_collection()

st.markdown('<div class="footer">TrueGlow 映真 · 内容信任源于证据</div>',unsafe_allow_html=True)
