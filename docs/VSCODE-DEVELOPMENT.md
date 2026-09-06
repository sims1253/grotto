# VS Code mapping notes

Edit `spec/mappings/vscode.yaml`, then regenerate the themes with
`uv run grotto vscode --out editors/vscode` from the repository root.
Each generated file records its source palette and SHA-256 hash. Tests check
that regeneration matches the committed themes.

For installation and packaging, use [the extension guide](../editors/vscode/README.md).

## Syntax colors

The themes enable semantic highlighting and provide TextMate rules as a
fallback. Ordinary variables and parameters use neutral foreground; recognized
parameters are italic. Deprecated symbols use strikethrough.

Use **Developer: Inspect Editor Tokens and Scopes** to investigate a color.
Check both the grammar scope and any semantic token. Scope rules use prefix
matching, so a broad parent rule can color tokens it was not intended to cover.

## R and TypeScript arguments

The R rule for `meta.function-call` colors function names. R also places plain
arguments under that scope. A later `meta.function-call.arguments.r` rule returns
those arguments to neutral foreground. Tokens with their own scopes, such as
strings, numbers, and nested calls, retain their colors. The mapping treats
`keyword.accessor.dollar.r` as an operator.

TS/JS argument tokens sit directly under `meta.function-call.ts`, without an
`.arguments` child scope. The mapping assigns `variable.other.readwrite` and
`variable.other.object` to neutral foreground. These more specific scopes prevent
ordinary arguments from inheriting the function color. `meta.brace` maps to
punctuation.

The R correction was checked in VS Code under Balanced Night. Recheck TS/JS
in the editor, and repeat these checks when the grammar changes. The mapping
also covers roxygen comments and R Markdown headings; exact behavior depends
on the installed grammar.

## Workbench colors

Workbench colors are opaque except for overlays that must preserve text beneath
them. Secondary selection, search, hover, bracket-match, diff, and debug overlays
use hex alpha `80`. The primary selection and current search match are opaque.
`editorUnnecessaryCode.opacity` uses alpha `66`.

The theme controls parameter italics, strikethrough, focus borders, and search
match borders. VS Code controls diagnostic squiggle shapes, gutter icons, and
diff signs. The selection treatment uses a lightness change rather than a border.
Unmapped workbench keys use VS Code defaults.
