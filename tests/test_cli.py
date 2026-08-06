from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from sprinter_mkdll.cli import main
from sprinter_mkdll.format import decode_library
from sprinter_mkdll.model import LibraryFormat


class CliTests(unittest.TestCase):
    def test_build_through_custom_assembler_template(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            source = temp / "sample.asm"
            source.write_text("org 0\n", encoding="ascii")
            fake = temp / "fake_assembler.py"
            fake.write_text(
                "from pathlib import Path\n"
                "import sys\n"
                "source = Path(sys.argv[1]).read_text()\n"
                "assert '0x0020' in source or '0x0120' in source\n"
                "Path(sys.argv[2]).write_bytes(b'\\xc3\\x29' + (b'\\x01' if '0x0120' in source else b'\\x00'))\n",
                encoding="ascii",
            )
            output = temp / "sample.dll"
            command = f'"{sys.executable}" "{fake}" {{source}} {{output}}'
            with redirect_stdout(StringIO()):
                status = main(
                    [
                        "build",
                        str(source),
                        "-o",
                        str(output),
                        "--assembler-command",
                        command,
                        "--name",
                        "sample",
                        "--no-compress",
                    ]
                )
            self.assertEqual(status, 0)
            library = decode_library(output.read_bytes())
            self.assertIs(library.header.format, LibraryFormat.L1)
            self.assertEqual(library.relocation_count, 1)
            self.assertEqual(library.image[32:35], b"\xC3\x29\x00")

    def test_build_l2_defaults_to_uncompressed_without_a_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            source = temp / "sample.asm"
            source.write_text("org 0\n", encoding="ascii")
            fake = temp / "fake_assembler.py"
            fake.write_text(
                "from pathlib import Path\n"
                "import sys\n"
                "source = Path(sys.argv[1]).read_text()\n"
                "assert '0x0020' in source or '0x0120' in source\n"
                "Path(sys.argv[2]).write_bytes(b'\\xc3\\x29' + (b'\\x01' if '0x0120' in source else b'\\x00'))\n",
                encoding="ascii",
            )
            output = temp / "sample.dll"
            command = f'"{sys.executable}" "{fake}" {{source}} {{output}}'
            with redirect_stdout(StringIO()):
                status = main(
                    [
                        "build",
                        str(source),
                        "-o",
                        str(output),
                        "--format",
                        "l2",
                        "--target",
                        "1.4",
                        "--assembler-command",
                        command,
                        "--name",
                        "sample",
                    ]
                )
            self.assertEqual(status, 0)
            library = decode_library(output.read_bytes())
            self.assertIs(library.header.format, LibraryFormat.L2)
            self.assertFalse(library.compressed)
            self.assertEqual(library.relocation_count, 1)
            self.assertEqual(library.image[32:35], b"\xC3\x29\x00")

    def test_build_l2_rejects_an_explicit_compress_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            source = temp / "sample.asm"
            source.write_text("org 0\n", encoding="ascii")
            fake = temp / "fake_assembler.py"
            fake.write_text(
                "from pathlib import Path\n"
                "import sys\n"
                "Path(sys.argv[2]).write_bytes(b'\\x00')\n",
                encoding="ascii",
            )
            output = temp / "sample.dll"
            command = f'"{sys.executable}" "{fake}" {{source}} {{output}}'
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()) as err:
                status = main(
                    [
                        "build",
                        str(source),
                        "-o",
                        str(output),
                        "--format",
                        "l2",
                        "--target",
                        "1.4",
                        "--assembler-command",
                        command,
                        "--name",
                        "sample",
                        "--compress",
                    ]
                )
            self.assertEqual(status, 2)
            self.assertIn("does not support RLE compression", err.getvalue())

    def test_build_l2_requires_target_1_4(self) -> None:
        # validate_target runs before assembling, so an unresolvable assembler
        # command never needs to execute.
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            source = temp / "sample.asm"
            source.write_text("org 0\n", encoding="ascii")
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()) as err:
                status = main(["build", str(source), "--format", "l2"])
            self.assertEqual(status, 2)
            self.assertIn("requires --target 1.4", err.getvalue())

    @unittest.skipUnless(shutil.which("sjasmplus"), "sjasmplus is not installed")
    def test_sjasmplus_build_resolves_include_relative_to_source(self) -> None:
        source = Path(__file__).resolve().parent / "fixtures" / "include_main.asm"
        with tempfile.TemporaryDirectory() as temp_name:
            output = Path(temp_name) / "include.dll"
            with redirect_stdout(StringIO()):
                status = main(
                    [
                        "build",
                        str(source),
                        "-o",
                        str(output),
                        "--assembler",
                        "sjasmplus",
                        "--name",
                        "include",
                        "--no-compress",
                    ]
                )
            self.assertEqual(status, 0)
            library = decode_library(output.read_bytes())
            self.assertEqual(library.image[32:36], b"\xC3\x23\x00\xC9")
