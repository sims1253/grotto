# Theme development

Run commands from the repository root after `uv sync --locked`.

## Change a theme

Edit the family bindings in `spec/bindings/candidate-*.yaml` or the shared
transform settings in `spec/environments.yaml`. Then regenerate:

```bash
uv run grotto candidates --out out/candidates
uv run grotto vscode --out editors/vscode
uv run grotto zed --out editors/zed
uv run pytest -q
```

The candidate command writes nine palettes to `themes/candidates/` and reports
to `out/candidates/`. The editor commands apply `spec/mappings/vscode.yaml` and
`spec/mappings/zed.yaml` to those palettes. Edit mappings to fix highlighting;
do not edit generated theme JSON. See [the VS Code mapping notes](VSCODE-DEVELOPMENT.md)
for grammar-specific behavior.

Reports record input hashes and omit timestamps. Identical inputs produce
identical output. Review the generated diff as well as the test results.

## Inspect the result

Open `out/candidates/comparison.html` locally for the comparison of all families.
Each family directory also contains a `*.specimens.html` page with code and
critical UI states. These pages use simulated color vision to expose colors
that become hard to distinguish. They cannot validate an editor's grammar or
reproduce an individual's vision.

Install the regenerated themes and check the same code in the editor. To write
the source specimens for that check:

```bash
uv run grotto specimens --out out/specimens
```

## Other evaluations

| Command | Purpose |
| --- | --- |
| `grotto palette <palette> --out <dir>` | Audit one palette and render a report |
| `grotto stability <day> <evening> <night> --out <dir>` | Check consistency across variants |
| `grotto references --out <dir>` | Compare the reference themes |
| `grotto family <binding> --out <dir>` | Derive a family from one binding |
| `grotto compare-families --help` | Compare a derived family with hand-tuned palettes |
| `grotto raster --help` | Analyze screenshot coverage |

Prefix commands with `uv run`. Each command's `--help` lists its inputs and
options. The [raster guide](../evaluation/raster/README.md) explains screenshot
capture, and [NUMERIC.md](../NUMERIC.md) records the Night search experiments.

The specification files define the constraints. [DESIGN.md](../DESIGN.md) explains
them; [RESEARCH.md](../RESEARCH.md) and [REFERENCES.md](../REFERENCES.md) cover the
evidence. APCA is experimental, color-vision simulations are models, and spectral
estimates apply only within the assumed display model. None selects a theme on
behalf of its user.
