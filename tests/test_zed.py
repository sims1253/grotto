"""Static Zed evaluation-preview adapter."""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from pathlib import Path

import pytest
import yaml

from grotto.cli import main
from grotto.spec import RoleSpec, load
from grotto.zed import GENERATOR, SCHEMA, write_extension

REPO = Path(__file__).resolve().parents[1]
EXT = REPO / "editors/zed"
CANDIDATES = REPO / "themes/candidates"
MAPPING = REPO / "spec/mappings/zed.yaml"
THEME_FILE = EXT / "themes/grotto.json"
PROVENANCE_FILE = EXT / "provenance.json"
RGBA = re.compile(r"^#[0-9a-fA-F]{8}$")


@pytest.fixture(scope="module")
def mapping() -> dict:
    return yaml.safe_load(MAPPING.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def family() -> dict:
    return json.loads(THEME_FILE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def provenance() -> dict:
    return json.loads(PROVENANCE_FILE.read_text(encoding="utf-8"))


def test_extension_is_static_and_minimal():
    manifest = tomllib.loads((EXT / "extension.toml").read_text(encoding="utf-8"))
    assert manifest["id"] == "grotto-evaluation-preview"
    assert manifest["schema_version"] == 1
    assert "evaluation" in manifest["description"].lower()
    assert sorted(path.name for path in (EXT / "themes").glob("*.json")) == ["grotto.json"]
    forbidden = {"Cargo.toml", "package.json", "src", "dist", "node_modules"}
    assert not forbidden.intersection(path.name for path in EXT.iterdir())


def test_theme_family_has_nine_unique_candidates(family, mapping):
    assert family["$schema"] == SCHEMA
    assert family["name"] == "Grotto Evaluation Preview"
    themes = family["themes"]
    assert len(themes) == mapping["extension"]["theme_count"] == 9
    names = [theme["name"] for theme in themes]
    assert len(names) == len(set(names))
    assert names == [theme["label"] for theme in mapping["extension"]["themes"]]


def test_appearances_match_variants(family, mapping):
    for theme, entry in zip(family["themes"], mapping["extension"]["themes"], strict=True):
        expected = mapping["variants"][entry["variant"]]["appearance"]
        assert theme["appearance"] == expected


def test_regeneration_is_byte_identical(tmp_path):
    written = write_extension(
        tmp_path, candidates_dir=CANDIDATES, mapping_path=MAPPING,
        roles=RoleSpec.load(REPO / "spec/roles.yaml"),
    )
    assert set(written) == {"themes/grotto.json", "provenance.json"}
    for relative, generated in written.items():
        assert generated.read_bytes() == (EXT / relative).read_bytes()


def test_cli_matches_committed_files(tmp_path):
    rc = main([
        "--roles", str(REPO / "spec/roles.yaml"), "zed",
        "--out", str(tmp_path), "--candidates", str(CANDIDATES),
        "--mapping", str(MAPPING),
    ])
    assert rc == 0
    for relative in ("themes/grotto.json", "provenance.json"):
        assert (tmp_path / relative).read_bytes() == (EXT / relative).read_bytes()


def test_provenance_hashes_canonical_candidates(provenance):
    assert provenance["generator"] == GENERATOR
    assert provenance["candidate"] is True
    assert len(provenance["themes"]) == 9
    for entry in provenance["themes"]:
        source = CANDIDATES / entry["palette"]
        assert source.is_file()
        assert entry["palette"].startswith("candidate-")
        assert entry["palette_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()


def test_required_style_and_palette_sources(family, mapping, provenance):
    for theme, source_info in zip(family["themes"], provenance["themes"], strict=True):
        style = theme["style"]
        assert all(key in style for key in mapping["required_style"])
        palette = load(CANDIDATES / source_info["palette"])
        assert style["editor.background"] == palette["bg"] + "ff"
        assert style["editor.foreground"] == palette["fg"] + "ff"
        assert style["error"] == palette["error"] + "ff"


def test_all_emitted_colors_are_rgba(family):
    def walk(value):
        if isinstance(value, dict):
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
        elif isinstance(value, str) and value.startswith("#"):
            assert RGBA.fullmatch(value), value

    walk(family["themes"])


def test_syntax_is_semantic_and_neutral_where_intended(family):
    required = {
        "comment", "string", "number", "constant", "keyword", "operator",
        "function", "type", "variable", "variable.parameter", "property",
        "variant", "namespace", "attribute", "preproc", "punctuation", "tag",
        "embedded", "emphasis", "emphasis.strong", "link_text", "text.literal",
    }
    for theme in family["themes"]:
        syntax = theme["style"]["syntax"]
        assert required <= syntax.keys()
        foreground = theme["style"]["editor.foreground"]
        assert syntax["variable"]["color"] == foreground
        assert syntax["variable.parameter"]["color"] == foreground
        assert syntax["variable.parameter"]["font_style"] == "italic"
        assert syntax["emphasis.strong"]["font_weight"] == 700


def test_mapping_only_references_known_roles(mapping):
    roles = RoleSpec.load(REPO / "spec/roles.yaml")

    def role_of(value):
        return value if isinstance(value, str) else value["role"]

    values = list(mapping["style"].values()) + list(mapping["syntax"].values())
    values += [value for player in mapping["players"] for value in player.values()]
    assert all(role_of(value) in roles for value in values)
