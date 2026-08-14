"""Phase 8a: static VS Code evaluation-preview adapter.

Acceptance points:
  * exactly nine contributes.themes (3 families x Day/Evening/Night), uiTheme
    `vs` for Day and `vs-dark` for Evening/Night;
  * themes/*.json are VALID, DETERMINISTIC regeneration of the committed
    files, with candidate source hashes recorded and correct;
  * required workbench keys present; semantic highlighting enabled with the
    standard selectors; parameter italic; deprecated strikethrough;
  * mapping integrity against spec/roles.yaml;
  * NO runtime surface: no main/commands/activationEvents/scripts/deps, no
    JS/TS files, exactly nine theme JSONs.
No winner is selected anywhere -- these are candidate previews.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from grotto.cli import main
from grotto.spec import RoleSpec
from grotto.vscode import write_extension

REPO = Path(__file__).resolve().parents[1]
EXT = REPO / "editors/vscode"
CAND = REPO / "themes/candidates"
MAPPING = REPO / "spec/mappings/vscode.yaml"

EXPECTED_LABELS = {
    "Grotto Restrained Day", "Grotto Restrained Evening", "Grotto Restrained Night",
    "Grotto Balanced Day", "Grotto Balanced Evening", "Grotto Balanced Night",
    "Grotto Expressive Day", "Grotto Expressive Evening", "Grotto Expressive Night",
}


@pytest.fixture(scope="module")
def roles() -> RoleSpec:
    return RoleSpec.load(REPO / "spec/roles.yaml")


@pytest.fixture(scope="module")
def mapping() -> dict:
    return yaml.safe_load(MAPPING.read_text())


@pytest.fixture(scope="module")
def package() -> dict:
    return json.loads((EXT / "package.json").read_text())


@pytest.fixture(scope="module")
def themes() -> dict[str, dict]:
    files = sorted((EXT / "themes").glob("*.json"))
    assert len(files) == 9
    return {f.name: json.loads(f.read_text()) for f in files}


# -- package.json: exactly nine contributions, correct uiTheme ------------

def test_nine_contributions(package):
    assert len(package["contributes"]["themes"]) == 9
    labels = {t["label"] for t in package["contributes"]["themes"]}
    assert labels == EXPECTED_LABELS
    for t in package["contributes"]["themes"]:
        variant = t["label"].rsplit(" ", 1)[-1].lower()
        expect = "vs" if variant == "day" else "vs-dark"
        assert t["uiTheme"] == expect, t["label"]
        assert (EXT / t["path"]).is_file(), t["path"]


def test_contributions_agree_with_mapping(package, mapping):
    listed = {t["label"] for t in package["contributes"]["themes"]}
    mapped = {t["label"] for t in mapping["extension"]["themes"]}
    assert listed == mapped


# -- determinism + hashes ---------------------------------------------------

def test_regeneration_is_byte_identical(tmp_path):
    written = write_extension(tmp_path, candidates_dir=CAND, mapping_path=MAPPING)
    assert len(written) == 9
    for rel, path in written.items():
        committed = EXT / rel
        assert committed.is_file()
        assert path.read_bytes() == committed.read_bytes(), f"{rel} drifted"


def test_cli_vscode_matches_committed(tmp_path):
    rc = main(["vscode", "--out", str(tmp_path), "--candidates", str(CAND),
               "--mapping", str(MAPPING)])
    assert rc == 0
    for committed in sorted((EXT / "themes").glob("*.json")):
        regen = tmp_path / "themes" / committed.name
        assert regen.read_bytes() == committed.read_bytes()


def test_candidate_hashes(themes):
    for name, theme in themes.items():
        src = CAND / theme["grotto"]["palette"]
        assert src.is_file(), f"{name}: source palette missing"
        digest = hashlib.sha256(src.read_bytes()).hexdigest()
        assert theme["grotto"]["palette_sha256"] == digest
        assert theme["grotto"]["candidate"] is True
        # every committed palette is one of the nine candidates
        assert theme["grotto"]["palette"].startswith("candidate-")


def test_variant_type(themes):
    for name, theme in themes.items():
        assert "day" not in name or theme["type"] == "light"
        assert ("evening" in name or "night" in name) or theme["type"] == "light"
        if "evening" in name or "night" in name:
            assert theme["type"] == "dark"


# -- workbench colors -------------------------------------------------------

def test_required_workbench_keys(themes, mapping):
    required = mapping["required_workbench"]
    for name, theme in themes.items():
        for key in required:
            assert key in theme["colors"], f"{name}: missing {key}"


def test_color_format_and_transparency_policy(themes):
    # Opaque everywhere except the ids whose policy contract expects alpha
    # (spec/mappings/vscode.yaml): the four content-preserving secondary
    # overlays at alpha 80 and editorUnnecessaryCode.opacity at alpha 66.
    # These five are the ONLY RGBA ids; notably editor.selectionBackground
    # and editor.findMatchBackground must stay opaque #rrggbb.
    alpha_exact = {
        "editor.inactiveSelectionBackground": "80",
        "editor.selectionHighlightBackground": "80",
        "editor.findMatchHighlightBackground": "80",
        "editor.hoverHighlightBackground": "80",
        "editorUnnecessaryCode.opacity": "66",
    }
    for name, theme in themes.items():
        for key, hx in theme["colors"].items():
            hx = hx.lstrip("#")
            if key in alpha_exact:
                assert len(hx) == 8, f"{name}: {key} must be #rrggbbaa"
                assert hx[6:] == alpha_exact[key], \
                    f"{name}: {key} alpha must be {alpha_exact[key]}, got {hx[6:]}"
            else:
                assert len(hx) == 6, f"{name}: {key} must be opaque #rrggbb, got #{hx}"
            int(hx, 16)  # valid hex


def test_colors_come_from_the_named_candidate(themes):
    import grotto.spec as spec_mod

    for name, theme in themes.items():
        pal = spec_mod.load(CAND / theme["grotto"]["palette"])
        assert theme["colors"]["editor.background"] == pal["bg"]
        assert theme["colors"]["editor.foreground"] == pal["fg"]
        assert theme["colors"]["editor.selectionBackground"] == pal["selection"]
        assert theme["colors"]["editorError.foreground"] == pal["error"]


# -- tokens + semantics -----------------------------------------------------

def test_semantic_highlighting(themes):
    for name, theme in themes.items():
        assert theme["semanticHighlighting"] is True
        sem = theme["semanticTokenColors"]
        assert len(sem) >= 20
        # ordinary variables/parameters neutral
        assert sem["variable"]["foreground"] == theme["colors"]["editor.foreground"]
        assert sem["parameter"]["fontStyle"] == "italic"
        assert sem["parameter"]["foreground"] == theme["colors"]["editor.foreground"]
        # deprecated -> strikethrough (modifier rule, no colour change)
        assert sem["*.deprecated"]["fontStyle"] == "strikethrough"
        assert "foreground" not in sem["*.deprecated"]
        for sel in ("function", "type", "keyword", "string", "number", "comment",
                    "property", "namespace", "enumMember", "macro"):
            assert sel in sem, f"{name}: semantic selector {sel} missing"


def test_textmate_rules(themes, mapping):
    emitted_scopes = [tuple(r["scope"]) for r in next(iter(themes.values()))["tokenColors"]]
    mapped_scopes = [tuple(r["scopes"]) for r in mapping["textmate"]]
    assert emitted_scopes == mapped_scopes
    joined = " ".join(s for scope in emitted_scopes for s in scope)
    # broad built-in-language coverage
    for expected in ("comment", "string", "keyword", "constant.numeric",
                     "entity.name.function", "support.function", "variable.parameter",
                     "entity.name.type", "punctuation"):
        assert expected in joined
    # deprecated strikethrough via TextMate
    for theme in themes.values():
        dep = [r for r in theme["tokenColors"] if "invalid.deprecated" in r["scope"]]
        assert dep and dep[0]["settings"]["fontStyle"] == "strikethrough"


# -- R grammar normalization (regression) ---------------------------------
#
# Developer evidence from `Developer: Inspect Editor Tokens and Scopes`
# (Balanced Night, R file, no semantic tokens present):
#   * plain `log` outside a call: `source.r`, no selector -> neutral fg;
#   * `log` / `temp_c` inside a call:
#     `meta.function-call.arguments.r > meta.function-call.r > source.r`,
#     winner `meta.function-call` -> function colour -- whole argument lists
#     of plain identifiers rendered as function names;
#   * `$`: `keyword.accessor.dollar.r`, winner generic `keyword`, so the
#     accessor lost the operator rule.
# Normalization under test: the generic `meta.function-call` stays on
# `function` (actual function names / nested calls keep their highlight), a
# LATER R-specific `meta.function-call.arguments.r` rule maps to `fg` so
# plain R arguments override the broad parent, and `keyword.accessor.dollar.r`
# rides an operator rule placed after the generic keyword rule.

def _find_rule(scopes: list[tuple[str, ...]], scope: str):
    """Index of the first rule whose scope list contains `scope`, else None."""
    return next((i for i, s in enumerate(scopes) if scope in s), None)


def test_r_call_arguments_normalized_mapping(mapping):
    rules = mapping["textmate"]
    scopes = [tuple(r["scopes"]) for r in rules]

    function_idx = _find_rule(scopes, "meta.function-call")
    assert function_idx is not None, "meta.function-call must stay mapped"
    assert rules[function_idx]["role"] == "function"
    # the broad parent stays generic: it must not absorb the R argument scope
    assert "meta.function-call.arguments.r" not in scopes[function_idx]

    arg_idx = _find_rule(scopes, "meta.function-call.arguments.r")
    assert arg_idx is not None, \
        "meta.function-call.arguments.r needs its own rule"
    assert arg_idx > function_idx, "R argument rule must follow the function rule"
    assert rules[arg_idx]["role"] == "fg"
    # narrowly R-specific: nothing else is neutralized alongside it
    assert scopes[arg_idx] == ("meta.function-call.arguments.r",)

    keyword_idx = _find_rule(scopes, "keyword")
    dollar_idx = _find_rule(scopes, "keyword.accessor.dollar.r")
    assert dollar_idx is not None, "keyword.accessor.dollar.r must be mapped"
    assert rules[dollar_idx]["role"] == "operator"
    assert dollar_idx > keyword_idx, \
        "dollar accessor rule must follow the generic keyword rule"


def test_r_call_arguments_normalized_themes(themes):
    import grotto.spec as spec_mod

    for name, theme in themes.items():
        pal = spec_mod.load(CAND / theme["grotto"]["palette"])
        rules = theme["tokenColors"]
        scopes = [tuple(r["scope"]) for r in rules]

        function_idx = _find_rule(scopes, "meta.function-call")
        assert function_idx is not None, f"{name}: meta.function-call missing"
        assert rules[function_idx]["settings"]["foreground"] == pal["function"]

        arg_idx = _find_rule(scopes, "meta.function-call.arguments.r")
        assert arg_idx is not None, \
            f"{name}: meta.function-call.arguments.r rule missing"
        assert arg_idx > function_idx, f"{name}: argument rule ordering"
        assert rules[arg_idx]["settings"]["foreground"] == pal["fg"]

        dollar_idx = _find_rule(scopes, "keyword.accessor.dollar.r")
        assert dollar_idx is not None, \
            f"{name}: keyword.accessor.dollar.r rule missing"
        assert rules[dollar_idx]["settings"]["foreground"] == pal["operator"]


# -- mapping integrity ------------------------------------------------------

def test_mapping_roles_exist(roles, mapping):
    for key, v in mapping["workbench"].items():
        role = v["role"] if isinstance(v, dict) else v
        assert role in roles, f"workbench.{key} -> unknown role {role}"
    for rule in mapping["textmate"]:
        assert rule["role"] in roles, rule
    for rule in mapping["semantic"]:
        if "role" in rule:
            assert rule["role"] in roles, rule


def test_mapping_covers_all_nine_candidates(mapping):
    fams = mapping["families"]
    assert set(fams) == {"restrained", "balanced", "expressive"}
    for fam in fams.values():
        for variant in ("day", "evening", "night"):
            assert (CAND / f"{fam['candidate']}.{variant}.yaml").is_file()


# -- no runtime surface -----------------------------------------------------

def test_no_runtime_surface(package):
    pkg_keys = set(package)
    forbidden = {"main", "browser", "activationEvents", "scripts", "commands",
                 "dependencies", "devDependencies", "extensionDependencies"}
    assert pkg_keys & forbidden == set(), f"runtime keys present: {pkg_keys & forbidden}"
    assert package["private"] is True
    assert set(package["contributes"]) == {"themes"}
    # files on disk: only static manifest + docs + the nine generated themes
    files = sorted(p.relative_to(EXT).as_posix() for p in EXT.rglob("*") if p.is_file())
    expected = ["README.md", "package.json"] + [
        t["path"].removeprefix("./") for t in package["contributes"]["themes"]
    ]
    assert files == sorted(expected), files
    for p in EXT.rglob("*"):
        assert p.suffix not in (".js", ".ts", ".mjs", ".cjs"), p
        assert p.name not in ("node_modules",), p
        assert p.suffix != ".vsix", p
