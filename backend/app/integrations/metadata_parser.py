import exifread
import json
import sys

def extract_metadata(image_path):
    """提取图片的 EXIF 元数据"""
    result = {
        "image_path": image_path,
        "exif": {},
        "has_metadata": False,
        "reliability": "low"
    }

    try:
        with open(image_path, 'rb') as f:
            tags = exifread.process_file(f, details=False)

        if tags:
            result["has_metadata"] = True
            result["reliability"] = "medium"
            for tag, value in tags.items():
                result["exif"][str(tag)] = str(value)
        else:
            result["exif"] = {"info": "无EXIF元数据"}

    except Exception as e:
        result["exif"] = {"error": str(e)}

    return result


def detect_c2pa_manifest(file_path):
    """检测文件中是否嵌入 C2PA / Content Credentials 清单（仅存在性检测）。

    只判断清单标记是否存在，**不验证签名链**，因此：
      - 检测到清单 ≠ 内容真实/未被修饰
      - 未检测到清单 ≠ 伪造（平台压缩/转码可能剥离清单）
    返回 {"status": "present" | "absent" | "unknown", "markers": [...], "detail": str}
    """
    try:
        with open(file_path, "rb") as f:
            head = f.read(4 * 1024 * 1024)  # 清单通常位于文件头部，读取前 4MB
    except OSError as exc:
        return {"status": "unknown", "markers": [], "detail": f"文件读取失败：{exc}"}

    markers = []
    # JPEG：APP11 段 + JUMBF superbox，标识符为 "c2pa\0"
    if b"\xff\xeb" in head and b"c2pa\x00" in head:
        markers.append("JPEG APP11 / c2pa JUMBF")
    # PNG：C2PA 规范使用 caBX chunk
    if b"caBX" in head:
        markers.append("PNG caBX chunk")
    # 兜底：XMP / JUMBF 中的 c2pa 命名空间（部分写入器不按标准段放置）
    if not markers and (b"urn:c2pa" in head or b"http://c2pa" in head or b"c2pa.actions" in head):
        markers.append("XMP / JUMBF c2pa 命名空间")

    if markers:
        return {
            "status": "present",
            "markers": markers,
            "detail": "检测到 Content Credentials 清单标记（仅存在性检测，未验证签名链）",
        }
    return {
        "status": "absent",
        "markers": [],
        "detail": "未检测到 C2PA/Content Credentials 清单标记（仅存在性检测）",
    }


if __name__ == "__main__":
    # 从命令行参数获取图片路径
    if len(sys.argv) < 2:
        print("用法: python metadata_parser.py <图片路径>")
        print("示例: python metadata_parser.py C:\\Users\\wangshuai\\Desktop\\test.jpg")
        sys.exit(1)
    
    image_path = sys.argv[1]
    result = extract_metadata(image_path)
    
    print(json.dumps(result, indent=2, ensure_ascii=False))