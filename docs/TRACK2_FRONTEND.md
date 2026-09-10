# Track 2 Frontend

Primary workflow: content submission, multimodal evidence, risk explanation,
creator review, traceable report. Research resources live in a separate
evaluation workspace. The homepage opens the actual verification tool.

Navigation:
- Content verification: images, OCR, text, optional before image and comments.
- Creator review: associate a report and submit original material.
- Evidence archive: current-session reports and JSON exports.
- Claims and efficacy: dictionary analysis, product-scoped brand evidence.
- Evaluation workspace: rerun metrics, paired dataset, visual demo artifacts.

Uploaded analysis no longer injects Case A/B signals. Legacy simulated cases
remain explicitly selectable. The underlying visual tools are still mocks;
the UI does not represent their results as live forensic verification.
No actual C2PA certificate is issued. Records shown in the archive are
session-local; backend evidence remains on disk.

Design: the original dark atelier palette, muted gold accents and original
typography, adapted to a compact sidebar and the new functional sections.
`styles/theme.css` remains the original visual source; `styles/workbench.css`
only adapts the new layout. This preserves the user's preferred visual style.
Previous app/CSS snapshots are in `.integration/`.

Run the new frontend on port 8503 (8502 was already occupied):
`python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8503`

Requirement context: user-provided track description and public competition
summary at https://www.competehub.dev/zh/competitions/tianchi532496 .
Official entry: https://tianchi.aliyun.com/competition/entrance/532496 .
The official dynamic page did not expose full rules during this run; no
unverified scoring rubric has been claimed as an official requirement.
