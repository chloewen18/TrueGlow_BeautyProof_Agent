# BeautyProof API Spec

## Switch

`api/client.py` uses `USE_MOCK = True` for local demos. Change it to `False` when the backend is ready.

The real backend base URL is read from `BEAUTYPROOF_API_BASE_URL`; the default is `http://localhost:8000`.

## Verify Content

`POST /verify`

Form fields:

- `image`: uploaded image file
- `text`: content copy
- `product_name`: product name
- `user_need`: optional skin type or user need
- `case_id`: optional demo case ID, one of `case_a`, `case_b`, or `case_c_review`

Response:

```json
{
  "request_id": "req_case_b_001",
  "content_id": "content_case_b",
  "report": {
    "trust_card": {
      "verdict": "medium_risk",
      "verdict_label": "部分可疑",
      "main_findings": [],
      "sections": [],
      "creator_actions": [],
      "advanced": {}
    }
  }
}
```

## Submit Creator Evidence

`POST /creator/evidence`

Form fields:

- `content_id`: original content ID
- `original_request_id`: original verify request ID
- `original_file`: original image or video file
- `filter_info`: optional shooting, filter, beauty, lighting, and exposure notes

Response uses the same `report.trust_card` shape as `/verify`.

## Dataset Manifest

`GET /dataset/manifest`

Returns the current dataset version, folder layout, required labels, split policy, hard-negative list, and release checklist.

## Benchmark Summary

`GET /benchmark/summary`

Returns MVP benchmark metrics, target values, required demo case results, and user-test tasks.
