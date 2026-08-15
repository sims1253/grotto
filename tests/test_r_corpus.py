"""Phase 8b: matched R pilot corpus.

Acceptance points:
  * manifest hashes match the frozen items (recomputed, not trusted);
  * item uniqueness (no duplicated excerpts, distinct hashes);
  * provenance/license completeness with the honest project-authored
    labelling (frozen for this experiment, NOT externally established);
  * schedule counterbalancing: nine deterministic cyclic lists, each a
    bijection, and every item x every exact condition exactly once across
    lists (item x condition Latin square);
  * coarse matching tolerances (length band, nesting, construct coverage);
  * seeded-error patches in the answer key match the frozen files exactly,
    so the answer key can never silently drift from the corpus.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
CORPUS = REPO / "evaluation/r-corpus"

# import the stdlib-only metrics tool directly from the corpus
_spec = importlib.util.spec_from_file_location(
    "corpus_metrics", CORPUS / "tools/metrics.py"
)
metrics_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(metrics_mod)


def _load(name: str) -> dict:
    return yaml.safe_load((CORPUS / name).read_text())


def test_manifest_metrics_and_hashes_match_files():
    manifest = _load("manifest.yaml")
    assert len(manifest["items"]) == 9
    seen_files: set[str] = set()
    for item in manifest["items"]:
        path = CORPUS / item["file"]
        assert path.is_file(), item["file"]
        assert item["file"].endswith(".R")
        seen_files.add(item["file"])
        recomputed = metrics_mod.item_metrics(path)
        assert item["sha256"] == recomputed["sha256"], item["file"]
        for key in ("lines", "nonblank_lines", "comment_lines", "max_nesting",
                    "construct_families"):
            assert item["metrics"][key] == recomputed[key], (item["file"], key)
    # every corpus file is manifested -- no hidden extras
    on_disk = {f"items/{p.name}" for p in (CORPUS / "items").glob("*.R")}
    assert on_disk == seen_files


def test_item_uniqueness():
    manifest = _load("manifest.yaml")
    hashes = [i["sha256"] for i in manifest["items"]]
    assert len(set(hashes)) == len(hashes)
    texts = [(CORPUS / i["file"]).read_text() for i in manifest["items"]]
    # normalised (strip blank lines) bodies must also differ
    normalised = {"\n".join(t for t in x.splitlines() if t.strip()) for x in texts}
    assert len(normalised) == len(texts)


def test_provenance_completeness_and_honesty():
    prov = _load("manifest.yaml")["provenance"]
    assert prov["authorship"] == "project-authored"
    assert prov["frozen"] is True
    assert prov["frozen_date"]
    assert prov["license"]
    assert prov["copyright"]
    statement = prov["statement"].upper()
    # the two honesty clauses must be explicit
    assert "PROJECT-AUTHORED" in statement
    assert "NOT EXTERNALLY ESTABLISHED" in statement
    assert prov["external_sources"] == "none"


def test_coarse_matching_tolerances():
    manifest = _load("manifest.yaml")
    for item in manifest["items"]:
        m = item["metrics"]
        # 25-60 visible lines target; first-pass coarse band
        assert 25 <= m["lines"] <= 60, item["file"]
        assert m["nonblank_lines"] >= 20, item["file"]
        assert m["comment_lines"] >= 3, item["file"]  # comments must be exercisable
        assert m["max_nesting"] >= 3, item["file"]
        assert m["construct_families"] >= 6, item["file"]
        c = m["constructs"]
        # representative R syntax per CORPUS_RESEARCH.md stratification
        assert c["assignment"] >= 5, item["file"]
        assert c["function_def"] >= 1, item["file"]
        assert c["string_literal"] >= 1, item["file"]
        assert c["numeric_literal"] >= 1, item["file"]
        assert (c["if_else"] + c["loop"]) >= 1, item["file"]


def test_schedule_counterbalancing():
    schedule = _load("schedule.yaml")
    manifest = _load("manifest.yaml")
    items = {i["id"] for i in manifest["items"]}
    # ordered enumeration of the nine exact conditions (schedule.yaml procedure)
    families = ["restrained", "balanced", "expressive"]
    variants = ["day", "evening", "night"]
    conditions = [(v, f) for v in variants for f in families]
    # items r-01..r-09 map to indices 0..8 in sorted id order
    item_index = {item: i for i, item in enumerate(sorted(items))}
    lists = schedule["lists"]
    assert len(lists) == 9
    assert [L["name"] for L in lists] == [f"L{n}" for n in range(1, 10)]

    # (item, variant, family) -> names of the lists presenting that pairing
    seen_on: dict[tuple[str, str, str], list[str]] = {}
    for k, L in enumerate(lists):
        assigned: list[str] = []
        assert set(L["assignments"]) == set(variants)
        for v, by_family in L["assignments"].items():
            assert set(by_family) == set(families)
            for fam, item in by_family.items():
                assert item in items, item
                assigned.append(item)  # no repeat within a list ...
                seen_on.setdefault((item, v, fam), []).append(L["name"])
                # deterministic cyclic construction: list k (L{k+1}) assigns
                # item i to condition (i + k) mod 9
                expected = conditions[(item_index[item] + k) % 9]
                assert (v, fam) == expected, (L["name"], item, expected, (v, fam))
        # ... and the list is a bijection: 9 items onto the 9 exact conditions
        assert sorted(assigned) == sorted(items), L["name"]

    # across the nine lists every item meets every exact condition exactly
    # once (item x condition is a Latin square)
    for item in items:
        for cond in conditions:
            assert len(seen_on.get((item, *cond), [])) == 1, (item, cond)


def test_schedule_positions_are_not_confounded_with_items():
    """v3 property: an item's within-block ordinal position must VARY across
    lists.  v2 assigned family sequences in lockstep with the item rotation,
    which pinned r-01/r-04/r-07 to first, r-03/r-06/r-09 to third in every
    list -- item difficulty perfectly confounded with practice/fatigue
    position.  Each item must now occupy each position exactly 3 of 9 lists."""
    schedule = _load("schedule.yaml")
    manifest = _load("manifest.yaml")
    items = sorted({i["id"] for i in manifest["items"]})
    families = ["restrained", "balanced", "expressive"]
    variants = ["day", "evening", "night"]
    conditions = [(v, f) for v in variants for f in families]
    item_index = {item: i for i, item in enumerate(items)}
    seq_orders = {
        1: ["restrained", "balanced", "expressive"],
        2: ["balanced", "expressive", "restrained"],
        3: ["expressive", "restrained", "balanced"],
    }
    from collections import Counter

    pos_count: dict[str, Counter] = {item: Counter() for item in items}
    for k, L in enumerate(schedule["lists"]):
        order = seq_orders[L["family_sequence"]]
        assert L["family_sequence_order"] == " -> ".join(order), L["name"]
        # sequence mapping is the documented decoupled one: ((k*2) mod 3)+1
        assert L["family_sequence"] == ((k * 2) % 3) + 1, L["name"]
        inv = {}
        for v, by_family in L["assignments"].items():
            for fam, item in by_family.items():
                inv[item] = (v, fam)
        for item in items:
            v, fam = inv[item]
            assert (v, fam) == conditions[(item_index[item] + k) % 9]
            pos_count[item][order.index(fam)] += 1
    for item, c in pos_count.items():
        assert c == Counter({0: 3, 1: 3, 2: 3}), (item, dict(c))


def test_answer_key_patches_match_frozen_items():
    key = _load("answers/answer-key.yaml")
    manifest = _load("manifest.yaml")
    ids = {i["id"] for i in manifest["items"]}
    assert set(key["items"]) == ids
    for item_id, entry in key["items"].items():
        path = CORPUS / "items" / f"{item_id}.R"
        lines = path.read_text().splitlines()
        se = entry["seeded_error"]
        assert 1 <= se["line"] <= len(lines), item_id
        original = lines[se["line"] - 1]
        assert original == se["original"], (
            f"{item_id}: answer key original line drifted\n"
            f"  file    : {original!r}\n  key     : {se['original']!r}"
        )
        assert se["broken"] != se["original"], item_id
        assert se.get("why"), item_id
        assert entry.get("scan") and entry.get("comprehension"), item_id


def test_tasks_cover_every_item_without_answers():
    tasks = (CORPUS / "tasks/form-a-tasks.md").read_text()
    manifest = _load("manifest.yaml")
    for item in manifest["items"]:
        prefix = item["id"].split("-")[0] + "-" + item["id"].split("-")[1][:2]
        assert re.search(rf"\| {re.escape(prefix)} ", tasks), item["id"]
    # the public sheet must not leak answer content
    key = _load("answers/answer-key.yaml")
    for entry in key["items"].values():
        why = entry["seeded_error"]["why"].strip()
        assert why.split("\n")[0] not in tasks
