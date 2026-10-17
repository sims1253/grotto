#!/usr/bin/env python3
"""Autoresearch loop driver.

The pi-autoresearch extension tools (`init_experiment`, `run_experiment`,
`log_experiment`) are not loaded in this harness, so this script reproduces
their contract exactly:

    ar.py measure                     -> runs .auto/measure.sh, prints the
                                         summary JSON, caches it
    ar.py checks                      -> runs .auto/checks.sh, exit 0/1
    ar.py log STATUS "desc" [--asi k=v ...]
                                       -> appends to .auto/log.jsonl;
                                          STATUS in
                                          keep | discard | crash | checks_failed
                                          keep commits, the rest revert the
                                          experiment's code changes
    ar.py status                      -> session summary + confidence score
    ar.py show ASI_KEY                -> every value ever logged for a key
    ar.py target                      -> the current target to beat

Reverting keeps `.auto/` (the log is the only durable record of a discarded
run) and removes everything else the experiment touched.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
AUTO = REPO / ".auto"
LOG = AUTO / "log.jsonl"
LAST = AUTO / "last.json"
KEEP_FILES = [".auto"]


def sh(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, **kw)


def read_log() -> list[dict]:
    if not LOG.exists():
        return []
    return [json.loads(l) for l in LOG.read_text().splitlines() if l.strip()]


def parse_asi(argv: list[str]) -> dict:
    pairs = [a for a in argv if a != "--asi"]
    out = {}
    for p in pairs:
        if "=" not in p:
            print(f"bad --asi {p!r}: expected key=value", file=sys.stderr)
            sys.exit(2)
        k, v = p.split("=", 1)
        out[k] = v
    return out


def metric_of(entry: dict, key: str = "utility") -> float | None:
    v = (entry.get("metrics") or {}).get(key)
    return float(v) if v is not None else None


def confidence(log: list[dict]) -> tuple[float, float, float]:
    """(confidence, best_improvement, noise_floor).

    The benchmark is byte-deterministic for a fixed seed, so ordinary
    measurement noise is zero.  The honest stand-in is `seed_spread`: the
    spread of the per-seed utilities the benchmark averages over.  A gain
    smaller than the spread is seed luck, not a better search.
    """
    scored = [e for e in log if metric_of(e) is not None and e["status"] != "crash"]
    if not scored:
        return 0.0, 0.0, 0.0
    base = metric_of(scored[0])
    best = max(metric_of(e) for e in scored)
    spreads = [float((e.get("metrics") or {}).get("seed_spread") or 0.0) for e in scored]
    noise = (sum(spreads) / len(spreads)) if spreads else 0.0
    imp = best - base
    conf = (imp / noise) if noise > 1e-9 else (999.0 if imp > 0 else 0.0)
    return conf, imp, noise


def revert() -> None:
    sh(["git", "checkout", "--", "."])
    sh(["git", "clean", "-fd", "-e", ".auto/", "-e", ".venv/"])


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""

    if cmd == "measure":
        t0 = time.monotonic()
        r = sh(["bash", str(AUTO / "measure.sh")])
        dt = time.monotonic() - t0
        metrics: dict[str, float] = {}
        for line in r.stdout.splitlines():
            if line.startswith("METRIC "):
                k, _, v = line[7:].partition("=")
                metrics[k] = float(v)
        if r.returncode != 0 or "utility" not in metrics:
            print("MEASURE FAILED")
            print(r.stdout[-4000:])
            print(r.stderr[-4000:])
            sys.exit(1)
        metrics["_wall"] = dt
        LAST.write_text(json.dumps(metrics, indent=2) + "\n")
        print(json.dumps(metrics, indent=2))
        return

    if cmd == "checks":
        r = sh(["bash", str(AUTO / "checks.sh")])
        print(r.stdout[-4000:])
        if r.returncode != 0:
            print(r.stderr[-2000:])
            print("CHECKS FAILED")
        sys.exit(r.returncode)

    if cmd == "log":
        status = sys.argv[2]
        desc = sys.argv[3]
        asi = parse_asi(sys.argv[4:])
        if not LAST.exists():
            print("no .auto/last.json -- run `ar.py measure` first", file=sys.stderr)
            sys.exit(2)
        metrics = json.loads(LAST.read_text())
        entry = {
            "n": len(read_log()) + 1,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "status": status,
            "description": desc,
            "asi": asi,
            "metrics": metrics,
        }
        with LOG.open("a") as f:
            f.write(json.dumps(entry) + "\n")
        if status == "keep":
            sh(["git", "add", "-A", "--", ".auto", "scripts", "src", "spec", "docs", "tests"])
            msg = f"autoresearch: {desc} (utility {metrics['utility']:.4f})"
            sh(["git", "commit", "-m", msg, "--allow-empty"])
            print(f"kept  {metrics['utility']:.4f}  {desc}")
        else:
            revert()
            print(f"{status}  {metrics['utility']:.4f}  {desc}")
        c, imp, noise = confidence(read_log())
        print(f"session best gain {imp:+.4f} (noise floor {noise:.5f}) "
              f"confidence {c:.1f}x")
        return

    if cmd == "status":
        log = read_log()
        if not log:
            print("no runs yet")
            return
        c, imp, noise = confidence(log)
        best = max((e for e in log if metric_of(e) is not None),
                   key=lambda e: metric_of(e), default=None)
        print(f"runs {len(log)}  kept {sum(1 for e in log if e['status']=='keep')}"
              f"  discarded {sum(1 for e in log if e['status']!='keep')}")
        if best:
            print(f"best utility {metric_of(best):.4f} (run {best['n']}) {best['description']}")
        print(f"gain {imp:+.4f}  noise floor {noise:.5f}  confidence {c:.1f}x")
        print("\nrecent:")
        for e in log[-12:]:
            m = metric_of(e)
            ms = f"{m:.4f}" if m is not None else "  -  "
            print(f"  {e['n']:>3} {e['status']:<14} {ms}  {e['description'][:70]}")
        return

    if cmd == "show":
        key = sys.argv[2]
        for e in read_log():
            if key in (e.get("asi") or {}):
                m = metric_of(e)
                ms = f"{m:.4f}" if m is not None else "  -  "
                print(f"{e['n']:>3} {e['status']:<14} {ms}  {e[key]}  | {e['description']}")
        return

    print(__doc__)
    sys.exit(2)


if __name__ == "__main__":
    main()