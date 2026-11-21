"""CLI for the pair-scoped redundant-channel audit (D-3).

    uv run python scripts/channel_audit.py out/soft-night/soft-s01.night.yaml
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from grotto.channels import report  # noqa: E402


def main(argv: list[str]) -> int:
    paths = argv[1:] or ["out/soft-night/soft-s01.night.yaml"]
    for p in paths:
        print(report(p))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
