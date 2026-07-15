#!/usr/bin/env python3
"""Write reproducible Git build metadata for the packaged executable."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def git_output(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--commit", default="")
    args = parser.parse_args()

    if args.commit.strip():
        commit = args.commit.strip()
    else:
        try:
            commit = git_output("rev-parse", "--short=8", "HEAD")
            if git_output("status", "--porcelain"):
                commit += ".dirty"
        except (OSError, subprocess.SubprocessError):
            commit = "unknown"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(commit, encoding="ascii")
    print(commit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
