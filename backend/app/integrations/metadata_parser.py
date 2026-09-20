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

if __name__ == "__main__":
    # 从命令行参数获取图片路径
    if len(sys.argv) < 2:
        print("用法: python metadata_parser.py <图片路径>")
        print("示例: python metadata_parser.py C:\\Users\\wangshuai\\Desktop\\test.jpg")
        sys.exit(1)
    
    image_path = sys.argv[1]
    result = extract_metadata(image_path)
    
    print(json.dumps(result, indent=2, ensure_ascii=False))