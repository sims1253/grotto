"""Layer 2 environment parameters (spec/environments.yaml).

This is the *input* side of the transform described in DESIGN.md section 9:
contrast bands, accessibility floors, chroma classes, per-environment
backgrounds and the cross-variant stability thresholds.  Phase 2 only *reads*
these to classify measured contrast and to size the stability gate; the
transform itself lives in ``model.py`` (Phase 4).  The loader here retains
EVERY parameter the transform reads, including the elevated/overlay
backgrounds, the per-hue rotation weights and the warm anchor that the
senior-review correction to the hue adaptation needs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

CONTRAST_BAND_NAMES = ("maximal", "high", "comfortable", "low", "minimal")

#: Default warm anchor if the YAML omits ``warm_anchor`` (DESIGN.md section 9;
#: matches the Night background's warm-neutral bias).
DEFAULT_WARM_ANCHOR = 70.0


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
    # Phase 4: the elevated/overlay backgrounds are authored directly (DESIGN.md
    # section 9: "backgrounds are specified directly").  The transform emits
    # them verbatim rather than deriving them, so an authoring error cannot
    # propagate into the contrast reference every ink role solves against.
    background_elevated: EnvironmentBackground
    background_overlay: EnvironmentBackground
    chroma_attenuation: float
    # |hue_rotation| is the rotation CAP per environment; the warm-ward
    # direction comes from the top-level ``warm_anchor`` (see hue_weight).
    hue_rotation: float
    chroma_gain: float
    foreground_ceiling: float | None

    @property
    def rotation_cap_deg(self) -> float:
        """Absolute rotation magnitude (degrees); direction is via warm_anchor."""
        return abs(self.hue_rotation)


@dataclass(frozen=True)
class Environments:
    version: int
    contrast_bands: dict[str, ContrastBand]
    accessibility_floors: dict[str, float]
    chroma_classes: dict[str, float]
    chroma_absolute_ceiling: float
    environments: dict[str, Environment]
    # Phase 4 parameters retained for the transform.
    hue_rotation_weight: tuple[tuple[float, float], ...]  # sorted (hue_deg, weight)
    warm_anchor: float
    stability: dict
    salience_budget: dict

    def band(self, name: str) -> ContrastBand:
        return self.contrast_bands[name]

    def band_for_lc(self, lc_abs: float) -> ContrastBand | None:
        """Which band an absolute APCA Lc falls into, or None.

        Bands can overlap, so this returns the FIRST band (in CONTRAST_BAND_NAMES
        order, maximal->minimal) that contains the value -- a classification
        convenience for reports.  The transform never uses this to decide a
        role's band; it tests membership against the role's *target* band.
        """
        for name in CONTRAST_BAND_NAMES:
            b = self.contrast_bands[name]
            if b.contains(abs(lc_abs)):
                return b
        return None

    def hue_weight(self, hue_deg: float) -> float:
        """Per-hue rotation weight w(h0), piecewise-linear in OKLCH hue.

        Warm hues barely move; cool hues carry the rotation.  ``hue_deg`` is
        taken modulo 360; the control-point table spans 0..360.
        """
        return hue_weight(self.hue_rotation_weight, hue_deg)

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
            elev = e.get("background_elevated") or bg
            ovly = e.get("background_overlay") or bg
            envs[name] = Environment(
                name=name,
                polarity=e["polarity"],
                background=EnvironmentBackground(float(bg["L"]), float(bg["C"]), float(bg["h"])),
                background_elevated=EnvironmentBackground(
                    float(elev["L"]), float(elev["C"]), float(elev["h"])
                ),
                background_overlay=EnvironmentBackground(
                    float(ovly["L"]), float(ovly["C"]), float(ovly["h"])
                ),
                chroma_attenuation=float(e.get("chroma_attenuation", 0.0)),
                hue_rotation=float(e.get("hue_rotation", 0.0)),
                chroma_gain=float(e.get("chroma_gain", 1.0)),
                foreground_ceiling=e.get("foreground_ceiling"),
            )
        # hue_rotation_weight control points, sorted by hue for interpolation.
        weight_items = tuple(
            sorted(
                ((float(k), float(v)) for k, v in (d.get("hue_rotation_weight") or {}).items()),
                key=lambda kv: kv[0],
            )
        )
        warm = float(d.get("warm_anchor", DEFAULT_WARM_ANCHOR))
        return cls(
            version=int(d.get("version", 0)),
            contrast_bands=bands,
            accessibility_floors=dict(d.get("accessibility_floors") or {}),
            chroma_classes=dict(d.get("chroma_classes") or {}),
            chroma_absolute_ceiling=float(d.get("chroma_absolute_ceiling", 0.16)),
            environments=envs,
            hue_rotation_weight=weight_items,
            warm_anchor=warm,
            stability=dict(d.get("stability") or {}),
            salience_budget=dict(d.get("salience_budget") or {}),
        )


# ---------------------------------------------------------------------------
# Piecewise-linear hue-weight interpolation (module-level so the transform and
# tests can call it without an Environments instance).
# ---------------------------------------------------------------------------


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def hue_weight(weight_points: tuple[tuple[float, float], ...], hue_deg: float) -> float:
    """Piecewise-linear interpolation of (hue, weight) control points.

    ``weight_points`` must be sorted ascending by hue and span the circle
    (first point at 0, last at 360).  ``hue_deg`` is taken modulo 360.
    """
    if not weight_points:
        return 1.0
    h = hue_deg % 360.0
    pts = weight_points
    # find the bracketing segment
    for i in range(len(pts) - 1):
        h0, w0 = pts[i]
        h1, w1 = pts[i + 1]
        if h0 <= h <= h1:
            t = 0.0 if h1 == h0 else (h - h0) / (h1 - h0)
            return _lerp(w0, w1, t)
    # below first / above last control point: clamp to the nearest endpoint.
    if h < pts[0][0]:
        return pts[0][1]
    return pts[-1][1]
