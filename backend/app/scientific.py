from __future__ import annotations
from math import pi, exp


def horton_infiltration_mmhr(f0: float, fc: float, k: float, t_hr: float) -> float:
    if min(f0, fc, k) < 0:
        raise ValueError("Horton parameters must be non-negative")
    if f0 < fc:
        raise ValueError("Horton f0 must be >= fc")
    return max(fc, fc + (f0 - fc) * exp(-k * max(0.0, t_hr)))


def manning_full_flow_capacity(diameter_m: float, slope: float, roughness: float) -> float:
    if diameter_m <= 0 or slope <= 0 or roughness <= 0:
        return 0.0
    area = pi * diameter_m**2 / 4.0
    hydraulic_radius = diameter_m / 4.0
    return (1.0 / roughness) * area * hydraulic_radius ** (2.0 / 3.0) * slope ** 0.5


def mmhr_to_m3s(intensity_mmhr: float, area_m2: float) -> float:
    return max(0.0, intensity_mmhr) / 1000.0 / 3600.0 * max(0.0, area_m2)


def rainfall_depth_m3(intensity_mmhr: float, area_m2: float, minutes: float) -> float:
    return max(0.0, intensity_mmhr) / 1000.0 * max(0.0, area_m2) * minutes / 60.0
