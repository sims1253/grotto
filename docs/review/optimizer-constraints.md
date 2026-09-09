# Constraints for a less intense optimizer

The [next-generation review](../../out/next-generation/README.md) now contains
Cove, Grove, and Dusk in Day and Night, with examples and editor previews.

Numeric N01 is rejected: the owner finds it too intense and not visually
pleasing. This is a preference constraint for Grotto, not evidence that saturated
palettes are universally bad. Middle M01 has not been selected.

We can keep an optimizer. It should search within a design direction and stop
rewarding differences that already serve their purpose. Adding more caps to the
current distance-maximizing objective will tend to move the optimum to those caps.
This is a proposal; the optimizer has not been changed.

## What is already there

[`middle_palette.py`](../../scripts/middle_palette.py) already constrains hues by
role, holds ink lightness within 0.04 of Balanced Night and surface lightness
within 0.06, and limits chroma to 0.12 for syntax, 0.16 for diagnostics, and 0.10
for surfaces. It also caps chroma at 70% of the available sRGB gamut. Those values
are authored preferences, not research constants.

Middle retains Numeric's objective: maximize the worst normalized distance,
then use the mean distance as a tie-break. Neither term rewards restraint once
a useful distinction has been achieved. The first experiment should change
that incentive before adding more degrees of freedom or another optimizer.

## Constraints worth borrowing

| Constraint | Support | Proposed use in Grotto |
| --- | --- | --- |
| Text remains readable on every surface it can occupy | Accessibility criterion | Require the project's 4.5:1 body-text floor on canvas, selection, search, and diff surfaces after actual alpha composition; evaluate non-text components under their applicable requirements |
| Critical meaning survives loss of hue | Accessibility criterion | Verify error/warning labels or distinct icons and diff signs in editor output; simulations supplement those checks |
| Large, persistent areas stay quieter than small accents | Established UI design practice, not a comfort law | Give surfaces lower chroma limits than syntax and penalize widespread high-chroma ink on representative code |
| Related roles may share a color | Design hypothesis supported by grouping concepts | Remove unconditional number/constant separation; make builtin/function similarity a deliberate option |
| Important roles need enough separation, not maximum separation | Objective design choice | Penalize shortfalls below selected targets; give no reward for exceeding them |
| Size and context affect discriminability | Perception research outside syntax highlighting | Inspect actual glyphs, fonts, adjacent tokens, and UI states; do not infer readability from large swatches alone |
| Stable semantic associations reduce surprises | Design convention, with cultural limits | Preserve chosen error/warning and added/removed meanings; allow broader syntax hue choices within a family |
| Coherence and preference are separate questions | Color-preference research | Treat harmony as a soft preference and ask for choices between rendered compositions |

### Accessibility supplies floors, not a beauty function

WCAG 2.2 specifies a 4.5:1 minimum for ordinary text, with defined exceptions.
Its use-of-color criterion requires another visual means of conveying meaning.
For desktop editors, WCAG2ICT explains application to non-web software, but is
informative guidance rather than a separate conformance standard. Theme-level
checks cannot certify the entire editor. [WCAG 2.2](https://www.w3.org/TR/WCAG22/),
[use of color](https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html),
[WCAG2ICT](https://www.w3.org/WAI/standards-guidelines/wcag/non-web-ict/).

Do not invent a universal upper contrast limit for comfort. Chroma, luminance,
font rendering, display brightness, and room light are different variables.
Reduce distracting accents without sacrificing text contrast.

### Give the composition an emphasis budget

Microsoft's Fluent guidance uses neutrals for surfaces and ordinary text, and
reserves shared colors for selective emphasis. That supports separate treatment
of surface, body, and accent roles. It does not supply an optimal chroma value
for code. [Fluent color guidance](https://fluent2.microsoft.design/color).

A practical soft penalty could sum excessive chroma weighted by visible ink area
across several code specimens. A frequently repeated builtin would cost more
than a rare decorator. Track surface area separately: including the mostly dark
canvas in one average would hide intense syntax. Inspect the worst specimen as
well as the average so a string-heavy or numeric file does not disappear in the
aggregate. This is a proposed proxy for emphasis, not a model of fatigue.

Clutter research connects image feature variation to visual search, but does
not validate a simple chroma sum for coding comfort. Use it as motivation for
rendered checks, not permission to label our penalty a scientific salience score.
[Rosenholtz, Li, and Nakano, 2007](https://pubmed.ncbi.nlm.nih.gov/18217832/).

### Use relationships instead of assigning every role a separate hue

Start with a few semantic groups whose members may look alike. For example,
function and builtin can share a family; literal numbers and named constants
can be related. Whether that helps this theme is a design decision to compare.
Do not require exactly five hue families or mechanically space them around a
color wheel.

Heer and Stone model color naming and describe palette-selection tools that use
name reliability and name distance. This supports considering categorical
identity alongside metric distance. Their naming measure is not an attention
model and does not prescribe which color belongs to a syntax role.
[Heer and Stone, 2012](https://hci.stanford.edu/publications/2012/2012-ColorNameModels-CHI.pdf).

Szafir's studies of points, bars, and lines show why large uniform patches are an
incomplete basis for visualization color choice. The transfer to code is to
check small glyphs at the intended size, not to copy the paper's thresholds into
OKLab. [Szafir, 2018](https://cmci.colorado.edu/visualab/VisColors/).

### Use culture and psychology as priors

The [companion evidence review](color-preference-evidence.md) distinguishes color
harmony, preference, learned associations, and cross-cultural findings. These
can suggest options to test. They do not establish universal rules such as
blue functions being calming or red text being cognitively harmful.

Error and diff hue conventions are reasonable product choices for the intended
editor audience. Syntax hue conventions are much less fixed. Keep conventional
state meanings where useful, retain non-color cues, and learn the owner's
preferences from whole code examples.

## Proposed search order

```text
For each proposed palette:
  reject out-of-gamut colors and failed text/surface contrast
  verify critical labels, icons, and signs in the editor mapping
  measure shortfalls for selected role distinctions
  measure excessive emphasis and departures from the chosen design
  retain alternatives that trade these costs differently

Render a small set with the same code and UI states.
Choose a direction by sight, then test it during ordinary coding.
```

For a pair with normalized separation m, use a shortfall such as
`max(0, 1 - m)^2`. This contributes zero above the target. Replace the current
uncapped mean-distance tie-break too, or it will keep rewarding oversaturation.
This loss is an optimization choice, not a perceptual law. The pair list and
targets still need review; current distance targets are design judgments and
some are infeasible within restrained palettes.

Keep accessibility requirements hard. Keep speculative distance and aesthetic
costs visible and negotiable; do not hide them all inside one claimed quality
score. Never trade away required text contrast for a better appearance score.

## Smallest useful next experiment

Use the existing Middle search machinery and the same fixed source specimens.
Change one factor at a time:

1. Keep the present Middle constraints but replace the uncapped distance reward
   with shortfall penalties and a restrained-emphasis preference.
2. Add a quiet builtin/function grouping, removing the need for a separate pink
   builtin accent. Keep the first variant as the comparison.
3. Add a lower surface-emphasis budget while retaining readable text and
   visible diff signs. Compare it with the second variant.

Preserve a few visually different outcomes from each run; do not return only
the numerically best one. Keep Numeric N01 only as the rejected reference.
No automatic promotion or additional global theme-generation system is needed.

The numerical caps, grouping choices, and penalty strengths should be stated as
trial settings. Universal emotion-to-hue mappings, fixed complementary/triadic
schemes, and a literal 60/30/10 area rule would add confidence unsupported by
this coding task.
