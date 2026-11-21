"""Pair-scoped audit of D-3 redundant channels.

DESIGN.md D-3 makes redundant non-colour coding a hard obligation on every role
with ``cvd_priority: critical``, and ``spec.check()`` enforces it: a CVD failure
on a ``must_distinguish`` pair is a *warning* when "one does" declare a
redundant channel, on the stated grounds that "the theme is then legitimately
relying on that channel".

That resolution is per **role**.  The obligation is per **pair**.  A role can
declare a channel that the adapter never emits (VS Code has no selectable
selection border), or that cannot discriminate the particular pair it is being
used to excuse (``search_match`` and ``search_match_current`` both draw a
border -- two borders of different colour are still two borders), or that is
not independent of the metric being failed at all (``lightness_offset``: OKLab
distance already measures lightness, so excusing a distance shortfall with a
lightness offset is circular).

This module keeps the spec's severity ladder intact and adds the missing
question *as a report*: for each ``must_distinguish`` pair that fails under
CVD, which declared channel -- if any -- actually covers that pair?  The answer
is what tells the palette author where the remaining separation gap lives.

Vocabulary, not inference.  The marks below are facts about what an editor
*draws*, not about what a palette scores: VS Code renders the squiggle, the
``+``/``-`` gutter signs and the gutter glyphs from the severity and the diff,
not from theme colours.  The mapping half of ``spec/mappings/vscode.yaml`` can
tell you *which* colour id a role is bound to, and the stylesheet keys its marks
on exactly that id -- so the squiggle marks are derived from the mapping, while
the gutter vocabulary is asserted here and covered by tests.  Deriving the
squiggle is deliberate: an earlier version hardcoded "wavy for errors, dotted
for warnings", which VS Code has never rendered (all of error/warning/info are
``4px double``; only hint is dotted), and the mistake understated the audit's
own result.

Boundaries:
  * report-only -- ``spec.check()`` is unchanged and keeps its severities;
  * host facts are declared or derived, and covered by tests, never silently
    edited;
  * delivery is read from the mapping, so a mapping change is visible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .spec import Palette, RoleSpec

DEFAULT_MAPPING = "spec/mappings/vscode.yaml"

# --------------------------------------------------------------------------
# Channel vocabulary
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Channel:
    """One non-colour channel, and the marks it can actually put on screen.

    ``independent`` is the load-bearing flag.  ``lightness_offset`` is False:
    the distance metric already integrates lightness, so the offset cannot
    rescue a distance threshold without the rescue being an identity.

    ``marks`` maps role -> the mark drawn for it.  A role that is absent draws
    nothing, which is exactly what makes the channel discriminating: the
    comparison is ``a != b``, not merely "a channel was declared".
    """

    name: str
    locus: str                       # text | gutter | border | axis
    independent: bool
    origin: str                      # host | mapping
    marks: dict[str, str] = field(default_factory=dict)
    note: str = ""


# VS Code renders diagnostics from the severity, not from theme colours, so
# these marks exist at runtime and no palette can remove them.
#
# Only the glyph margin markers that actually exist.  There are NO diagnostic
# glyphs: marker decorations carry className/overviewRuler/minimap only, and
# MarkerSeverity has no Success member, so an earlier version of this table
# listing error:x / warning:! / success:v was asserting marks the editor does
# not draw.
_GUTTER_MARKS = {
    "diff_added": "+",
    "diff_removed": "-",
}

# Squiggles, keyed by which editor colour id the role is bound to.  All three
# of error/warning/info render as `border-bottom: 4px double` -- one mark, not
# three -- and only Hint is `2px dotted`.  Derived from the mapping in
# load_delivery() rather than listed here, so the table cannot claim a
# distinction the stylesheet does not make.
_DOUBLE_IDS = ("editorerror", "editorwarning", "editorinfo")
_DOTTED_IDS = ("editorhint",)

# Genuinely theme-controlled: fontStyle in the generated token/semantic rules.
# Which roles it reaches is read from the mapping, not listed here.
_STRIKE_CH = Channel(
    "strikethrough", "text", True, "mapping", {},
    "Delivered through fontStyle; the one channel the theme controls.",
)


CHANNELS: dict[str, Channel] = {
    "gutter_sign": Channel(
        "gutter_sign", "gutter", True, "host", dict(_GUTTER_MARKS),
        "VS Code diff-margin codicons, not theme colours.",
    ),
    "gutter_icon": Channel(
        "gutter_icon", "gutter", True, "host", {},
        "No diagnostic glyph-margin icons exist in the editor; this channel "
        "only reaches roles the host draws a codicon for.",
    ),
    "gutter_shape": Channel("gutter_shape", "gutter", True, "host",
                            {"breakpoint": "disc"}),
    "gutter_arrow": Channel("gutter_arrow", "gutter", True, "host",
                             {"debug_current": ">"}),
    "underline_wavy": Channel(
        "underline_wavy", "text", True, "host", {},
        "The spec's name for the double underline. error, warning and info "
        "all render as `4px double`, so they share one mark and the channel "
        "cannot separate them from each other.",
    ),
    "underline_dotted": Channel(
        "underline_dotted", "text", True, "host", {},
        "Hint only: `2px dotted`.",
    ),
    "strikethrough": _STRIKE_CH,
    "border": Channel(
        "border", "border", True, "mapping", {},
        "Shape, not colour: discriminates only when one side has a ring. "
        "Marks are read from the mapping's *Border/*Outline ids.",
    ),
    "lightness_offset": Channel(
        "lightness_offset", "axis", False, "palette", {},
        "Not independent: delta_e_ok already measures lightness, so this "
        "cannot excuse a distance shortfall without being circular.",
    ),
}


# --------------------------------------------------------------------------
# Delivery: what the adapter actually emits
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Delivery:
    """Which channels the mapping can actually put on screen, per role."""

    border_roles: frozenset[str] = frozenset()
    strikethrough_roles: frozenset[str] = frozenset()
    double_underline_roles: frozenset[str] = frozenset()
    dotted_underline_roles: frozenset[str] = frozenset()
    source: str = ""

    def marks_for(self, ch: Channel) -> dict[str, str]:
        """The marks this channel actually renders, for the roles it reaches.

        Everything here is derived from the mapping rather than asserted here,
        because the host facts this table encodes are exactly the kind that
        drift: a stylesheet revision can make "error and warning differ" false
        without touching this repository.
        """
        if ch.name == "border":
            return {r: "ring" for r in self.border_roles}
        if ch.name == "strikethrough":
            return {r: "line" for r in self.strikethrough_roles}
        if ch.name == "underline_wavy":
            return {r: "double" for r in self.double_underline_roles}
        if ch.name == "underline_dotted":
            return {r: "dotted" for r in self.dotted_underline_roles}
        return dict(ch.marks)


def load_delivery(mapping_path: str | Path = DEFAULT_MAPPING) -> Delivery:
    """Read delivery out of the mapping file rather than assuming it."""
    d = yaml.safe_load(Path(mapping_path).read_text(encoding="utf-8"))
    if not isinstance(d, dict):
        raise ValueError(f"{mapping_path}: expected a mapping")

    role_of = lambda v: v["role"] if isinstance(v, dict) else v  # noqa: E731

    border = {
        role_of(v)
        for k, v in d["workbench"].items()
        if "border" in k.lower() or "outline" in k.lower()
    }
    # A semantic rule may be style-only (`*.deprecated`), in which case the
    # selector names the modifier it decorates and no role key exists.
    strike = {
        r.get("role") or str(r["selector"]).lstrip("*.").split(".")[-1]
        for r in d["semantic"]
        if "strikethrough" in str(r.get("font_style", ""))
    } | {
        r["role"]
        for r in d["textmate"]
        if "strikethrough" in str(r.get("font_style", ""))
    }
    # Which squiggle a role gets follows from the editor colour id it is bound
    # to, because that is what the stylesheet keys on.  Derived, not asserted:
    # an earlier version hardcoded "error wavy, warning dotted", which no VS
    # Code release has ever rendered.
    double = {
        role_of(v) for k, v in d["workbench"].items()
        if k.lower().startswith(_DOUBLE_IDS)
    }
    dotted = {
        role_of(v) for k, v in d["workbench"].items()
        if k.lower().startswith(_DOTTED_IDS)
    }

    return Delivery(frozenset(border), frozenset(strike),
                    frozenset(double), frozenset(dotted), str(mapping_path))


# --------------------------------------------------------------------------
# Coverage
# --------------------------------------------------------------------------


def covers(ch: Channel, a: str, b: str, delivery: Delivery) -> bool:
    """True if ``ch`` puts a *different* mark on ``a`` and ``b`` as rendered."""
    if not ch.independent:
        return False
    marks = delivery.marks_for(ch)
    ma, mb = marks.get(a), marks.get(b)
    if ma is None and mb is None:
        return False
    return ma != mb


@dataclass(frozen=True)
class Verdict:
    """Why a CVD failure is, or is not, excused by a redundant channel."""

    covered: bool
    channel: str | None
    reason: str

    def __str__(self) -> str:
        if self.covered:
            return f"covered by {self.channel}"
        return self.reason


def judge(roles: RoleSpec, a: str, b: str, delivery: Delivery) -> Verdict:
    """Which declared channel, if any, covers the pair ``(a, b)``.

    The role-level test in :func:`grotto.spec.check` answers "does either role
    declare a channel".  This answers the question D-3 is actually about:
    "does a channel a user can see discriminate *these two*".
    """
    for name in (a, b):
        role = roles.roles.get(name)
        if role is None:
            continue
        for ch_name in role.redundant_channels:
            ch = CHANNELS.get(ch_name)
            if ch is None:
                continue                      # unknown channel: cannot claim it
            if covers(ch, name, b if name == a else a, delivery):
                return Verdict(True, ch_name, f"{a}/{b} differ in {ch_name}")

    declared = [c for n in (a, b)
                for c in (roles.roles[n].redundant_channels if n in roles.roles else ())]
    if not declared:
        return Verdict(False, None, f"neither {a} nor {b} declares a channel")
    return Verdict(
        False, None,
        f"declared {sorted(set(declared))} but none discriminates {a}/{b} "
        f"as rendered",
    )


def role_level(roles: RoleSpec, a: str, b: str, channel: str | None = None) -> bool:
    """The current spec.py rule, restated, so the two can be compared directly.

    Mirrors :func:`grotto.spec._has_redundancy` literally; a test asserts the
    two cannot drift.
    """
    if channel:
        return True
    return any(
        roles.roles[n].redundant_channels
        for n in (a, b)
        if n in roles.roles
    )


# --------------------------------------------------------------------------
# Audit
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    """One ``must_distinguish`` pair that fails under CVD."""

    a: str
    b: str
    condition: str
    measured: float
    excused_today: bool
    verdict: Verdict

    @property
    def unexcused(self) -> bool:
        """Today: a warning. Under a pair-scoped reading: an error."""
        return self.excused_today and not self.verdict.covered


def audit(
    palette: Palette,
    roles: RoleSpec,
    *,
    delivery: Delivery | None = None,
    mapping_path: str | Path = DEFAULT_MAPPING,
) -> list[Finding]:
    """Every CVD-shortfall ``must_distinguish`` pair, with its coverage verdict."""
    from .cvd import CVD_TYPES
    from .distance import delta_e_ok
    from .cvd import simulate
    from .spec import DistanceSpec

    if delivery is None:
        delivery = load_delivery(mapping_path)
    dists = DistanceSpec.load("spec/distance-matrix.yaml")
    limit = dists.thresholds["must_distinguish"]["cvd_dichromat"]

    out: list[Finding] = []
    for c in dists.constraints:
        if c.kind != "must_distinguish":
            continue
        ca, cb = palette.get(c.a), palette.get(c.b)
        if not ca or not cb:
            continue
        excused = role_level(roles, c.a, c.b, c.channel)
        verdict = judge(roles, c.a, c.b, delivery)
        for kind in CVD_TYPES:
            measured = delta_e_ok(simulate(ca, kind, 1.0), simulate(cb, kind, 1.0))
            if measured < limit:
                out.append(
                    Finding(c.a, c.b, f"{kind}@1.0", measured, excused, verdict)
                )
    return out


def report(palette_path: str | Path, roles_path: str | Path = "spec/roles.yaml",
           mapping_path: str | Path = DEFAULT_MAPPING) -> str:
    """Human-readable audit of one palette."""
    palette = Palette.from_yaml(palette_path)
    roles = RoleSpec.load(roles_path)
    findings = audit(palette, roles, mapping_path=mapping_path)

    pairs: dict[tuple[str, str], Finding] = {}
    for f in findings:
        pairs.setdefault((f.a, f.b), f)

    lines = [
        f"redundant-channel audit: {Path(palette_path).name}",
        "",
        f"{len(pairs)} must_distinguish pair(s) short a CVD threshold "
        f"({len(findings)} shortfall(s) across protan/deutan/tritan)",
        "",
    ]
    unexcused = [f for f in pairs.values() if f.unexcused]
    for label, group in (("NOT COVERED by any channel", unexcused),
                         ("covered", [f for f in pairs.values()
                                      if not f.unexcused])):
        if not group:
            continue
        lines.append(f"== {label} ({len(group)}) ==")
        for f in sorted(group, key=lambda x: (x.a, x.b)):
            worst = min(x.measured for x in findings
                        if (x.a, x.b) == (f.a, f.b))
            mark = "!" if f.unexcused else " "
            lines.append(
                f" {mark} {f.a:22s}/{f.b:22s} worst dE {worst:.3f}  -- {f.verdict}"
            )
        lines.append("")
    lines.append(
        f"verdict: {len(unexcused)} pair(s) are warned about today on a channel "
        f"that does not discriminate them."
    )
    return "\n".join(lines)
