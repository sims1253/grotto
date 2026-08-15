"""Render: self-contained HTML/SVG structure and determinism."""

from pathlib import Path
from html.parser import HTMLParser
import re

import pytest

from grotto import render
from grotto.environments import Environments
from grotto.spec import DistanceSpec, Palette, RoleSpec, load

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def ctx():
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    dists = DistanceSpec.load(REPO / "spec/distance-matrix.yaml", roles)
    env = Environments.load(REPO / "spec/environments.yaml")
    pal = load(REPO / "themes/fixtures/eval-night-full.yaml")
    return pal, roles, dists, env


class _BalanceChecker(HTMLParser):
    VOID = {"meta", "br", "hr", "img", "input", "link", "col", "area", "base",
            "source", "track", "wbr"}

    def __init__(self):
        super().__init__()
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        else:
            self.errors.append((tag, list(self.stack[-3:])))


def _assert_balanced(html):
    p = _BalanceChecker()
    p.feed(html)
    assert not p.errors, f"unbalanced tags: {p.errors[:3]}"
    assert not p.stack, f"unclosed tags: {p.stack[-3:]}"


def test_palette_html_is_self_contained_and_balanced(ctx):
    pal, roles, dists, env = ctx
    html = render.palette_html_report(pal, roles, dists, env)
    assert html.startswith("<!doctype html>") and html.rstrip().endswith("</html>")
    # self-contained: no external src/href
    assert "src=" not in html and "href=" not in html
    _assert_balanced(html)


def test_palette_html_contains_all_sections(ctx):
    pal, roles, dists, env = ctx
    html = render.palette_html_report(pal, roles, dists, env)
    for needle in ("Swatches", "Contrast", "Distance-matrix", "Diagnostics",
                   "CVD", "Spectral", "Specimens"):
        assert needle in html, f"section {needle!r} missing"
    # one specimen block per required language
    assert html.count('class="specimen"') >= 8
    # fixture banner present (palette is non-candidate)
    assert "NOT A CANDIDATE" in html
    # CVD overrides are explicit selectors, not CSS-nesting syntax whose
    # support varies across embedded editor webviews.
    assert "body.view-protan .specimen .r-keyword{" in html
    assert "body.view-protan .specimen {\n.r-keyword" not in html
    bar_widths = [float(v) for v in re.findall(r'bar-fill" style="width:([0-9.]+)%', html)]
    assert bar_widths and max(bar_widths) == pytest.approx(100.0)
    assert all(0 <= width <= 100 for width in bar_widths)


def test_svg_is_well_formed_and_has_one_rect_per_role(ctx):
    pal, roles, dists, env = ctx
    svg = render.palette_svg_strip(pal, roles)
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert svg.count("<rect") >= len(pal)  # bg + one per role
    # self-contained
    assert "xmlns" in svg


def test_html_is_deterministic(ctx):
    pal, roles, dists, env = ctx
    a = render.palette_html_report(pal, roles, dists, env)
    b = render.palette_html_report(pal, roles, dists, env)
    assert a == b, "HTML render is not deterministic"


def test_stability_html_is_balanced(ctx):
    pal, roles, dists, env = ctx
    from grotto.stability import cross_variant_report

    trio = {
        v: load(REPO / f"themes/fixtures/eval-{v}.yaml")
        for v in ("day", "evening", "night")
    }
    rep = cross_variant_report(trio, roles)
    html = render.stability_html_report(rep, roles)
    assert html.startswith("<!doctype html>") and html.rstrip().endswith("</html>")
    _assert_balanced(html)
    assert "Cross-variant stability" in html


def test_on_text_picks_readable_contrast():
    assert render._on_text("#ffffff") == "#000"
    assert render._on_text("#000000") == "#fff"


def test_on_text_threshold_is_the_shared_decision():
    """One project-wide light/dark cutoff drives every renderer's chip ink."""
    assert render.on_text_threshold("#ffffff") is True
    assert render.on_text_threshold("#000000") is False
    # #999999 sits in the band where family_report's former local rule
    # (OKLCH L > 0.55) disagreed (L=0.683 but luminance=0.319): the unified
    # decision is False, so those chips now take white ink
    assert render.on_text_threshold("#999999") is False


def test_cvd_select_has_exactly_one_change_handler(ctx):
    """The CVD selector keeps ONLY the script listener; the old inline
    onchange set document.body.className a second time per change."""
    pal, roles, dists, env = ctx
    html = render.palette_html_report(pal, roles, dists, env)
    assert "onchange=" not in html
    assert "addEventListener('change'" in html


# --------------------------------------------------------------------------
# Phase 3 reference rendering: warm/cool neutral split + honest '-' caption
# --------------------------------------------------------------------------


def test_warm_cool_balance_splits_boundary_roles_into_neutral(monkeypatch):
    """A warm/cool score of exactly 0 (hue on the 150/330 deg boundary) is
    NEUTRAL -- the same three-way split _classify_hue uses -- not a cool role.
    Real reference hues never land exactly on the boundary, so the score is
    forced to 0 here to exercise the branch."""
    from grotto import reference_analysis as ra

    monkeypatch.setattr(ra, "_warm_cool_score", lambda C, h: 0.0)
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    pal = Palette("t", "dark", {"bg": "#1a1a1a", "error": "#bf4040",
                                "keyword": "#4060bf"})
    wc = ra.warm_cool_balance(pal, roles)
    assert wc["neutral_roles"] == ["error", "keyword"]
    assert wc["warm_roles"] == [] and wc["cool_roles"] == []
    assert (wc["n_warm_roles"] + wc["n_cool_roles"] + wc["n_neutral_roles"]
            == wc["n_chromatic_roles"])


def test_reference_analysis_html_lists_neutral_roles(monkeypatch, ctx):
    """The warm/cool section of the per-reference page shows the neutral list
    alongside warm/cool."""
    from grotto import reference_analysis as ra

    pal, roles, dists, env = ctx
    monkeypatch.setattr(ra, "_warm_cool_score", lambda C, h: 0.0)
    rv = ra.ReferenceVariant(
        name="t", label="dark", palette=pal, source_url="", source_note="",
        is_primary=True, source_ambiguous=False,
    )
    a = ra.analyze_reference(rv, roles, dists, env)
    html = render.reference_analysis_html(a)
    neutral = a["warm_cool_balance"]["neutral_roles"]
    assert neutral  # the forced-zero patch makes every chromatic role neutral
    assert f"neutral ({len(neutral)}): {', '.join(neutral)}" in html


def test_reference_comparison_dash_covers_mapped_but_achromatic(ctx):
    """The swatch '-' means unmapped OR mapped-but-achromatic (the hex lookup
    only includes chromatic roles); the caption must say both."""
    from grotto.reference_analysis import (
        analyze_reference, compare_references, load_reference_file, primary_variant,
    )

    _pal, roles, dists, env = ctx
    variants = load_reference_file(REPO / "themes/references/nord.yaml")
    analyses = {
        "nord": analyze_reference(primary_variant(variants), roles, dists, env)
    }
    c = compare_references(analyses, roles, dists, env)
    html = render.reference_comparison_html(c, analyses)
    assert "both mapped and chromatic" in html
    assert "mapped but achromatic" in html
