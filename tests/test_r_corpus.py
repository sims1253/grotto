"""Phase 8b: matched R pilot corpus.

Acceptance points:
  * manifest hashes match the frozen items (recomputed, not trusted);
  * item uniqueness (no duplicated excerpts, distinct hashes);
  * provenance/license completeness with the honest project-authored
    labelling (frozen for this experiment, NOT externally established);
  * schedule counterbalancing: bijections, no repeats, family balance,
    distinct items per condition;
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
    families = {"restrained", "balanced", "expressive"}
    variants = {"day", "evening", "night"}
    lists = schedule["lists"]
    assert len(lists) == 3

    fam_meet: dict[str, set[str]] = {i: set() for i in items}
    cond_items: dict[tuple[str, str], list[str]] = {}
    for L in lists:
        assigned: list[str] = []
        assert set(L["assignments"]) == variants
        for v, by_family in L["assignments"].items():
            assert set(by_family) == families
            for fam, item in by_family.items():
                assert item in items, item
                assigned.append(item)          # no repeat within a list ...
                fam_meet[item].add(fam)
                cond_items.setdefault((v, fam), []).append(item)
        # ... and the list is a bijection over the corpus
        assert sorted(assigned) == sorted(items), L["name"]

    # across the three lists each item meets each family exactly once
    for item, fams in fam_meet.items():
        assert fams == families, item
    # every condition receives three distinct items across lists
    for cond, got in cond_items.items():
        assert len(got) == 3 and len(set(got)) == 3, cond
    # no item permanently bound to one theme: pairing must differ per list
    for cond, got in cond_items.items():
        assert len(got) == len(set(got)), cond


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
