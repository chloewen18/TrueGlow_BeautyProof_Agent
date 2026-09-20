# Member 4 Full Pipeline Final

## 功能
成员4文本 / 评论 / 功效证据完整流水线。

处理流程：
图片 -> PaddleOCR文字识别 -> 妆效宣称提取与标准化 -> 功效证据匹配 -> 消费者解释 -> JSON结果

## 环境
推荐 Python 3.12。

## 安装
建议创建独立虚拟环境：

python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

## 运行
示例：

python full_pipeline_v1.py --image demo/test.PNG --out result.json

也可以指定产品：

python full_pipeline_v1.py --image demo/test.PNG --product "产品名称" --out result.json

## Demo验证
真实测试图片：demo/test.PNG

已验证输出：demo/Member4_Full_Result_v1.json

本次端到端测试成功：
OCR识别 -> Claim提取 -> Evidence匹配 -> JSON输出

示例中OCR识别到“然后鼻翼也没有干卡”，系统将其标准化为“不卡粉”。

## 主要文件
- full_pipeline_v1.py：完整流水线入口
- ocr_paddle_v2_1.py：OCR模块
- claim_extractor_mock_v2_1.py：宣称提取模块
- Foundation_Claim_Dictionary_V2_2_Separate_Slang_Exaggerated.xlsx：宣称词典
- Member4_Mini_Efficacy_Evidence_Library_v1.json：功效证据库
- requirements.txt：Python依赖
- demo/：真实测试输入与输出

## 说明
Evidence Library 当前为项目Demo证据库。若某条宣称没有匹配到证据，系统会返回未找到匹配证据，不应将其解释为该宣称已被证实或证伪。

## Efficacy Evidence Library V2

新增 `Member4_Mini_Efficacy_Evidence_Library_v2.json`，用于为粉底功效 Claim 提供结构化证据说明。

当前版本包含：
- 5 个粉底产品
- 19 条功效 Claim
- Evidence Strength（证据强度）
- Evidence Level CN（中文证据等级）
- Official Source（品牌官方来源名称、类型及 URL）
- Limitations（证据局限）
- Consumer Explanation（消费者可理解说明）

### Evidence interpretation

证据等级用于 Demo 中的信息排序和解释，不等同于独立医学或科学验证。

品牌官网产品声明属于品牌提供的信息；消费者测试虽然具有测试依据，但仍会受到样本构成、测试设计、使用环境和个体差异影响。

因此系统在展示功效 Claim 时，同时保留证据来源和局限说明，避免将品牌功效声明直接表述为普遍适用或独立科学验证的结论。
