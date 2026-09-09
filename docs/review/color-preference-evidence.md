# Color preference: useful constraints and their limits

Grotto needs readable code that people enjoy using for hours. Numeric N01's
rejection tells us that its current objective misses this user's preference.
Research can suggest better search boundaries. It cannot supply a universal
beauty score or prove that a palette will feel comfortable during a workday.

## What the research supports

| Primary study | Finding | Transfer to Grotto |
| --- | --- | --- |
| [Schloss and Palmer, 2011: preference, harmony, and similarity](https://link.springer.com/article/10.3758/s13414-010-0027-0) | Participants distinguished liking a color pair, judging it harmonious, and liking its foreground color. Similar hues helped pair harmony and pair preference, while hue contrast helped foreground preference. The study used colored squares and 48 participants screened for color deficiency. | Keep readability, visual harmony, and preference separate. A global distance reward can work against harmony; a global hue-similarity reward can erase useful accents. Neither is an adequate theme objective. |
| [Schloss and Palmer, 2011: spatial organization](https://journals.sagepub.com/doi/10.1068/p6992) | Reversing figure and background changed preferences for the same color pair. Relative area mattered. Lightness effects differed between figure/background and mosaic arrangements. | Evaluate actual code and UI composition. A frequently used string color and a rare diagnostic color should not receive equal compositional weight. The paper does not establish the right weight or a syntax-specific saturation limit. |
| [Palmer and Schloss, 2010: ecological valence theory](https://pmc.ncbi.nlm.nih.gov/articles/PMC2889342/) | Color preferences were related to people's evaluations of objects associated with those colors. The authors proposed these associations as an explanation for preference. | Learn from this user's accepted and rejected examples. Do not treat an average preference for a hue as a rule for all programmers or all syntax roles. This is evidence about preference, not a test of coding performance. |
| [Jonauskaite and colleagues, 2020: color and emotion across nations](https://www.psychologicalscience.org/journals/psychological-science/0956797620948810/) | In 4,598 participants from 30 nations, associations between 12 color terms and 20 emotion concepts had strong shared patterns, plus differences related to nation, language, and geography. | Keep familiar interface meanings consistent, but do not claim that a particular hue reliably causes calm, focus, danger, or fatigue. The experiment measured associations with color terms, not emotional effects of rendered editor palettes. |

## Soft constraints worth trying

These are design hypotheses informed by the studies, not validated formulas.
Their settings should come from comparisons of rendered code.

1. **Limit excursions from an accepted palette.** Penalize large changes in each
   role's perceptual color coordinates. Middle M01 is a proposal to test, not an
   accepted preference: the user has rejected Numeric N01 but has not selected
   Middle. Start from a confirmed preference once available.
2. **Control the amount of strong color on screen.** Penalize chroma above a
   chosen role limit, weighted by the role's visible glyph area in each specimen.
   Also inspect large UI fills separately. Score several languages so a sparse
   example cannot hide a color that dominates a string-heavy file. Chroma is a
   rough design control here, not a complete measure of salience or fatigue.
3. **Group roles deliberately.** Let related syntax roles share hue families,
   with small differences where useful. Choose these groups as part of the
   design. Do not impose a triad, complementary pair, or equal hue spacing as a
   scientific law.
4. **Stop rewarding separation after it is sufficient.** Reward only the
   distinctions required by a reading or navigation task, and cap that reward.
   This is an optimizer design choice. The cited preference studies do not
   establish discrimination thresholds for syntax text.
5. **Use direct comparisons as preference evidence.** Hold the code, font,
   background, and layout fixed. Compare a few nearby candidates and record
   which the user prefers and why. Ask separately about intensity, readability,
   and overall appearance. A single rejection narrows the search but does not
   identify which color or combination caused it.

```text
Readable candidates
  -> stay near the chosen visual direction
  -> limit strong color in representative code
  -> compare a few alternatives on screen
  -> keep the user's preferred candidate
```

Hard accessibility requirements should remain outside this preference score.
Aesthetic penalties must never compensate for unreadable text. Conversely,
passing accessibility checks does not establish aesthetic quality.

None of these studies justifies a universal OKLCH chroma cap, a fixed number of
syntax colors, a 60/30/10 area rule, or claims that warm colors reduce fatigue.
Treat such choices as tunable design decisions and assess prolonged use
separately from first impressions.
