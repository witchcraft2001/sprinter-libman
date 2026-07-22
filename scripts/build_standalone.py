#!/usr/bin/env python3
"""Build a native standalone archive for the host platform using PyInstaller."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BUILD = ROOT / "build" / "pyinstaller"


def main() -> int:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--name",
            "sprinter-mkdll",
            "--paths",
            str(ROOT / "src"),
            "--distpath",
            str(DIST),
            "--workpath",
            str(BUILD),
            "--specpath",
            str(BUILD),
            str(ROOT / "scripts" / "sprinter_mkdll_entry.py"),
        ],
        cwd=ROOT,
        check=True,
    )
    print(f"standalone executable: {DIST / 'sprinter-mkdll'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
