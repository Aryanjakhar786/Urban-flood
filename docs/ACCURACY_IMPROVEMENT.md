# Accuracy Improvement Protocol — v10

This release improves *calibratability and validation*, not by inventing an accuracy percentage.

## What changed
- Bounded calibration over inlet-efficiency and Manning-roughness scale factors.
- Chronological holdout validation to reduce overfitting.
- Empirical residual-based uncertainty once at least five observations exist.
- MAE, RMSE and bias remain tied to actual observed water-level records.
- Calibration changes physical parameters; it never overwrites predicted depth.

## Why this is more credible
A model can only claim empirical accuracy when paired with observed data. With no observations, the system reports `NO_OBSERVATIONS` rather than manufacturing a score. With observations, the calibration routine searches a small, transparent parameter space and evaluates a later chronological holdout set.

## Production path
For a municipal pilot, ingest historical rainfall + observed water levels, split by storm event (not random rows), calibrate on earlier events, validate on unseen events, and report uncertainty plus MAE/RMSE/bias. A validated hydraulic reference such as SWMM Dynamic Wave should be used for network benchmarking.
