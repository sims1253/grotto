# Grotto R pilot corpus (Phase 8b)

A small, **frozen** corpus of R excerpts for the short *timed* tasks
(scan / comprehension / seeded error) in `HUMAN_EVALUATION.md` Part A.
It is deliberately NOT a benchmark: no CRAN download, no bulk processing,
no 4.4 GB artifact (see `CORPUS_RESEARCH.md`).

## Provenance — read this first

These excerpts are **project-authored** for this experiment. They are frozen
for this experiment but **not externally established**: they have not been
validated as representative R code, and no external provenance is claimed or
implied. If a CRAN-derived corpus is introduced later, it must follow
`CORPUS_RESEARCH.md` (at most 3 pinned, permissively licensed tarballs;
per-excerpt package/version/URL/archive-SHA256/path/line-range/license/
attribution in its own manifest; tarballs never committed). Never invent
provenance; never merge corpora silently.

## Layout

```
items/*.R                 the frozen excerpts (form A: 9 items, 25-60 lines)
manifest.yaml             provenance + per-item hashes + matching metrics
tools/metrics.py          stdlib-only deterministic metrics (LOC, comments,
                          construct counts, max delimiter nesting, sha256)
tasks/form-a-tasks.md     PUBLIC task sheet (no answers)
answers/answer-key.yaml   ANSWER KEY — keep out of the participant's view
schedule.yaml             nine deterministic counterbalancing lists (form A)
```

## What the corpus is for (and not for)

- **For:** short scan/comprehension/seeded-error trials (60–180 s each)
  comparing the nine candidate themes from one fixed editor adapter:
  `editors/vscode/` or `editors/zed/`.
- **Not for:** evidence about 1–2 hour comfort — that is Part B (sustained
  coding on real work), which this corpus cannot speak to.

## Matching limits (honest note)

Form A is a *first pass*: one form of 9 items. The full 3-form design
(3 disjoint matched forms × 9 items) is the documented interface for a later
increment (`manifest.yaml: forms`). Matching on `tools/metrics.py` features
is approximate and still needs piloting before preference data is collected;
the metrics screen for gross inequality, they do not prove equal difficulty.

## Rules during collection

1. Assign items only per the participant's single list in `schedule.yaml`;
   never ad hoc.
2. One participant uses EXACTLY ONE of the nine lists for all nine form-A
   trials; the lists counterbalance item<->condition pairings ACROSS
   participants, not within one participant. Never hand a second form-A list
   to the same participant (they would repeat timed items); a repeated
   within-participant experiment needs the future disjoint forms B/C
   (`manifest.yaml: forms`), which do not exist yet.
3. Apply seeded errors from `answers/answer-key.yaml` to a **copy** of the
   item at presentation time; the corpus files stay frozen.
4. Record which item, list, theme family and variant were on screen in the
   session file — without revealing labels to the participant.

## Regenerate / verify

```bash
# from evaluation/r-corpus/ (metrics.py resolves item paths from there):
python3 tools/metrics.py items   # table

# from the repository root:
uv run pytest tests/test_r_corpus.py -q   # hashes, balance, tolerances
```
