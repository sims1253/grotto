# Grotto VS Code evaluation preview (Phase 8a)

**These are not nine finished themes and no winner is selected.** They are a
static, no-build evaluation preview of the three Phase 5 *candidate* families
(`themes/candidates/*.yaml`) under the three environment variants, so the human
evaluation in `HUMAN_EVALUATION.md` can view real editor rendering before any
selection. Labels are neutral about preference; nothing here ranks or scores.

## What this is (and is not)

- exactly nine themes via `contributes.themes`: Restrained / Balanced /
  Expressive × Day / Evening / Night. Day is `uiTheme: "vs"` (light);
  Evening and Night are `uiTheme: "vs-dark"`.
- **static only**: no runtime JS/TS, no commands, no activation events, no
  automatic Day/Evening/Night switching, no publishing, no npm dependencies.
  Switching variants is the participant's manual act, on purpose — the study
  protocol records every switch.
- the nine `themes/*.json` files are **generated**, never hand-copied:

  ```bash
  uv run grotto vscode --out editors/vscode
  ```

  Generation is byte-deterministic from `spec/mappings/vscode.yaml` +
  `themes/candidates/*.yaml`; each theme file records its source palette and
  its SHA-256 under a `grotto` metadata key, and tests re-verify regeneration
  and hashes.

## Install (no build)

Copy or symlink this directory into your VS Code extensions folder, then
reload and pick a theme by label from the Color Theme picker:

```bash
mkdir -p ~/.vscode/extensions

# symlink (recommended: stays in sync with the repo)
ln -s "$(pwd)/editors/vscode" ~/.vscode/extensions/grotto-evaluation-preview

# or copy
mkdir -p ~/.vscode/extensions/grotto-evaluation-preview
cp -a editors/vscode/. ~/.vscode/extensions/grotto-evaluation-preview/
```

Undo with `rm ~/.vscode/extensions/grotto-evaluation-preview` (add `-r` if you
copied; a symlink needs no `-r`).

### From WSL

When you open this repo from WSL with VS Code running on Windows
(Remote-WSL), the theme must live in the **Windows-side** extensions folder:

```bash
windows_user="YOUR_WINDOWS_USERNAME"  # replace this value
extension_dir="/mnt/c/Users/$windows_user/.vscode/extensions/grotto-evaluation-preview"
mkdir -p "$extension_dir"
cp -a editors/vscode/. "$extension_dir/"
```

then reload VS Code on Windows. Copy rather than symlink: a WSL symlink may
not resolve on the Windows filesystem. The F5 development host below needs no
install at all.

## Development host (no install at all)

Open this folder in VS Code and press **F5** ("Run Extension"): an Extension
Development Host starts with the nine themes loaded without touching your
profile. Do not run `npm install` — there is nothing to build.

## Semantic highlighting

The theme JSONs set `semanticHighlighting: true` and provide
`semanticTokenColors`. Ordinary variables/parameters stay neutral; parameters
are distinguished by *italic*, deprecated symbols by *strikethrough* (also via
the TextMate `invalid.deprecated` scope). If semantic tokens appear inactive
for a language, check `editor.semanticTokenColorCustomizations` in user
settings.

## R support

The mapping covers the R scopes the stock and common R grammars emit via
prefix matching (`string`, `keyword.control.r`, `entity.name.function.r`,
`constant.numeric.*`, roxygen docstrings, R Markdown headings). Installing
**REditorSupport.r** is *recommended* for the evaluation (better R grammar and
R Markdown embedding), but not required — the themes work with any grammar.

### Call-argument normalization (R, then TS/JS)

The R grammar wraps whole argument lists in
`meta.function-call.arguments.r > meta.function-call.r`; because the mapping
paints `meta.function-call` as `function` (so real function names and nested
calls keep their highlight), every plain identifier argument (`log`, `temp_c`)
inherited the function colour. A later, R-only `meta.function-call.arguments.r`
rule paints those arguments back to neutral foreground, and
`keyword.accessor.dollar.r` is routed through the operator rule so R's `$`
accessor renders as an operator rather than a keyword. **Limitation:** the
override is keyed to the exact `.r` scope, so it normalizes only plain
argument tokens that carry it — with no semantic tokens present, argument
*names* with their own grammar scopes (strings, numbers, nested calls) keep
those scopes' colours.

The **TS/JS grammars have no `.arguments` child scope** — plain-identifier
arguments sit directly inside `meta.function-call.ts` — so the same
overpainting occurred there (visible in `console.log(rollingMean([1, 2, 3]))`
in the TS specimen). Since no `.arguments` scope exists to key a narrow rule
on, the mapping instead routes `variable.other.readwrite` /
`variable.other.object` (which those argument tokens carry, and which match
deeper than `meta.function-call`) to neutral `fg`; that is also the L1 intent
(there is no `variable` role — variables are `fg`) and matches the
semantic-token mapping. `meta.brace` is routed to `punctuation` for the same
reason (bracket scopes in TS/JS are `meta.brace.*`, not `punctuation.*`).
Verified with `Developer: Inspect Editor Tokens and Scopes` under Balanced
Night for R; the TS/JS rules follow the same inspect-and-map loop and should
be re-verified in a real editor. Re-check if a grammar changes.

## Known gaps and honesty notes

- Scope lists are broad/prefix-based; exact R/R Markdown and niche-language
  scope behaviour needs eyeballing in a real VS Code. Inspect with
  `Developer: Inspect Editor Tokens and Scopes` and fix
  `spec/mappings/vscode.yaml` (then regenerate) — never the generated files.
  One such verified fix is the R call-argument normalization above; the same
  inspect-and-map loop applies to any residual R/R Markdown oddities.
- Redundant non-hue channels VS Code does not let a theme control: squiggle
  shapes and diagnostic gutter icons (fixed UI), diff `+/-` gutter signs,
  selection borders (only the lightness offset survives). Strikethrough,
  parameter italics, focus borders and the find-match *borders*
  (`editor.findMatchBorder` / `editor.findMatchHighlightBorder`, which deliver
  `search_match`/`search_match_current`'s declared border channel) *are*
  honored. See the notes in `spec/mappings/vscode.yaml`.
- Chrome colors are opaque by policy, per the official VS Code transparency
  guidance.  Ids that paint a highlight OVER editor content keep that content
  readable with alpha 80: the secondary selection/search/hover overlays
  (`editor.inactiveSelectionBackground`,
  `editor.selectionHighlightBackground`,
  `editor.findMatchHighlightBackground`, `editor.hoverHighlightBackground`),
  the bracket-match fill (`editorBracketMatch.background`), every diffEditor
  wash (word-level and whole-line inserted/removed), and the debug
  stack-frame highlights.  The primary selection and the current find match
  stay opaque.  `editorUnnecessaryCode.opacity` ships alpha 66 as its
  contract expects.
- Unmapped workbench keys fall back to VS Code defaults; the mapping covers
  canvas, chrome, line numbers, cursor/focus, selection, active line, search,
  diagnostics, diff, breakpoint/debug, panels/sidebar/lists, but not every id.
