# Members 2/3 Integration

Imported on 2026-09-06, preserving all original delivery files.

- `data/datasets/FFHQ_FFHQR_100_pairs_v1/`: 100 pairs, 200 images.
- `data/deliverables/TruFor_交付物/`: four simulated scores and output maps.
- `backend/app/integrations/metadata_parser.py`: original EXIF parser.

Dataset validation passed: all 200 SHA256 hashes match the manifest; all
images decode at the declared resolution; 100 pairs contain one original
and one retouched image; each pair belongs to a single split (80/10/10).
This is pair isolation, not verified person-identity isolation.
Labels only support generic professional retouching, not individual
operations or intensity. Original dataset cards, provenance and licenses
remain alongside the images.

The Source Trace tool parses uploaded files using ExifRead and computes
SHA256. Uploaded references are constrained to the uploads directory.
EXIF presence does not establish metadata completeness or authenticity.
C2PA is unimplemented and reported as unknown (`error` in the existing
schema). Upload-based creator reviews do not issue credentials.
Legacy named demo fixtures still use simulated source evidence.

Read-only API endpoints:
- `/api/v1/deliverables/dataset`
- `/api/v1/deliverables/trufor?threshold=0.65`

The new frontend tab browses paired images and displays TruFor artifacts.
The four scores are suspiciousness scores (higher means more suspicious),
not the backend's integrity scores. They are not fed into live analysis.
At threshold 0.65, recalculation gives FPR=0% and TPR=100%; the delivered
report's FPR=50% is an arithmetic error. These are simulated sample
statistics, not measured TruFor accuracy. The package has no inference
script, weights, input originals or pixel masks. Real inference and
pixel-level evaluation cannot be completed from this delivery alone.

Run integration checks from the project root:
`python -m unittest discover -s tests -p test_member_deliverables.py`
