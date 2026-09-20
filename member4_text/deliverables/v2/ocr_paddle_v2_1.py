import argparse, json, tempfile
from pathlib import Path
from difflib import SequenceMatcher
import cv2
from paddleocr import PaddleOCR

def norm(s):
    return "".join(c for c in s if not c.isspace())

def zh_ratio(s):
    t=[c for c in s if not c.isspace()]
    return sum("\u4e00" <= c <= "\u9fff" for c in t)/len(t) if t else 0.0

def make_variants(image):
    h,w=image.shape[:2]
    y1,y2=int(h*0.58),int(h*0.78)
    x1,x2=int(w*0.03),int(w*0.97)
    crop=image[y1:y2,x1:x2]
    big=cv2.resize(crop,None,fx=3.0,fy=3.0,interpolation=cv2.INTER_CUBIC)
    gray=cv2.cvtColor(big,cv2.COLOR_BGR2GRAY)
    clahe=cv2.createCLAHE(clipLimit=2.5,tileGridSize=(8,8))
    enh=clahe.apply(gray)
    binary=cv2.adaptiveThreshold(enh,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,31,7)
    return {"enhanced":enh,"original":crop,"binary":binary},(x1,y1,x2,y2)

def parse_json(path, source):
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    res=data.get("res",data)
    texts=res.get("rec_texts",[]) or []
    scores=res.get("rec_scores",[]) or []
    out=[]
    for i,t in enumerate(texts):
        t=str(t).strip()
        if not t: continue
        score=float(scores[i]) if i<len(scores) else 0.0
        out.append({"text":t,"confidence":round(score,4),"source":source,"chinese_ratio":round(zh_ratio(t),3)})
    return out

def run_one(ocr,img,source,tmp):
    p=Path(tmp)/f"{source}.png"
    cv2.imwrite(str(p),img)
    out=[]
    for i,res in enumerate(ocr.predict(str(p))):
        jp=Path(tmp)/f"{source}_{i}.json"
        res.save_to_json(str(jp))
        out.extend(parse_json(jp,source))
    return out

def quality(x):
    s=x["confidence"]+x["chinese_ratio"]*0.12
    s += {"enhanced":0.05,"original":0.04,"binary":0.01}.get(x["source"],0)
    L=len(norm(x["text"]))
    if 5<=L<=20: s+=0.06
    elif L<=2: s-=0.12
    return s

def sim(a,b):
    return SequenceMatcher(None,norm(a),norm(b)).ratio()

def clean(lines):
    lines=[x for x in lines if len(norm(x["text"]))>1]
    groups=[]
    for item in lines:
        for g in groups:
            if any(sim(item["text"],z["text"])>=0.62 for z in g):
                g.append(item); break
        else:
            groups.append([item])
    best=[]
    for g in groups:
        b=max(g,key=quality).copy()
        b["quality_score"]=round(quality(b),4)
        b["merged_candidates"]=[z["text"] for z in g]
        best.append(b)
    best.sort(key=lambda x: (x["chinese_ratio"]>=0.6 and len(norm(x["text"]))>=4, x["quality_score"]), reverse=True)
    return best

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--image",required=True)
    p.add_argument("--out",default="OCR_Result_v2_1.json")
    p.add_argument("--txt",default="OCR_Result_v2_1.txt")
    p.add_argument("--preview",default="OCR_Subtitle_Crop_v2_1.png")
    a=p.parse_args()
    image=cv2.imread(a.image)
    if image is None: raise ValueError(f"Cannot read image: {a.image}")
    variants,region=make_variants(image)
    cv2.imwrite(a.preview,variants["original"])
    ocr=PaddleOCR(use_doc_orientation_classify=False,use_doc_unwarping=False,use_textline_orientation=False)
    with tempfile.TemporaryDirectory() as td:
        lines=[]
        for name in ["enhanced","original","binary"]:
            lines.extend(run_one(ocr,variants[name],name,td))
    cleaned=clean(lines)
    text="\n".join(x["text"] for x in cleaned)
    result={"tool_name":"ocr_extraction","version":"v2.1_paddleocr_clean","input":{"image_path":a.image},"output":{"language":"zh+en","subtitle_region":{"x1":region[0],"y1":region[1],"x2":region[2],"y2":region[3]},"extracted_text":text,"lines":cleaned}}
    Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    Path(a.txt).write_text(text,encoding="utf-8")
    print(json.dumps({"status":"success","version":"v2.1_paddleocr_clean","cleaned_lines":len(cleaned),"output_file":a.out,"txt_file":a.txt,"preview_file":a.preview},ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
