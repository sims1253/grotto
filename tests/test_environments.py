"""Layer 2 loader: the salience_apca_step environment knob (Phase-7 feedback).

``salience_apca_step`` is the per-salience-level APCA Lc added to a role's
contrast-band centre above the normal reading level (model.py
NORMAL_SALIENCE), clamped to the band max.  Day carries the design judgment
(2.0, revised down from 5.0 after the widened step over-weighted lightness
and left moderate syntax darker than intended); evening/night keep it off at
0.0.
"""

from pathlib import Path

import yaml

from grotto.environments import Environments

REPO = Path(__file__).resolve().parents[1]


def test_salience_apca_step_loaded_from_spec():
    env = Environments.load(REPO / "spec/environments.yaml")
    assert env.environments["day"].salience_apca_step == 2.0
    assert env.environments["evening"].salience_apca_step == 0.0
    assert env.environments["night"].salience_apca_step == 0.0


def test_salience_apca_step_defaults_to_zero_when_absent(tmp_path):
    """An environment that omits the knob gets the neutral default 0.0."""
    src = yaml.safe_load((REPO / "spec/environments.yaml").read_text())
    for entry in src["environments"].values():
        entry.pop("salience_apca_step", None)
    p = tmp_path / "environments-no-step.yaml"
    p.write_text(yaml.safe_dump(src))
    env = Environments.load(p)
    assert set(env.environments) == {"day", "evening", "night"}
    assert all(e.salience_apca_step == 0.0 for e in env.environments.values())


def test_day_revision_restores_gain_and_softens_step():
    """Day uses more chroma and a softer contrast step; dark gains stay put."""
    env = Environments.load(REPO / "spec/environments.yaml")
    day, evening, night = (
        env.environments["day"], env.environments["evening"], env.environments["night"]
    )
    assert day.chroma_gain == 1.23
    assert day.salience_apca_step == 2.0
    assert evening.chroma_gain == 1.00
    assert night.chroma_gain == 0.95
    assert night.foreground_ceiling == 0.88
    assert day.rotation_cap_deg == 0.0
    assert night.rotation_cap_deg == 8.0
