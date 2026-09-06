# Street-Level Urban Flood Digital Twin — Scientific MVP v10

SIH PS 26085 demonstrator: **Rainfall → Runoff → Inlet → Drainage → Surcharge → Flood Debt → Street Depth → ETA-aware Route**.

## What is improved in v10
- Horton infiltration restricted to pervious area.
- Explicit SI-unit water balance and continuity audit.
- Separate surface ponding, drainage debt (Flood Debt), network storage and total unresolved water.
- Explicit road-to-inlet-to-node connections.
- Deterministic moving spatial rainfall for reproducible demo scenarios.
- Manning-based transparent pipe capacity.
- Parameter-only calibration from observations; no direct depth override.
- Arrival-time flood depth in route scoring.
- Complete inspectable SWMM reference input export (execution remains external).
- Live rainfall adapter with explicit unit/accumulation metadata and stale/cache provenance.
- Model card and SIH evaluator checklist.

## Scientific honesty
This is a **lumped surface-cell MVP**, not a validated 2-D hydraulic solver. SWMM is a reference workflow/export boundary, not an engine claimed to be executing in this package. No predictive accuracy percentage is fabricated.

## Run
```bash
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload
```
Open `http://127.0.0.1:8000`.

## Tests
```bash
pytest -q
```
Expected: **22 passed**.

## Live rainfall
Set `RAINFALL_MODE=imd` only after authorized endpoint access is available. Configure `IMD_RAINFALL_UNIT` explicitly. If the provider returns accumulated mm, also set `IMD_RAINFALL_ACCUMULATION_MINUTES`. The app refuses to normalize an unknown unit rather than silently treating it as mm/hr.

## Municipal pilot requirements
Authorized rainfall/nowcast, DEM, road/drain/inlet GIS, observed water levels, calibration/validation dataset, approved SWMM runtime/workflow, authentication, TLS, monitoring and backups.

See `docs/SCIENTIFIC_MODEL.md`, `docs/ITERATION_LOG.md`, and `docs/SIH_EVALUATOR_CHECKLIST.md`.


## Accuracy hardening
See `docs/ACCURACY_IMPROVEMENT.md`. The `/api/calibration` endpoint performs bounded parameter calibration with a chronological holdout when observations are available. Accuracy metrics are never fabricated.
