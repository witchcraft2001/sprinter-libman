from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from sprinter_mkdll.format import decode_library
from sprinter_mkdll.model import LibraryFormat


ROOT = Path(__file__).resolve().parents[1]


class LibmanTargetExampleTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("sjasmplus"), "sjasmplus is not installed")
    def test_l0_l1_target_example_builds(self) -> None:
        script = ROOT / "examples" / "libmantst" / "build.py"
        with tempfile.TemporaryDirectory() as temp_name:
            output = Path(temp_name)
            result = subprocess.run(
                [sys.executable, str(script), "--output", str(output)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            l0 = decode_library((output / "LMTL0.DLL").read_bytes())
            l1 = decode_library((output / "LMTL1.DLL").read_bytes())
            antonfnt_path = output / "ANTONFNT.DLL"
            sample_path = output / "TEST.DLL"
            antonfnt = decode_library(antonfnt_path.read_bytes())
            sample = decode_library(sample_path.read_bytes())
            self.assertIs(l0.header.format, LibraryFormat.L0)
            self.assertIs(l1.header.format, LibraryFormat.L1)
            self.assertIs(antonfnt.header.format, LibraryFormat.L0)
            self.assertIs(sample.header.format, LibraryFormat.L0)
            self.assertEqual(l0.header.display_name(), "LIBMAN TEST L0")
            self.assertEqual(l1.header.display_name(), "LIBMAN TEST L1")
            self.assertEqual(antonfnt.header.display_name(), "Anton Enin Font")
            self.assertEqual(sample.header.display_name(), "Sample Library")
            self.assertFalse(l0.compressed)
            self.assertFalse(l1.compressed)
            self.assertEqual(len((output / "LMTL0.DLL").read_bytes()), 0x120)
            self.assertEqual(len((output / "LMTL1.DLL").read_bytes()), 0x06B)
            self.assertTrue(antonfnt.compressed)
            self.assertTrue(sample.compressed)
            self.assertGreater(l0.relocation_count, 0)
            self.assertGreater(l1.relocation_count, 0)
            self.assertEqual(
                antonfnt_path.read_bytes(),
                (ROOT / "docs" / "LIBSHAOS" / "ANTONFNT.DLL").read_bytes(),
            )
            self.assertEqual(
                sample_path.read_bytes(),
                (ROOT / "docs" / "LIBSHAOS" / "TEST.DLL").read_bytes(),
            )
            self.assertEqual(
                sample_path.read_bytes(),
                (ROOT / "docs" / "libman" / "TEST.DLL").read_bytes(),
            )

            for artifact in output.iterdir():
                if artifact.is_file():
                    stem, suffix = artifact.name.rsplit(".", 1)
                    self.assertLessEqual(len(stem), 8, artifact.name)
                    self.assertLessEqual(len(suffix), 3, artifact.name)

            executable = (output / "LMTEST.EXE").read_bytes()
            self.assertEqual(executable[:4], b"EXE\x01")
            self.assertEqual(int.from_bytes(executable[4:8], "little"), 0x200)
