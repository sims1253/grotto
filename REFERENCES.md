# Reference-theme provenance and comparison contract

Status: Phase 3 source audit  
Snapshot date: 2026-08-14

This document fixes the upstream sources and interpretation rules for the
Kanagawa, Palenight, Monokai, Nord, Rosé Pine, and Solarized comparisons. It
does not rank the themes, endorse upstream design claims, or treat an editor
port as a universal semantic definition.

## Comparison contract

Every extracted reference record should carry, at minimum:

- `source_repository`, `source_commit`, and `source_path`;
- the exact theme and variant name;
- whether a value came from a raw palette, a semantic theme layer, an editor UI
  mapping, or a syntax/token mapping;
- the editor/token system involved (for example Neovim highlight groups or VS
  Code TextMate scopes);
- alpha and the background against which the color was composited; and
- any project-role assignment made by Grotto, marked as an interpretation rather
  than an upstream fact.

The primary comparison profiles are:

| Reference label | Reproducible profile used for the primary comparison |
| --- | --- |
| Kanagawa | Kanagawa Wave, the upstream default, at `bb85e4b` |
| Palenight | Olaolu Olawuyi's **Palenight Theme**, default non-Operator profile, at `6291efa` |
| Monokai | VS Code's built-in **Monokai**, at VS Code commit `c49d45d` |
| Nord | Canonical Nord palette plus the official VS Code **Nord** mapping |
| Rosé Pine | Canonical **main** palette plus the official VS Code **Rosé Pine** mapping |
| Solarized | Both canonical Solarized Dark and Solarized Light; neither is collapsed into a single profile |

These choices create reproducible baselines, not claims that the selected port
is the only legitimate meaning of the theme name. Secondary variants may be
reported in separate rows, never averaged into the primary profile.

## Source register

### Kanagawa

Selected source: [`rebelot/kanagawa.nvim`](https://github.com/rebelot/kanagawa.nvim)
at commit
[`bb85e4bfc8d89b0e62c8fa53ccdd13d12e2f77b3`](https://github.com/rebelot/kanagawa.nvim/tree/bb85e4bfc8d89b0e62c8fa53ccdd13d12e2f77b3).
No release tag points at this snapshot.

Primary files:

- [raw named palette](https://github.com/rebelot/kanagawa.nvim/blob/bb85e4bfc8d89b0e62c8fa53ccdd13d12e2f77b3/lua/kanagawa/colors.lua);
- [Wave, Dragon, and Lotus semantic theme mappings](https://github.com/rebelot/kanagawa.nvim/blob/bb85e4bfc8d89b0e62c8fa53ccdd13d12e2f77b3/lua/kanagawa/themes.lua);
- [classic syntax highlight mappings](https://github.com/rebelot/kanagawa.nvim/blob/bb85e4bfc8d89b0e62c8fa53ccdd13d12e2f77b3/lua/kanagawa/highlights/syntax.lua);
- [Tree-sitter mappings](https://github.com/rebelot/kanagawa.nvim/blob/bb85e4bfc8d89b0e62c8fa53ccdd13d12e2f77b3/lua/kanagawa/highlights/treesitter.lua); and
- [upstream description of palette versus theme colors and variant defaults](https://github.com/rebelot/kanagawa.nvim/blob/bb85e4bfc8d89b0e62c8fa53ccdd13d12e2f77b3/README.md#themes).

Interpretation:

- Use **Wave** for the primary dark-theme reference because upstream selects it
  as the default. Report **Dragon** (upstream's late-night variant) and **Lotus**
  (light variant) independently when cross-environment behavior is relevant.
- Do not calculate syntax roles directly from all colors in `colors.lua`.
  `themes.lua` maps the raw palette into semantic `syn`, `ui`, and diagnostic
  roles, and the highlight files map those roles to editor groups.
- Neovim configuration, highlight links, Tree-sitter queries, language plugins,
  and user overrides can change the color finally rendered. A Grotto role such
  as `function` must cite the specific highlight-group mapping used.

### Palenight

Selected source: [`whizkydee/vscode-palenight-theme`](https://github.com/whizkydee/vscode-palenight-theme)
at commit
[`6291efaace90855abe3d79025327ca41b9a3138c`](https://github.com/whizkydee/vscode-palenight-theme/tree/6291efaace90855abe3d79025327ca41b9a3138c),
whose package version is `2.0.4`. The repository has no corresponding Git tag.

Primary files:

- [extension manifest and variant list](https://github.com/whizkydee/vscode-palenight-theme/blob/6291efaace90855abe3d79025327ca41b9a3138c/package.json);
- [default Palenight theme](https://github.com/whizkydee/vscode-palenight-theme/blob/6291efaace90855abe3d79025327ca41b9a3138c/themes/palenight.json);
- [italic variant](https://github.com/whizkydee/vscode-palenight-theme/blob/6291efaace90855abe3d79025327ca41b9a3138c/themes/palenight-italic.json);
- [Operator variant](https://github.com/whizkydee/vscode-palenight-theme/blob/6291efaace90855abe3d79025327ca41b9a3138c/themes/palenight-operator.json); and
- [mild-contrast variant](https://github.com/whizkydee/vscode-palenight-theme/blob/6291efaace90855abe3d79025327ca41b9a3138c/themes/palenight-mild-contrast.json).

`Palenight` is ambiguous. The selected project describes itself as
"material-inspired" and is distinct from Mattia Astorino's Material Theme
Palenight. The latter's current public repository snapshot
[`a64a6e0`](https://github.com/material-theme/vsc-material-theme/tree/a64a6e01625f69b0e51b4c146964c7e69d2774c3)
does not contain an inspectable VS Code theme definition. A historical source
snapshot remains addressable at
[`64acc58`](https://github.com/material-theme/vsc-material-theme/tree/64acc5838d47f31d15317b9852f3c7db316e09c3),
including the generated-theme input for
[Material Theme Palenight](https://github.com/material-theme/vsc-material-theme/blob/64acc5838d47f31d15317b9852f3c7db316e09c3/scripts/generator/settings/specific/palenight.ts)
and package version `34.3.1`.

Interpretation:

- Use only `themes/palenight.json` for the primary profile. Font-focused
  variants and the mild-contrast variant are separate experimental conditions.
- Label the result **Palenight Theme (whizkydee)**, not "the original
  Palenight" or "Material Theme Palenight."
- A future comparison against the historical Material Theme implementation
  must use its generator inputs and common syntax templates at the same commit;
  its small `palenight.ts` file is not a complete theme by itself.

### Monokai

Selected source: the built-in VS Code
[Monokai theme file](https://github.com/microsoft/vscode/blob/c49d45dc4a20ffe7495e6872e3bddc78407bd84f/extensions/theme-monokai/themes/monokai-color-theme.json)
at VS Code commit
[`c49d45dc4a20ffe7495e6872e3bddc78407bd84f`](https://github.com/microsoft/vscode/tree/c49d45dc4a20ffe7495e6872e3bddc78407bd84f).
The source file explicitly says its colors are based on the original Monokai.

Interpretation:

- Call this profile **VS Code built-in Monokai**. `Monokai` also names numerous
  ports, forks, and commercial variants; the measurements must not be
  generalized to Monokai Pro or to every editor port.
- Extract UI colors and `tokenColors` separately. The five colors named in the
  file header are not the complete syntax or diagnostic palette.
- Preserve upstream font styles such as italics and underlines in qualitative
  salience notes, even when the numeric color report cannot represent them.

This source is chosen because it is first-party for the inspected editor,
versionable, and complete. No equally inspectable, editor-independent
"canonical semantic Monokai" source has been established by this audit.

### Nord

Canonical palette source: [`nordtheme/nord`](https://github.com/nordtheme/nord)
on its upstream default `develop` branch at commit
[`1cef71605416a222e57225b544540ce0fcec18d4`](https://github.com/nordtheme/nord/tree/1cef71605416a222e57225b544540ce0fcec18d4),
package version `0.2.1`.

Editor mapping source: the official
[`nordtheme/visual-studio-code`](https://github.com/nordtheme/visual-studio-code)
port at commit
[`8ead09822c02d0d49d0f764104505e5a34d3689f`](https://github.com/nordtheme/visual-studio-code/tree/8ead09822c02d0d49d0f764104505e5a34d3689f),
package version `0.19.0`.

Primary files:

- [canonical sixteen-color values](https://github.com/nordtheme/nord/blob/1cef71605416a222e57225b544540ce0fcec18d4/src/nord.css);
- [canonical palette description](https://github.com/nordtheme/nord/blob/1cef71605416a222e57225b544540ce0fcec18d4/readme.md); and
- [official VS Code UI, semantic-token, and TextMate mapping](https://github.com/nordtheme/visual-studio-code/blob/8ead09822c02d0d49d0f764104505e5a34d3689f/themes/nord-color-theme.json).

Interpretation:

- The sixteen-color package establishes colors and broad named palette groups;
  it does not alone establish how every language token should render. Use the
  official editor port for role mapping and keep that adapter dependency in the
  result.
- The official VS Code theme enables semantic highlighting. Depending on the
  installed language extension, semantic-token rules may supersede or fall
  back to TextMate rules. Comparisons should state which path produced a role.
- Nord currently supplies one dark VS Code profile in this port. Do not invent
  a light "Nord" reference from third-party ports or treat palette ordering as
  a Day/Evening/Night transform.

### Rosé Pine

Canonical palette source: [`rose-pine/palette`](https://github.com/rose-pine/palette)
at commit
[`92af52b465ab6e47437aca223c9b8d3009a2023b`](https://github.com/rose-pine/palette/tree/92af52b465ab6e47437aca223c9b8d3009a2023b),
package version `4.0.1`.

Editor mapping source: the official
[`rose-pine/vscode`](https://github.com/rose-pine/vscode) port at commit
[`d8f5ebe8e096fa833e997c07eb7685ee1677a4ba`](https://github.com/rose-pine/vscode/tree/d8f5ebe8e096fa833e997c07eb7685ee1677a4ba),
package version `2.15.2`.

Primary files:

- [canonical `main`, `moon`, and `dawn` palette data](https://github.com/rose-pine/palette/blob/92af52b465ab6e47437aca223c9b8d3009a2023b/palette.json);
- [official VS Code variant manifest](https://github.com/rose-pine/vscode/blob/d8f5ebe8e096fa833e997c07eb7685ee1677a4ba/package.json);
- [Rosé Pine main VS Code theme](https://github.com/rose-pine/vscode/blob/d8f5ebe8e096fa833e997c07eb7685ee1677a4ba/themes/rose-pine-color-theme.json);
- [Moon theme](https://github.com/rose-pine/vscode/blob/d8f5ebe8e096fa833e997c07eb7685ee1677a4ba/themes/rose-pine-moon-color-theme.json); and
- [Dawn theme](https://github.com/rose-pine/vscode/blob/d8f5ebe8e096fa833e997c07eb7685ee1677a4ba/themes/rose-pine-dawn-color-theme.json).

Interpretation:

- Use `main` / **Rosé Pine** as the primary profile. Report **Moon** and the
  light **Dawn** profile separately. No-italics variants are style ablations,
  not additional palettes.
- Palette roles such as `love`, `gold`, and `foam` are upstream color identities,
  not Grotto syntax roles. The VS Code rules determine their concrete use.
- The checked-in VS Code package declares `@rose-pine/palette` version `3.0.1`
  as a development dependency, while the independently current palette source
  is `4.0.1`. Therefore use the checked-in generated theme JSON for exact
  editor measurements and the current palette repository only for canonical
  palette documentation. Do not silently regenerate the editor theme with the
  newer palette package.

### Solarized

Canonical source: [`altercation/solarized`](https://github.com/altercation/solarized)
at commit
[`62f656a02f93c5190a8753159e34b385588d5ff3`](https://github.com/altercation/solarized/tree/62f656a02f93c5190a8753159e34b385588d5ff3).
The README identifies the current release as `v1.0.0beta2`; there is no Git tag
with that exact name in the upstream tag set.

Primary files:

- [canonical palette, design description, and dark/light rebasing rules](https://github.com/altercation/solarized/blob/62f656a02f93c5190a8753159e34b385588d5ff3/README.md#features); and
- [upstream Vim syntax mapping included in the canonical repository](https://github.com/altercation/solarized/blob/62f656a02f93c5190a8753159e34b385588d5ff3/vim-colors-solarized/colors/solarized.vim).

The standalone upstream
[`altercation/vim-colors-solarized`](https://github.com/altercation/vim-colors-solarized)
repository is pinned at
[`528a59f26d12278698bb946f8fb82a63711eec21`](https://github.com/altercation/vim-colors-solarized/tree/528a59f26d12278698bb946f8fb82a63711eec21).
The canonical repository describes its application-specific directories as
kept in sync through `git-subtree`; Phase 3 should use the copy inside the
canonical snapshot so palette prose and mapping have one provenance root.

Interpretation:

- Solarized is explicitly a dual-mode system. Measure **Solarized Dark** and
  **Solarized Light** independently and also analyze their shared accent
  identities and rebased monotone roles.
- The sixteen raw colors are not sixteen equally weighted syntax categories.
  The upstream usage model assigns monotones and accents contextually, while
  the Vim adapter adds language- and option-dependent mappings.
- Claims in the README about comfort, calibrated-display testing, perceptual
  symmetry, or equal readability are upstream design claims, not independent
  empirical findings. Phase 3 may test measurable properties but must not cite
  those statements as validation.

## Semantic-role mapping rules

1. **Keep raw palette and rendered role data separate.** A color's presence in
   an upstream palette does not establish its frequency, salience, or syntax
   meaning.
2. **Treat editor scopes as implementation evidence, not universal semantics.**
   TextMate grammar scopes vary by language and extension; Neovim highlight
   groups and Tree-sitter captures have their own fallback and link behavior.
3. **Record every normalization judgment.** For example, mapping several
   upstream scopes to Grotto `function` is a Phase 3 interpretation and should
   retain the source scopes beside the normalized role.
4. **Respect rule precedence and fallback.** The final color for a token can
   depend on rule order, scope specificity, semantic-token overrides, and the
   installed grammar. When resolution is uncertain, mark it unresolved rather
   than selecting the most convenient color.
5. **Include non-color encodings.** Italic, bold, underline, borders, and alpha
   fills affect salience and semantic redundancy. Numeric palette comparisons
   should list these even when they cannot include them in color distance.
6. **Composite transparent colors before contrast or distance calculations.**
   Preserve the source RGBA value as well as the resulting color and name the
   background used. Selection, diff, search, and diagnostic fills commonly use
   alpha.
7. **Separate UI, syntax, diagnostics, and terminal colors.** Combining all
   unique hex values into one pairwise-distance distribution would overweight
   large themes and conflate different tasks.
8. **Do not infer pixel coverage from palette membership.** Coverage must come
   from the same rendered specimen and editor layout used for the comparison.
9. **Do not infer adaptation from variant names.** "Dragon," "Moon," "Dawn,"
   "mild contrast," and "dark" are upstream labels. They do not establish a
   controlled ambient-illumination or circadian model.
10. **Do not score a winner.** Comparisons should explain which measurable
    properties contribute to a theme's character and where mappings or variants
    make direct comparison invalid.

## Remaining provenance gaps

- No editor-independent canonical semantic mapping was established for Monokai.
  The selected VS Code implementation is complete and reproducible but is only
  one port.
- "Palenight" has no single unambiguous upstream. The primary profile is the
  inspectable whizkydee theme; the historical Material Theme source is a
  distinct comparison and the current public repository does not expose a
  complete theme definition.
- Kanagawa, Nord, Rosé Pine, and Solarized can render differently across editor
  adapters. This audit pins one official mapping where available; it cannot
  make adapter effects disappear.
- The Solarized repository's stated `v1.0.0beta2` release label has no exact
  matching Git tag, so the commit pin, not the release string, is authoritative
  for reproduction.
- The Rosé Pine canonical palette and checked-in VS Code generator dependency
  are at different package versions. Exact editor analysis must not assume they
  were generated from the same snapshot.

