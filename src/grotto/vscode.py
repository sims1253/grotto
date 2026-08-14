"""L3 adapter: deterministic VS Code theme generation (evaluation preview).

Phase 8a exists because human evaluation (HUMAN_EVALUATION.md) requires the
three candidate families to be seen in a real editor.  This module is the
single small public interface behind the generator: :func:`write_extension`
reads ``spec/mappings/vscode.yaml`` plus the nine generated candidate palettes
in ``themes/candidates/*.yaml`` and writes one theme JSON per
family x variant under ``editors/vscode/themes/``.

Boundaries (deliberate, see editors/vscode/README.md):
  * static adapter only -- no runtime JS/TS, no commands, no activation
    events, no automatic variant switching, no publishing machinery;
  * the nine themes are an EVALUATION PREVIEW; no winner is selected;
  * generation is deterministic: same inputs -> byte-identical JSON, so the
    committed files are re-verified by tests instead of being hand-copied.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from .spec import Palette, RoleSpec

GENERATOR = "grotto-vscode/1"

DEFAULT_MAPPING = "spec/mappings/vscode.yaml"
DEFAULT_CANDIDATES = "themes/candidates"

_NOTE = (
    "EVALUATION PREVIEW generated from a Phase 5 CANDIDATE palette. "
    "No theme is selected, ranked or final (DESIGN.md section 1)."
)


@dataclass(frozen=True)
class _Mapping:
    """Parsed spec/mappings/vscode.yaml (validated against spec/roles.yaml)."""

    themes: list[dict]          # [{family, variant, label, path}]
    variants: dict              # variant -> {ui_theme, type}
    families: dict              # family -> {candidate, label}
    workbench: dict             # vscode color id -> role | {role, alpha}
    required_workbench: list[str]
    textmate: list[dict]        # [{role, scopes, font_style?}]
    semantic: list[dict]        # [{selector, role?, font_style?}]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_mapping(mapping_path: Path, roles: RoleSpec | None) -> _Mapping:
    d = yaml.safe_load(mapping_path.read_text(encoding="utf-8"))
    if not isinstance(d, dict):
        raise ValueError(f"{mapping_path}: expected a mapping")
    m = _Mapping(
        themes=list(d["extension"]["themes"]),
        variants=dict(d["variants"]),
        families=dict(d["families"]),
        workbench=dict(d["workbench"]),
        required_workbench=list(d["required_workbench"]),
        textmate=list(d["textmate"]),
        semantic=list(d["semantic"]),
    )
    if len(m.themes) != d["extension"]["theme_count"]:
        raise ValueError(f"{mapping_path}: theme_count disagrees with listed themes")
    seen: set[tuple[str, str]] = set()
    for t in m.themes:
        key = (t["family"], t["variant"])
        if key in seen:
            raise ValueError(f"{mapping_path}: duplicate theme {key}")
        seen.add(key)
        if t["variant"] not in m.variants:
            raise ValueError(f"{mapping_path}: unknown variant {t['variant']!r}")
        if t["family"] not in m.families:
            raise ValueError(f"{mapping_path}: unknown family {t['family']!r}")
    # mapping integrity: every referenced role must exist in L1
    if roles is not None:
        for key, v in m.workbench.items():
            role = v["role"] if isinstance(v, dict) else v
            if role not in roles:
                raise ValueError(f"{mapping_path}: workbench.{key} -> unknown role {role!r}")
        for rule in m.textmate:
            if rule["role"] not in roles:
                raise ValueError(f"{mapping_path}: textmate rule -> unknown role {rule['role']!r}")
        for rule in m.semantic:
            if "role" in rule and rule["role"] not in roles:
                raise ValueError(
                    f"{mapping_path}: semantic {rule['selector']!r} -> unknown role {rule['role']!r}"
                )
    return m


def _build_theme(palette: Palette, label: str, variant: str, m: _Mapping,
                 *, source_name: str, source_sha256: str) -> dict:
    """One theme-JSON dict; construction order is fixed for determinism."""
    colors: dict[str, str] = {}
    for key in m.workbench:                       # yaml order preserved
        v = m.workbench[key]
        if isinstance(v, dict):
            colors[key] = palette[v["role"]] + v["alpha"]
        else:
            colors[key] = palette[v]
    missing = [k for k in m.required_workbench if k not in colors]
    if missing:
        raise ValueError(f"required workbench keys missing from mapping: {missing}")

    token_colors = []
    for rule in m.textmate:
        settings: dict[str, str] = {"foreground": palette[rule["role"]]}
        if rule.get("font_style"):
            settings["fontStyle"] = rule["font_style"]
        token_colors.append({"scope": list(rule["scopes"]), "settings": settings})

    semantic: dict[str, object] = {}
    for rule in m.semantic:
        if "role" in rule:
            entry: object = {"foreground": palette[rule["role"]]}
            if rule.get("font_style"):
                entry["fontStyle"] = rule["font_style"]
        else:
            entry = {"fontStyle": rule["font_style"]}   # style-only modifier rule
        semantic[rule["selector"]] = entry

    return {
        "name": label,
        "type": m.variants[variant]["type"],
        "semanticHighlighting": True,
        "colors": colors,
        "tokenColors": token_colors,
        "semanticTokenColors": semantic,
        "grotto": {
            "generator": GENERATOR,
            "palette": source_name,
            "palette_sha256": source_sha256,
            "candidate": True,
            "note": _NOTE,
        },
    }


def _dump(theme: dict) -> str:
    return json.dumps(theme, indent=2, ensure_ascii=True) + "\n"


def write_extension(
    out_dir: str | Path = "editors/vscode",
    *,
    candidates_dir: str | Path = DEFAULT_CANDIDATES,
    mapping_path: str | Path = DEFAULT_MAPPING,
    roles: RoleSpec | None = None,
) -> dict[str, Path]:
    """Generate the nine evaluation-preview theme JSONs.

    Returns ``{relative theme path: written file}``.  ``package.json`` and
    ``README.md`` are committed static files; only ``themes/*.json`` is
    generated, byte-deterministically, from the candidate palettes.
    """
    from .spec import RoleSpec as _RS
    if roles is None:
        roles = _RS.load("spec/roles.yaml")
    mapping = _load_mapping(Path(mapping_path), roles)
    out = Path(out_dir)
    themes_dir = out / "themes"
    themes_dir.mkdir(parents=True, exist_ok=True)

    written: dict[str, Path] = {}
    for t in mapping.themes:
        fam = mapping.families[t["family"]]
        src = Path(candidates_dir) / f"{fam['candidate']}.{t['variant']}.yaml"
        palette = Palette.from_yaml(src)
        if not palette.is_candidate:
            raise ValueError(f"{src}: refusing to ship a non-candidate palette")
        theme = _build_theme(
            palette, t["label"], t["variant"], mapping,
            source_name=src.name, source_sha256=_sha256_file(src),
        )
        path = out / t["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_dump(theme), encoding="utf-8", newline="\n")
        written[t["path"]] = path
    return written
