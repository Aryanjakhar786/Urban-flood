# Engineering review log — v9

1. Unit audit — all rainfall/volume conversions use SI units.
2. Horton audit — infiltration is restricted to the pervious fraction.
3. Surface audit — street depth is derived from physical surface volume.
4. Storage audit — depression-storage parameter is explicit; ponded water remains a measurable state.
5. Flood Debt audit — drainage debt is separated from surface ponding and total unresolved water.
6. Surcharge audit — spill is recorded separately and is never simultaneously counted as drainage debt.
7. Calibration audit — observations update bounded physical parameters; no direct depth overwrite.
8. Forecast audit — cloned simulations restore live clock/state even if an exception occurs.
9. Routing audit — road arrival times are cumulative and rounded to the 5-minute forecast grid.
10. Rainfall provenance audit — live mode requires explicit rainfall units/accumulation configuration.
11. SWMM audit — export now includes hydraulic, subcatchment, infiltration, rainfall time series and coordinates sections; execution is not falsely claimed.
12. Regression tests — 15/15 pass.
13. Surface-storage refinement — inlet capture is limited to ponded water above depression storage; rainfall still accumulates during road closure.
14. Validation honesty — validation endpoint reports NO_OBSERVATIONS until verified observations exist and then computes MAE/RMSE/bias only from supplied observations.
15. SWMM structure audit — corrected SUBAREAS fields and retained explicit external-runtime boundary.
16. Regression expansion — 19/19 tests pass after the storage and SWMM audits.
