from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    ROOT / "tests" / "fixtures" / "libman_smoke.asm",
    ROOT / "tests" / "fixtures" / "libman_win0_smoke.asm",
)


class LibmanIncludeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("sjasmplus"), "sjasmplus is not installed")
    def test_exported_libman_assembles_with_sjasmplus(self) -> None:
        assembler = shutil.which("sjasmplus")
        assert assembler is not None

        for fixture in SOURCES:
            with self.subTest(fixture=fixture.name):
                with tempfile.TemporaryDirectory() as temp_name:
                    temp = Path(temp_name)
                    shutil.copytree(ROOT / "libman", temp / "libman")
                    source = temp / fixture.name
                    source.write_text(
                        fixture.read_text(encoding="utf-8").replace(
                            "../../libman/", "libman/"
                        ),
                        encoding="utf-8",
                    )
                    output = temp / f"{fixture.stem}.bin"
                    result = subprocess.run(
                        [assembler, f"--raw={output}", str(source)],
                        cwd=temp,
                        capture_output=True,
                        text=True,
                        check=False,
                    )

                    self.assertEqual(
                        result.returncode, 0, result.stdout + result.stderr
                    )
                    self.assertGreater(output.stat().st_size, 0)
