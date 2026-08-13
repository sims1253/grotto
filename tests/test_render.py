"""Render: self-contained HTML/SVG structure and determinism."""

from pathlib import Path
from html.parser import HTMLParser
import re

import pytest

from grotto import render
from grotto.environments import Environments
from grotto.spec import DistanceSpec, RoleSpec, load

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
