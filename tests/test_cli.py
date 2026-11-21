"""CLI smoke tests: every subcommand runs end-to-end against the repo specs."""

import json
from pathlib import Path

import pytest

from grotto.cli import main

REPO = Path(__file__).resolve().parents[1]


def _common_args():
    return [
        "--roles", str(REPO / "spec/roles.yaml"),
        "--distances", str(REPO / "spec/distance-matrix.yaml"),
        "--environments", str(REPO / "spec/environments.yaml"),
    ]


def test_cli_palette(tmp_path):
    rc = main(
        _common_args()
        + ["palette", str(REPO / "themes/fixtures/eval-night-full.yaml"), "--out", str(tmp_path)]
    )
    assert rc == 0
    files = {p.name for p in tmp_path.iterdir()}
    assert "eval-night-full.report.json" in files
    assert "eval-night-full.html" in files
    assert "eval-night-full.svg" in files
    # the JSON is valid and self-describes as non-candidate
    d = json.loads((tmp_path / "eval-night-full.report.json").read_text())
    assert d["palette"]["is_candidate"] is False


def test_cli_palette_reference_theme(tmp_path):
    """Reference themes (hex, partial) must also flow through the CLI."""
    rc = main(
        _common_args()
        + ["palette", str(REPO / "themes/references/nord.yaml"), "--out", str(tmp_path)]
    )
    assert rc == 0
    assert (tmp_path / "nord.report.json").exists()


def test_cli_stability(tmp_path):
    rc = main(
        _common_args()
        + [
            "stability",
            str(REPO / "themes/fixtures/eval-day.yaml"),
            str(REPO / "themes/fixtures/eval-evening.yaml"),
            str(REPO / "themes/fixtures/eval-night.yaml"),
            "--out", str(tmp_path),
        ]
    )
    assert rc == 0
    assert (tmp_path / "stability.report.json").exists()
    assert (tmp_path / "stability.html").exists()


def test_cli_specimens(tmp_path):
    rc = main(_common_args() + ["specimens", "--out", str(tmp_path)])
    assert rc == 0
    names = {p.name for p in tmp_path.iterdir()}
    for fn in ("rolling.py", "rolling.rs", "rolling.ts", "rolling.sh",
               "rolling.json", "rolling.yaml", "rolling.md", "rolling.R"):
        assert fn in names, f"specimen {fn} not written"
