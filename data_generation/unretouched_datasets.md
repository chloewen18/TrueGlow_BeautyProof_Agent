# 无磨皮人像数据源清单

> 目标：找到 **完全没有数字磨皮/美颜/皮肤平滑** 的人像原图，作为 Hard-Negative 模块的 clean base。

## 第一推荐：MIT-Adobe FiveK

- **规模**：5,000 张 RAW 照片
- **来源**：单反相机直出（DNG 格式）
- **优势**：RAW 保留了传感器原始信息，未经过局部修图/磨皮；仅有 5 位专家的全局调色版本
- **适合场景**：hard-negative 原图、曝光/HDR 扰动基图
- **下载**：https://groups.csail.mit.edu/graphics/fivek_dataset/
- **许可证**：研究用途，需查看 LicenseAdobeMIT.txt / LicenseAdobe.txt
- **注意**：需要 DNG → JPG 转换；筛选 `subject=people` 的图像

## 第二推荐：FFHQ in-the-wild images

- **规模**：70,000 张原始 Flickr 图像
- **来源**：Flickr 用户上传，经过 NVIDIA 过滤
- **优势**：分辨率高、多样性好、人像数量大
- **适合场景**：模拟社交媒体原图
- **下载**：https://github.com/NVlabs/ffhq-dataset
- **许可证**：CC BY-NC-SA 4.0（非商业可用）
- **注意**：**不能 100% 保证无修图**，需要人工抽检；优先选择 `in-the-wild-images`，不要选 `images1024x1024`（后者是算法对齐裁剪版）

## 第三推荐：DPED（DSLR Photo Enhancement Dataset）

- **规模**：22,000+ 张同步拍摄照片
- **来源**：iPhone 3GS / BlackBerry / Sony 手机 + Canon 70D 单反
- **优势**：真实手机直出，无美颜算法；非常适合模拟“社交平台上传图”
- **适合场景**：JPEG 压缩、resize、降噪、曝光扰动
- **下载**：http://dped-photos.vision.ee.ethz.ch
- **许可证**：研究用途
- **注意**：不全是人像，需要筛选含有人脸的子集

## 备选：自己拍摄（最可靠）

- **方案**：5 人每人用手机原生相机拍 10-12 张人像
- **要求**：
  - 关闭所有美颜、滤镜、人像模式
  - 光线自然，包含正面/侧面/逆光/侧光
  - 皮肤纹理可见
- **优势**：完全可控、无版权风险
- **缺点**：多样性受限

## 不太推荐的数据集

| 数据集 | 不推荐原因 |
|--------|-----------|
| CelebA / CelebA-HQ | 名人照片常被媒体/官方修图 |
| LFW | 新闻照片，可能经过后期处理 |
| PubFig | 网络抓取，修图情况不明 |
| RetouchingFFHQ / MDRF / FFHQR | 这些是“修过”的数据集，不能作为 hard-negative 原图 |

## 推荐组合策略

1. **主要来源**：MIT-Adobe FiveK RAW 中筛选人像（约 500-800 张可用）
2. **补充来源**：DPED 手机照片（筛选人像）
3. **多样性补充**：FFHQ in-the-wild 人工抽检
4. **可控基线**：团队自拍照 50-60 张

## 人工核验标准

无论来源何处，每张进入 hard-negative 集合的原图必须满足：

1. [ ] 无皮肤平滑/磨皮痕迹
2. [ ] 毛孔、细纹、皮肤纹理可见
3. [ ] 无过度液化/瘦脸
4. [ ] 不是 AI 生成图像
5. [ ] 保留原始拍摄的光影、噪点、压缩特征

> 人工核验是**不可跳过**的环节，AI 只能辅助生成扰动，无法替代人眼判断“是否磨皮”。
