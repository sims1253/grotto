#!/usr/bin/env python3
"""Deterministic matching metrics for the Grotto R pilot corpus.

Stdlib only (no numpy/pyyaml) so the corpus can be audited without the
project environment.  Metrics are deliberately *coarse*: they exist so
excerpts can be matched on observable features before piloting (CORPUS_RESEARCH.md
"matched parallel forms").  Approximate matching still needs piloting with
real participants; these numbers are a screening aid, not a difficulty score.

Usage:
    python3 evaluation/r-corpus/tools/metrics.py evaluation/r-corpus/items --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

CONSTRUCT_PATTERNS: dict[str, str] = {
    "function_def": r"<-\s*function\s*\(",
    "assignment": r"<-|<<-|->>",
    "dollar_index": r"\$[A-Za-z._][A-Za-z0-9._]*",
    "bracket_index": r"\[\[",
    "if_else": r"\bif\s*\(|\belse\b|\bifelse\s*\(",
    "loop": r"\bfor\s*\(|\bwhile\s*\(|\brepeat\b|\bnext\b|\bbreak\b",
    "apply_call": r"\b(l|s|v|m|t|r)?apply\s*\(",
    "string_literal": r'"[^"\n]*"',
    "numeric_literal": r"\b\d+(\.\d+)?([eE][+-]?\d+)?\b",
    "comment": r"^\s*#",
}

_OPEN = "([{"
_CLOSE = ")]}"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def max_delimiter_nesting(text: str) -> int:
    """Max simultaneous open (), [], {} depth, ignoring strings/comments.

    Deliberately simple: it may overcount on odd nesting inside string
    literals that span quote handling edge cases.  Deterministic and equal
    across items, which is what coarse matching needs.
    """
    depth = 0
    best = 0
    in_string = False
    in_comment = False
    prev = ""
    for ch in text:
        if in_comment:
            if ch == "\n":
                in_comment = False
            prev = ch
            continue
        if in_string:
            if ch == '"' and prev != "\\":
                in_string = False
            prev = ch
            continue
        if ch == "#":
            in_comment = True
        elif ch == '"':
            in_string = True
        elif ch in _OPEN:
            depth += 1
            best = max(best, depth)
        elif ch in _CLOSE:
            depth = max(0, depth - 1)
        prev = ch
    return best


def item_metrics(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    counts = {
        name: len(re.findall(pat, text, flags=re.MULTILINE))
        for name, pat in CONSTRUCT_PATTERNS.items()
    }
    nonblank = [ln for ln in lines if ln.strip()]
    return {
        "path": path.name,
        "sha256": sha256_text(text),
        "lines": len(lines),
        "nonblank_lines": len(nonblank),
        "blank_lines": len(lines) - len(nonblank),
        "comment_lines": counts["comment"],
        "comment_ratio": round(counts["comment"] / max(len(nonblank), 1), 3),
        "constructs": {k: v for k, v in counts.items() if k != "comment"},
        "construct_families": sum(1 for v in counts.values() if v > 0),
        "max_nesting": max_delimiter_nesting(text),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("items_dir", nargs="?", default="evaluation/r-corpus/items")
    ap.add_argument("--json", action="store_true", help="emit JSON (default: table)")
    args = ap.parse_args(argv)

    paths = sorted(Path(args.items_dir).glob("*.R"))
    if not paths:
        print(f"no .R items under {args.items_dir}", file=sys.stderr)
        return 1
    metrics = [item_metrics(p) for p in paths]

    if args.json:
        print(json.dumps(metrics, indent=2))
        return 0
    hdr = ("item", "lines", "nonblank", "comments", "nest", "families", "sha256[:12]")
    print("{:<32}{:>6}{:>9}{:>9}{:>5}{:>9}{:>14}".format(*hdr))
    for m in metrics:
        print(
            f"{m['path']:<32}{m['lines']:>6}{m['nonblank_lines']:>9}"
            f"{m['comment_lines']:>9}{m['max_nesting']:>5}{m['construct_families']:>9}"
            f"{m['sha256'][:12]:>14}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
