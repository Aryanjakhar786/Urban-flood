# Scientific Model Card — v8

## Scope
This is a fast, transparent SIH demonstrator. It is **not** a validated 1-D/2-D hydraulic solver. The production pathway is to calibrate this fast layer against an approved hydraulic reference workflow (for example, EPA SWMM) and observed municipal data.

## Hydrology
- Rainfall is represented as a 5-minute time series.
- Demo mode uses a deterministic moving spatial storm so every surface cell can receive a different intensity.
- Horton infiltration is applied only to the pervious fraction.
- All water quantities are tracked in SI units (m3).
- Surface water is converted to street depth using cell area.

## Surface storage
Each road has an explicit depression-storage parameter. The current lumped MVP keeps ponded water as surface state; the storage parameter is exposed for calibration and future surface-routing refinement. It does not claim 2-D flow routing.

## Hydraulics
Pipe capacity is bounded by configured capacity and Manning full-flow capacity. Network routing is a transparent lumped approximation. Surcharge above operational node storage spills through connected inlets back to surface; unresolved drainage storage is reported separately as **Flood Debt**.

## Flood Debt definition
**Flood Debt = drainage storage above operational capacity after available surcharge spill.**

It is intentionally separate from:
- Surface ponding (m3)
- Network storage (m3)
- Total unresolved water (m3)

This avoids mixing a diagnostic drainage metric with total surface flooding.

## Calibration
An observation creates a residual (observed - predicted) and updates inlet efficiency and roughness within bounded ranges. It does **not** directly add a depth bias or overwrite the physical state. Future forecasts therefore respond through model parameters.

## Data credibility
Live rainfall requires explicit deployment configuration for units:
- `mm/hr`, or
- accumulated `mm` plus accumulation period.

The provider response retains source, raw field/value, retrieval time, observation time when supplied, unit metadata, cache/stale status and a quality flag. Demo mode is never labelled LIVE.

## SWMM reference export
The API exports a more complete SWMM input containing:
- options / dynamic-wave routing
- junctions and outfall
- conduits and circular cross-sections
- rain gauge and 5-minute timeseries
- subcatchments
- subareas
- Horton infiltration parameters
- node coordinates
- continuity reporting

The export is a **reference input artifact**; this package does not claim to execute SWMM. Operational use requires a calibrated network, authorized data and an approved SWMM runtime/workflow.

## Validation
Accuracy metrics such as MAE, RMSE, bias, F1 and ETA error are intentionally not fabricated. They should be generated only after historical or municipal observations are paired with model forecasts.
