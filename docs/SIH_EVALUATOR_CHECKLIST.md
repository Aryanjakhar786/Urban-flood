# SIH evaluator checklist — v8

## Claims we can defend
- Physics-first transparent MVP.
- Horton infiltration on pervious area.
- Manning-based pipe capacity.
- Explicit water-volume continuity audit.
- Bidirectional surface/drainage coupling through surcharge spill.
- ETA-aware route scoring on forecast arrival depth.
- Calibration updates model parameters rather than forcing observations.
- SWMM reference-input export.
- Live-data adapter with provenance and explicit unit normalization.

## Claims we should NOT make yet
- “Scientifically validated accuracy of X%” — no observed validation dataset is bundled.
- “Full 2-D hydraulic solver” — the surface layer is lumped.
- “SWMM is executing inside the app” — export is provided; runtime is external.
- “Live IMD data is connected” unless an authorized endpoint is configured and returns a fresh, normalized value.
- “Municipality deployed” without municipal authorization, GIS, sensors and infrastructure access.

## Demo sequence
1. Start in DEMO mode.
2. Select 140–180 mm/hr scenario.
3. Advance 5-minute steps.
4. Show spatially varying rainfall and rising surface depth.
5. Open a drainage bottleneck and show Flood Debt/surcharge.
6. Compare baseline and ETA-aware route.
7. Submit a mock observation and show parameter update.
8. Open Model Transparency and SWMM reference input.
