# Local Integration

Upstream: https://github.com/chloewen18/TrueGlow_BeautyProof_Agent
Imported snapshot: c7fe2ed (2026-09-06), via GitHub API archive.

Member 1 code is in `backend/`; original docs and schemas are in
`docs/member1/` and `schemas/member1/`. Existing frontend, styles, datasets
and evaluation pages are retained. This folder is not a Git clone.

From the project root, install and start in two terminals:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

```powershell
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8502
```

Frontend: http://127.0.0.1:8502
API docs: http://127.0.0.1:8000/docs

The frontend defaults to the Main Agent HTTP API. Set
`BEAUTYPROOF_API_BASE_URL` if changing the backend port.
`BEAUTYPROOF_USE_MOCK=true` restores the old static frontend fixtures.
`api/server.py` remains the legacy mock service; do not start it on the
same port as the Main Agent.

Uploaded-file source tracing now parses real EXIF; C2PA remains unimplemented.
Visual detection tools are still upstream mocks. Case A/B use upstream
simulation signals. Uploads are saved under `backend/data/uploads`, with
evidence and logs alongside them. Creator review submits uploaded file
references; it does not inject the predetermined Case C recheck.
Review conclusions may therefore remain unchanged. The upstream three-case
demo includes that simulated recheck and can be run from `backend/` with
`python -m demo.run_demo`.

No API key is needed for local rule-based demonstration. DeepSeek is optional;
consult `.env.example`. Configuring it does not replace the mock detectors.
