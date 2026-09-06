# Grotto evaluation preview for Zed

This static extension contains all nine unranked Grotto candidates: three
families, each with Day, Evening, and Night variants. It is for evaluation.
No candidate is selected or final.

## Install

1. Open Zed's Extensions page.
2. Select **Install Dev Extension**.
3. Select this `editors/zed` directory.
4. Open the theme selector (`Ctrl+K`, then `Ctrl+T` on Linux and Windows;
   `Cmd+K`, then `Cmd+T` on macOS) and choose a `Grotto …` theme.

The extension has no executable code. It does not switch variants
automatically. You can select any variant manually. Zed can also pair one
light theme and one dark theme with the system appearance setting, but that
does not represent the full Day → Evening → Night sequence.

## Check highlighting

Zed uses Tree-sitter highlighting by default. Its `semantic_tokens` setting is
`off` unless you change it. Test the default first, then repeat with
`semantic_tokens` set to `combined` if the language server supports semantic
tokens. Use `dev: open highlights tree view` to inspect the highlight beneath
the cursor.

The adapter maps both Tree-sitter and semantic-token highlight names onto the
same Grotto roles. Ordinary variables remain neutral. Parameters are neutral
and italic when the grammar or language server identifies them.

## Regenerate

From the repository root:

```bash
uv run grotto zed --out editors/zed
```

The command reads `themes/candidates/*.yaml` and
`spec/mappings/zed.yaml`. It writes the Zed theme family to
`themes/grotto.json` and source hashes to `provenance.json`. Do not edit the
generated files by hand.

The generator targets Zed's hosted theme schema `v0.2.0`. The schema can lag
new keys used by Zed's built-in themes, so this preview uses only hosted-schema
keys. See the repository documentation for the evaluation protocol and known
display and typography controls.
