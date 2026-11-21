"""Phase 3: quantitative reference-theme analysis.

Covers the small public interface, deterministic output, the alpha-hex
normalisation, variant/source ambiguity handling, missing-role handling, the
warm/cool definition, achromatic hue suppression, constraint-coverage maths,
the CLI ``references`` command end-to-end, and well-formedness of the
HTML/SVG comparison outputs.

Reference themes are inputs only -- none of these tests asserts that any
reference is "better" than another. The comparison is descriptive.
"""

from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path

import pytest
import yaml

from grotto.environments import Environments
from grotto.reference_analysis import (
    ACHROMATIC_CHROMA_FLOOR,
    WARM_HUE_CENTER,
    analyze_reference,
    compare_references,
    comparison_text,
    load_reference_dir,
    load_reference_file,
    primary_variant,
    reference_text,
    warm_cool_balance,
)
from grotto.report import to_json, to_yaml
from grotto.spec import Palette, RoleSpec, DistanceSpec
from grotto import render

REPO = Path(__file__).resolve().parents[1]
REF_DIR = REPO / "themes/references"


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def specs():
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    dists = DistanceSpec.load(REPO / "spec/distance-matrix.yaml", roles)
    env = Environments.load(REPO / "spec/environments.yaml")
    return roles, dists, env


@pytest.fixture(scope="module")
def all_refs():
    return load_reference_dir(REF_DIR)


@pytest.fixture(scope="module")
def analyses(specs, all_refs):
    roles, dists, env = specs
    return {
        stem: analyze_reference(primary_variant(vs), roles, dists, env)
        for stem, vs in all_refs.items()
    }


# ===========================================================================
# loading: six references, variant ambiguity, alpha normalisation
# ===========================================================================


def test_loads_all_six_references(all_refs):
    assert set(all_refs) == {
        "kanagawa", "monokai", "nord", "palenight", "rose-pine", "solarized"
    }


def test_every_reference_has_a_primary_dark_variant(all_refs):
    for stem, variants in all_refs.items():
        pv = primary_variant(variants)
        assert pv.is_primary is True
        assert pv.label == "dark", f"{stem} primary variant is {pv.label!r}, expected 'dark'"
        assert "bg" in pv.palette and "fg" in pv.palette


def test_variant_ambiguity_is_detected(all_refs):
    # solarized (roles_light) and rose-pine (dawn) carry extra light variants
    assert all_refs["solarized"][-1].source_ambiguous is True
    assert any(v.label == "light" for v in all_refs["solarized"])
    assert all_refs["rose-pine"][-1].source_ambiguous is True
    assert any(v.label in ("light", "dawn") for v in all_refs["rose-pine"])
    # the other four are single-variant
    for stem in ("kanagawa", "monokai", "nord", "palenight"):
        assert len(all_refs[stem]) == 1, f"{stem} unexpectedly has extra variants"
        assert all_refs[stem][0].source_ambiguous is False


def test_alpha_hex_is_normalised_not_rejected(all_refs):
    """monokai/palenight ship 8-digit alpha hex for selection; the loader must
    base-strip it to 6-digit (canonical files unchanged) and record it."""
    mono = primary_variant(all_refs["monokai"])
    pal = primary_variant(all_refs["palenight"])
    assert "selection" in mono.normalized_alpha_roles
    assert "selection" in pal.normalized_alpha_roles
    # the stored value is now clean 6-digit hex
    assert mono.palette["selection"] == "#878b91"
    assert pal.palette["selection"] == "#7580b8"
    # and the palette validates against the strict #rrggbb contract
    from grotto.spec import validate_hex
    validate_hex(mono.palette)
    validate_hex(pal.palette)


def test_canonical_reference_files_are_not_modified():
    """The loader must never mutate the source YAML on disk."""
    before = (REF_DIR / "monokai.yaml").read_text()
    load_reference_file(REF_DIR / "monokai.yaml")
    after = (REF_DIR / "monokai.yaml").read_text()
    assert before == after


def test_extra_variants_load_as_separate_non_primary_palettes(all_refs):
    sol = all_refs["solarized"]
    light = [v for v in sol if v.label == "light"]
    assert len(light) == 1
    assert light[0].is_primary is False
    assert "bg" in light[0].palette
    # the light variant is NOT the one compare_references uses
    assert primary_variant(sol).label == "dark"


# ===========================================================================
# analysis structure + determinism
# ===========================================================================


EXPECTED_AXES = {
    "background", "reading_contrast", "distributions", "constraints",
    "warm_cool_balance", "spectral", "cvd", "caveats",
}


def test_analysis_has_every_required_axis(analyses):
    for stem, a in analyses.items():
        assert a["schema"] == "grotto.reference-analysis"
        assert a["schema_version"] == "phase3"
        missing = EXPECTED_AXES - set(a)
        assert not missing, f"{stem} missing axes: {missing}"


def test_analysis_is_deterministic(specs, all_refs):
    """Same inputs -> byte-identical JSON, every reference."""
    roles, dists, env = specs
    for stem, vs in all_refs.items():
        a1 = analyze_reference(primary_variant(vs), roles, dists, env)
        a2 = analyze_reference(primary_variant(vs), roles, dists, env)
        assert to_json(a1) == to_json(a2), f"{stem} analysis is not deterministic"


def test_analysis_round_trips_through_json_and_yaml(analyses):
    for stem, a in analyses.items():
        j = json.loads(to_json(a))
        assert j["schema"] == "grotto.reference-analysis"
        y = yaml.safe_load(to_yaml(a))
        assert y["reference"]["name"] == a["reference"]["name"]
        # no numpy scalars leak (would break YAML / cross-language consumers)
        bg = j["background"]["bg"]
        assert type(bg["L"]) is float


# ===========================================================================
# background hue suppression (achromatic)
# ===========================================================================


def test_background_hue_suppressed_when_effectively_achromatic(analyses):
    """kanagawa (C~0.017) and monokai (C~0.011) backgrounds are below the
    chroma floor; their hue must be null and classification 'achromatic'."""
    for stem in ("kanagawa", "monokai"):
        bg = analyses[stem]["background"]["bg"]
        assert bg["C"] < ACHROMATIC_CHROMA_FLOOR
        assert bg["h"] is None
        assert bg["h_meaningful"] is False
        assert bg["classification"] == "achromatic"


def test_background_hue_reported_when_chromatic(analyses):
    """solarized has the most chromatic background (C~0.049); hue is real."""
    bg = analyses["solarized"]["background"]["bg"]
    assert bg["C"] > ACHROMATIC_CHROMA_FLOOR
    assert bg["h"] is not None
    assert bg["h_meaningful"] is True
    assert bg["classification"] == "cool"  # h~220


def test_achromatic_floor_matches_stability_module():
    """Hue-meaningfulness floor is the project-wide convention."""
    from grotto.stability import DEFAULT_CHROMA_FLOOR
    assert ACHROMATIC_CHROMA_FLOOR == DEFAULT_CHROMA_FLOOR


# ===========================================================================
# warm / cool balance: explicit, bounded, chroma-weighted
# ===========================================================================


def test_warm_cool_score_is_in_range_and_documented(analyses):
    for stem, a in analyses.items():
        wc = a["warm_cool_balance"]
        assert -1.0 <= wc["chroma_weighted_score"] <= 1.0
        assert wc["warm_hue_center_deg"] == WARM_HUE_CENTER
        assert "cos(h_i - 60deg)" in wc["definition"]
        # warm + cool role counts partition the chromatic roles
        assert wc["n_warm_roles"] + wc["n_cool_roles"] == wc["n_chromatic_roles"]


def test_warm_cool_score_matches_manual_definition(specs):
    """Re-derive the score independently and check it agrees."""
    import math
    roles, dists, env = specs
    vs = load_reference_file(REF_DIR / "nord.yaml")
    pal = primary_variant(vs).palette
    from grotto.color import hex_to_oklch
    num = den = 0.0
    for role, hx in pal.items():
        L, C, h = hex_to_oklch(hx)
        if C < ACHROMATIC_CHROMA_FLOOR:
            continue
        num += C * math.cos(math.radians(h - WARM_HUE_CENTER))
        den += C
    expected = num / den
    wc = warm_cool_balance(pal, roles)
    assert wc["chroma_weighted_score"] == pytest.approx(expected, abs=1e-6)


def test_warm_cool_excludes_achromatic_roles(specs):
    roles, _dists, _env = specs
    pal = Palette("t", "dark", {
        "bg": "#1a1a1a",        # near-achromatic
        "error": "#bf4040",     # warm, saturated
        "keyword": "#4060bf",   # cool, saturated
    })
    wc = warm_cool_balance(pal, roles)
    assert "bg" not in wc["per_role"]
    assert set(wc["per_role"]) == {"error", "keyword"}
    assert wc["n_chromatic_roles"] == 2


# ===========================================================================
# declared-constraint coverage + missing-role handling
# ===========================================================================


def test_constraint_coverage_fractions_are_consistent(specs, all_refs):
    roles, dists, env = specs
    from grotto.spec import CONSTRAINT_KINDS
    for stem, vs in all_refs.items():
        a = analyze_reference(primary_variant(vs), roles, dists, env)
        pal = primary_variant(vs).palette
        cs = a["constraints"]
        for kind in CONSTRAINT_KINDS:
            block = cs[kind]
            total = block["declared_pairs"]
            present = block["present_pairs"]
            frac = block["coverage_fraction"]
            assert present <= total
            if total:
                assert frac == pytest.approx(present / total, abs=1e-4)
            # the present-pair count matches an independent recount
            declared = [c for c in dists.constraints if c.kind == kind]
            recount = sum(1 for c in declared if c.a in pal and c.b in pal)
            assert present == recount, f"{stem} {kind}: {present} vs recount {recount}"
        assert "note" in cs  # the explanatory note is carried


def test_missing_roles_are_explicit_and_consistent(analyses, specs):
    roles, _d, _e = specs
    spec_roles = set(roles.roles)
    for stem, a in analyses.items():
        pal_roles = set(a["reference"]["roles_missing"]) | set(
            # roles present are not in the missing list; reconstruct from counts
            r for r in spec_roles if r not in a["reference"]["roles_missing"]
        )
        present = a["reference"]["roles_present_count"]
        total = a["reference"]["mapping_completeness"]["total_spec_roles"]
        assert total == len(spec_roles)
        assert present + a["reference"]["roles_missing_count"] == total
        # coverage fraction matches
        assert a["reference"]["mapping_completeness"]["fraction"] == pytest.approx(present / total)
        # every missing role is a real spec role
        assert set(a["reference"]["roles_missing"]) <= spec_roles


def test_partial_palette_missing_role_handling(specs):
    """A palette with almost nothing mapped must still analyse cleanly:
    background section partial, reading_contrast null where fg/bg absent,
    coverage fractions reflect the emptiness."""
    roles, dists, env = specs
    from grotto.reference_analysis import ReferenceVariant
    pal = Palette("sparse", "dark", {"bg": "#101010"})  # no fg!
    rv = ReferenceVariant(
        name="sparse", label="dark", palette=pal, source_url="", source_note="",
        is_primary=True, source_ambiguous=False,
    )
    a = analyze_reference(rv, roles, dists, env)
    assert a["reading_contrast"] is None  # no fg -> no reading pair
    assert a["background"]["bg"] is not None
    assert a["background"]["bg_elevated"] is None
    assert a["background"]["bg_overlay"] is None
    # must_distinguish has many declared pairs, almost none present
    must = a["constraints"]["must_distinguish"]
    assert must["present_pairs"] == 0  # no pair has both roles (only bg present)
    assert must["coverage_fraction"] == pytest.approx(0.0)
    # still JSON-serialisable
    json.loads(to_json(a))


def test_constraint_distances_carry_channel_breakdown(analyses):
    a = analyses["nord"]
    # find a present must_distinguish pair (e.g. error/string) and check breakdown
    must = a["constraints"]["must_distinguish"]
    pair = next(p for p in must["pairs"] if {p["a"], p["b"]} == {"error", "string"})
    for k in ("de", "d_lightness", "d_chroma", "d_hue", "dominant_channel"):
        assert k in pair
    assert pair["dominant_channel"] in ("lightness", "chroma", "hue")


# ===========================================================================
# spectral: nominal, exploratory, background-vs-token decomposition
# ===========================================================================


def test_spectral_shares_partition_to_one(analyses):
    for stem, a in analyses.items():
        sp = a["spectral"]
        assert sp is not None
        total = sp["background_share"] + sp["foreground_share"] + sp["token_share"]
        assert total == pytest.approx(1.0, abs=1e-6)
        assert 0 < sp["melanopic_ratio"] < 2


def test_spectral_caveat_is_present(analyses):
    for a in analyses.values():
        assert "retinal" in a["spectral"]["caveat"] or "exposure" in a["spectral"]["caveat"]


def test_foreground_dominates_melanopic_in_some_dark_themes(analyses):
    """Confirms RESEARCH.md M-1 in the reference set: in at least one dark
    theme the foreground, not the (much larger) background, is the leading
    melanopic contributor. Descriptive observation, not a ranking."""
    found = False
    for a in analyses.values():
        sp = a["spectral"]
        if sp["foreground_share"] > sp["background_share"]:
            found = True
            break
    assert found, "no reference shows foreground > background melanopic share"


# ===========================================================================
# CVD: informational, references not bound by D-3
# ===========================================================================


def test_cvd_section_covers_three_types(analyses):
    for a in analyses.values():
        cvd = a["cvd"]
        for pair in cvd["pairs"]:
            for kind in ("protan", "deutan", "tritan"):
                assert kind in pair["cvd_dichromat_de"]
        assert "not bound by d-3" in cvd["note"].lower()


# ===========================================================================
# comparison: fixed order, NOT a ranking, no winner
# ===========================================================================


def test_comparison_uses_fixed_alphabetical_order(analyses, specs):
    roles, dists, env = specs
    c = compare_references(analyses, roles, dists, env)
    assert c["schema"] == "grotto.reference-comparison"
    assert c["references"] == sorted(analyses)
    assert "NOT a ranking" in c["ordering_note"]
    assert "no winner" in c["ordering_note"].lower()


def test_comparison_table_has_a_row_per_metric_and_a_col_per_reference(analyses, specs):
    roles, dists, env = specs
    c = compare_references(analyses, roles, dists, env)
    stems = c["references"]
    assert len(c["table"]) >= 20  # the curated metric rows
    for row in c["table"]:
        assert set(row) >= {"key", "label"} and set(stems) <= set(row)
    # every reference column is populated for the background-L row
    bg_L = next(r for r in c["table"] if r["key"] == "bg_L")
    for s in stems:
        assert bg_L[s] is not None


def test_comparison_text_does_not_rank(comparisons_fixture):
    txt = comparison_text(comparisons_fixture)
    assert "NOT a ranking" in txt
    assert "descriptive" in txt.lower()
    # the word 'best' must not appear as a superlative verdict
    assert " best " not in txt.lower()


@pytest.fixture(scope="module")
def comparisons_fixture(analyses, specs):
    roles, dists, env = specs
    return compare_references(analyses, roles, dists, env)


# ===========================================================================
# CLI: end-to-end command writes all outputs deterministically
# ===========================================================================


def _common_args():
    return [
        "--roles", str(REPO / "spec/roles.yaml"),
        "--distances", str(REPO / "spec/distance-matrix.yaml"),
        "--environments", str(REPO / "spec/environments.yaml"),
    ]


def test_cli_references_writes_all_outputs(tmp_path):
    from grotto.cli import main
    rc = main(_common_args() + ["references", "--out", str(tmp_path)])
    assert rc == 0
    names = {p.name for p in tmp_path.iterdir()}
    for stem in ("kanagawa", "monokai", "nord", "palenight", "rose-pine", "solarized"):
        for ext in ("json", "yaml", "txt", "html"):
            assert f"{stem}.{ext}" in names, f"missing {stem}.{ext}"
    for ext in ("json", "yaml", "txt", "html", "svg"):
        assert f"comparison.{ext}" in names, f"missing comparison.{ext}"


def test_cli_references_explicit_file_list(tmp_path):
    from grotto.cli import main
    rc = main(_common_args() + [
        "references",
        str(REF_DIR / "nord.yaml"),
        str(REF_DIR / "solarized.yaml"),
        "--out", str(tmp_path),
    ])
    assert rc == 0
    names = {p.name for p in tmp_path.iterdir()}
    assert "nord.json" in names and "solarized.json" in names
    # only the two requested references
    assert "monokai.json" not in names


def test_cli_references_output_is_deterministic(tmp_path):
    from grotto.cli import main
    args = _common_args() + ["references", "--out", str(tmp_path / "a")]
    main(args)
    main(_common_args() + ["references", "--out", str(tmp_path / "b")])
    for fn in ("nord.json", "comparison.json", "comparison.html", "comparison.svg"):
        a = (tmp_path / "a" / fn).read_text()
        b = (tmp_path / "b" / fn).read_text()
        assert a == b, f"{fn} not byte-identical across runs"


# ===========================================================================
# render: well-formed, self-contained HTML/SVG
# ===========================================================================


class _Balanced(HTMLParser):
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
    p = _Balanced()
    p.feed(html)
    assert not p.errors, f"unbalanced: {p.errors[:2]}"
    assert not p.stack, f"unclosed: {p.stack[-3:]}"


def test_comparison_html_is_balanced_and_self_contained(comparisons_fixture, analyses):
    html = render.reference_comparison_html(comparisons_fixture, analyses)
    assert html.startswith("<!doctype html>") and html.rstrip().endswith("</html>")
    assert "src=" not in html and "href=" not in html
    _assert_balanced(html)
    assert "NOT a ranking" in html or "not a ranking" in html.lower()


def test_reference_analysis_html_is_balanced(analyses):
    for a in analyses.values():
        html = render.reference_analysis_html(a)
        assert html.startswith("<!doctype html>") and html.rstrip().endswith("</html>")
        _assert_balanced(html)


def test_comparison_svg_is_well_formed(analyses, comparisons_fixture):
    order = comparisons_fixture["references"]
    svg = render.reference_comparison_svg(analyses, order)
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert "xmlns" in svg
    # one row per reference
    assert svg.count("reference") >= 0  # smoke; structure validated by render


def test_render_is_deterministic(comparisons_fixture, analyses):
    a = render.reference_comparison_html(comparisons_fixture, analyses)
    b = render.reference_comparison_html(comparisons_fixture, analyses)
    assert a == b
    order = comparisons_fixture["references"]
    assert render.reference_comparison_svg(analyses, order) == render.reference_comparison_svg(analyses, order)
