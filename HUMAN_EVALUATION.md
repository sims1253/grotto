# Phase 7 — Human evaluation protocol

## Purpose and limits

This is a compact, single-participant repeated-measures study for comparing the
Restrained, Balanced, and Expressive adaptive theme families. It produces
preference and usability evidence for this user, display, workload, and viewing
context. It is not medical research, a circadian study, or evidence that a theme
prevents fatigue or improves health.

Do not collapse the observations into a weighted score or an automatic winner.
Scanability, readability, semantic learning, annoyance, environmental fit, and
discomfort can disagree. Preserve those disagreements in the decision record.

## Experimental unit

One condition is a `family × variant` pair. With three families and Day,
Evening, and Night variants there are nine conditions. Evaluate each condition
with:

1. a 10–15 minute structured scan task; and
2. a 60–120 minute sustained coding block on a different occasion or after a
   sufficient break.

The intended context is part of the condition: Day in normal/high ambient
illumination, Evening as illumination falls, and Night in a dim room. Record the
actual context rather than assuming the label describes it.

## Controls and context record

Keep these fixed within a comparison set:

- display, OS colour mode/profile, scaling, editor, font, font size/weight,
  line height, layout, UI visibility, and application zoom;
- system colour-temperature filters, HDR, True Tone/adaptive colour, local
  dimming, and automatic brightness state;
- the same frozen source specimens and viewport positions for scan tasks;
  the identical multi-language visual fixtures are `out/specimens/`
  (`grotto specimens`); the *disjoint timed R forms* are a different
  thing — see [evaluation/r-corpus](evaluation/r-corpus/README.md), which
  supplies the frozen, project-authored pilot items and the
  counterbalanced assignment schedule for the short scan/comprehension/
  seeded-error trials. Identical visual fixtures control content exactly but
  cannot be reused for timed tasks without practice effects; the corpus
  forms are rotated so no timed item repeats for one participant;
- diagnostic text, selection, cursor/focus, diff, search, and debug examples;
- viewing distance and room/task lighting as far as practical.

Record display make/model, panel technology when known, brightness setting and
whether it is automatic. Measured white/background luminance in cd/m² is useful
if a meter is available, but do not estimate it from the brightness slider.
Record measured ambient lux if available; otherwise describe the room, window
light, lamp placement, reflections, and perceived brightness. Record local time,
time since entering the room or changing illumination, recent exposure to a
bright display/outdoors, and minutes spent adapting before the trial.

Record whether switching was manual or automatic and the exact trigger. Disable
unrelated automatic display changes unless automatic adaptation itself is the
thing being tested.

## Ordering and counterbalancing

Generate the order before looking at preferences. Use one of these balanced
three-family orders in successive blocks:

| Sequence | Order |
| --- | --- |
| 1 | Restrained → Balanced → Expressive |
| 2 | Balanced → Expressive → Restrained |
| 3 | Expressive → Restrained → Balanced |

Rotate which sequence is used for Day, Evening, and Night, then rotate again on
a repeat. Randomly choose the first sequence with a recorded seed. Do not always
put the presumed favourite last.

Environmental variants cannot always be fully randomized without destroying
their intended context. Across repeat days, use a balanced order where practical
(for example Day–Evening–Night, Evening–Night–Day, and Night–Day–Evening), while
recording actual light and time. If a variant is deliberately viewed outside its
intended context, mark it as a cross-context check and do not combine it silently
with intended-context observations.

Before each condition, use 5–10 minutes with a fixed neutral/default theme or a
blank neutral editor view. Then allow at least 5 minutes in the tested condition
before rating it. This is a practical washout/adaptation convention, not a claim
that visual adaptation has been eliminated. Avoid direct A/B flickering.

## Part A — structured scan (10–15 minutes)

Use the identical frozen multi-language specimens and editor state for every
condition. For the short timed R scan/comprehension/seeded-error trials, use
the disjoint frozen items from
[evaluation/r-corpus](evaluation/r-corpus/README.md) assigned per its
counterbalanced `schedule.yaml` (never the identical excerpt under multiple
themes for timed tasks). Complete the same tasks in the same order, without
a palette legend:

1. Locate function definitions and calls, control flow, types, strings, comments,
   constants, ordinary variables, parameters, and nested delimiters.
2. Find a seeded error, warning, information item, breakpoint/current-execution
   state, search match, selection, and focus indicator.
3. Compare added and removed diff regions while reading the text inside them.
4. Read two short dense passages and answer one simple content question from
   each, discouraging colour-only scanning.
5. After switching from the prior variant, identify the semantic role of several
   highlighted tokens without a legend. Record answer, confidence, and response
   time. This probes semantic familiarity; colour distance alone cannot prove it.
6. Inspect the critical states in normal colour, grayscale, and the project’s CVD
   simulations. Check whether icon, label, underline, border, shape, or placement
   still communicates state. Simulation is an engineering check, not a substitute
   for testing with people who have colour-vision deficiencies.

Immediately record ratings and observations. Timing may reveal large failures,
but this is not a speed contest and a single participant supplies no population
performance estimate.

## Part B — sustained coding (60–120 minutes)

Use real work in the same project and keep the editor configuration fixed. Exact
tasks cannot remain identical after they have been solved, so use comparable work
units and record language, activity (reading, editing, debugging, or review),
complexity, interruptions, and fraction of time spent outside the editor. Avoid
assigning every difficult task to one family.

Record an immediate baseline before the block, brief observations at roughly 30
and 60 minutes, the full post-block ratings, and delayed observations later that
day or the next morning. Keep immediate legibility judgments separate from
accumulating annoyance or discomfort.

Stop the block if the participant develops notable headache, nausea, dizziness,
visual disturbance, persistent afterimages, worsening eye pain, or discomfort
that they do not wish to continue through. Record the stop and context; do not
encourage endurance and do not interpret the event as a diagnosis.

## Questions to answer per condition

Use 1–7 ratings where the endpoints in the feedback template apply, plus free
text. Record prominence problems directionally (`too faint`, `appropriate`, or
`too prominent`) rather than treating both extremes as the same number.

- Can I scan structure quickly?
- Are comments too prominent or too faint?
- Do ordinary variables disappear?
- Are functions excessively salient?
- Does punctuation create noise?
- Are diagnostics unmistakable without hue alone?
- Is selection distinct while its text remains readable?
- Are search, focus, and current execution distinct from one another?
- Does Day remain readable in a bright room without feeling washed out?
- Does Evening fit as ambient illumination falls?
- Does Night feel less glaring in a dim room without making text muddy?
- After switching, are learned semantic associations preserved?
- After 1–2 hours, which colours or role treatments become annoying?
- What became easier to miss, slower to read, or unnecessarily attention-grabbing?

Also record overall preference, but never use it to overwrite the individual
answers.

## Minimal schedule

A compact first pass is six to twelve days:

- Days 1–3: one environmental context per day, all three 10–15 minute scan
  conditions in counterbalanced order.
- Days 4–12: one sustained block for each of the nine conditions, with family and
  variant order counterbalanced as practical and no more than two blocks per day.
- Next-day entries: delayed annoyance, remembered semantic identities, and any
  desire to avoid a condition.

If this is too burdensome, run all nine scan conditions, shortlist on explicit
tradeoffs, then sustain-test the shortlist. Label untested conditions; do not
impute sustained comfort from scan results.

## Recording and interpretation

Copy `feedback/session-template.yaml` for every condition. Use stable anonymous
condition labels during collection if feasible; reveal family names only when
writing the decision record. Preserve raw entries and do not edit them to match
later impressions.

Look for:

- repeated within-person patterns across tasks and days;
- order, time-of-day, task-difficulty, and ambient-light confounds;
- immediate-versus-delayed reversals;
- critical-state or semantic-recall failures that need redesign regardless of
  aesthetic preference;
- cases where instrumented palette metrics and visual judgment disagree.

The result may reasonably be “different families for different contexts” or “no
meaningful difference detected.” A small rating difference is not automatically
actionable.

## Decision record

Complete this section after the raw records are frozen.

- **Decision date and candidate/version hashes:**
- **Conditions actually tested:**
- **Decision or next experiment:**
- **Evidence supporting it:** List observations by dimension, not a composite.
- **Evidence against it:** Include disliked properties and failed states.
- **Tradeoffs accepted:** For example, faster function scanning at the cost of
  greater long-session salience.
- **Metrics–judgment disagreements:** State which evidence was trusted for this
  decision and why.
- **Confounds and missing evidence:** Display, ambient, task, ordering, learning,
  incomplete duration, or CVD-observer limitations.
- **Uncertainty:** What could change the decision?
- **Rejected alternatives and why:** Preserve viable alternatives rather than
  declaring a numerical winner.
- **Follow-up and rollback criterion:** What to test next, and what observation
  would reopen the decision?

