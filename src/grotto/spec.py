"""Layer 1: the semantic specification, and the checker that enforces it.

Loads `spec/roles.yaml` and `spec/distance-matrix.yaml`, validates them, and
checks a concrete `Palette` against the declared constraints.

The validation here is deliberately strict.  A spec that declares a role
`cvd_priority: critical` without declaring any redundant channel is a *spec
bug*, not a palette bug, and is rejected at load time -- the whole point of the
architecture is that Layer 1 states obligations that Layer 2 cannot quietly
ignore.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .color import (
    gamut_map,
    gamut_status,
    hex_to_oklch,
    oklch_to_hex,
    oklch_to_oklab,
)
from .cvd import CVD_TYPES, simulate
from .distance import delta_e_ok

# --------------------------------------------------------------------------
# Vocabularies -- these mirror the documentation block in spec/roles.yaml.
# --------------------------------------------------------------------------

GROUPS = ("neutrals", "syntax", "diagnostics")
FAMILIES = ("neutral", "warm-neutral", "sand", "rose", "violet", "azure", "sage", "teal")
CHROMA_CLASSES = ("none", "trace", "low", "medium", "high")
CONTRAST_TARGETS = ("minimal", "low", "comfortable", "high", "maximal")
CVD_PRIORITIES = ("critical", "high", "normal", "low")
AREA_CLASSES = ("dominant", "major", "minor", "trace")
VARIANTS = ("day", "evening", "night")

CONSTRAINT_KINDS = (
    "must_distinguish",
    "should_distinguish",
    "same_family",
    "differentiated_by",
    "redundant_encoding",
)


# --------------------------------------------------------------------------
# Roles
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Role:
    name: str
    group: str
    description: str
    salience: int
    family: str
    chroma_class: str
    contrast_target: str | None
    cvd_priority: str
    night_adaptation: float
    area_class: str
    redundant_channels: tuple[str, ...] = ()
    notes: str = ""


def _fail(role: str, msg: str) -> None:
    raise ValueError(f"spec/roles.yaml: role {role!r}: {msg}")


def _build_role(name: str, group: str, d: dict) -> Role:
    if not isinstance(d, dict):
        _fail(name, "entry must be a mapping")

    sal = d.get("salience")
    if not isinstance(sal, int) or not 0 <= sal <= 6:
        _fail(name, f"salience must be an int in 0..6, got {sal!r}")

    fam = d.get("family")
    if fam not in FAMILIES:
        _fail(name, f"family {fam!r} not in {FAMILIES}")

    cc = d.get("chroma_class")
    if cc not in CHROMA_CLASSES:
        _fail(name, f"chroma_class {cc!r} not in {CHROMA_CLASSES}")

    ct = d.get("contrast_target")
    if ct is not None and ct not in CONTRAST_TARGETS:
        _fail(name, f"contrast_target {ct!r} not in {CONTRAST_TARGETS} or null")

    cp = d.get("cvd_priority")
    if cp not in CVD_PRIORITIES:
        _fail(name, f"cvd_priority {cp!r} not in {CVD_PRIORITIES}")

    na = d.get("night_adaptation")
    if not isinstance(na, (int, float)) or not 0.0 <= float(na) <= 1.0:
        _fail(name, f"night_adaptation must be a float in 0.0..1.0, got {na!r}")

    ac = d.get("area_class")
    if ac not in AREA_CLASSES:
        _fail(name, f"area_class {ac!r} not in {AREA_CLASSES}")

    channels = tuple(d.get("redundant_channels") or ())

    # The structural rule: a critical role that leans on hue alone is a spec bug.
    if cp == "critical" and not channels:
        _fail(
            name,
            "cvd_priority is 'critical' but no redundant_channels are declared; "
            "critical roles must not rely on hue alone (DESIGN.md D-3)",
        )

    return Role(
        name=name,
        group=group,
        description=str(d.get("description", "")),
        salience=sal,
        family=fam,
        chroma_class=cc,
        contrast_target=ct,
        cvd_priority=cp,
        night_adaptation=float(na),
        area_class=ac,
        redundant_channels=channels,
        notes=str(d.get("notes", "") or ""),
    )


@dataclass(frozen=True)
class RoleSpec:
    version: int
    roles: dict[str, Role]

    def __getitem__(self, name: str) -> Role:
        return self.roles[name]

    def __contains__(self, name: object) -> bool:
        return name in self.roles

    def __iter__(self):
        return iter(self.roles.values())

    def __len__(self) -> int:
        return len(self.roles)

    def by_group(self, group: str) -> dict[str, Role]:
        if group not in GROUPS:
            raise ValueError(f"unknown group {group!r}")
        return {n: r for n, r in self.roles.items() if r.group == group}

    def by_salience(self, level: int) -> list[Role]:
        return [r for r in self.roles.values() if r.salience == level]

    @classmethod
    def load(cls, path: str | Path = "spec/roles.yaml") -> RoleSpec:
        data = yaml.safe_load(Path(path).read_text())
        roles: dict[str, Role] = {}
        for group in GROUPS:
            for name, entry in (data.get(group) or {}).items():
                if name in roles:
                    raise ValueError(f"spec/roles.yaml: duplicate role {name!r}")
                roles[name] = _build_role(name, group, entry)
        if not roles:
            raise ValueError("spec/roles.yaml: no roles defined")
        return cls(version=int(data.get("version", 0)), roles=roles)


# --------------------------------------------------------------------------
# Distance constraints
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Constraint:
    a: str
    b: str
    kind: str
    channel: str | None = None
    rationale: str | None = None

    def __str__(self) -> str:
        s = f"{self.kind}({self.a}, {self.b})"
        return f"{s} via {self.channel}" if self.channel else s


@dataclass(frozen=True)
class DistanceSpec:
    version: int
    thresholds: dict
    constraints: tuple[Constraint, ...]
    non_goals: tuple = ()

    def of_kind(self, kind: str) -> list[Constraint]:
        return [c for c in self.constraints if c.kind == kind]

    @classmethod
    def load(
        cls,
        path: str | Path = "spec/distance-matrix.yaml",
        roles: RoleSpec | None = None,
    ) -> DistanceSpec:
        data = yaml.safe_load(Path(path).read_text())
        out: list[Constraint] = []

        for kind in ("must_distinguish", "should_distinguish"):
            for pair in data.get(kind) or []:
                if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                    raise ValueError(f"{path}: {kind}: expected [a, b], got {pair!r}")
                out.append(Constraint(pair[0], pair[1], kind))

        for kind in ("same_family", "differentiated_by", "redundant_encoding"):
            for entry in data.get(kind) or []:
                pair = entry.get("pair")
                if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                    raise ValueError(f"{path}: {kind}: expected 'pair: [a, b]', got {entry!r}")
                out.append(
                    Constraint(
                        pair[0],
                        pair[1],
                        kind,
                        channel=entry.get("channel"),
                        rationale=entry.get("rationale"),
                    )
                )

        if roles is not None:
            unknown = sorted(
                {n for c in out for n in (c.a, c.b) if n not in roles}
            )
            if unknown:
                raise ValueError(
                    f"{path}: references roles absent from the role spec: {unknown}"
                )

        return cls(
            version=int(data.get("version", 0)),
            thresholds=data.get("thresholds") or {},
            constraints=tuple(out),
            non_goals=tuple(data.get("non_goals") or ()),
        )


# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------


class Palette:
    """A concrete role -> hex assignment for one environment variant.

    A palette may be sourced two ways, and the provenance is preserved so the
    report can show it:

    * ``source == "hex"``      -- hex literals (reference themes, hand sets).
    * ``source == "oklch"``    -- canonical perceptual OKLCH coordinates, which
      were converted to hex at load time.  ``gamut_losses`` records any chroma
      lost to gamut mapping, because a silent clip there is exactly the
      "design asked for a colour the display cannot make" failure that
      DESIGN.md section 5 prohibits.

    The canonical input form remains perceptual-space-first; hex is the
    *serialised* form.  See ``from_perceptual`` / ``load``.
    """

    def __init__(
        self,
        name: str,
        variant: str,
        colors: dict[str, str],
        *,
        source: str = "hex",
        perceptual: dict[str, tuple[float, float, float]] | None = None,
        gamut_losses: dict[str, float] | None = None,
        note: str = "",
        meta: dict | None = None,
    ):
        # ``variant`` is a label (grotto uses day/evening/night; reference
        # themes use the editor convention dark/light).  No logic depends on
        # the specific value, so we accept any non-empty string rather than
        # reject legitimate inputs.  See VARIANTS for the canonical grotto set.
        if not isinstance(variant, str) or not variant.strip():
            raise ValueError(f"variant must be a non-empty string, got {variant!r}")
        if variant not in VARIANTS:
            # not an error: reference themes legitimately use dark/light.
            pass
        if source not in ("hex", "oklch"):
            raise ValueError(f"source must be 'hex' or 'oklch', got {source!r}")
        self.name = name
        self.variant = variant
        self.source = source
        self.colors: dict[str, str] = {k: v.lower() for k, v in colors.items() if v}
        self.perceptual = dict(perceptual or {})
        self.gamut_losses = dict(gamut_losses or {})
        self.note = str(note or "")
        self.meta = dict(meta or {})

    def __getitem__(self, role: str) -> str:
        return self.colors[role]

    def __contains__(self, role: object) -> bool:
        return role in self.colors

    def __len__(self) -> int:
        return len(self.colors)

    def __repr__(self) -> str:
        return f"Palette({self.name!r}, {self.variant!r}, {len(self.colors)} roles)"

    def get(self, role: str, default=None):
        return self.colors.get(role, default)

    def items(self):
        return self.colors.items()

    def roles(self) -> list[str]:
        return list(self.colors)

    def oklch(self, role: str) -> tuple[float, float, float]:
        return hex_to_oklch(self.colors[role])

    @property
    def bg(self) -> str:
        return self.colors["bg"]

    @property
    def is_candidate(self) -> bool:
        """A palette is a candidate only if it explicitly says so.

        Fixtures and reference themes default to non-candidate so tooling can
        refuse to present them as final outputs (DESIGN.md: no palette is
        finalised in Phase 2).
        """
        return bool(self.meta.get("candidate", False))

    # -- construction -------------------------------------------------------

    @classmethod
    def from_perceptual(
        cls,
        name: str,
        variant: str,
        oklch_colors: dict[str, tuple[float, float, float]],
        *,
        note: str = "",
        meta: dict | None = None,
        gamut: str = "srgb",
    ) -> Palette:
        """Build a palette from canonical OKLCH coordinates.

        Each role is gamut-mapped to ``gamut`` (default sRGB) and quantised to
        8-bit hex.  The chroma lost in that mapping is recorded per role so the
        audit can surface it.  Perceptual coordinates are kept verbatim.
        """
        hex_colors: dict[str, str] = {}
        perceptual: dict[str, tuple[float, float, float]] = {}
        losses: dict[str, float] = {}
        for role, lch in oklch_colors.items():
            if lch is None:
                continue
            L, C, h = (float(x) for x in lch)
            perceptual[role] = (L, C, h)
            mapped, lost = gamut_map((L, C, h), gamut=gamut)
            hex_colors[role] = oklch_to_hex(mapped)
            losses[role] = lost
        return cls(
            name,
            variant,
            hex_colors,
            source="oklch",
            perceptual=perceptual,
            gamut_losses=losses,
            note=note,
            meta=meta,
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> Palette:
        """Load a palette from YAML.

        Accepts three shapes:
          * reference themes: a ``roles:`` map of hex values (possibly null).
          * hex palettes: a ``colors:`` map of hex values.
          * perceptual-first fixtures: ``format: oklch`` with a ``colors:`` map
            of ``{role: {L, C, h}}``.  This is the canonical input form.

        ``note``, ``kind`` and ``candidate`` are carried through as metadata.
        """
        d = yaml.safe_load(Path(path).read_text())
        if not isinstance(d, dict):
            raise ValueError(f"{path}: expected a mapping at the top level")
        name = d.get("name", Path(path).stem)
        variant = d.get("variant", "night")
        note = str(d.get("note", "") or "")
        meta = dict(d.get("meta") or {})
        if "kind" in d:
            meta.setdefault("kind", d["kind"])
        if "candidate" in d:
            meta["candidate"] = bool(d["candidate"])
        meta.setdefault("source_path", str(path))

        fmt = (d.get("format") or "hex").lower()
        if fmt == "oklch":
            raw = d.get("colors") or {}
            if not raw:
                raise ValueError(f"{path}: format: oklch but no 'colors' map")
            oklch_colors: dict[str, tuple[float, float, float]] = {}
            for role, v in raw.items():
                if v is None:
                    continue
                if isinstance(v, (list, tuple)):
                    L, C, h = v
                elif isinstance(v, dict):
                    L, C, h = v["L"], v["C"], v["h"]
                else:
                    raise ValueError(f"{path}: role {role!r}: expected {{L,C,h}}, got {v!r}")
                oklch_colors[role] = (float(L), float(C), float(h))
            return cls.from_perceptual(name, variant, oklch_colors, note=note, meta=meta)

        # hex path (reference themes use 'roles', hand sets use 'colors')
        colors = d.get("colors") or d.get("roles") or {}
        return cls(name, variant, colors, source="hex", note=note, meta=meta)

    def to_yaml(self, path: str | Path) -> None:
        Path(path).write_text(
            yaml.safe_dump(
                {"name": self.name, "variant": self.variant, "colors": dict(self.colors)},
                sort_keys=False,
            )
        )


# --------------------------------------------------------------------------
# Palette audit -- per-role colour/gamut provenance
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RoleColorAudit:
    """Auditable colour provenance for one role in one palette.

    Everything downstream (contrast, distance, CVD, spectral) is derived from
    hex, so the audit pins down exactly what hex means in OKLCH/OKLab and
    whether it sits inside the sRGB and Display P3 gamuts.  Gamut excursion is
    reported explicitly rather than clipped silently (DESIGN.md section 5).
    """

    role: str
    hex: str
    oklch: tuple[float, float, float]
    oklab: tuple[float, float, float]
    in_srgb: bool
    in_p3: bool
    srgb_excursion: float
    p3_excursion: float
    chroma_lost: float
    source: str

    def as_dict(self) -> dict:
        L, C, h = self.oklch
        la, aa, ba = self.oklab
        return {
            "role": self.role,
            "hex": self.hex,
            "oklch": {"L": round(L, 6), "C": round(C, 6), "h": round(h, 6)},
            "oklab": {"L": round(la, 6), "a": round(aa, 6), "b": round(ba, 6)},
            "gamut": {
                "in_srgb": self.in_srgb,
                "in_p3": self.in_p3,
                "srgb_excursion": round(self.srgb_excursion, 6),
                "p3_excursion": round(self.p3_excursion, 6),
            },
            "chroma_lost": round(self.chroma_lost, 6),
            "source": self.source,
        }


def audit_palette(palette: Palette, roles: RoleSpec | None = None) -> dict[str, RoleColorAudit]:
    """Per-role colour/gamut audit, in spec role order when ``roles`` is given."""
    order: list[str]
    if roles is not None:
        order = [n for n in roles.roles if n in palette] + [
            n for n in palette.roles() if n not in roles.roles
        ]
    else:
        order = palette.roles()

    out: dict[str, RoleColorAudit] = {}
    for role in order:
        hx = palette[role]
        # For perceptual-first inputs, audit the authored coordinate. Auditing
        # the mapped 8-bit hex would make every sRGB status trivially pass and
        # conceal exactly the out-of-gamut request this report must expose.
        lch = palette.perceptual.get(role, hex_to_oklch(hx))
        lab = oklch_to_oklab(lch)
        st = gamut_status(lch)
        out[role] = RoleColorAudit(
            role=role,
            hex=hx,
            oklch=lch,
            oklab=lab,
            in_srgb=st.in_srgb,
            in_p3=st.in_p3,
            srgb_excursion=st.srgb_excursion,
            p3_excursion=st.p3_excursion,
            chroma_lost=palette.gamut_losses.get(role, 0.0),
            source=palette.source,
        )
    return out


def load(path: str | Path) -> Palette:
    """Load a palette (any supported format) and validate its hex values."""
    p = Palette.from_yaml(path)
    validate_hex(p)
    return p


def validate_hex(palette: Palette) -> None:
    """Raise if any stored colour is not a valid 6-digit hex string."""
    import re

    for role, hx in palette.colors.items():
        if not re.fullmatch(r"#[0-9a-f]{6}", hx):
            raise ValueError(f"palette {palette.name!r}: role {role!r} = {hx!r} is not #rrggbb")


# --------------------------------------------------------------------------
# Checking
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Violation:
    constraint: Constraint
    measured: float
    threshold: float
    condition: str
    severity: str

    def __str__(self) -> str:
        return (
            f"[{self.severity}] {self.constraint} under {self.condition}: "
            f"dE {self.measured:.3f} vs threshold {self.threshold:.3f}"
        )


def missing_roles(palette: Palette, roles: RoleSpec) -> list[str]:
    """Roles the spec declares that this palette does not yet define."""
    return sorted(n for n in roles.roles if n not in palette)


def _has_redundancy(c: Constraint, roles: RoleSpec) -> bool:
    """True if the theme legitimately leans on a non-colour channel for this pair."""
    if c.channel:
        return True
    for n in (c.a, c.b):
        r = roles.roles.get(n)
        if r is not None and r.redundant_channels:
            return True
    return False


def check(palette: Palette, roles: RoleSpec, dists: DistanceSpec) -> list[Violation]:
    """Check a palette against the distance matrix.

    Pairs where either role is absent from the palette are skipped silently --
    partial palettes are a normal intermediate state.  Use `missing_roles()` to
    see what was not covered.
    """
    th = dists.thresholds
    out: list[Violation] = []

    for c in dists.constraints:
        a, b = palette.get(c.a), palette.get(c.b)
        if not a or not b:
            continue
        de = delta_e_ok(a, b)

        if c.kind == "must_distinguish":
            lim = th["must_distinguish"]["normal_vision"]
            if de < lim:
                out.append(Violation(c, de, lim, "normal", "error"))

            cvd_lim = th["must_distinguish"]["cvd_dichromat"]
            redundant = _has_redundancy(c, roles)
            for kind in CVD_TYPES:
                cde = delta_e_ok(simulate(a, kind, 1.0), simulate(b, kind, 1.0))
                if cde < cvd_lim:
                    out.append(
                        Violation(
                            c,
                            cde,
                            cvd_lim,
                            f"{kind}@1.0",
                            "warning" if redundant else "error",
                        )
                    )

        elif c.kind == "should_distinguish":
            lim = th["should_distinguish"]["normal_vision"]
            if de < lim:
                out.append(Violation(c, de, lim, "normal", "warning"))

        elif c.kind == "same_family":
            hi = th["same_family"]["max_distance"]
            lo = th["same_family"]["min_distance"]
            if de > hi:
                out.append(Violation(c, de, hi, "upper", "warning"))
            elif de < lo:
                out.append(Violation(c, de, lo, "lower", "warning"))

        elif c.kind == "differentiated_by":
            spec_d = th["differentiated_by"]
            if spec_d.get("requires_channel") and not c.channel:
                out.append(Violation(c, de, 0.0, "channel", "error"))
            hi = spec_d["max_distance"]
            if de > hi:
                out.append(Violation(c, de, hi, "upper", "warning"))

        elif c.kind == "redundant_encoding":
            if not c.channel:
                out.append(Violation(c, de, 0.0, "channel", "error"))

    return out


# --------------------------------------------------------------------------
# Screen composition models
# --------------------------------------------------------------------------

#: Estimated share of visible pixels per role, for three usage situations.
#: These are DESIGN ESTIMATES [J], not measurements from real screenshots.
#: They exist so that spectral and salience analysis weight roles by how much
#: of the screen they actually occupy, rather than treating every palette entry
#: as equally present.  Replacing these with measurements from real screenshots
#: is listed as future work.
COVERAGE_MODELS: dict[str, dict[str, float]] = {
    "code": {
        "bg": 0.74,
        "bg_elevated": 0.08,
        "fg": 0.07,
        "comment": 0.035,
        "punctuation": 0.025,
        "keyword": 0.012,
        "string": 0.018,
        "function": 0.010,
        "type": 0.006,
        "number": 0.004,
    },
    "config": {
        "bg": 0.72,
        "bg_elevated": 0.08,
        "tag": 0.06,
        "string": 0.06,
        "fg": 0.04,
        "comment": 0.03,
        "punctuation": 0.01,
    },
    "diff": {
        "bg": 0.55,
        "diff_added": 0.14,
        "diff_removed": 0.12,
        "bg_elevated": 0.07,
        "fg": 0.07,
        "comment": 0.03,
        "punctuation": 0.02,
    },
}


def coverage_model(palette: Palette, kind: str = "code") -> dict[str, float]:
    """Map hex colour -> pixel fraction for a usage situation, summing to 1.0.

    Roles absent from the palette have their share folded into `bg`, which is
    the honest fallback: if a theme does not colour comments distinctly, those
    pixels are still on screen, just carrying the background or default colour.
    """
    if kind not in COVERAGE_MODELS:
        raise ValueError(f"unknown coverage model {kind!r}; have {sorted(COVERAGE_MODELS)}")
    if "bg" not in palette:
        raise ValueError("palette has no 'bg' role; cannot build a coverage model")

    plan = COVERAGE_MODELS[kind]
    out: dict[str, float] = {}
    orphaned = 0.0
    for role, frac in plan.items():
        hx = palette.get(role)
        if hx:
            out[hx] = out.get(hx, 0.0) + frac
        else:
            orphaned += frac

    bg = palette.bg
    out[bg] = out.get(bg, 0.0) + orphaned

    total = sum(out.values())
    return {k: v / total for k, v in out.items()}
