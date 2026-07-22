#!/usr/bin/env python3

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    candidates = (ROOT / "dist" / "sprinter-mkdll", ROOT / "dist" / "sprinter-mkdll.exe")
    executable = next((path for path in candidates if path.is_file()), None)
    if executable is None:
        raise SystemExit("standalone executable was not produced")
    subprocess.run([str(executable), "--version"], check=True)
    subprocess.run([str(executable), "verify", str(ROOT / "docs" / "libman" / "TEST.DLL"), "--target", "1.2"], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
