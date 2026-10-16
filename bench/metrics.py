"""Derived quantities and per-device gates (docs/plan-bench.md §8).

Both sides' spectra go through the same functions here, so every derived number
(coupling ratio, imbalance, ring resonance wavelength, FSR, Q, extinction) is
extracted identically for Meep and for etalon. Runs in etalon's environment only.

S arrays are complex, indexed by wavelength; keys are "S<out><in>" (point2d: "T21").
"""

import itertools
import math
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import curve_fit
from scipy.signal import find_peaks

GATE = 0.01
"""|ΔS| < 1 %, made concrete per device in ``compare``."""
POINT2D_GATE = 1e-3
NEFF_GATE = 3e-3
"""Straight guide: |Δn_eff| implied by the S21 phase over the port spacing L,

    Δn_eff = |arg(S21_e / S21_m)| / (2π L / λ),

must stay below Meep's own discretisation error at resolution 50 (pilot P4: Meep's
phase moves 0.13 rad over 10 µm, Δn_eff 3.1e-3, from 20 nm to 10 nm cells). The
wrapped phase assumes |Δn_eff| < λ / (2L), i.e. < 0.075 for L = 10 µm."""
DECAY_LIMIT = 1e-5
"""A run whose output-port field has not decayed below this (energy) is not converged."""


@dataclass(frozen=True)
class Metric:
    name: str
    value: float | None
    """None when it cannot be computed (e.g. a resonance missing on one side)."""
    gate: float | None = None
    """Pass when value < gate; None for metrics that are reported, not gated."""
    unit: str = ""

    @property
    def passed(self) -> bool | None:
        if self.gate is None:
            return None
        return self.value is not None and math.isfinite(self.value) and self.value < self.gate


@dataclass(frozen=True)
class Resonance:
    wavelength: float
    """Centre of the Airy line fitted to the drop-port peak, µm."""
    fwhm: float
    """Full width at half maximum of that line, µm."""
    drop_peak: float
    """Fitted peak drop-port power |S31|²."""
    t_min: float
    """Smallest through-port power |S21|² within ±FWHM/2 of the resonance."""
    t_max: float
    """Off-resonance through-port power: the largest |S21|² in the band."""

    @property
    def q(self) -> float:
        """Loaded quality factor λ0 / FWHM."""
        return self.wavelength / self.fwhm

    @property
    def extinction_db(self) -> float:
        """10 log10(t_max / t_min) at the through port."""
        return 10.0 * math.log10(self.t_max / max(self.t_min, 1e-30))


@dataclass
class Comparison:
    metrics: list[Metric]
    max_abs_s: float
    """max over the band and the shared S entries of | |S_e| − |S_m| |: the headline."""
    details: dict[str, object] = field(default_factory=dict)


def power(s: np.ndarray) -> np.ndarray:
    return np.asarray(np.abs(s) ** 2, dtype=float)


def imbalance_db(s_a: np.ndarray, s_b: np.ndarray) -> np.ndarray:
    """10 log10(|S_a|² / |S_b|²), dB."""
    return np.asarray(10.0 * np.log10(power(s_a) / power(s_b)), dtype=float)


def coupling_ratio(through: np.ndarray, cross: np.ndarray) -> np.ndarray:
    """|S_cross|² / (|S_through|² + |S_cross|²)."""
    return np.asarray(power(cross) / (power(through) + power(cross)), dtype=float)


def airy(
    wl: np.ndarray, peak: float, center: float, fsr: float, f_coef: float, floor: float
) -> np.ndarray:
    """Drop-port line shape of a ring: peak / (1 + F sin²(π(λ − λ0)/FSR)) + floor.

    The resonator transfer function in the Fabry–Pérot form, written locally in
    wavelength (FSR treated as constant across one fit window). Unlike a Lorentzian it
    includes the neighbouring resonances, so their tails do not bias λ0 or the width.
    """
    return floor + peak / (1.0 + f_coef * np.sin(np.pi * (wl - center) / fsr) ** 2)


def airy_fwhm(fsr: float, f_coef: float) -> float:
    """Full width at half maximum of ``airy``: (2 FSR/π) arcsin(1/√F)."""
    return 2.0 * fsr / np.pi * math.asin(min(1.0, 1.0 / math.sqrt(f_coef)))


def find_resonances(
    wl: np.ndarray, drop_power: np.ndarray, through_power: np.ndarray
) -> list[Resonance]:
    """Resonances fully inside the band, from Airy fits to the drop-port peaks.

    Each peak is fitted over half the spacing to its neighbours on either side; peaks
    closer than one FWHM to a band edge are skipped. At least two peaks are needed (the
    FSR enters the line shape).
    """
    step = float(wl[1] - wl[0])
    peaks, _ = find_peaks(drop_power, prominence=0.2 * float(np.max(drop_power)))
    if len(peaks) < 2:
        return []
    spacing = float(np.mean(np.diff(wl[peaks])))
    t_max = float(np.max(through_power))
    found = []
    for i in peaks:
        half = 0.5 * drop_power[i]
        lo = i
        while lo > 0 and drop_power[lo] > half:
            lo -= 1
        hi = i
        while hi < wl.size - 1 and drop_power[hi] > half:
            hi += 1
        fwhm_est = max((hi - lo) * step, 2 * step)
        if wl[i] - fwhm_est < wl[0] or wl[i] + fwhm_est > wl[-1]:
            continue  # resonance not fully inside the band
        window = np.abs(wl - wl[i]) <= 0.5 * spacing
        f_guess = 1.0 / math.sin(math.pi * fwhm_est / (2.0 * spacing)) ** 2
        guess = (float(drop_power[i]), float(wl[i]), spacing, f_guess, 0.0)
        params, _ = curve_fit(airy, wl[window], drop_power[window], p0=guess, maxfev=20000)
        peak, center, local_fsr, f_coef, floor = params
        fwhm = airy_fwhm(abs(float(local_fsr)), float(f_coef))
        near = np.abs(wl - center) <= fwhm / 2
        t_min = float(np.min(through_power[near])) if near.any() else float(through_power[i])
        found.append(Resonance(float(center), fwhm, float(peak + floor), t_min, t_max))
    return found


def fsr(resonances: list[Resonance]) -> list[float]:
    """Spacings between adjacent resonances, µm."""
    centers = [r.wavelength for r in resonances]
    return [b - a for a, b in itertools.pairwise(centers)]


def max_abs_s(meep: dict[str, np.ndarray], etalon: dict[str, np.ndarray]) -> float:
    """The headline: max over shared entries and the band of | |S_e| − |S_m| |."""
    shared = sorted(set(meep) & set(etalon))
    if not shared:
        return float("nan")
    return float(max(np.max(np.abs(np.abs(etalon[k]) - np.abs(meep[k]))) for k in shared))


def compare(
    device: str,
    wl: np.ndarray,
    meep: dict[str, np.ndarray],
    etalon: dict[str, np.ndarray],
    length: float | None = None,
) -> Comparison:
    """Gated metrics for ``device`` (plan §8). ``length``: straight-guide port spacing, µm."""
    headline = max_abs_s(meep, etalon)
    if device == "point2d":
        value = float(np.max(np.abs(etalon["T21"] - meep["T21"])))
        return Comparison([Metric("max |ΔT21| (complex)", value, POINT2D_GATE)], headline)
    if device == "straight":
        s_e, s_m = etalon["S21"], meep["S21"]
        dphi = np.angle(s_e / s_m)
        dn = float(np.max(np.abs(dphi) / (2 * np.pi * length / wl))) if length else None
        metrics = [
            Metric(
                "max | |S21|e − |S21|m |", float(np.max(np.abs(np.abs(s_e) - np.abs(s_m)))), GATE
            ),
            Metric("max |Δn_eff| implied by the S21 phase", dn, NEFF_GATE),
            Metric("max |Δ arg S21|", float(np.max(np.abs(dphi))), unit="rad"),
            Metric("max |ΔS21| (complex)", float(np.max(np.abs(s_e - s_m)))),
        ]
        return Comparison(metrics, headline)
    if device == "bend":
        value = float(np.max(np.abs(np.abs(etalon["S21"]) - np.abs(meep["S21"]))))
        return Comparison([Metric("max | |S21|e − |S21|m |", value, GATE)], headline)
    if device == "dc":
        metrics = [
            Metric(f"max |Δ|{k}|²|", float(np.max(np.abs(power(etalon[k]) - power(meep[k])))), GATE)
            for k in ("S31", "S41")
        ]
        ratio = coupling_ratio(etalon["S31"], etalon["S41"]) - coupling_ratio(
            meep["S31"], meep["S41"]
        )
        metrics.append(Metric("max |Δ coupling ratio|", float(np.max(np.abs(ratio)))))
        return Comparison(metrics, headline)
    if device == "mmi":
        metrics = [
            Metric(f"max |Δ|{k}|²|", float(np.max(np.abs(power(etalon[k]) - power(meep[k])))), GATE)
            for k in ("S21", "S31")
        ]
        imbalance = imbalance_db(etalon["S21"], etalon["S31"]) - imbalance_db(
            meep["S21"], meep["S31"]
        )
        metrics.append(Metric("max |Δ imbalance|", float(np.max(np.abs(imbalance))), unit="dB"))
        return Comparison(metrics, headline)
    if device == "ring":
        return _compare_ring(wl, meep, etalon, headline)
    raise ValueError(f"no comparison defined for device {device!r}")


def _compare_ring(
    wl: np.ndarray, meep: dict[str, np.ndarray], etalon: dict[str, np.ndarray], headline: float
) -> Comparison:
    res_m = find_resonances(wl, power(meep["S31"]), power(meep["S21"]))
    res_e = find_resonances(wl, power(etalon["S31"]), power(etalon["S21"]))
    details: dict[str, object] = {"meep": res_m, "etalon": res_e}
    if not res_m or len(res_m) != len(res_e):
        missing = Metric("resonances found (Meep, etalon)", None, GATE)
        details["count"] = (len(res_m), len(res_e))
        return Comparison([missing], headline, details)
    fsr_m, fsr_e = fsr(res_m), fsr(res_e)
    scale = float(np.mean(fsr_m)) if fsr_m else float("nan")
    d_lambda = max(abs(e.wavelength - m.wavelength) for m, e in zip(res_m, res_e, strict=True))
    d_q = max(abs(e.q - m.q) / m.q for m, e in zip(res_m, res_e, strict=True))
    d_tmin = max(abs(e.t_min - m.t_min) for m, e in zip(res_m, res_e, strict=True))
    d_er = max(abs(e.extinction_db - m.extinction_db) for m, e in zip(res_m, res_e, strict=True))
    metrics = [
        Metric("max |Δλ_res| / FSR", d_lambda / scale if fsr_m else None, GATE),
        Metric(
            "max |ΔFSR| / FSR",
            max(abs(e - m) / m for m, e in zip(fsr_m, fsr_e, strict=True)) if fsr_m else None,
            GATE,
        ),
        Metric("max |ΔQ| / Q", d_q, GATE),
        Metric("max |Δ through-port min|S21|²|", d_tmin, GATE),
        Metric("max |Δ extinction|", d_er, unit="dB"),
    ]
    return Comparison(metrics, headline, details)
