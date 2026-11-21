"""Render a theme preview sheet for a Night palette, with Pillow only.

    uv run python scripts/soft_preview.py out/soft-night out/soft-night/soft-s01.night.yaml

Why Pillow and not a browser capture: the committed review PNGs were made with
a headless chromium that is not present on every machine, and this sheet has to
be reproducible from the repo alone.  Pillow is already a dependency, DejaVu
Sans Mono is what ``docs/review/build.py`` pins for the existing captures, and
the roles come from ``specimens.py`` rather than from a hand-copied snippet.

The sheet is not a vanity render.  Its lower half is the **surface cluster** --
selection, active line, diff added, diff removed, search match -- stacked the
way they co-occur in an editor, drawn twice: as authored, and under simulated
deuteranopia.  That is the exact region where the redundant-channel audit
found two pairs excused by a channel the editor does not deliver
(docs/review/redundant-channel-audit.md), so the preview shows the claim
instead of asserting it.  Text stays in its real role colours in both halves;
only the surfaces and the ink are simulated, because that is what a viewer with
a dichromacy actually receives.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from grotto.cvd import simulate  # noqa: E402
from grotto.contrast import wcag_contrast  # noqa: E402
from grotto.render import on_text_threshold  # noqa: E402
from grotto.spec import Palette  # noqa: E402
from grotto.specimens import specimen  # noqa: E402

MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
MONO_B = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

W = 1280
PAD = 26
INSET = 14          # card inner inset
GUTTER = 6          # gap between the two columns
FS = 15             # code
FS_SM = 12          # labels
LH = 22             # code line height
CHAR_W = 8.4        # measured advance width of DejaVu Sans Mono at FS

#: Column width, derived once so the height arithmetic and the drawing cannot
#: disagree about how wide a line may be before it has to be dropped.
COLS = (W - PAD * 2 - 2 * INSET - GUTTER) // 2

BG_PANEL = "#0f1216"
BG_CARD = "#161b22"
BORDER = "#2a323d"
INK_DIM = "#8b98a5"
INK_FAINT = "#6b7783"

#: The seven co-occurring surfaces the audit is about, in draw order.
CLUSTER = [
    ("selection", "selection", "selected text"),
    ("active_line", "active_line", "active line"),
    ("diff_added", "diff_added", "added"),
    ("diff_removed", "diff_removed", "removed"),
    ("diff_changed", "diff_changed", "changed"),
    ("search_match", "search_match", "match"),
    ("search_match_current", "search_match_current", "current match"),
]

#: Diagnostics as VS Code draws them: error/warning/info share one
#: ``4px double`` underline and differ only by colour (redundant-channel
#: audit §4); hint is dotted.  The message text uses the role colour too,
#: as the hover and problems panel do.
DIAGNOSTICS = [
    ("error", "error", "rolling_mean(values, decy)", "object 'decy' not found"),
    ("warning", "warning", "library(dplyr)", "package loaded but unused"),
    ("info", "info", "acc <- 0", "consider vapply()"),
    ("success", "success", "result <- rolling_mean(...)", "tests passed"),
]


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _ink_on(surface: str, palette: Palette) -> str:
    """Dark or light chip ink -- the project-wide cutoff from render.py."""
    return "#0b0e12" if on_text_threshold(surface) else "#e6edf3"


def _panel(d: ImageDraw.ImageDraw, box, fill=BG_CARD) -> None:
    d.rounded_rectangle(box, radius=10, fill=fill, outline=BORDER, width=1)


def _code_block(d, palette, lines, x, y, w, *, ink_map=None) -> int:
    """Draw specimen lines clipped to ``w``; return the y after the block."""
    f = _font(MONO, FS)
    for line in lines:
        cx = x
        for role, text in line:
            if cx - x >= w:
                break
            hx = (ink_map or {}).get(role) or palette.get(role) or palette.get("fg")
            d.text((cx, y), text, font=f, fill=hx)
            cx += d.textlength(text, font=f)
        y += LH
    return y


def _fit_lines(spec, max_chars: int, count: int):
    """Lines of ``spec`` that fit whole in ``max_chars``.

    Blank lines are kept -- stripping them makes a specimen read as a dense
    wall rather than as code -- and over-long lines are dropped rather than
    clipped, because a clipped half-token looks like a rendering bug instead
    of like a line that continues.
    """
    picked = []
    for line in spec.lines:
        if len("".join(t for _, t in line)) <= max_chars:
            picked.append(line)
        if len(picked) == count:
            break
    return picked


def _cluster_lines(max_chars: int, count: int = 6):
    return _fit_lines(specimen("typescript"), max_chars, count)


def _cluster_half(d, palette, x, y, w, title, *, cvd: str | None) -> int:
    """One rendering of the surface cluster. Returns the y after it."""
    f = _font(MONO_B, FS_SM)
    d.text((x, y), title, font=f, fill=INK_DIM)
    y += FS_SM + 12

    band_lines = _cluster_lines(max_chars=int((COLS - 40) / 8.4))
    band_h = 14 + LH * len(band_lines) + 12

    for role, _key, label in CLUSTER:
        raw = palette.get(role)
        surf = simulate(raw, cvd, 1.0) if cvd else raw

        d.rounded_rectangle((x, y, x + w, y + band_h), radius=6,
                            fill=surf, outline=BORDER, width=1)
        d.text((x + 12, y + 4), label, font=f, fill=_ink_on(surf, palette))

        roles = {r for ln in band_lines for r, _ in ln}
        ink = {r: (simulate(palette.get(r), cvd, 1.0) if cvd else palette.get(r))
               for r in roles}
        _code_block(d, palette, band_lines, x + 12, y + 14 + 8, w - 24, ink_map=ink)
        y += band_h + 12
    return y


def _diag_half(d, palette, x, y, w, title, *, cvd: str | None) -> int:
    """Diagnostics on the canvas: underline + message per severity, plus the
    gutter marks (breakpoint dot, focus ring).  Returns the y after it."""
    f = _font(MONO, FS)
    fb = _font(MONO_B, FS_SM)
    sim = (lambda hx: simulate(hx, cvd, 1.0)) if cvd else (lambda hx: hx)
    d.text((x, y), title, font=fb, fill=INK_DIM)
    y += FS_SM + 12
    canvas = sim(palette.get("bg"))
    h = 14 + (LH + 12) * len(DIAGNOSTICS) + LH + 14
    d.rounded_rectangle((x, y, x + w, y + h), radius=6, fill=canvas,
                        outline=BORDER, width=1)
    ty = y + 12
    for role, _key, code, msg in DIAGNOSTICS:
        col = sim(palette.get(role))
        d.ellipse((x + 10, ty + 6, x + 20, ty + 16), fill=col)
        cx = x + 30
        d.text((cx, ty), code, font=f, fill=sim(palette.get("fg")))
        tw = d.textlength(code, font=f)
        if role != "success":
            # 4px double: two 1px rules, 3px apart
            d.line((cx, ty + LH - 2, cx + tw, ty + LH - 2), fill=col, width=1)
            d.line((cx, ty + LH + 1, cx + tw, ty + LH + 1), fill=col, width=1)
        d.text((cx + tw + 16, ty), msg, font=f, fill=col)
        ty += LH + 12
    # gutter marks
    bp = sim(palette.get("breakpoint"))
    d.ellipse((x + 10, ty + 5, x + 22, ty + 17), fill=bp)
    d.text((x + 30, ty), "breakpoint", font=f, fill=bp)
    fx = x + 30 + d.textlength("breakpoint", font=f) + 30
    focus = sim(palette.get("focus"))
    d.rectangle((fx, ty - 2, fx + d.textlength("focus ring", font=f) + 12, ty + LH),
                outline=focus, width=1)
    d.text((fx + 6, ty), "focus ring", font=f, fill=focus)
    return y + h + 12


def sheet(palette_path: Path, out_dir: Path) -> Path:
    palette = Palette.from_yaml(palette_path)
    bg = palette.get("bg")
    ink = palette.get("fg")

    # ---- measure first so the canvas is exactly as tall as the content ----
    ft = _font(MONO_B, 20)
    fm = _font(MONO, FS_SM)
    cols = COLS
    head = 34 + 26 + 20
    spec_rows = _fit_lines(specimen("r"), max_chars=int(cols / CHAR_W), count=16)
    spec_h = 22 + FS_SM + 10 + LH * len(spec_rows) + 26
    band_lines = _cluster_lines(max_chars=int((cols - 40) / CHAR_W))
    clus_h = 22 + FS_SM + 12 + (14 + LH * len(band_lines) + 12 + 12) * len(CLUSTER) + 10
    diag_h = 22 + FS_SM + 12 + 14 + (LH + 12) * len(DIAGNOSTICS) + LH + 14 + 12 + 10
    foot = 56
    H = PAD + head + spec_h + 26 + clus_h + 26 + diag_h + foot + PAD
    im = Image.new("RGB", (W, H), BG_PANEL)
    d = ImageDraw.Draw(im)

    # ---- header ----
    d.text((PAD, PAD), palette.name, font=ft, fill=ink)
    wl = wcag_contrast(palette.get("fg"), bg)
    ml = wcag_contrast(palette.get("fg_muted"), bg)
    meta = (f"body text on canvas {wl:.2f}:1   ·   muted on canvas {ml:.2f}:1"
            f"   ·   surfaces co-occur in the lower half")
    d.text((PAD, PAD + 30), meta, font=fm, fill=INK_FAINT)

    # ---- code specimens, two languages ----
    y = PAD + head
    # On the palette's OWN canvas: a neutral card here would show the syntax
    # colours against a background the theme never draws.
    _panel(d, (PAD, y, W - PAD, y + spec_h - 14), fill=bg)
    d.text((PAD + INSET, y + 10), "code specimens", font=_font(MONO_B, FS_SM), fill=INK_DIM)
    for i, lang in enumerate(("r", "typescript")):
        cx = PAD + INSET + i * (cols + GUTTER)
        sp = specimen(lang)
        d.text((cx, y + 10 + FS_SM + 10), sp.filename, font=fm, fill=INK_FAINT)
        _code_block(d, palette, _fit_lines(sp, int(cols / CHAR_W), 16),
                    cx, y + 10 + FS_SM + 10 + LH + 8, cols)

    # ---- the surface cluster, as authored and under deuteranopia ----
    y = PAD + head + spec_h + 26
    _panel(d, (PAD, y, W - PAD, y + clus_h - 14))
    d.text((PAD + INSET, y + 10), "the surface cluster — as authored, and under deuteranopia",
           font=_font(MONO_B, FS_SM), fill=INK_DIM)
    top = y + 10 + FS_SM + 12
    _cluster_half(d, palette, PAD + INSET, top, cols, "as authored", cvd=None)
    _cluster_half(d, palette, PAD + INSET + cols + GUTTER, top, cols,
                  "deutan @ 1.0", cvd="deutan")

    # ---- diagnostics, as authored and under tritanopia ----
    # Tritan, not deutan: error/warning are a red/amber pair that tritanopia
    # collapses (both land on its confusion axis; audit §7).
    y = PAD + head + spec_h + 26 + clus_h + 26
    _panel(d, (PAD, y, W - PAD, y + diag_h - 14))
    d.text((PAD + INSET, y + 10), "diagnostics — as authored, and under tritanopia",
           font=_font(MONO_B, FS_SM), fill=INK_DIM)
    top = y + 10 + FS_SM + 12
    _diag_half(d, palette, PAD + INSET, top, cols, "as authored", cvd=None)
    _diag_half(d, palette, PAD + INSET + cols + GUTTER, top, cols,
               "tritan @ 1.0", cvd="tritan")

    # ---- footer ----
    fy = PAD + head + spec_h + 26 + clus_h + 26 + diag_h - 4
    d.text((PAD, fy),
           "Sources: scripts/soft_preview.py  ·  specimens from grotto.specimens  ·  "
           "CVD via grotto.cvd.simulate  ·  ink cutoff from grotto.render",
           font=_font(MONO, 10), fill=INK_FAINT)

    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"preview-{palette_path.stem}.png"
    im.save(out, "PNG", optimize=True)
    return out


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        print("\nusage: soft_preview.py OUT_DIR PALETTE.yaml [PALETTE.yaml ...]")
        return 2
    out_dir = Path(argv[1])
    for p in argv[2:]:
        print(sheet(Path(p), out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
