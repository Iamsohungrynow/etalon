"""bench/config.yaml as validated models, plus every number derived from it.

Both sides import this module: the etalon side in etalon's environment and
bench/meep/run_device.py in the Meep environment. It depends on numpy, pydantic and
pyyaml only.

Unit conventions (docs/plan-bench.md §5):

* etalon: lengths in µm, time in s; ``courant`` is the fraction of the Courant limit.
* Meep, with its length unit a = 1 µm: frequency f = 1/λ[µm] in units of c/a; time in
  units of a/c = 3.33564 fs; Courant number S with cΔt = S·Δx. Since etalon's
  Δt = courant·Δx / (c·√D) on a uniform grid, the same Δt needs courant = S·√D.
* Pulse: etalon's GaussianPulse has spectral width σ_f = (f_hi − f_lo)/2, temporal
  width τ = 1/(2πσ_f) and delay t0 = 5τ. Meep's GaussianSource has envelope
  exp(−(t−t0)²/2w²) with w = 1/fwidth and t0 = cutoff·w, so fwidth = 2πσ_f (in c/a)
  and cutoff = 5 give both codes the same envelope and delay.
"""

import hashlib
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import yaml
from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, PositiveInt, model_validator

C_0 = 299_792_458.0
"""Speed of light in vacuum, m/s."""

MEEP_TIME_UNIT_FS = 1e-6 / C_0 * 1e15
"""Meep's time unit a/c for a = 1 µm, in fs (≈ 3.33564)."""

CONFIG_PATH = Path(__file__).with_name("config.yaml")

DeviceName = Literal["point2d", "straight", "bend", "dc", "mmi", "ring"]
DEVICE_NAMES: tuple[str, ...] = ("point2d", "straight", "bend", "dc", "mmi", "ring")

# A number of cells is accepted as whole when it is this close to an integer.
_CELL_TOLERANCE = 1e-6


class Model(BaseModel):
    """Immutable and typo-proof: an unknown key in config.yaml is an error, never ignored."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class Materials(Model):
    """Refractive indices, fixed (non-dispersive)."""

    si: PositiveFloat
    sio2: PositiveFloat


class Strip(Model):
    """Cross-section of every waveguide, µm."""

    width: PositiveFloat
    thickness: PositiveFloat


class Ports(Model):
    """Mode planes and the source plane, µm."""

    width: PositiveFloat
    height: PositiveFloat
    lead: PositiveFloat
    source_offset: PositiveFloat


class Band(Model):
    """Vacuum wavelengths sampled uniformly from min to max inclusive, µm."""

    min: PositiveFloat
    max: PositiveFloat
    points: int = Field(ge=2)

    @model_validator(mode="after")
    def _ordered(self) -> "Band":
        if not self.min < self.max:
            raise ValueError(f"band min {self.min} µm must be below max {self.max} µm")
        return self

    def wavelengths(self) -> np.ndarray:
        """The sampled wavelengths, µm."""
        return np.linspace(self.min, self.max, self.points)

    @property
    def center(self) -> float:
        """Centre wavelength (min + max)/2, µm: the source's wavelength."""
        return 0.5 * (self.min + self.max)

    @property
    def width(self) -> float:
        """max − min, µm: the source's bandwidth."""
        return self.max - self.min


class Region(Model):
    """In-plane simulation region (x, y), µm, PML excluded."""

    center: tuple[float, float]
    size: tuple[PositiveFloat, PositiveFloat]


class Device(Model):
    """What every device has."""

    region: Region
    band: Band
    run_time_fs: PositiveFloat


class Point2D(Device):
    """Device 0: Hz line source and two Hz probes in a homogeneous medium (2D only)."""

    medium: Literal["si", "sio2"]
    source: tuple[float, float]
    probes: tuple[tuple[float, float], tuple[float, float]]


class Straight(Device):
    length: PositiveFloat


class Bend(Device):
    radius: PositiveFloat


class DirectionalCoupler(Device):
    gap: PositiveFloat
    coupling_length: PositiveFloat
    sbend_length: PositiveFloat
    pitch: PositiveFloat


class MMI(Device):
    width: PositiveFloat
    length: PositiveFloat
    taper_width: PositiveFloat
    taper_length: PositiveFloat
    output_offset: PositiveFloat


class Ring(Device):
    radius: PositiveFloat
    gap: PositiveFloat
    straight_x: PositiveFloat
    straight_y: PositiveFloat


class Devices(Model):
    point2d: Point2D
    straight: Straight
    bend: Bend
    dc: DirectionalCoupler
    mmi: MMI
    ring: Ring


class Tier(Model):
    """One set of numerics: dimensionality, grid, PML, time step and its devices."""

    dims: Literal[2, 3]
    resolution: PositiveInt
    """Pixels per µm in both codes."""
    pml: PositiveFloat
    """PML thickness, µm (inside Meep's cell, outside etalon's region)."""
    courant_meep: float = Field(gt=0.0)
    """Meep's Courant number S."""
    core_index: PositiveFloat | None = None
    """2D only: the effective index that stands in for the Si strip."""
    z_span: PositiveFloat | None = None
    """3D only: region extent along z, centred on the strip, µm."""
    devices: tuple[DeviceName, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _consistent(self) -> "Tier":
        if self.dims == 2 and (self.core_index is None or self.z_span is not None):
            raise ValueError("a 2D tier needs core_index and no z_span")
        if self.dims == 3 and (self.z_span is None or self.core_index is not None):
            raise ValueError("a 3D tier needs z_span and no core_index")
        if self.dims == 3 and "point2d" in self.devices:
            raise ValueError("point2d is a 2D device; it cannot be in a 3D tier")
        if len(set(self.devices)) != len(self.devices):
            raise ValueError(f"devices repeats a name: {self.devices}")
        limit = 1.0 / math.sqrt(self.dims)
        if self.courant_meep > limit:
            raise ValueError(
                f"courant_meep = {self.courant_meep} exceeds the {self.dims}D vacuum stability "
                f"limit S ≤ 1/√{self.dims} = {limit:.4f}"
            )
        whole_cells("pml", self.pml, self.resolution)
        if self.z_span is not None:
            even_cells("z_span", self.z_span, self.resolution)
        return self

    @property
    def dl(self) -> float:
        """Cell size Δ = 1/resolution, µm."""
        return 1.0 / self.resolution

    @property
    def courant_etalon(self) -> float:
        """etalon's courant (fraction of the limit) giving Meep's Δt: S·√D."""
        return self.courant_meep * math.sqrt(self.dims)

    @property
    def pml_layers(self) -> int:
        """etalon PML layers = pml · resolution."""
        return whole_cells("pml", self.pml, self.resolution)


class EtalonSettings(Model):
    precision: Literal["single", "double"]
    cpu_full_run_max_minutes: PositiveFloat


class MeepSettings(Model):
    processes: PositiveInt


class BenchConfig(Model):
    """The whole of bench/config.yaml."""

    version: Literal[1] = Field(alias="schema")
    materials: Materials
    strip: Strip
    ports: Ports
    curve_tolerance: PositiveFloat
    tiers: dict[str, Tier]
    etalon: EtalonSettings
    meep: MeepSettings
    devices: Devices

    @model_validator(mode="after")
    def _on_grid(self) -> "BenchConfig":
        """Region centres on nodes, extents even in cells, point2d source and probes on Hz nodes."""
        for tier_name, tier in self.tiers.items():
            for name in tier.devices:
                device = self.device(name)
                where = f"tiers.{tier_name}: devices.{name}"
                region = device.region
                for axis, center, size in zip("xy", region.center, region.size, strict=True):
                    whole_cells(f"{where}.region.center ({axis})", center, tier.resolution)
                    even_cells(f"{where}.region.size ({axis})", size, tier.resolution)
                if isinstance(device, Point2D):
                    points = {"source": device.source, "probes[0]": device.probes[0]}
                    points["probes[1]"] = device.probes[1]
                    for label, point in points.items():
                        for axis, value in zip("xy", point, strict=True):
                            # Hz nodes sit half a cell off the integer nodes
                            whole_cells(
                                f"{where}.{label} ({axis}) − Δ/2",
                                value - 0.5 * tier.dl,
                                tier.resolution,
                            )
        return self

    def tier(self, name: str) -> Tier:
        """The tier called ``name``, with a helpful error for a wrong name."""
        if name not in self.tiers:
            raise ValueError(f"unknown tier {name!r}; config.yaml defines {sorted(self.tiers)}")
        return self.tiers[name]

    def device(self, name: str) -> Device:
        """The device section called ``name``."""
        if name not in DEVICE_NAMES:
            raise ValueError(f"unknown device {name!r}; devices are {', '.join(DEVICE_NAMES)}")
        device: Device = getattr(self.devices, name)
        return device

    def device_spec(self, tier: str, device: str) -> dict[str, Any]:
        """Every input a run of ``device`` in ``tier`` depends on, as plain JSON data.

        Its hash (``config_sha256``) is stored in both sides' result files; results with
        different hashes are never compared. Solver-only settings (etalon precision, Meep
        process count) are left out: they do not change what is being simulated.
        """
        if device not in self.tier(tier).devices:
            raise ValueError(f"device {device!r} is not in tier {tier!r}")
        return {
            "schema": self.version,
            "tier": tier,
            "tier_numerics": self.tier(tier).model_dump(exclude={"devices"}),
            "device": device,
            "device_numerics": self.device(device).model_dump(),
            "materials": self.materials.model_dump(),
            "strip": self.strip.model_dump(),
            "ports": self.ports.model_dump(),
            "curve_tolerance": self.curve_tolerance,
        }

    def config_sha256(self, tier: str, device: str) -> str:
        """SHA-256 of ``device_spec`` in canonical JSON (sorted keys, no whitespace)."""
        return sha256_json(self.device_spec(tier, device))


def load_config(path: Path = CONFIG_PATH, overrides: Sequence[str] = ()) -> BenchConfig:
    """Read and validate config.yaml, with optional ``dotted.key=value`` overrides.

    Overrides exist for pilot and convergence runs (``--set tiers.2d.pml=0.5``). They
    change the config hash, so an overridden result is never compared with a reference.
    """
    with open(path, encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    for item in overrides:
        apply_override(data, item)
    return BenchConfig.model_validate(data)


def apply_override(data: dict[str, Any], item: str) -> None:
    """Set ``a.b.c=value`` in nested ``data``; the value is parsed as YAML (numbers, lists)."""
    key, sep, value = item.partition("=")
    if not sep:
        raise ValueError(f"override {item!r} must look like dotted.key=value")
    *parents, leaf = key.strip().split(".")
    node = data
    for part in parents:
        if not isinstance(node.get(part), dict):
            raise ValueError(f"override {item!r}: {part!r} is not a section of config.yaml")
        node = node[part]
    if leaf not in node:
        raise ValueError(f"override {item!r}: {leaf!r} is not a key of that section")
    node[leaf] = yaml.safe_load(value)


def sha256_json(data: Any) -> str:
    """SHA-256 hex digest of ``data`` as canonical JSON."""
    text = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def whole_cells(what: str, length: float, resolution: int) -> int:
    """length · resolution as an int; ValueError unless it is a whole number of cells."""
    cells = length * resolution
    if abs(cells - round(cells)) > _CELL_TOLERANCE * max(1.0, abs(cells)):
        raise ValueError(
            f"{what} = {length} µm is {cells:.6g} cells at resolution {resolution}; it must be "
            "a whole number of cells so both codes put the same Yee nodes in the same places"
        )
    return round(cells)


def even_cells(what: str, length: float, resolution: int) -> int:
    """Like ``whole_cells``, and the count must also be even (the centre is then a node)."""
    cells = whole_cells(what, length, resolution)
    if cells % 2:
        raise ValueError(
            f"{what} = {length} µm is {cells} cells at resolution {resolution}; it must be an "
            "even number of cells so the region centre lies on a grid node"
        )
    return cells


def meep_frequency(wavelength_um: float | np.ndarray) -> float | np.ndarray:
    """Meep frequency in units of c/a (a = 1 µm): f = 1/λ."""
    return 1.0 / wavelength_um


def meep_time(time_fs: float) -> float:
    """Simulated time in Meep units a/c (a = 1 µm)."""
    return time_fs / MEEP_TIME_UNIT_FS


@dataclass(frozen=True)
class Pulse:
    """The source time signature, in both codes' terms (docstring of this module)."""

    wavelength: float
    """etalon GaussianPulse(wavelength=...), µm."""
    bandwidth: float
    """etalon GaussianPulse(bandwidth=...), µm."""
    sigma_f: float
    """Spectral standard deviation σ_f = (f_hi − f_lo)/2, Hz."""
    tau: float
    """Temporal width τ = 1/(2πσ_f), s."""
    meep_frequency: float
    """Meep GaussianSource(frequency=...), c/a."""
    meep_fwidth: float
    """Meep GaussianSource(fwidth=...) = 2πσ_f, c/a; with cutoff = 5, w = τ and t0 = 5τ."""

    meep_cutoff: float = 5.0


def pulse(band: Band) -> Pulse:
    """The Gaussian pulse that covers ``band``, for both codes."""
    f_hi = C_0 / (band.min * 1e-6)
    f_lo = C_0 / (band.max * 1e-6)
    sigma_f = 0.5 * (f_hi - f_lo)
    return Pulse(
        wavelength=band.center,
        bandwidth=band.width,
        sigma_f=sigma_f,
        tau=1.0 / (2.0 * math.pi * sigma_f),
        meep_frequency=1.0 / band.center,
        meep_fwidth=2.0 * math.pi * sigma_f * 1e-6 / C_0,
    )
