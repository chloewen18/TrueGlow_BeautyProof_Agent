"""Live HTTP verification of uploads, real inference, artifacts, OCR and review."""
import argparse
import json
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base = args.url
    def upload(path):
        with path.open("rb") as file:
            result = requests.post(base+"/api/v1/upload", files={"files":(path.name,file,"image/png")}, timeout=60)
        result.raise_for_status()
        return {"kind":"image", "ref":result.json()["uploaded"][0]["media_ref"]}
    before = upload(ROOT/"data/datasets/FFHQ_FFHQR_100_pairs_v1/originals/00001.png")
    after = upload(ROOT/"data/datasets/FFHQ_FFHQR_100_pairs_v1/retouched/00001.png")
    response = requests.post(base+"/api/v1/verify",json={"content_id":"integration_real_pair", "content":{
        "media":[after], "before_after":{"before":before,"after":after}, "body_text":"中等遮瑕，很服帖，原相机",
        "product":"L'Oréal Paris True Match Super-Blendable Foundation"}}, timeout=600)
    data = response.json()
    assert data["status"] == "success", data
    result = data["result"]
    assert all(c["status"] == "success" for c in result["report"]["tool_calls"]), result["report"]["tool_calls"]
    assert all(c["model"] != "mock" for c in result["report"]["tool_calls"])
    visual = result["report"]["evidence"]["visual_evidence"]["raw"]
    assert abs(visual["trufor_score"]+visual["integrity_score"]-1) < 1e-8
    artifacts = [visual["manipulation_map"],visual["reliability_map"]]
    pair = result["report"]["evidence"]["before_after_evidence"]["raw"]
    assert pair["attribution_strength"] == "Unknown"
    assert pair["difference"]["status"] == "success", pair["difference"]
    artifacts.append(pair["difference"]["map"])
    for reference in artifacts:
        asset = requests.get(base+reference["value"], timeout=30)
        assert asset.status_code == 200 and asset.content.startswith(b"\x89PNG")
    screenshot = upload(ROOT/"member4_text/deliverables/v2/demo/test.PNG")
    ocr = requests.post(base+"/api/v1/member4/ocr",json={"media_ref":screenshot["ref"]}, timeout=300)
    assert ocr.status_code == 200 and ocr.json()["text"], ocr.text
    review = requests.post(base+"/api/v1/creators/review",json={"content_id":result["content_id"],
        "original_request_id":result["request_id"],"creator_submission":{"original_file":[before]}},timeout=600).json()
    assert review["status"] == "success", review
    assert review["result"]["credential"] is None
    assert all(c["status"] == "success" for c in review["result"]["report"]["tool_calls"])
    folder = ROOT/"data/evaluation_runs/live_http"
    folder.mkdir(parents=True,exist_ok=True)
    for name,value in [("verify",result),("review",review["result"]),("ocr",ocr.json())]:
        (folder/f"{name}.json").write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"status":"passed","request_id":result["request_id"],"calls":result["report"]["tool_calls"],
                      "pair_difference":pair["difference"]["status"],"ocr_characters":len(ocr.json()["text"])},ensure_ascii=False))


if __name__ == "__main__":
    main()
