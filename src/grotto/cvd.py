"""Colour-vision-deficiency simulation.

Provenance
----------
We do not re-derive the CVD matrices; we delegate to `coloraide`, which ships
the published matrices for:

* Brettel, Viénot & Mollon (1997) -- the two-half-plane projection.  Reasonable
  accuracy for all three dichromacies, and the only one of the three that is
  well-behaved for tritanopia.
* Viénot, Brettel & Mollon (1999) -- single-matrix simplification, valid for
  protanopia/deuteranopia only.
* Machado, Oliveira & Fernandes (2009) -- severity-parameterised; the only one
  of the three that actually models *anomalous trichromacy* rather than
  interpolating toward the original image.

Policy used here (see RESEARCH.md R-9):
  dichromacy (severity 1.0)  -> Brettel 1997
  anomaly    (severity < 1)  -> Machado 2009

Caveat that matters for design decisions: all of these are population-average
models of *dichromat* colour appearance derived from unilateral-dichromat
matching data.  They tell you whether two colours *collapse*, which is what we
need.  They do not tell you what an individual with anomalous trichromacy
actually experiences.
"""

from __future__ import annotations

from dataclasses import dataclass

from coloraide import Color

from .distance import delta_e_ok

CVD_TYPES = ("protan", "deutan", "tritan")

#: Approximate prevalence among people assigned male at birth, Northern
#: European ancestry.  Prevalence among AFAB people is far lower for the
#: X-linked red-green forms (~0.4%).  Sources vary; these are rounded.
PREVALENCE = {
    "deutan": 0.06,  # deuteranomaly dominates this figure
    "protan": 0.02,
    "tritan": 0.0001,  # autosomal, rare, but included because it is the one
    # that breaks blue/yellow distinctions -- and blue/yellow
    # is exactly the axis dark themes lean on.
}


def simulate(hex_color: str, kind: str, severity: float = 1.0) -> str:
    """Simulate `kind` CVD at `severity` in [0, 1]; returns a hex string."""
    if kind not in CVD_TYPES:
        raise ValueError(f"unknown CVD type {kind!r}")
    method = "brettel" if severity >= 1.0 else "machado"
    if kind == "tritan":
        method = "brettel"  # Machado's tritan fit is the weakest of the three
    c = Color(hex_color).filter(kind, severity, method=method, space="srgb-linear")
    return c.convert("srgb").fit("srgb").to_string(hex=True)


@dataclass(frozen=True)
class CvdCollapse:
    """One pair of colours that a CVD observer may not be able to separate."""

    a: str
    b: str
    kind: str
    severity: float
    normal_de: float
    cvd_de: float

    @property
    def retention(self) -> float:
        """Fraction of the normal-vision distance that survives."""
        return self.cvd_de / self.normal_de if self.normal_de else 1.0


def check_pair(
    a_hex: str,
    b_hex: str,
    min_de: float,
    severities: tuple[float, ...] = (0.6, 1.0),
) -> list[CvdCollapse]:
    """Return the CVD conditions under which `a` and `b` fall below `min_de`."""
    out = []
    normal = delta_e_ok(a_hex, b_hex)
    for kind in CVD_TYPES:
        for sev in severities:
            ca, cb = simulate(a_hex, kind, sev), simulate(b_hex, kind, sev)
            de = delta_e_ok(ca, cb)
            if de < min_de:
                out.append(CvdCollapse(a_hex, b_hex, kind, sev, normal, de))
    return out
