"""Session template vs JSON-schema drift guard.

pullfrog (PR #1) caught the committed schema requiring ``randomization_seed``
-- a field the v3 protocol had just abolished -- while rejecting the
template's new ``timed_r_trials`` block under ``additionalProperties: false``.
Every session file filled out per the template would have failed validation.
This test compares the shipped template and schema STRUCTURALLY (no jsonschema
dependency) so that class of drift fails CI instead of Phase 7.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((REPO / "spec/human-evaluation.schema.json").read_text())
TEMPLATE = yaml.safe_load((REPO / "feedback/session-template.yaml").read_text())


def _schema_object(name: str) -> dict:
    node = SCHEMA["properties"][name]
    assert node.get("type") == "object", name
    return node


def test_template_root_keys_exist_in_schema():
    missing = set(TEMPLATE) - set(SCHEMA["properties"])
    assert not missing, f"template keys the schema would reject: {sorted(missing)}"


def test_schema_root_required_keys_exist_in_template():
    missing = set(SCHEMA["required"]) - set(TEMPLATE)
    assert not missing, f"schema requires keys the template does not carry: {sorted(missing)}"


def test_session_block_alignment():
    session = _schema_object("session")
    missing = set(TEMPLATE["session"]) - set(session["properties"])
    assert not missing, f"session keys the schema would reject: {sorted(missing)}"
    unrequired = set(session["required"]) - set(TEMPLATE["session"])
    assert not unrequired, f"session requires fields the template lacks: {sorted(unrequired)}"


def test_v3_allocation_replaces_the_abolished_seed():
    """The physical-draw/list-id rule removed the RNG seed; the schema must
    not resurrect it, and must know the list/draw fields instead."""
    session = _schema_object("session")
    assert "randomization_seed" not in session["properties"]
    assert "randomization_seed" not in session["required"]
    for key in ("r_corpus_list", "r_corpus_draw"):
        assert key in session["properties"], key
        assert key in session["required"], key


def test_timed_r_trials_item_fields_match_template():
    template_entry = TEMPLATE["timed_r_trials"][0]
    trial = SCHEMA["$defs"]["timedRTrial"]
    assert set(template_entry) == set(trial["properties"])
    assert set(trial["required"]) == set(trial["properties"])  # template rows are complete
    # list ids agree with the schedule vocabulary
    lists = trial["properties"]["list_id"]["enum"]
    assert [f"L{i}" for i in range(1, 10)] == [x for x in lists if x]


def test_role_observation_prominence_is_directional():
    """HUMAN_EVALUATION.md prescribes too_faint/appropriate/too_prominent;
    the schema's enum must carry exactly that vocabulary (plus bookkeeping)."""
    enum = SCHEMA["$defs"]["roleObservation"]["properties"]["prominence"]["enum"]
    for word in ("too_faint", "appropriate", "too_prominent"):
        assert word in enum, word
