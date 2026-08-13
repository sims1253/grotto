"""Layer 2 environment parameters (spec/environments.yaml).

This is the *input* side of the transform described in DESIGN.md section 9:
contrast bands, accessibility floors, chroma classes, per-environment
backgrounds and the cross-variant stability thresholds.  Phase 2 only *reads*
these to classify measured contrast and to size the stability gate; it does
not run the transform (that is Phase 4 work), so background-derivation logic
is intentionally absent here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

CONTRAST_BAND_NAMES = ("maximal", "high", "comfortable", "low", "minimal")


@dataclass(frozen=True)
class ContrastBand:
    name: str
    min: float
    max: float
    centre: float

    def contains(self, lc_abs: float) -> bool:
        return self.min <= lc_abs <= self.max


@dataclass(frozen=True)
class EnvironmentBackground:
    L: float
    C: float
    h: float


@dataclass(frozen=True)
class Environment:
    name: str
    polarity: str
    background: EnvironmentBackground
    chroma_attenuation: float
    hue_rotation: float
    chroma_gain: float
    foreground_ceiling: float | None


@dataclass(frozen=True)
class Environments:
    version: int
    contrast_bands: dict[str, ContrastBand]
    accessibility_floors: dict[str, float]
    chroma_classes: dict[str, float]
    chroma_absolute_ceiling: float
    environments: dict[str, Environment]
    stability: dict
    salience_budget: dict

    def band(self, name: str) -> ContrastBand:
        return self.contrast_bands[name]

    def band_for_lc(self, lc_abs: float) -> ContrastBand | None:
        """Which band an absolute APCA Lc falls into, or None."""
        for name in CONTRAST_BAND_NAMES:
            b = self.contrast_bands[name]
            if b.contains(abs(lc_abs)):
                return b
        return None

    @classmethod
    def load(cls, path: str | Path = "spec/environments.yaml") -> Environments:
        d = yaml.safe_load(Path(path).read_text())
        bands = {
            n: ContrastBand(n, float(v["min"]), float(v["max"]), float(v["centre"]))
            for n, v in d["contrast_bands"].items()
        }
        envs: dict[str, Environment] = {}
        for name, e in d.get("environments", {}).items():
            bg = e["background"]
            envs[name] = Environment(
                name=name,
                polarity=e["polarity"],
                background=EnvironmentBackground(float(bg["L"]), float(bg["C"]), float(bg["h"])),
                chroma_attenuation=float(e.get("chroma_attenuation", 0.0)),
                hue_rotation=float(e.get("hue_rotation", 0.0)),
                chroma_gain=float(e.get("chroma_gain", 1.0)),
                foreground_ceiling=e.get("foreground_ceiling"),
            )
        return cls(
            version=int(d.get("version", 0)),
            contrast_bands=bands,
            accessibility_floors=dict(d.get("accessibility_floors") or {}),
            chroma_classes=dict(d.get("chroma_classes") or {}),
            chroma_absolute_ceiling=float(d.get("chroma_absolute_ceiling", 0.16)),
            environments=envs,
            stability=dict(d.get("stability") or {}),
            salience_budget=dict(d.get("salience_budget") or {}),
        )
