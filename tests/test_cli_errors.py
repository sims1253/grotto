"""CLI error-path and flag-coverage tests.

Every test here asserts that a bad invocation fails *cleanly*: a nonzero
exit with a short human-readable message on stderr (or an argparse
rejection with exit code 2 for invalid flag values) -- never a silent
success and never an unhandled traceback escaping :func:`grotto.cli.main`.

Invocations are in-process (like tests/test_cli.py); the single subprocess
test proves the same cleanliness at the real console entry point.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from grotto.cli import main
from grotto.spectral import DISPLAYS

REPO = Path(__file__).resolve().parents[1]

FIXTURES = REPO / "themes/fixtures"
TRIO = [
    str(FIXTURES / "eval-day.yaml"),
    str(FIXTURES / "eval-evening.yaml"),
    str(FIXTURES / "eval-night.yaml"),
]


def _common_args():
    return [
        "--roles", str(REPO / "spec/roles.yaml"),
        "--distances", str(REPO / "spec/distance-matrix.yaml"),
        "--environments", str(REPO / "spec/environments.yaml"),
    ]


# ---------------------------------------------------------------------------
# (a) palette --display <unknown>
# ---------------------------------------------------------------------------


def test_palette_unknown_display_rejected_by_argparse(tmp_path, capsys):
    """``--display bogus`` is rejected by argparse with exit code 2, before
    any palette is loaded or any output file is written."""
    with pytest.raises(SystemExit) as excinfo:
        main(
            _common_args()
            + [
                "palette",
                str(FIXTURES / "eval-night.yaml"),
                "--out", str(tmp_path),
                "--display", "bogus",
            ]
        )
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "invalid choice" in err
    assert "'bogus'" in err
    # nothing was produced
    assert not any(tmp_path.iterdir())


def test_display_flag_choices_track_spectral_displays(tmp_path, capsys):
    """The argparse choices must be exactly the display models grotto.spectral
    actually implements (the report layer raises ``unknown display model``
    otherwise; the parser is the clean first line of defence)."""
    with pytest.raises(SystemExit) as excinfo:
        main(
            _common_args()
            + [
                "palette",
                str(FIXTURES / "eval-night.yaml"),
                "--out", str(tmp_path),
                "--display", "__no_such_display__",
            ]
        )
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    for name in sorted(DISPLAYS):
        assert name in err, f"--display choices lost {name!r}"


# ---------------------------------------------------------------------------
# (b) references with no reference YAMLs
# ---------------------------------------------------------------------------


def test_references_empty_dir_fails_cleanly(tmp_path, capsys):
    """An empty references dir is a clean nonzero failure with a stderr
    message, and no report files are written to --out."""
    empty_dir = tmp_path / "empty-references"
    empty_dir.mkdir()
    out = tmp_path / "out"
    rc = main(
        _common_args()
        + ["references", "--references-dir", str(empty_dir), "--out", str(out)]
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "no reference files found" in err
    # the command must not leave half-written reports behind
    files = list(out.iterdir()) if out.exists() else []
    assert files == [], f"unexpected output files: {files}"


# ---------------------------------------------------------------------------
# (c) stability with fewer than two palettes
# ---------------------------------------------------------------------------


def test_stability_single_palette_fails_cleanly(tmp_path, capsys):
    """stability.cross_variant_report raises ValueError for <2 variants;
    the CLI boundary must turn that into rc != 0 plus a clear message
    (returning from main() at all already proves no exception escaped)."""
    rc = main(
        _common_args()
        + ["stability", str(FIXTURES / "eval-day.yaml"), "--out", str(tmp_path)]
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "at least 2 variants" in err
    assert "Traceback" not in err
    # no half-written stability report
    assert not (tmp_path / "stability.report.json").exists()
    assert not (tmp_path / "stability.html").exists()


def test_stability_single_palette_no_traceback_on_console(tmp_path):
    """End-to-end at the real entry point: the same failure prints a one-line
    error, not a stack trace."""
    proc = subprocess.run(
        [
            sys.executable, "-m", "grotto.cli",
            "stability", str(FIXTURES / "eval-day.yaml"),
            "--out", str(tmp_path / "out"),
        ],
        capture_output=True, text=True, cwd=REPO,
    )
    assert proc.returncode == 1
    assert "Traceback" not in proc.stderr
    assert "at least 2 variants" in proc.stderr


# ---------------------------------------------------------------------------
# (d) --max-hue-drift plumbing
# ---------------------------------------------------------------------------


def test_stability_max_hue_drift_flag_reaches_report(tmp_path):
    """An unusually small threshold must land in the report (both as the
    recorded threshold and as surfaced drift violations)."""
    rc = main(
        _common_args() + ["stability", *TRIO, "--out", str(tmp_path), "--max-hue-drift", "0.5"]
    )
    assert rc == 0
    d = json.loads((tmp_path / "stability.report.json").read_text())
    assert d["max_hue_drift_threshold_deg"] == 0.5
    assert len(d["drift_violations"]) >= 1
    assert d["ok"] is False


def test_stability_default_drift_threshold_matches_environments_spec(tmp_path):
    """Without the flag the threshold must equal the stability contract in
    spec/environments.yaml (12 deg), and the committed fixture trio passes it."""
    env_spec = yaml.safe_load((REPO / "spec/environments.yaml").read_text())
    spec_threshold = float(env_spec["stability"]["max_hue_drift_deg"])
    assert spec_threshold == 12.0  # guard: spec moved, update this test knowingly

    rc = main(_common_args() + ["stability", *TRIO, "--out", str(tmp_path)])
    assert rc == 0
    d = json.loads((tmp_path / "stability.report.json").read_text())
    assert d["max_hue_drift_threshold_deg"] == spec_threshold
    # the committed fixture trio is stable enough for the spec threshold
    assert d["drift_violations"] == []


def test_stability_tighter_threshold_surfaces_more_violations(tmp_path):
    """0.5 deg must flag at least everything the 12 deg default flags."""
    out_loose = tmp_path / "default"
    out_tight = tmp_path / "tight"
    assert main(_common_args() + ["stability", *TRIO, "--out", str(out_loose)]) == 0
    assert (
        main(_common_args() + ["stability", *TRIO, "--out", str(out_tight), "--max-hue-drift", "0.5"])
        == 0
    )
    loose = json.loads((out_loose / "stability.report.json").read_text())
    tight = json.loads((out_tight / "stability.report.json").read_text())
    loose_roles = {v["role"] for v in loose["drift_violations"]}
    tight_roles = {v["role"] for v in tight["drift_violations"]}
    assert loose_roles <= tight_roles
    assert len(tight_roles) >= 1


# ---------------------------------------------------------------------------
# (e) nonexistent --roles / --distances / --environments overrides
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("flag", ["--roles", "--distances", "--environments"])
def test_palette_nonexistent_spec_override_fails_cleanly(tmp_path, capsys, flag):
    """A missing spec file must produce a clear one-line error naming the
    path -- not a traceback, and not a failure attributed to something else."""
    missing = tmp_path / f"missing-{flag.lstrip('-')}.yaml"
    rc = main(
        _common_args()
        + [flag, str(missing), "palette", str(FIXTURES / "eval-night.yaml"), "--out", str(tmp_path / "out")]
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert str(missing) in err
    assert "No such file or directory" in err
    assert "Traceback" not in err
    # nothing half-written
    assert not (tmp_path / "out" / "eval-night.report.json").exists()
