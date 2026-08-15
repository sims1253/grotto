"""Phase 6 cross-candidate comparison: visuals, CLI, reproducibility (commit 3)."""

from __future__ import annotations

import glob
from pathlib import Path

import pytest

from grotto.candidate_report import (
    AREA_CATEGORIES,
    CRITICAL_STATES,
    compare_candidates,
    candidate_comparison_html,
    candidate_comparison_svg,
    candidate_comparison_text,
    candidate_family_specimens_html,
)
from grotto.candidates import build_candidates, write_all_candidate_artifacts
from grotto.cli import main
from grotto.environments import Environments
from grotto.model import ModelSpec
from grotto.report import to_json
from grotto.spec import DistanceSpec, RoleSpec

REPO = Path(__file__).resolve().parents[1]
STRATEGIES = ("a-restrained", "b-balanced", "c-expressive")
LANGS = ("Python", "Rust", "TypeScript", "Shell", "JSON", "YAML", "Markdown")


@pytest.fixture(scope="module")
def spec() -> ModelSpec:
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    dists = DistanceSpec.load(REPO / "spec/distance-matrix.yaml", roles)
    env = Environments.load(REPO / "spec/environments.yaml")
    return ModelSpec(roles, env, dists)


@pytest.fixture(scope="module")
def families(spec):
    return build_candidates(spec)


@pytest.fixture(scope="module")
def comparison(families, spec):
    return compare_candidates(families, spec)


def _common():
    return ["--roles", str(REPO / "spec/roles.yaml"),
            "--distances", str(REPO / "spec/distance-matrix.yaml"),
            "--environments", str(REPO / "spec/environments.yaml")]


# ===========================================================================
# comparison structure: no ranking, required blocks present
# ===========================================================================


def test_comparison_has_required_blocks(comparison):
    for key in ("matrix", "per_candidate", "cross_candidate_drift_night",
                "disagreement_log", "tradeoffs", "area_model", "caveats"):
        assert key in comparison, f"missing {key}"
    assert comparison["n_candidates"] == 3


def test_comparison_has_no_score_rank_or_winner(comparison):
    forbidden = {"score", "rank", "winner", "recommendation", "best"}
    assert not (forbidden & set(comparison))
    for row in comparison["matrix"]:
        assert not (forbidden & set(row))
    # the disclaimer text says "no winner" -- that must not be treated as a
    # field name (caveats legitimately MENTION the word in prose)
    assert "winner" not in [k for k in comparison if k != "caveats"]


def test_matrix_is_descriptive_not_scored(comparison):
    cols = set(comparison["matrix"][0])
    # required descriptive columns
    for c in ("candidate", "mean_realized_chroma_night", "mel_ratio_led_night",
              "mel_ratio_oled_night", "distance_errors_night",
              "cvd_worst_retention_night", "max_hue_drift_deg",
              "min_wcag_body_text_night"):
        assert c in cols
    # the mean realized chroma ordering is visible in the data but NOT asserted
    # as a verdict anywhere
    assert "verdict" not in cols and "score" not in cols


def test_matrix_reuse_path_equals_standalone(families, spec, comparison):
    """candidate_matrix must produce identical rows whether it reuses the
    summaries compare_candidates already computed (the cheap path) or
    recomputes them itself (the standalone path)."""
    from grotto.candidate_report import candidate_matrix

    assert (candidate_matrix(families, spec, comparison["per_candidate"])
            == candidate_matrix(families, spec))


# ===========================================================================
# per candidate x variant: distributions, distance, CVD, spectral (both models)
# ===========================================================================


def test_per_candidate_variants_have_full_audit(comparison):
    for name, pc in comparison["per_candidate"].items():
        for v in ("day", "evening", "night"):
            vr = pc["variants"][v]
            for key in ("distributions", "distance_summary", "cvd_summary",
                        "spectral_both_displays", "area_category_weights"):
                assert key in vr, f"{name}.{v} missing {key}"
            # spectral reports BOTH display models
            assert "led-lcd" in vr["spectral_both_displays"]
            assert "oled" in vr["spectral_both_displays"]
            # distributions include chroma ordering
            assert "chroma_ordering" in vr["distributions"]


def test_spectral_carries_nominal_only_caveat(comparison):
    caveats = " ".join(comparison["caveats"]).lower()
    assert "nominal" in caveats and "retinal" in caveats
    # the spectral block itself repeats the limitation near the numbers
    pc = comparison["per_candidate"]["candidate-a-restrained"]
    sp = pc["variants"]["night"]["spectral_both_displays"]
    assert "caveat" in sp and "nominal" in sp["caveat"].lower()


def test_area_model_covers_required_categories(comparison):
    cats = set(comparison["area_model"]["categories"])
    required = {"background", "normal_foreground", "comments",
                "syntax_accents", "ui_chrome", "selection_highlights"}
    assert required <= cats
    assert "declared estimate" in comparison["area_model"]["measurement"].lower()


def test_area_categories_are_exhaustive():
    """Every spec role must fall into exactly one area category."""
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    categorized = {r for members in AREA_CATEGORIES.values() for r in members}
    spec_roles = set(roles.roles)
    missing = spec_roles - categorized
    # diagnostics-state inks (error/warning/info/success) are not area categories
    # per se but are covered by spectral via DECLARED_AREA; assert no UNLISTED
    # structural role is silently dropped.
    assert not missing, f"roles with no area category and no declared weight: {missing}"


# ===========================================================================
# drift: cross-variant (within) and cross-candidate (between)
# ===========================================================================


def test_cross_candidate_drift_nulls_achromatic_tag_hue(comparison):
    """tag is the declared strategy differentiator (A/B azure/neutral vs C
    violet), but A and B render it near-achromatically (OKLCH C < 0.02), so
    every tag pair includes a side whose hue angle is noise: dH is reported
    as None instead of a large meaningless number. dE/dL/dC stay numeric, and
    chromatic roles (keyword) keep their numeric hue deltas."""
    drift = comparison["cross_candidate_drift_night"]
    tag = drift["per_role"]["tag"]
    for pair, d in tag.items():
        assert d["dH_deg"] is None, f"{pair}: hue below the chroma floor must null"
        for k in ("dE", "dL", "dC"):
            assert d[k] is not None, f"{pair}.{k} stays defined"
    kw = drift["per_role"]["keyword"]
    assert all(d["dH_deg"] is not None for d in kw.values())


def test_role_drift_hue_null_below_chroma_floor():
    """Unit contract for _role_drift: EITHER side below _CHROMA_FLOOR (0.02)
    nulls dH; dE/dL/dC remain defined for achromatic colours."""
    from grotto.candidate_report import _role_drift

    d = _role_drift("#1a1a1a", "#bf4040")  # near-neutral surface vs warm ink
    assert d["dH_deg"] is None
    for k in ("dE", "dL", "dC"):
        assert isinstance(d[k], float)
    assert _role_drift("#bf4040", "#4060bf")["dH_deg"] is not None  # both chromatic


def test_drift_table_renders_dash_for_null_hue():
    from grotto.candidate_report import _drift_table

    drift = {
        "candidate_pairs": ["x|y"],
        "per_role": {
            "bg": {"x|y": {"dE": 1.5, "dL": 0.01, "dC": -0.001, "dH_deg": None}},
            "keyword": {"x|y": {"dE": 2.5, "dL": 0.02, "dC": 0.01, "dH_deg": 42.0}},
        },
    }
    html = _drift_table(drift, "t", ["bg", "keyword"])
    assert "dH - dC" in html       # null hue renders '-', never a fake number
    assert "dH 42&deg;" in html    # numeric hue still renders with degrees


def test_cross_variant_drift_notes_lightness_inversion(comparison):
    pc = comparison["per_candidate"]["candidate-a-restrained"]
    assert "informational" in pc["cross_variant_drift"]["note"].lower()


# ===========================================================================
# disagreement log + tradeoffs
# ===========================================================================


def test_disagreement_log_is_open_template(comparison):
    log = comparison["disagreement_log"]
    assert len(log["entries"]) >= 3
    for e in log["entries"]:
        assert e["status"] == "open"
        assert e["visual_judgment"] is None  # left for Phase 7


def test_tradeoffs_flagged_per_candidate(comparison):
    assert len(comparison["tradeoffs"]) == 3
    for t in comparison["tradeoffs"]:
        assert t["declared_tradeoffs"]  # each flags its own tradeoffs


# ===========================================================================
# visuals: side-by-side specimens + diagnostics + CVD views
# ===========================================================================


def test_family_specimens_page_has_every_language(families, spec):
    html = candidate_family_specimens_html(families[0], spec)
    for label in LANGS:
        assert label in html, f"{label} specimen missing from family page"
    # three variants present as scopes
    for v in ("day", "evening", "night"):
        assert f"scope-{v}" in html
    # CVD views scoped in CSS
    for view in ("normal", "protan", "deutan", "tritan"):
        assert f"body.view-{view}" in html
    # critical states with redundant markers
    assert 'class="mark"' in html
    # self-contained
    assert "<style>" in html and "src=" not in html and 'href="' not in html


def test_family_specimens_page_is_deterministic(families, spec):
    a = candidate_family_specimens_html(families[0], spec)
    b = candidate_family_specimens_html(families[0], spec)
    assert a == b


def test_comparison_page_has_matrix_and_specimens(comparison, families, spec):
    html = candidate_comparison_html(comparison, families, spec)
    assert "Candidate matrix" in html
    assert "Side-by-side specimen" in html
    assert "Cross-candidate per-role drift" in html
    assert "disagreement" in html.lower()
    # the side-by-side shows all three candidates
    for s in STRATEGIES:
        assert s in html


def test_matrix_html_renders_mel_ratio_led_day(comparison, families, spec):
    """mel_ratio_led_day was computed into every matrix row but never shown;
    the HTML matrix renders it next to the LED night column (the text table
    stays unchanged -- it is already at width)."""
    html = candidate_comparison_html(comparison, families, spec)
    assert "mel ratio LED day" in html
    for m in comparison["matrix"]:
        assert f'{m["mel_ratio_led_day"]:.3f}' in html


def test_comparison_svg_is_valid(families, spec):
    svg = candidate_comparison_svg(families, spec)
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    # three candidate columns
    for s in STRATEGIES:
        assert s in svg


def test_comparison_text_runs(comparison):
    txt = candidate_comparison_text(comparison)
    assert "matrix" in txt.lower() and "tradeoffs" in txt.lower()


# ===========================================================================
# reproducibility: committed reports match fresh builds
# ===========================================================================


def test_committed_comparison_matches_fresh(families, spec):
    fresh = to_json(compare_candidates(families, spec))
    committed = (REPO / "out/candidates/comparison.json").read_text()
    assert fresh == committed


def test_committed_comparison_html_matches_fresh(comparison, families, spec):
    fresh = candidate_comparison_html(comparison, families, spec)
    committed = (REPO / "out/candidates/comparison.html").read_text()
    assert fresh == committed


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_committed_specimen_page_matches_fresh(strategy, families, spec):
    fb = next(f for f in families if f.binding.name == f"candidate-{strategy}")
    fresh = candidate_family_specimens_html(fb, spec)
    committed = (
        REPO / "out/candidates" / f"candidate-{strategy}"
        / f"candidate-{strategy}.specimens.html"
    ).read_text()
    assert fresh == committed


# ===========================================================================
# CLI: grotto candidates rebuilds everything
# ===========================================================================


def test_cli_candidates(tmp_path):
    rc = main(_common() + ["candidates", "--out", str(tmp_path / "cand")])
    assert rc == 0
    out = tmp_path / "cand"
    # comparison + index
    assert (out / "comparison.json").exists()
    assert (out / "comparison.html").exists()
    assert (out / "comparison.svg").exists()
    assert (out / "index.json").exists()
    # per-candidate specimen pages + eval
    for s in STRATEGIES:
        d = out / f"candidate-{s}"
        assert (d / f"candidate-{s}.specimens.html").exists()
        assert (d / f"candidate-{s}.eval.json").exists()
    cmp = __import__("json").loads((out / "comparison.json").read_text())
    assert cmp["n_candidates"] == 3
