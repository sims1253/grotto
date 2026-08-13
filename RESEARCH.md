# RESEARCH.md — Phase 1 evidence base

This document records the evidence that can legitimately constrain the design.
It deliberately separates established measurement methods, controlled findings,
expert recommendations, project modelling, and design judgement. A metric can
be standardized without having been shown to predict programmer comfort or
performance.

## Evidence grading

| Grade | Meaning |
|---|---|
| **A** | Convergent evidence from systematic review or multiple strong controlled studies; or an authoritative standard **for the measurement claim it defines**. |
| **B** | At least one directly relevant controlled study plus supporting evidence, with material limitations. |
| **C** | A small or indirect study, mixed evidence, or a model with limited external validation. |
| **D** | Plausible mechanism, expert consensus, or engineering judgement without direct evidence for this use. |
| **E** | Speculation or an explicit project hypothesis. |

Grades express both source quality and directness. For example, CIE S 026 is
grade A for how alpha-opic quantities are calculated, but it does not make an
RGB theme a grade-A sleep intervention. Internal model results use a separate
`M` label and are never upgraded to clinical evidence.

Entries are grouped by topic rather than number. The `R-n` identifiers are kept
stable because `DESIGN.md` cites them; new findings use new identifiers instead
of renumbering the original evidence base.

---

## R-1. Blue-filtering spectacles probably do little for short-term digital eye-strain symptoms — **A for spectacles; D for theme inference**

The 2023 Cochrane review included 17 randomized trials. It concluded that
blue-light-filtering spectacle lenses may not attenuate short-term eye-strain
symptoms compared with non-blue-filtering lenses; the certainty of the
eye-strain evidence was low, and sleep results were indeterminate. The review
also found no eligible trial evidence for several proposed outcomes, including
contrast sensitivity and colour discrimination. A double-masked randomized
trial of 120 symptomatic computer users likewise found no benefit over clear
lenses for symptoms or critical flicker-fusion frequency after a two-hour
computer task.

This is evidence against confidently marketing short-wavelength reduction as
an eye-strain remedy. It is **not** a direct test of display themes: spectacles
filter the whole visual field, while a theme changes the luminance and spectrum
of selected display pixels. The supported conclusion is therefore narrow:
this project must not claim that a warm palette prevents or treats digital eye
strain.

> Sources: [Cochrane systematic review (Singh et al., 2023)](https://doi.org/10.1002/14651858.CD013244.pub2) — systematic review; [Singh et al. (2021)](https://doi.org/10.1016/j.ajo.2021.02.010) — double-masked randomized trial; [Cochrane summary](https://www.cochrane.org/evidence/CD013244_are-blue-light-filtering-spectacle-lenses-effective-reducing-eye-strain-or-protecting-macula) — first-party plain-language summary.

## R-2. Digital eye strain is not one mechanism — **B**

Digital eye strain/asthenopia groups symptoms with at least two broad pathways:
external or ocular-surface symptoms associated with dryness and blinking, and
internal visual symptoms associated with accommodation and binocular/vergence
demand. Display luminance, reflections, text rendering, viewing distance,
uncorrected refractive error, task duration, and the surrounding environment
can interact with those pathways.

A colour theme directly changes pixel luminance, contrast, colour, and screen
average luminance. It does not by itself change viewing distance, task duration,
refractive correction, or room lighting. Even blink behaviour should not be
declared theme-independent: display conditions can correlate with blink
measures, but the causal and clinical interpretation of those measures is not
settled. Theme-driven comfort effects are plausible; large or medical effects
are not established.

> Sources: [Sheppard & Wolffsohn (2018)](https://doi.org/10.1136/bmjophth-2018-000146) — review of prevalence, measurement, and mechanisms; [Rosenfield (2016)](https://doi.org/10.1111/opo.12340) — clinical review. These are synthesis sources, used because the claim is taxonomic rather than a single intervention effect.

## R-3. Positive polarity often improves small-text legibility; comfort superiority is not established — **B**

Controlled proofreading and glance-reading experiments repeatedly report a
positive-polarity advantage: dark text on a light background is identified or
proofread more accurately or rapidly than light text on a dark background.
Piepenbrock, Mayr, and Buchner found the advantage was larger for smaller
characters. A related experiment measured smaller pupils and better
proofreading performance under positive polarity, supporting — but not proving
as the only mechanism — an optical account involving pupil size, depth of
field, and aberrations. Dobres et al. observed a positive-polarity advantage in
both near-dark and daylight-like ambient conditions for brief, glance-like
reading.

The boundary matters. These studies used prose, word recognition, or
proofreading tasks rather than hours of programming. They show a performance
advantage under tested conditions, not that light themes always feel better,
reduce fatigue, or suit every low-vision condition. Older CRT work also found
no practically significant polarity effect on typing performance or reported
discomfort in eight experienced typists. Therefore neither “dark is better at
night” nor “light is always better” is supported.

**Design consequence.** Day must be a first-class variant. Evening and Night
remain hypotheses about environmental fit and preference, not superior
legibility modes.

> Sources: [Piepenbrock, Mayr & Buchner (2014)](https://doi.org/10.1177/0018720813515509) — controlled experiments; [Piepenbrock & Buchner (2014)](https://doi.org/10.1080/00140139.2014.948496) — pupil size and proofreading experiment; [Dobres, Chahine & Reimer (2017)](https://doi.org/10.1016/j.apergo.2016.08.001) — polarity × ambient illumination × size experiment; [Zwahlen & Kothari (1986)](https://doi.org/10.1177/154193128603000215) — small, older counterexample.

## R-6. Ambient and display luminance affect performance and fatigue, but no universal matching ratio is known — **C**

In a one-hour digital-reading experiment, Benedetto et al. varied screen
luminance and ambient illuminance. Higher screen luminance increased one
objective fatigue indicator while also increasing reading speed and alertness;
higher ambient illuminance improved some performance/arousal measures. In a
separate study of 33 young adults under 0–100 lx evening conditions, preferred
or comfortable display luminance rose with ambient illuminance. The latter was
short, subjective, and demographically narrow.

This supports adapting display luminance to the environment and expecting a
performance/comfort tradeoff. It does **not** establish a single ideal
screen-to-surround luminance ratio, prove that a dark theme is optimal in a
dark room, or isolate palette from the monitor brightness control. Glare,
reflections, adaptation state, absolute luminance, font rendering, and task all
remain relevant.

> Sources: [Benedetto et al. (2014)](https://doi.org/10.1016/j.chb.2014.09.023) — controlled one-hour reading study; [Zhou et al. (2021)](https://doi.org/10.3390/app11094108) — controlled preference/comfort study; [ISO/TR 9241-610:2022](https://www.iso.org/standard/80750.html) — official scope for visual and non-image-forming lighting considerations, not outcome evidence.

## R-4. Melanopic quantities are the defensible spectral language, but melanopsin is not the whole circadian system — **A for metrology; B for controlled response evidence**

CIE S 026:2018 defines spectral sensitivity functions and alpha-opic
irradiance/radiance and equivalent daylight illuminance (EDI) quantities for
S cones, M cones, L cones, rods, and melanopsin-mediated ipRGC responses. A
melanopic quantity is more specific than informal statements about “blue
light,” and its computation requires a spectral distribution at the eye.

Melanopsin-expressing ipRGCs are central to non-image-forming responses, but
they also receive rod and cone input. “Circadian response is driven by blue” is
too vague; “melanopic EDI fully predicts sleep” is too strong. In a controlled
multi-primary-display experiment, nominally metameric stimuli with different
melanopic irradiance altered melatonin measures and evening alertness across
conditions; a sleep-latency difference was significant only in the highest-
luminance group. The authors also reported rod/cone-intrusion and standard-
observer limitations. Melanopic EDI is therefore a useful engineering
predictor, not a complete individual outcome model.

> Sources: [CIE S 026 standard page](https://cie.co.at/publications/cie-system-metrology-optical-radiation-iprgc-influenced-responses-light-0) — authoritative metrology; [CIE TN 015:2023](https://doi.org/10.25039/TN.015.2023) — official terminology and quantities; [Schöllhorn et al. (2023)](https://doi.org/10.1038/s42003-023-04598-4) — controlled multi-primary-display study.

## R-5. Evening light effects depend on dose, timing, spectrum, and prior history; “warmer” is not automatically safer or more comfortable — **B/C**

The 2022 expert consensus recommends at least 250 lx melanopic EDI at the eye
during daytime, no more than 10 lx during the three hours before bed, and no
more than 1 lx in the sleep environment for healthy adults aged 18–55 on
regular schedules. These are consensus recommendations synthesized from
laboratory evidence, not medically precise thresholds for every person.

Controlled display studies show why a theme-only claim is unsafe. Wood et al.
found that tablet exposure effects depended on intensity and duration. A study
of Apple Night Shift at maximum brightness found no significant difference in
acute melatonin suppression between its warmer and less-warm settings. A
separate controlled experiment found no sleep or melatonin change after two
hours of tablet reading when participants had substantial daytime bright-light
exposure. Another metameric-light crossover found melatonin suppression
without significant changes in sleepiness, vigilance, polysomnographic sleep,
or perceived sleep quality, showing that a biomarker difference does not imply
every subjective or sleep outcome. Prior light history, viewing duration,
brightness, distance, screen size, and spectrum all matter.

**Design consequence.** Night may reduce unnecessary screen-average luminance
and nominal melanopic output, but must be described as an environmental design
hypothesis. It is not a sleep treatment. Brightness control and room lighting
remain outside the palette and must be reported alongside it in any human
evaluation.

> Sources: [Brown et al. (2022)](https://doi.org/10.1371/journal.pbio.3001571) — expert consensus with stated population limits; [Wood et al. (2013)](https://doi.org/10.1016/j.apergo.2012.07.008) — small controlled tablet study; [Nagare, Plitnick & Figueiro (2019)](https://doi.org/10.1177/1477153517748189) — controlled Night Shift study; [Rångtell et al. (2016)](https://doi.org/10.1016/j.sleep.2016.06.016) — controlled counterexample involving prior bright-light exposure; [Blume et al. (2022)](https://doi.org/10.1093/sleep/zsac199) — controlled metameric-light crossover.

## R-7. Astigmatism, “halation,” and maximum-comfort contrast claims remain unverified — **D/E**

Negative polarity enlarges the pupil under many tested conditions, and a larger
pupil can increase the influence of optical aberrations. That mechanism is
compatible with reports of bright glyphs appearing to bloom on dark fields.
However, no primary experiment was found that isolates astigmatism and shows
that a dark editor UI harms astigmatic users, nor one demonstrating that
lowering foreground contrast improves their comfort during prolonged coding.
Positive-polarity studies support a task-performance and pupil-size effect,
not the stronger astigmatism-specific claim.

**Design consequence.** Avoid presenting near-black/near-white avoidance or an
upper APCA bound as established ergonomics. They may remain candidate-design
hypotheses, and user-adjustable contrast is preferable to a universal cap.

> Sources: [Buchner & Baumgartner (2007)](https://doi.org/10.1080/00140130701306413) — polarity improved performance without a reported fatigue/eyestrain difference; [Piepenbrock & Buchner (2014)](https://doi.org/10.1080/00140139.2014.948496) — pupil-size evidence, not an astigmatism intervention.

## R-12. The “blue dark background” hypothesis has no direct performance evidence — **D/E**

No primary study was found that compares otherwise matched coding themes with
neutral, blue-slate, and warm dark backgrounds during realistic programming.
The prevalence of navy/slate developer themes may reflect aesthetic lineage,
panel behaviour, contrast relationships, or taste; it cannot currently be
called a demonstrated perceptual advantage.

Two separate questions must remain separate:

1. **Visual character.** A low-chroma cool background can change simultaneous
   contrast, apparent warmth of accents, and aesthetic coherence. Claims that
   it “recedes” or makes warm alerts more salient are design hypotheses for
   human testing.
2. **Emitted spectrum.** A dark background can cover most pixels yet contribute
   little emitted light because its channel drive is low. A small area of
   bright cool syntax can contribute disproportionately. The result depends on
   the complete pixel distribution, absolute display luminance, and the
   display’s measured primary spectra.

Thus “blue is bad” and “background area always dominates” are both rejected.
For Day, a warm off-white is an aesthetic/model candidate, not a proven comfort
intervention. For Evening/Night, neutral or subtly warm backgrounds should be
compared with subtly cool alternatives at controlled screen luminance.

## R-11. WCAG 2 contrast is the compliance baseline; APCA is experimental here — **A for WCAG requirements; C/D for APCA-based design targets**

WCAG 2.2 defines contrast from the relative luminances of the lighter and
darker colours, so the ratio is polarity-independent and does not include font
size or weight in the equation. SC 1.4.3 requires 4.5:1 for normal text and
3:1 for large text, with stated exceptions. Its understanding document also
warns that antialiasing and thin fonts can make rendered text fainter than the
declared colour pair.

APCA produces polarity-dependent values and incorporates a model intended for
self-luminous display readability. It remains an independent work in progress,
not current WCAG 2 guidance and not a W3C Recommendation. The project may
report APCA as an exploratory diagnostic, but it must not describe APCA bands
as accessibility compliance or as experimentally validated comfort ranges.

There is also no strong source establishing a universal *upper* contrast limit
for prolonged code reading. Claims that near-black/near-white necessarily
causes fatigue or that a particular APCA upper bound prevents “halation” are
design hypotheses. Accessibility minima take precedence; optional user
variants are safer than reducing contrast for everyone.

> Sources: [WCAG 2.2 SC 1.4.3 understanding](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) — current authoritative guidance; [WCAG 2.2 SC 1.4.1 understanding](https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html) — redundant encoding requirement; [WCAG 3 status](https://www.w3.org/WAI/standards-guidelines/wcag/wcag3-intro/) — official warning that WCAG 3 remains incomplete; [APCA repository](https://github.com/Myndex/SAPC-APCA) — algorithm author’s work-in-progress documentation.

## R-8. OKLab/OKLCH is a pragmatic canonical space, not a proof of perceptual optimality — **C**

OKLab was introduced by Björn Ottosson as a simple model fitted to selected
lightness, chroma, and hue datasets, with stated goals including hue and
lightness prediction and numerical stability. OKLab/OKLCH is specified in CSS
Color 4, which gives it strong implementation value. CSS standardization does
not independently validate uniformity for low-light syntax highlighting.

No finite three-dimensional colour space is perfectly uniform across all
stimuli, viewing conditions, and observers. OKLCH Euclidean distance and hue
angle are useful engineering coordinates, not perceptual laws; hue is also
undefined/unstable near zero chroma. CAM02-UCS has a peer-reviewed derivation
from CIECAM02 and remains a reasonable comparison metric, but adds viewing-
condition assumptions and complexity. The present evidence does not justify a
claim that CAM02-UCS or OKLab predicts semantic separability in code.

**Design consequence.** Store canonical colours in OKLCH, expose gamut status,
inspect channel contributions to distance, and validate visually. Do not
maximize uniform spacing or treat a fixed `dE_OK` threshold as universally
perceptual. Explicit sRGB gamut mapping is necessary; Display P3 should be an
optional output, not a semantic dependency.

> Sources: [Ottosson, “A perceptual color space for image processing”](https://bottosson.github.io/posts/oklab/) — original model definition and test basis; [CSS Color 4](https://www.w3.org/TR/css-color-4/) — official syntax/conversion/gamut specification; [Luo, Cui & Li (2006)](https://doi.org/10.1002/col.20227) — original CAM02-UCS paper.

## R-9. CVD simulation is a collapse detector, not an individual’s view — **B/C**

Brettel, Viénot, and Mollon model dichromatic appearance by projecting colours
in cone-excitation space; their implementation depends on display primaries,
white point, and cone fundamentals. Viénot et al. later proposed replacement
colourmaps for protanopic and deuteranopic display checks. Machado, Oliveira,
and Fernandes proposed a unified severity model covering normal vision,
anomalous trichromacy, and dichromacy and evaluated it with observers.

These are defensible engineering models, but each embeds a standard observer,
device assumptions, and a model of deficiency. Congenital CVD varies between
people, and tritan defects are especially underrepresented in validation data.
Simulation can flag pairs likely to collapse; it cannot certify how a palette
looks to every user or substitute for redundant encodings.

**Design consequence.** Test protan, deutan, and tritan endpoints and anomaly
severities, but require icons, text, shape, underline, borders, or signs for
errors, warnings, focus, selection, and diffs whenever meaning is critical.
Report the model and assumed display transform with every simulation.

> Sources: [Brettel, Viénot & Mollon (1997)](https://doi.org/10.1364/JOSAA.14.002647) — original dichromacy model; [Viénot, Brettel & Mollon (1999)](https://doi.org/10.1002/%28SICI%291520-6378%28199908%2924%3A4%3C243%3A%3AAID-COL5%3E3.0.CO%3B2-3) — display colourmap method; [Machado, Oliveira & Fernandes (2009)](https://doi.org/10.1109/TVCG.2009.113) — unified model and observer evaluation.

## R-10. Syntax-highlighting evidence is mixed and does not select a palette — **C**

Sarkar’s randomized within-subject eye-tracking study (`n=10`) reported faster
task completion with syntax colouring and a weaker benefit with greater
programming experience; its size and short tasks limit generalization.
Beelders and du Plessis found non-significant differences in fixation metrics,
although students preferred coloured snippets. Hannebauer, Hesenius, and Gruhn
tested 390 introductory Java students and found no evidence that conventional
syntax highlighting improved correctness on their small comprehension tasks.
A 2023 crossover study of scope/background styling likewise reported gaze
changes without a significant correctness or response-time improvement.

The literature therefore does **not** support “highlighting beats no
highlighting” as a general fact, still less a role-specific salience order or
one colour scheme over another. There is no direct evidence here for neutral
local variables, high-salience functions, dim comments, a fixed number of hue
families, or semantic stability thresholds across Day/Evening/Night. Those are
explicit design hypotheses.

> Sources: [Sarkar (2015)](https://www.ppig.org/files/2015-PPIG-26th-Sarkar1.pdf) — small controlled study; [Beelders & du Plessis (2016)](https://doi.org/10.16910/jemr.9.1.1) — small controlled eye-tracking study; [Hannebauer, Hesenius & Gruhn (2018)](https://doi.org/10.1007/s10664-017-9579-0) — larger controlled novice study; [Park et al. (2023)](https://doi.org/10.1145/3568813.3600133) — scope/background-highlighting crossover.

## R-13. Hex/sRGB cannot determine retinal spectral exposure — **A for the metrology limitation; C for nominal proxy usefulness**

An RGB triplet specifies device-independent colourimetry only under a defined
RGB encoding and reference primaries; it does not provide the spectral power
distribution emitted by a particular monitor. Different spectra can produce
the same tristimulus match (metamerism), and real display technologies have
different primary spectra. CIE alpha-opic calculations accept spectral data,
not hex values.

For a characterized additive display with measured primary SPDs, linearized
channel drives can be combined with those SPDs and integrated against CIE
action spectra. Without measurements, Gaussian “LCD” or “OLED” primaries are
scenario models only. They may rank palettes **within the same stated model,
brightness calibration, and coverage image**; they cannot produce actual
corneal melanopic EDI, compare users’ biological dose, or establish health
benefit.

Area weighting is necessary but not sufficient. For each pixel class, emitted
radiance depends on linear channel drive and display hardware, not area alone.
Absolute screen luminance, viewing geometry, ambient light, exposure duration,
timing, and prior light history are outside a palette file. A defensible report
must call the output “relative nominal melanopic-weighted display output,” show
component coverage and contributions, and avoid clinical language.

> Sources: [CIE S 026 alpha-opic toolbox user guide](https://files.cie.co.at/CIE%20S%20026%20alpha-opic%20Toolbox%20User%20Guide.pdf) — official spectral-input method; [Trumpy et al. (2023), Mapping Quantitative Observer Metamerism of Displays](https://doi.org/10.3390/jimaging9100227) — display-primary SPD formulation and metamerism; [CIE S 026 standard page](https://cie.co.at/publications/cie-system-metrology-optical-radiation-iprgc-influenced-responses-light-0) — authoritative quantities.

---

## Findings from the project’s nominal model

These are scenario-specific engineering results, labelled **M**, not literature
grades. They are reproducible in the current test suite but are not validated
against measured displays.

### M-1. Pixel coverage alone does not determine the dark-theme spectral budget

For the fixture consisting of 88% `#1a1c22`, 10% `#c8ccd4`, and 2%
`#40e0e0`, the nominal LED-LCD model assigns more melanopic-weighted output to
the foreground than to the background. For the light-theme fixture, the 88%
bright background dominates. This usefully falsifies “the largest area always
dominates,” but it does not establish that foreground dominates every dark
theme.

Tests: `test_dark_theme_melanopic_output_dominated_by_foreground`,
`test_light_theme_melanopic_output_dominated_by_background`.

### M-2. A warm composition lowers the nominal melanopic/photopic ratio in one fixture

The current test compares a complete cool composition (`#1b2030` background,
`#c9d2e0` foreground) with a complete warm composition (`#22201c`, `#ded5c8`).
The warm composition has a lower nominal melanopic/photopic ratio. Because
both foreground and background change, this test does **not** isolate
background hue, does not hold appearance perfectly constant, and does not
quantify a biological effect.

Test: `test_warm_background_lowers_screen_melanopic_at_equal_luminance`.

### M-3. The tested red/green pair collapses under one simulated deutan endpoint

For `#c04c4c` and `#4c9c4c`, the implementation reports a much smaller
`dE_OK` under its deutan transform than under normal vision. This demonstrates
the intended collapse-detector workflow for one fixture; it is not validation
of the transform or a universal threshold. The accessibility conclusion comes
from redundant encoding policy, not from this one number.

### M-4. Current display archetypes are too synthetic for cross-display claims

The LED-LCD and OLED archetypes use smooth Gaussian primaries balanced to sRGB
photopic coefficients. Their small difference for current fixtures says more
about shared construction than real hardware. They must not be presented as
representative bounds. Measured SPDs from several actual displays are the main
unresolved validation requirement.

---

## Evidence-to-design ledger

| Design proposition | Current status |
|---|---|
| A high-quality Day variant is necessary | Supported by polarity/legibility evidence, with user preference exceptions (R-3). |
| Variants should adapt screen-average luminance to context | Plausible, limited direct evidence; must be tested at controlled monitor brightness (R-6). |
| Warm Night colours reduce eye strain | Unsupported and must not be claimed (R-1, R-2). |
| Lower evening melanopic exposure can affect circadian physiology | Supported under controlled exposure, but palette-only effectiveness is unproven (R-4, R-5). |
| A blue-slate dark background is perceptually superior | No direct evidence found (R-12). |
| Near-black/near-white is necessarily fatiguing | No direct evidence sufficient to define a universal upper contrast bound (R-7, R-11). |
| WCAG AA is an appropriate baseline floor | Supported as the current accessibility standard; code-editor applicability still requires rendered testing (R-11). |
| APCA should replace WCAG for this project | Unsupported; report it experimentally beside WCAG (R-11). |
| OKLCH is the one correct perceptual space | Unsupported; it is a pragmatic canonical representation (R-8). |
| CVD simulations certify accessibility | False; use as collapse detectors with redundant channels (R-9). |
| Syntax roles have an evidence-derived salience hierarchy | Unsupported; Phase 7 must test the hierarchy (R-10). |
| Hex values predict retinal/circadian dose | False without a measured display and viewing geometry (R-13). |

## Deliberately unresolved source gaps

- No controlled study was found comparing cool-neutral and warm-neutral coding
  backgrounds while holding luminance, contrast, syntax mapping, and monitor
  brightness constant.
- No strong evidence defines a comfortable **upper** WCAG/APCA contrast limit
  for prolonged code reading, including for astigmatic or older observers.
- No palette study establishes an optimal number of syntax hue families, role
  salience order, comment contrast, or callable emphasis.
- No evidence was found for a categorical hue-drift threshold that preserves a
  learned semantic association across polarity changes. The proposed 8°/12°
  limits in `DESIGN.md` are hypotheses.
- CVD models, especially tritan anomaly severities, lack enough validation to
  turn simulated distances into universal pass/fail thresholds.
- The nominal spectral model lacks measured primary SPDs, calibrated absolute
  luminance, viewing geometry, ambient contribution, and realistic screenshot
  coverage. Until those are added, it supports relative scenario comparison
  only.
- No direct evidence shows that Display P3 improves code comprehension or
  accessibility. It remains a portability/gamut experiment, not an objective.
