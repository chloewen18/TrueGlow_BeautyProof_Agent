# TruFor 官方模型使用参考（成员 2）

来源：grip-unina / TruFor（ICCV 2023）。官方代码与权重均可公开下载，许可为**非商业用途**（赛事已确认接受）。

## 1. 获取官方代码

```bash
git clone https://github.com/grip-unina/TruFor.git
```

（本仓库工作区已有副本：`../TruFor_train_test/`，含 LICENSE.txt、train/test/metrics/visualize 脚本与 backbone 权重。）

## 2. 下载最终权重

官方 README 要求另行下载训练好的模型：

```
下载地址：https://www.grip.unina.it/download/prog/TruFor/TruFor_weights.zip
校验 MD5：7bee48f3476c75616c3c5721ab256ff8
```

解压到 `pretrained_models/`，得到 `trufor.pth.tar`（约 100–200MB）。**没有这个文件，推理一行都跑不了。**

## 3. 运行推理

```bash
python test.py -in <图片或目录> -out <输出目录> \
  -exp trufor_ph3 TEST.MODEL_FILE "pretrained_models/trufor.pth.tar"
```

两个坑（官方脚本默认行为）：
- `test.py` 的 `except: pass` 会**静默吞掉异常**——跑失败不报错、输出目录为空。先改成 `raise` 跑通再改回。
- 默认走 GPU（`-g 0`）。无 CUDA 必须显式 `-g -1`。

## 4. 输出格式

输出为 `.npz` 文件，含 `map`（定位热力图）、`conf`（置信度图）、`score`（标量，越高越可疑）、`np++`（noiseprint++ 特征）、`imgsize`。
可视化用 `visualize.py` 转成图片。`map` 与 `conf` 是**两个不同数组**——这正好能验证旧模拟交付物有多离谱（它那两张 PNG 是同一个文件复制的）。

## 5. 不要训练

完整训练需要 tampCOCO / compRAISE / FantasticReality / CASIA 2.0 / IMD2020（几十 GB）+ 两阶段多 GPU 训练数天，30 天内不现实。**直接用官方权重做 inference**——这正符合原方案「基于已有模型做 inference」的路线。

## 6. 许可与声明

LICENSE.txt 原文：*"This work should only be used for nonprofit purposes."*
答辩时须在文档中写明：使用了 TruFor 官方权重做图像篡改检测，来源与许可范围。
