# Grotto themes for VS Code

Three coding color families, each with a light Day theme and dark Evening and
Night themes. Choose **Restrained**, **Balanced**, or **Expressive** in the theme
picker, then try the lighting variant that suits your room.

This is an early preview. The themes switch manually and contain no executable
code. No family has been selected as the final design.

## Install from VSIX

1. Build the VSIX using the commands below, or use a preview file shared by the maintainer.
2. In VS Code, run **Extensions: Install from VSIX...** from the command palette and select the file.
3. Run **Preferences: Color Theme** and choose a `Grotto` theme.

From the repository root, with Node.js and npm installed:

```bash
mkdir -p dist
cd editors/vscode
npx --yes @vscode/vsce@3.9.2 package --no-dependencies --out ../../dist/grotto-preview-0.1.0.vsix
```

When using VS Code on Windows with WSL, select the VSIX through the Windows
VS Code window. No manual copying into an extensions folder is needed.

To remove the preview, find **Grotto** in the Extensions view and select **Uninstall**.

## Try without installing

From the repository root:

```bash
code --extensionDevelopmentPath="$PWD/editors/vscode"
```

Choose a Grotto theme in the new development window. There are no npm dependencies
or compilation steps for the themes themselves.

## What to look for

Try familiar code and check comments, selected text, search results, diagnostics,
and diffs. Ordinary variables stay neutral; recognized parameters are italic.
Semantic highlighting is enabled, with TextMate scopes as a fallback.

Some Day selection and diff colors remain too close. Restrained can make errors
and warnings harder to distinguish. Language grammars affect the result, so
please include your language and extensions when reporting a highlighting issue.

[Share feedback](https://github.com/sims1253/grotto/issues) with the theme name,
editor version, font, and a small example or screenshot.

## Development

Theme JSON files are generated from canonical palettes. From the repository root:

```bash
uv run grotto vscode --out editors/vscode
```

See the [mapping and development notes](https://github.com/sims1253/grotto/blob/master/docs/VSCODE-DEVELOPMENT.md)
for scope rules and implementation limits. The [project README](https://github.com/sims1253/grotto)
links the comparison reports, Zed preview, and color research.
