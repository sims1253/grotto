"""Deterministic Zed theme-family generator for candidate evaluation.

This is a thin Layer 3 adapter. It reads the editor-independent candidate
palettes and ``spec/mappings/zed.yaml``, then writes one static Zed theme
family containing all nine evaluation variants. It does not select a winner,
switch themes at runtime, or define palette colours.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from .spec import Palette, RoleSpec

GENERATOR = "grotto-zed/1"
SCHEMA = "https://zed.dev/schema/themes/v0.2.0.json"
DEFAULT_MAPPING = "spec/mappings/zed.yaml"
DEFAULT_CANDIDATES = "themes/candidates"


@dataclass(frozen=True)
class _Mapping:
    extension: dict
    themes: list[dict]
    variants: dict
    families: dict
    style: dict
    players: list[dict]
    required_style: list[str]
    syntax: dict


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _role_of(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and isinstance(value.get("role"), str):
        return value["role"]
    raise ValueError(f"expected a role or role/alpha mapping, got {value!r}")


def _load_mapping(path: Path, roles: RoleSpec | None) -> _Mapping:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping")
    extension = dict(data["extension"])
    mapping = _Mapping(
        extension=extension,
        themes=list(extension["themes"]),
        variants=dict(data["variants"]),
        families=dict(data["families"]),
        style=dict(data["style"]),
        players=list(data.get("players", [])),
        required_style=list(data["required_style"]),
        syntax=dict(data["syntax"]),
    )
    if data.get("generator") != GENERATOR:
        raise ValueError(f"{path}: generator must be {GENERATOR!r}")
    if len(mapping.themes) != extension["theme_count"]:
        raise ValueError(f"{path}: theme_count disagrees with listed themes")

    seen: set[tuple[str, str]] = set()
    labels: set[str] = set()
    for theme in mapping.themes:
        key = (theme["family"], theme["variant"])
        if key in seen or theme["label"] in labels:
            raise ValueError(f"{path}: duplicate theme {key!r} or label")
        seen.add(key)
        labels.add(theme["label"])
        if theme["variant"] not in mapping.variants:
            raise ValueError(f"{path}: unknown variant {theme['variant']!r}")
        if theme["family"] not in mapping.families:
            raise ValueError(f"{path}: unknown family {theme['family']!r}")

    missing = [key for key in mapping.required_style if key not in mapping.style]
    if missing:
        raise ValueError(f"{path}: required style keys are not mapped: {missing}")

    if roles is not None:
        references: list[tuple[str, object]] = list(mapping.style.items())
        references.extend((f"syntax.{key}", value) for key, value in mapping.syntax.items())
        for index, player in enumerate(mapping.players):
            references.extend(
                (f"players[{index}].{key}", value) for key, value in player.items()
            )
        for key, value in references:
            role = _role_of(value)
            if role not in roles:
                raise ValueError(f"{path}: {key} -> unknown role {role!r}")
    return mapping


def _color(palette: Palette, value: object) -> str:
    role = _role_of(value)
    alpha = value.get("alpha", "ff") if isinstance(value, dict) else "ff"
    if not isinstance(alpha, str) or len(alpha) != 2:
        raise ValueError(f"invalid alpha for role {role!r}: {alpha!r}")
    int(alpha, 16)
    color = palette[role]
    if len(color) != 7 or not color.startswith("#"):
        raise ValueError(f"role {role!r} must be #RRGGBB, got {color!r}")
    return color + alpha.lower()


def _build_theme(palette: Palette, entry: dict, mapping: _Mapping) -> dict:
    style = {key: _color(palette, value) for key, value in mapping.style.items()}
    style["players"] = [
        {key: _color(palette, value) for key, value in player.items()}
        for player in mapping.players
    ]

    syntax: dict[str, dict[str, object]] = {}
    for name, rule in mapping.syntax.items():
        highlight: dict[str, object] = {"color": _color(palette, rule)}
        if rule.get("font_style"):
            highlight["font_style"] = rule["font_style"]
        if rule.get("font_weight"):
            highlight["font_weight"] = int(rule["font_weight"])
        syntax[name] = highlight
    style["syntax"] = syntax

    return {
        "name": entry["label"],
        "appearance": mapping.variants[entry["variant"]]["appearance"],
        "style": style,
    }


def _dump(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=True) + "\n"


def write_extension(
    out_dir: str | Path = "editors/zed",
    *,
    candidates_dir: str | Path = DEFAULT_CANDIDATES,
    mapping_path: str | Path = DEFAULT_MAPPING,
    roles: RoleSpec | None = None,
) -> dict[str, Path]:
    """Write the Zed theme family and a deterministic provenance sidecar."""
    if roles is None:
        roles = RoleSpec.load("spec/roles.yaml")
    mapping = _load_mapping(Path(mapping_path), roles)
    out = Path(out_dir)

    themes: list[dict] = []
    provenance_themes: list[dict] = []
    for entry in mapping.themes:
        family = mapping.families[entry["family"]]
        source = Path(candidates_dir) / f"{family['candidate']}.{entry['variant']}.yaml"
        palette = Palette.from_yaml(source)
        if not palette.is_candidate:
            raise ValueError(f"{source}: refusing to ship a non-candidate palette")
        themes.append(_build_theme(palette, entry, mapping))
        provenance_themes.append(
            {
                "name": entry["label"],
                "palette": source.name,
                "palette_sha256": _sha256_file(source),
            }
        )

    family_json = {
        "$schema": SCHEMA,
        "name": mapping.extension["family_name"],
        "author": mapping.extension["author"],
        "themes": themes,
    }
    provenance = {
        "generator": GENERATOR,
        "candidate": True,
        "note": "Unranked evaluation preview; no candidate is selected or final.",
        "themes": provenance_themes,
    }

    theme_path = out / mapping.extension["output"]
    provenance_path = out / mapping.extension["provenance"]
    theme_path.parent.mkdir(parents=True, exist_ok=True)
    provenance_path.parent.mkdir(parents=True, exist_ok=True)
    theme_path.write_text(_dump(family_json), encoding="utf-8", newline="\n")
    provenance_path.write_text(_dump(provenance), encoding="utf-8", newline="\n")
    return {
        mapping.extension["output"]: theme_path,
        mapping.extension["provenance"]: provenance_path,
    }
