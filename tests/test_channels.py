"""Pair-scoped redundant-channel audit (D-3), and the guard that keeps it honest.

These tests pin two different things:

  * the *vocabulary* -- which marks an editor actually draws, and which of them
    the mapping can deliver.  These are host facts; a test is what stops them
    drifting into folklore.
  * the *conclusion* -- that two specific pairs in the surface cluster are
    warned about today on a channel that cannot discriminate them.  That is the
    regression this module exists to hold.

Nothing here changes ``spec.check()``.  The audit is report-only by design:
amending D-3 is a design decision, not a bug fix (see
docs/review/redundant-channel-audit.md).
"""

from pathlib import Path

import pytest

from grotto.channels import (
    CHANNELS,
    Delivery,
    audit,
    covers,
    judge,
    load_delivery,
    report,
    role_level,
)
from grotto.spec import Palette, RoleSpec, check

REPO = Path(__file__).resolve().parents[1]
MAPPING = REPO / "spec/mappings/vscode.yaml"

# The pairs the audit exists for. All are excused today by a role-level
# channel test, and no channel discriminates them as rendered.
UNCOVERED = [
    ("error", "warning"),                  # one mark: both are `4px double`
    ("selection", "active_line"),          # no selection border exists
    ("search_match", "search_match_current"),  # two borders, one shape
]

# Pairs whose excuse does hold, one per channel kind -- the audit must not
# simply report everything as uncovered.
COVERED = [
    ("diff_added", "diff_removed"),        # + / - gutter signs
    ("error", "string"),                   # double underline vs nothing
    ("error", "success"),                  # double vs dotted underline
    ("selection", "search_match_current"),  # a ring vs no ring
]


@pytest.fixture(scope="module")
def roles() -> RoleSpec:
    return RoleSpec.load(REPO / "spec/roles.yaml")


@pytest.fixture(scope="module")
def delivery() -> Delivery:
    return load_delivery(MAPPING)


# --------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------


def test_every_declared_channel_is_in_the_vocabulary(roles):
    """An unknown channel name must never be silently skipped as coverage."""
    for r in roles:
        for ch in r.redundant_channels:
            assert ch in CHANNELS, (
                f"role {r.name!r} declares channel {ch!r}, which the audit "
                f"cannot evaluate -- add it to grotto.channels.CHANNELS"
            )


def test_lightness_offset_is_never_independent():
    """The circularity guard.

    delta_e_ok integrates lightness, so excusing a distance shortfall with a
    lightness offset would make the metric vouch for itself.
    """
    ch = CHANNELS["lightness_offset"]
    assert not ch.independent
    assert not covers(ch, "selection", "active_line", Delivery())


def test_coverage_requires_two_different_marks(delivery):
    wavy = CHANNELS["underline_wavy"]
    # error carries the double underline, string carries nothing
    assert covers(wavy, "error", "string", delivery)
    # neither side is underlined
    assert not covers(wavy, "string", "number", delivery)


def test_error_and_warning_share_one_underline_mark(delivery):
    """The fact this vocabulary got wrong once, and must not get wrong again.

    VS Code renders `.squiggly-error`, `.squiggly-warning` and
    `.squiggly-info` identically -- `border-bottom: 4px double` -- differing
    only in colour.  Only `.squiggly-hint` is `2px dotted`
    (vscode release/1.95 src/vs/editor/browser/widget/codeEditor/editor.css).
    An earlier version of this table asserted wavy-vs-dotted and therefore
    reported one pair fewer uncovered than the editor actually warrants.
    """
    marks = delivery.marks_for(CHANNELS["underline_wavy"])
    assert marks.get("error") == marks.get("warning") == "double"
    assert not covers(CHANNELS["underline_wavy"], "error", "warning", delivery)


def test_only_hint_gets_the_dotted_underline(delivery):
    marks = delivery.marks_for(CHANNELS["underline_dotted"])
    assert marks.get("success") == "dotted"      # editorHint.foreground -> success
    assert marks.get("error") is None


def test_no_diagnostic_glyph_margin_icons_exist(delivery):
    """Marker decorations carry no glyph, and MarkerSeverity has no Success."""
    gutter = delivery.marks_for(CHANNELS["gutter_icon"])
    for role in ("error", "warning", "success"):
        assert gutter.get(role) is None, (
            f"{role} has no glyph-margin icon; asserting one re-introduces the "
            f"false host fact this test exists to prevent"
        )
    signs = delivery.marks_for(CHANNELS["gutter_sign"])
    assert signs.get("diff_added") == "+"
    assert signs.get("diff_removed") == "-"


def test_same_mark_does_not_cover():
    """Two borders are still two borders -- shape, not colour, is the channel."""
    both_bordered = Delivery(border_roles=frozenset({"search_match",
                                                     "search_match_current"}))
    assert not covers(CHANNELS["border"], "search_match", "search_match_current",
                      both_bordered)
    one_bordered = Delivery(border_roles=frozenset({"search_match_current"}))
    assert covers(CHANNELS["border"], "selection", "search_match_current",
                  one_bordered)


# --------------------------------------------------------------------------
# Delivery is read from the mapping, not assumed
# --------------------------------------------------------------------------


def test_mapping_has_no_selection_border(delivery):
    """The mapping's prose says so; the ids must agree.

    ``spec/mappings/vscode.yaml`` states "VS Code has no selectable selection
    border".  If that ever changes, selection's ``border`` channel becomes real
    and this failure is the signal to revisit the audit's conclusions.
    """
    assert "selection" not in delivery.border_roles


def test_search_match_roles_do_get_borders(delivery):
    assert {"search_match", "search_match_current"} <= delivery.border_roles


def test_strikethrough_is_delivered_by_fontstyle(delivery):
    assert "deprecated" in delivery.strikethrough_roles


def test_strikethrough_coverage_comes_from_the_mapping_not_from_assumption():
    """An empty mapping means no strikethrough -- no silent fallback."""
    strike = CHANNELS["strikethrough"]
    assert covers(strike, "deprecated", "fg", load_delivery(MAPPING))
    assert not covers(strike, "deprecated", "fg", Delivery())


# --------------------------------------------------------------------------
# Conclusions
# --------------------------------------------------------------------------


@pytest.mark.parametrize("pair", UNCOVERED)
def test_surface_pairs_are_not_actually_covered(pair, roles, delivery):
    v = judge(roles, pair[0], pair[1], delivery)
    assert not v.covered, (
        f"{pair[0]}/{pair[1]} was expected to have no covering channel; "
        f"got {v}"
    )


@pytest.mark.parametrize("pair", COVERED)
def test_genuine_redundancy_still_counts(pair, roles, delivery):
    assert judge(roles, pair[0], pair[1], delivery).covered


@pytest.mark.parametrize("pair", UNCOVERED)
def test_they_are_warnings_today_not_errors(pair, roles):
    """The report-only guarantee: this module must not have changed check().

    Scoped to the CVD conditions, which is where the redundancy rule applies.
    These pairs also fail *normal* vision on some palettes, and a
    normal-vision failure is an error under any reading -- that error is not
    what this module touches.

    If a future change promotes the CVD shortfalls to errors, ``spec.check()``
    and D-3 have been amended on purpose, and this test is the reminder to
    update the audit's framing rather than a silent drift.
    """
    palette = Palette.from_yaml(
        REPO / "themes/candidates/candidate-b-balanced.night.yaml"
    )
    dists = _dists()
    cvd = [
        v for v in check(palette, roles, dists)
        if {v.constraint.a, v.constraint.b} == set(pair)
        and v.condition != "normal"
    ]
    assert cvd, f"{pair} produced no CVD shortfall to audit"
    assert all(v.severity == "warning" for v in cvd), (
        f"{pair} CVD shortfalls are no longer warnings; D-3 has changed"
    )


def test_role_level_agrees_with_spec(roles):
    """``role_level`` restates ``spec._has_redundancy``; they must not drift.

    The audit's whole value is the *contrast* between the role-level rule and
    the pair-scoped one.  If the baseline is mis-stated, the contrast is fiction.
    """
    from grotto.spec import _has_redundancy

    for c in _dists().constraints:
        assert role_level(roles, c.a, c.b, c.channel) == _has_redundancy(c, roles), (
            f"role_level disagrees with spec._has_redundancy on {c}"
        )


def test_audit_flags_exactly_the_three_known_pairs():
    palette = Palette.from_yaml(
        REPO / "out/soft-night/soft-s01.night.yaml"
    )
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    flagged = {(f.a, f.b) for f in audit(palette, roles) if f.unexcused}
    assert flagged == set(UNCOVERED)


def test_report_mentions_both_pairs():
    text = report(REPO / "out/soft-night/soft-s01.night.yaml")
    for a, b in UNCOVERED:
        assert a in text and b in text
    assert "verdict:" in text


def _dists():
    from grotto.spec import DistanceSpec

    return DistanceSpec.load(REPO / "spec/distance-matrix.yaml")
