"""Realistic code specimens for visual evaluation.

Each specimen is a short, plausible snippet in a real language, broken into
(role, text) spans so the renderer can colour it with a palette.  Spans use
the role vocabulary from ``spec/roles.yaml``; whitespace is carried in the
span text so the reconstructed plaintext is readable and diff-stable.

Coverage targets (requirement 8): Python, Rust, TypeScript/JavaScript, shell,
JSON, YAML, Markdown, R.  The specimens are written to exercise the requested
role variety (keywords, strings, numbers, functions, types, comments,
operators, punctuation, builtins, tags, etc.).  Diagnostic roles
(error/warning/...) are not natural inside source specimens, so the renderer
shows them in a dedicated diagnostics panel instead of faking them here.

Honesty note on Markdown: the ``**`` emphasis markers are labelled ``keyword``
and inline code spans ``function`` as a RENDERER-LEVEL choice to make structure
visible in the HTML reports; the VS Code mapping styles no markup.bold /
markup.inline.raw equivalents, so the real editor renders those tokens as
neutral ``fg``.  Do not treat the Markdown specimen row as a prediction of
in-editor Markdown appearance.
"""

from __future__ import annotations

from dataclasses import dataclass

# A span is a (role, text) pair.  role is a key into a Palette; text may carry
# leading indentation.  A line is a tuple of spans; a specimen is a tuple of
# lines (no embedded newlines -- the renderer joins lines).
Span = tuple[str, str]
Line = tuple[Span, ...]


@dataclass(frozen=True)
class Specimen:
    language: str
    label: str
    filename: str
    description: str
    lines: tuple[Line, ...]

    def spans(self):
        """Yield every (role, text) span in reading order."""
        for line in self.lines:
            yield from line

    def plaintext(self) -> str:
        return "\n".join("".join(t for _, t in line) for line in self.lines) + "\n"

    def roles_used(self) -> set[str]:
        return {r for r, _ in self.spans()}

    def line_count(self) -> int:
        return len(self.lines)


def _spec(language, label, filename, description, lines):
    return Specimen(language, label, filename, description, tuple(tuple(ln) for ln in lines))


# --------------------------------------------------------------------------
# Python
# --------------------------------------------------------------------------

PYTHON = _spec(
    "python", "Python", "rolling.py",
    "Decorators, type annotations, builtins, docstrings, a constant.",
    [
        [("comment", "# rolling.py -- exponential moving average with a decay knob")],
        [("keyword", "from "), ("namespace", "functools"), ("fg", " "), ("keyword", "import "), ("builtin", "lru_cache")],
        [("keyword", "from "), ("namespace", "numpy"), ("fg", " "), ("keyword", "import "), ("namespace", "linalg"), ("fg", " "), ("keyword", "as "), ("namespace", "la")],
        [],
        [("constant", "DEFAULT_DECAY"), ("operator", " = "), ("number", "0.92")],
        [],
        [("decorator", "@lru_cache"), ("punctuation", "("), ("parameter", "maxsize"), ("operator", "="), ("number", "128"), ("punctuation", ")")],
        [("keyword", "def "), ("function", "rolling_mean"), ("punctuation", "("), ("parameter", "values"), ("punctuation", ": "), ("builtin", "list"), ("punctuation", "["), ("type", "float"), ("punctuation", "], "), ("parameter", "decay"), ("punctuation", ": "), ("type", "float"), ("fg", " = "), ("constant", "DEFAULT_DECAY"), ("punctuation", ")"), ("fg", " -> "), ("type", "float"), ("punctuation", ":")],
        [("docstring", '    """Return the exponentially-smoothed mean of `values`."""')],
        [("fg", "    "), ("fg", "acc"), ("operator", " = "), ("number", "0.0")],
        [("fg", "    "), ("keyword", "for "), ("parameter", "x"), ("fg", " "), ("keyword", "in "), ("parameter", "values"), ("punctuation", ":")],
        [("fg", "        "), ("fg", "acc"), ("operator", " = "), ("parameter", "decay"), ("operator", " * "), ("fg", "acc"), ("operator", " + "), ("punctuation", "("), ("number", "1"), ("operator", " - "), ("parameter", "decay"), ("punctuation", ")"), ("operator", " * "), ("parameter", "x")],
        [("fg", "    "), ("keyword", "return "), ("fg", "acc")],
    ],
)


# --------------------------------------------------------------------------
# Rust
# --------------------------------------------------------------------------

RUST = _spec(
    "rust", "Rust", "rolling.rs",
    "Attributes, lifetimes-as-slices, generics-free, doc comment.",
    [
        [("comment", "// rolling.rs -- exponential moving average")],
        [("keyword", "use "), ("namespace", "std"), ("punctuation", "::"), ("namespace", "collections"), ("punctuation", "::"), ("type", "VecDeque"), ("punctuation", ";")],
        [],
        [("keyword", "const "), ("constant", "DEFAULT_DECAY"), ("punctuation", ": "), ("type", "f64"), ("fg", " = "), ("number", "0.92"), ("punctuation", ";")],
        [],
        [("decorator", "#[inline]")],
        [("docstring", "/// Exponentially-smoothed mean of a slice.")],
        [("keyword", "pub "), ("keyword", "fn "), ("function", "rolling_mean"), ("punctuation", "("), ("parameter", "values"), ("punctuation", ": &["), ("type", "f64"), ("punctuation", "], "), ("parameter", "decay"), ("punctuation", ": "), ("type", "f64"), ("punctuation", ")"), ("fg", " -> "), ("type", "f64"), ("fg", " {")],
        [("fg", "    "), ("keyword", "let "), ("keyword", "mut"), ("fg", " "), ("fg", "acc"), ("punctuation", ": "), ("type", "f64"), ("fg", " = "), ("number", "0.0"), ("punctuation", ";")],
        [("fg", "    "), ("keyword", "for "), ("operator", "&"), ("parameter", "x"), ("fg", " "), ("keyword", "in "), ("parameter", "values"), ("fg", " {")],
        [("fg", "        "), ("fg", "acc"), ("fg", " = "), ("parameter", "decay"), ("operator", " * "), ("fg", "acc"), ("operator", " + "), ("punctuation", "("), ("number", "1.0"), ("operator", " - "), ("parameter", "decay"), ("punctuation", ")"), ("operator", " * "), ("parameter", "x"), ("punctuation", ";")],
        [("fg", "    "), ("punctuation", "}")],
        [("fg", "    "), ("fg", "acc")],
        [("punctuation", "}")],
    ],
)


# --------------------------------------------------------------------------
# TypeScript / JavaScript
# --------------------------------------------------------------------------

TYPESCRIPT = _spec(
    "typescript", "TypeScript", "rolling.ts",
    "Imports, types, default parameter, namespace call.",
    [
        [("comment", "// rolling.ts -- exponential moving average")],
        [("keyword", "import "), ("punctuation", "{ "), ("function", "lruCache"), ("punctuation", " } "), ("keyword", "from "), ("string", '"./cache"'), ("punctuation", ";")],
        [],
        [("keyword", "export "), ("keyword", "const "), ("constant", "DEFAULT_DECAY"), ("fg", " = "), ("number", "0.92"), ("punctuation", ";")],
        [],
        [("keyword", "export "), ("keyword", "function "), ("function", "rollingMean"), ("punctuation", "("), ("parameter", "values"), ("punctuation", ": "), ("type", "number"), ("punctuation", "[], "), ("parameter", "decay"), ("punctuation", ": "), ("type", "number"), ("fg", " = "), ("constant", "DEFAULT_DECAY"), ("punctuation", ")"), ("punctuation", ": "), ("type", "number"), ("fg", " {")],
        [("docstring", "  /** Exponentially-smoothed mean of `values`. */")],
        [("fg", "  "), ("keyword", "let "), ("fg", "acc"), ("fg", " = "), ("number", "0"), ("punctuation", ";")],
        [("fg", "  "), ("keyword", "for "), ("punctuation", "("), ("keyword", "const "), ("parameter", "x"), ("fg", " "), ("keyword", "of "), ("parameter", "values"), ("punctuation", ") {")],
        [("fg", "    "), ("fg", "acc"), ("fg", " = "), ("parameter", "decay"), ("operator", " * "), ("fg", "acc"), ("operator", " + "), ("punctuation", "("), ("number", "1"), ("operator", " - "), ("parameter", "decay"), ("punctuation", ")"), ("operator", " * "), ("parameter", "x"), ("punctuation", ";")],
        [("fg", "  "), ("punctuation", "}")],
        [("fg", "  "), ("keyword", "return "), ("fg", "acc"), ("punctuation", ";")],
        [("punctuation", "}")],
        [],
        [("namespace", "console"), ("punctuation", "."), ("builtin", "log"), ("punctuation", "("), ("function", "rollingMean"), ("punctuation", "(["), ("number", "1"), ("punctuation", ", "), ("number", "2"), ("punctuation", ", "), ("number", "3"), ("punctuation", "]));")],
    ],
)


# --------------------------------------------------------------------------
# Shell (bash)
# --------------------------------------------------------------------------

SHELL = _spec(
    "shell", "Shell", "rolling.sh",
    "Shebang, builtins, parameter expansion, arithmetic via bc.",
    [
        [("comment", "#!/usr/bin/env bash")],
        [("comment", "# rolling.sh -- stream an exponential moving average")],
        [("builtin", "set"), ("fg", " -euo pipefail")],
        [],
        [("constant", "DECAY"), ("operator", "=\"${"), ("constant", "DECAY"), ("operator", ":-"), ("number", "0.92"), ("operator", "}\"")],
        [],
        [("function", "rolling_mean"), ("punctuation", "() {")],
        [("fg", "  "), ("builtin", "local"), ("fg", " acc="), ("number", "0")],
        [("fg", "  "), ("keyword", "while "), ("builtin", "read"), ("fg", " -r "), ("parameter", "x"), ("punctuation", "; "), ("keyword", "do")],
        [("fg", "    "), ("fg", "acc"), ("operator", "=$("), ("builtin", "awk"), ("fg", " -v d=\""), ("parameter", "$DECAY"), ("fg", "\" -v a=\""), ("parameter", "$acc"), ("fg", "\" -v x=\""), ("parameter", "$x"), ("fg", "\" 'BEGIN{print d*a+(1-d)*x}'"), ("operator", ")")],
        [("fg", "  "), ("keyword", "done")],
        [("fg", "  "), ("builtin", "printf"), ("fg", " "), ("string", "'%.4f\\n'"), ("fg", " \""), ("fg", "$acc"), ("fg", "\"")],
        [("punctuation", "}")],
        [],
        [("function", "rolling_mean"), ("fg", " < samples.txt")],
    ],
)


# --------------------------------------------------------------------------
# JSON
# --------------------------------------------------------------------------

JSON = _spec(
    "json", "JSON", "rolling.json",
    "Keys as tags, scalar values by type; the canonical config shape.",
    [
        [("punctuation", "{")],
        [("fg", "  \""), ("tag", "service"), ("fg", "\": "), ("string", "\"rolling\""), ("punctuation", ",")],
        [("fg", "  \""), ("tag", "version"), ("fg", "\": "), ("number", "3"), ("punctuation", ",")],
        [("fg", "  \""), ("tag", "decay"), ("fg", "\": "), ("number", "0.92"), ("punctuation", ",")],
        [("fg", "  \""), ("tag", "enabled"), ("fg", "\": "), ("constant", "true"), ("punctuation", ",")],
        [("fg", "  \""), ("tag", "samples"), ("fg", "\": ["), ("number", "1"), ("punctuation", ", "), ("number", "2"), ("punctuation", ", "), ("number", "3"), ("fg", "],")],
        [("fg", "  \""), ("tag", "notes"), ("fg", "\": "), ("string", "\"Exponentially-smoothed mean.\"")],
        [("punctuation", "}")],
    ],
)


# --------------------------------------------------------------------------
# YAML
# --------------------------------------------------------------------------

YAML = _spec(
    "yaml", "YAML", "rolling.yaml",
    "Keys as tags, block scalar, flow sequence; the other canonical config shape.",
    [
        [("comment", "# rolling service configuration")],
        [("tag", "service"), ("punctuation", ": "), ("string", "rolling")],
        [("tag", "version"), ("punctuation", ": "), ("number", "3")],
        [("tag", "decay"), ("punctuation", ": "), ("number", "0.92")],
        [("tag", "enabled"), ("punctuation", ": "), ("constant", "true")],
        [("tag", "samples"), ("punctuation", ": ["), ("number", "1"), ("punctuation", ", "), ("number", "2"), ("punctuation", ", "), ("number", "3"), ("punctuation", "]")],
        [("tag", "notes"), ("punctuation", ": "), ("operator", ">")],
        [("fg", "  Exponentially-smoothed mean of the samples.")],
    ],
)


# --------------------------------------------------------------------------
# Markdown
# --------------------------------------------------------------------------

MARKDOWN = _spec(
    "markdown", "Markdown", "rolling.md",
    "Headings as tags, inline code, bold/link structure, fenced block.",
    [
        [("tag", "# Rolling mean")],
        [],
        [("fg", "The "), ("keyword", "**"), ("fg", "exponential"), ("keyword", "**"), ("fg", " moving average smooths a "), ("function", "`signal`"), ("fg", " over time.")],
        [],
        [("tag", "## Usage")],
        [],
        [("punctuation", "- "), ("fg", "Set "), ("function", "`decay`"), ("fg", " between "), ("function", "`0`"), ("fg", " and "), ("function", "`1`"), ("fg", ".")],
        [("punctuation", "- "), ("fg", "See "), ("punctuation", "["), ("fg", "the docs"), ("punctuation", "]("), ("string", "https://example.com"), ("punctuation", ")"), ("fg", " for details.")],
        [],
        [("punctuation", "```python")],
        [("fg", "acc = "), ("parameter", "decay"), ("fg", " * acc + ("), ("number", "1"), ("fg", " - "), ("parameter", "decay"), ("fg", ") * x")],
        [("punctuation", "```")],
    ],
)


# --------------------------------------------------------------------------
# R
# --------------------------------------------------------------------------

R = _spec(
    "r", "R", "rolling.R",
    "Assignment operator, function/closure, builtins, roxygen doc.",
    [
        [("comment", "# rolling.R -- exponential moving average")],
        [("builtin", "library"), ("punctuation", "("), ("namespace", "dplyr"), ("punctuation", ")")],
        [],
        [("constant", "DEFAULT_DECAY"), ("operator", " <- "), ("number", "0.92")],
        [],
        [("function", "rolling_mean"), ("operator", " <- "), ("keyword", "function"), ("punctuation", "("), ("parameter", "values"), ("punctuation", ", "), ("parameter", "decay"), ("operator", " = "), ("constant", "DEFAULT_DECAY"), ("punctuation", ") {")],
        [("docstring", "  #' Exponentially-smoothed mean of `values`.")],
        [("fg", "  "), ("fg", "acc"), ("operator", " <- "), ("number", "0")],
        [("fg", "  "), ("keyword", "for "), ("punctuation", "("), ("parameter", "x"), ("fg", " "), ("keyword", "in"), ("fg", " "), ("parameter", "values"), ("punctuation", ") {")],
        [("fg", "    "), ("fg", "acc"), ("operator", " <- "), ("parameter", "decay"), ("fg", " * "), ("fg", "acc"), ("fg", " + ("), ("number", "1"), ("fg", " - "), ("parameter", "decay"), ("fg", ") * "), ("parameter", "x")],
        [("fg", "  "), ("punctuation", "}")],
        [("fg", "  "), ("keyword", "return"), ("punctuation", "("), ("fg", "acc"), ("punctuation", ")")],
        [("punctuation", "}")],
        [],
        [("fg", "result"), ("operator", " <- "), ("function", "rolling_mean"), ("punctuation", "("), ("builtin", "c"), ("punctuation", "("), ("number", "1"), ("punctuation", ", "), ("number", "2"), ("punctuation", ", "), ("number", "3"), ("punctuation", "))")],
        [("builtin", "print"), ("punctuation", "("), ("fg", "result"), ("punctuation", ")")],
    ],
)


SPECIMENS: dict[str, Specimen] = {
    s.language: s
    for s in (PYTHON, RUST, TYPESCRIPT, SHELL, JSON, YAML, MARKDOWN, R)
}

#: Languages required by the brief, in order.
REQUIRED_LANGUAGES = ("python", "rust", "typescript", "shell", "json", "yaml", "markdown", "r")


def all_roles_used() -> set[str]:
    out: set[str] = set()
    for s in SPECIMENS.values():
        out |= s.roles_used()
    return out


def specimen(language: str) -> Specimen:
    if language not in SPECIMENS:
        raise KeyError(f"no specimen for {language!r}; have {sorted(SPECIMENS)}")
    return SPECIMENS[language]
