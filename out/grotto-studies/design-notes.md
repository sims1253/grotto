# Four studies from the same place

The brief is a coding theme with the feeling of shelter beneath vines and
conversation around stone tables. Earlier Day palettes looked too grey. The
new studies should offer distinct choices in color placement as well as hue.

## Plan before building

Starting color vocabulary: pale limestone `#f4f5ec`, leaf `#277647`, tansy gold
`#856504`, grape violet `#8147a6`, cool blue `#2768b0`, and copper `#ac5124`.
These are direction references; final exported colors are repaired for contrast.

| Study | Frequent emphasis | Supporting colors | Canvas |
| --- | --- | --- | --- |
| Tansy | Golden keywords | Violet functions, green strings | Slightly green limestone |
| Fig | Plum keywords | Green functions, golden strings | Pale mineral violet / dark plum |
| Rainstone | Blue keywords | Copper functions, teal strings | Cool mineral grey |
| Lantern | Teal keywords | Amber functions, olive strings | Warm stone / dark brown-grey |

Use DejaVu Sans for review controls and DejaVu Sans Mono at 13px for every code
sample, matching the previous reviews. Keep labels and code left aligned.

```text
Grotto studies                    Day / Night    Language
[ overview / compare two ]        [ left theme ] [ right theme ]
Tansy / left theme                Fig / right theme
code                             same code
Rainstone                        Lantern
code                             same code
```

The code is the main visual. Give each study one prominent color relationship;
keep the review chrome neutral, omit animation and decorative imagery, and let
the user compare two candidates at the same size. Keep readable text, visible
focus, and conventional diagnostic colors through all experiments.

## Critique of the plan

Four green backgrounds with warm accents would repeat Pergola. Instead, vary
which roles receive warmth and include plum and cool-grey canvases. Rainstone
is the deliberate cooler departure. Lantern puts warm light into function calls,
which appear more often than numeric constants. Red remains available for errors.
Day and Night use separate chroma ranges so restrained Night colors do not
force Day back toward grey.

## Screenshot review

- Fig Day has the most playful color rhythm: plum control flow, green calls,
  blue numbers and gold strings. It is my first choice to compare with Pergola.
- Rainstone makes the strongest cool/warm split. Blue keywords and copper calls
  are easy to pick out. Its cool canvas moves furthest from the summer warmth.
- Tansy carries gold into frequent keywords and violet into calls. Copper type
  names become prominent in JSON, so its character varies with the file.
- Lantern Night keeps function calls warm against a brown-grey canvas. It is
  the closest of this set to the evening part of the brief.
- The initial Lantern assigned red to types. In JSON, that colored every key
  red and made the file resemble a diagnostic. I moved types and keys to blue,
  inspected the new screenshot, and kept warmth in calls.
- Related greens and golds still merge in color-vision simulations. Diagnostics
  retain labels/signs in the specimen; hue alone cannot carry those meanings.

Inspected actual TextMate screenshots in Day and Night, including a JSON stress
sample. State previews separately cover selections, diffs and color-vision
simulations. Font size is fixed across candidates; no screenshots are recolored.
