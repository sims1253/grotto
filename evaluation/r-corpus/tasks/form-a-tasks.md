# Public task sheet — form A (items r-01 .. r-09)
#
# One row per item. Shown to the participant per trial; contains NO answers.
# The answer key lives in answers/answer-key.yaml and must not be visible
# during collection. The seeded error is applied by the experimenter using the
# patch in the answer key, on a COPY of the item, never by editing the corpus.
#
# Timing: each item is one short trial (recommend 60-180 s). One participant
# uses EXACTLY ONE list from schedule.yaml for all nine trials; the nine
# lists counterbalance ACROSS participants, not within one participant. A
# repeated within-participant experiment needs the future disjoint forms
# B/C, never a second form-A list. These are not speeded tests — record
# times for failure analysis only, never as a score.

| item | scan task | comprehension question | seeded-error task |
|---|---|---|---|
| r-01 read-station-log | Count the argument names of `read_station_log` and name the two columns coerced with `suppressWarnings`. | When does the function `stop()` instead of `warning()`, and what is the difference for the caller? | find the introduced bug (answer key: r-01) |
| r-02 signif-round | Locate the line computing `magnitude` and say what happens for `x == 0`. | Why does `relative_diff` return `NA` when `old == 0` instead of dividing anyway? | find the introduced bug (answer key: r-02) |
| r-03 threshold-check | Name the two S3 methods defined and the fields of the object `threshold_check()` returns. | What does `check_counts` report for a value exactly equal to `lower`? | find the introduced bug (answer key: r-03) |
| r-04 rolling-window | Identify every control-flow keyword used inside `rolling_max_window` itself (candidates: break/for/next/return/while). Some of these candidates occur only in other functions in the same file and must NOT be included. | Why can `window_max` stay `-Inf`, and what does the function emit in that case? | find the introduced bug (answer key: r-04) |
| r-05 normalise-results | Count the `vapply` calls and state the type each asserts. | What does `safe_trim_mean` return for an all-NA vector, and why does that matter for the data frame? | find the introduced bug (answer key: r-05) |
| r-06 canonicalise-id | Say which line strips separators/symbols and which line splits prefix from suffix. | According to the example comments, what does `canon_id("s3#a2")` return and why? | find the introduced bug (answer key: r-06) |
| r-07 month-grid | Find where the range endpoints are swapped and where out-of-range dates are counted. | What is `bucket_by_month`'s `outside` value counting, and where does that count come from in the loop? | find the introduced bug (answer key: r-07) |
| r-08 dominant-direction | Count the distinct indexing operators used (`[`, `[[`, `%*%`, `%o%`, `[, k]`) and locate the deflation line. | What stops the inner iteration loop early, and what is `1e-12` guarding against? | find the introduced bug (answer key: r-08) |
| r-09 plot-with-band | Locate the `par()` save and the restore; name the mechanism that guarantees restoration. | What decides the annotation position (pos 1 vs 3) for the peak label? | find the introduced bug (answer key: r-09) |

Presentation rules (from HUMAN_EVALUATION.md / schedule.yaml):
- assign items per the participant's single schedule list; never substitute ad hoc;
- do not reveal which family/variant is on screen; record it in the session file;
- after the trial, note whether the participant read comments/docstrings at all
  (colour treatments of comments differ across candidates).
