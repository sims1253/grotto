# Grotto

A dark VS Code theme on a warm brown-black background.

![Grotto Night showing R and TypeScript code](docs/grotto-night.png)

Body text has a 10:1 contrast ratio against the background. Code stays at 4.5:1 or above on the background and on every highlight, and placeholder text and line numbers stay at 3:1 or above. Selection, search matches, and added, removed, and changed lines each get a distinct tint. Errors are red, warnings are yellow, and success is green.

Grotto is built for color vision deficiency. Every color pair that must stay apart is checked under simulated protanopia, deuteranopia, and tritanopia. Most pairs stay apart by color alone. Where color can't do it, as with added and removed diff lines, VS Code also marks the difference without color, using the `+` and `-` gutter signs or the error underline.

## Install

From the repository root, copy the extension into your VS Code extensions folder:

```bash
cp -r out/soft-night-v2/vscode-preview ~/.vscode/extensions/grotto-soft-objective-v2
```

Restart VS Code, run **Preferences: Color Theme**, and choose **Grotto S2-Explore 01 Night**.

To try the theme without installing it:

```bash
code --extensionDevelopmentPath="$PWD/out/soft-night-v2/vscode-preview"
```

Grotto is a preview. If something is hard to read, [open an issue](https://github.com/sims1253/grotto/issues) with the language, the font, and a code sample.

[MIT license](LICENSE).
