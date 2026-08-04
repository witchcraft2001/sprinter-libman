from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.export_z80asm import SOURCE_DIR, SOURCE_NAMES, translate


def assemble_sjasm(source: Path, output: Path, symbols: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sjasmplus", "--nologo", f"--sym={symbols}", f"--raw={output}", str(source)],
        cwd=source.parent,
        capture_output=True,
        text=True,
        check=False,
    )


def assemble_z80asm(source: Path, output: Path, include_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["z80asm", "-b", "-m", f"-I{include_dir}", f"-o={output}", str(source)],
        cwd=source.parent,
        capture_output=True,
        text=True,
        check=False,
    )


class Z80AsmExportTests(unittest.TestCase):
    def test_checked_in_export_is_current(self) -> None:
        for name in SOURCE_NAMES:
            with self.subTest(name=name):
                expected = translate((SOURCE_DIR / name).read_text(encoding="utf-8"))
                actual = (SOURCE_DIR / "z80asm" / name).read_text(encoding="utf-8")
                self.assertEqual(actual, expected)

    @unittest.skipUnless(
        shutil.which("sjasmplus") and shutil.which("z80asm"),
        "sjasmplus and z80asm are required",
    )
    def test_exports_are_byte_identical_and_public_offsets_match(self) -> None:
        variants = (
            ("compact", ""),
            (
                "diagnostics_max3",
                "        define LIBMAN_MAX_LIBS 3\n        define LIBMAN_DIAGNOSTICS\n",
            ),
        )
        public_names = (
            "l_load",
            "l_free",
            "l_call",
            "l_info",
            "l_reason",
            "l_dss_error",
            "l_load_stage",
            "l_init_status",
        )

        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            for variant, sj_defines in variants:
                with self.subTest(variant=variant):
                    sj_source = temp / f"{variant}_sj.asm"
                    z80_source = temp / f"{variant}_z80.asm"
                    sj_bin = temp / f"{variant}_sj.bin"
                    z80_bin = temp / f"{variant}_z80.bin"
                    sj_sym = temp / f"{variant}_sj.sym"

                    shutil.copytree(SOURCE_DIR, temp / f"sj_{variant}")
                    shutil.copytree(SOURCE_DIR / "z80asm", temp / f"z80_{variant}")
                    sj_source.write_text(
                        "        device noslot64k\n"
                        + sj_defines
                        + "        org #8100\n"
                        + f'        include "sj_{variant}/libman.asm"\n',
                        encoding="utf-8",
                    )
                    z80_defines = sj_defines.replace("define ", "defc ").replace(" 3\n", " = 3\n").replace(
                        "LIBMAN_DIAGNOSTICS\n", "LIBMAN_DIAGNOSTICS = 1\n"
                    )
                    z80_source.write_text(
                        z80_defines
                        + "        org 8100h\n"
                        + f'        include "z80_{variant}/libman.asm"\n',
                        encoding="utf-8",
                    )

                    sj = assemble_sjasm(sj_source, sj_bin, sj_sym)
                    self.assertEqual(sj.returncode, 0, sj.stdout + sj.stderr)
                    z80 = assemble_z80asm(z80_source, z80_bin, temp / f"z80_{variant}")
                    self.assertEqual(z80.returncode, 0, z80.stdout + z80.stderr)
                    self.assertEqual(z80_bin.read_bytes(), sj_bin.read_bytes())

                    sj_symbols = sj_sym.read_text(encoding="utf-8")
                    z80_map = z80_source.with_suffix(".map").read_text(encoding="utf-8")
                    for name in public_names:
                        sj_match = re.search(
                            rf"^(?:LIBMAN\.)?{re.escape(name)}:\s+EQU\s+0x([0-9A-Fa-f]+)",
                            sj_symbols,
                            re.MULTILINE,
                        )
                        z80_match = re.search(rf"^{re.escape(name)}\s+=\s+\$([0-9A-Fa-f]+)", z80_map, re.MULTILINE)
                        self.assertIsNotNone(sj_match, name)
                        self.assertIsNotNone(z80_match, name)
                        self.assertEqual(int(sj_match.group(1), 16), int(z80_match.group(1), 16), name)

    @unittest.skipUnless(
        shutil.which("z80asm") and shutil.which("z88dk-ticks"),
        "z80asm and z88dk-ticks are required",
    )
    def test_z80asm_diagnostic_vectors(self) -> None:
        fixture = (ROOT / "tests/fixtures/libman_diag_vectors.asm").read_text(encoding="utf-8")
        lines: list[str] = ["        org 0", "        defs 10h,0"]
        for line in fixture.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("device ") or stripped.lower().startswith("end "):
                continue
            if stripped.lower().startswith("org "):
                continue
            match = re.match(r"^(\s*)define\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s+(.+))?$", line, re.IGNORECASE)
            if match:
                indent, name, value = match.groups()
                line = f"{indent}defc {name} = {value or '1'}"
            line = re.sub(r"#([0-9A-Fa-f]+)", r"0x\1", line)
            line = line.replace("LIBMAN.", "")
            line = line.replace('include "../../libman/libman.asm"', 'include "libman.asm"')
            lines.append(line)

        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            source = temp / "diag_z80asm.asm"
            output = temp / "diag_z80asm.bin"
            ram = temp / "diag_z80asm.ram"
            source.write_text("\n".join(lines) + "\n", encoding="utf-8")
            assembled = assemble_z80asm(source, output, SOURCE_DIR / "z80asm")
            self.assertEqual(assembled.returncode, 0, assembled.stdout + assembled.stderr)
            map_text = source.with_suffix(".map").read_text(encoding="utf-8")
            match = re.search(r"^test_done\s+=\s+\$([0-9A-Fa-f]+)", map_text, re.MULTILINE)
            self.assertIsNotNone(match)
            assert match is not None
            emulated = subprocess.run(
                [
                    "z88dk-ticks",
                    "-l",
                    "16",
                    "-pc",
                    "0100",
                    "-end",
                    match.group(1),
                    "-output",
                    str(ram),
                    str(output),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(emulated.returncode, 0, emulated.stdout + emulated.stderr)
            self.assertEqual(ram.read_bytes()[0x7000], 0)


if __name__ == "__main__":
    unittest.main()
