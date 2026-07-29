from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    ROOT / "tests" / "fixtures" / "libman_smoke.asm",
    ROOT / "tests" / "fixtures" / "libman_win0_smoke.asm",
    ROOT / "tests" / "fixtures" / "libman_diag_vectors.asm",
)


class LibmanIncludeTests(unittest.TestCase):
    def test_runtime_uses_explicit_setwin_calls(self) -> None:
        source = (ROOT / "libman" / "libman_core13.asm").read_text(
            encoding="utf-8"
        )
        dispatcher = source.split("_L_CALL:", 1)[1].split(
            ";==================================================================\n;  Получить информацию",
            1,
        )[0]
        self.assertNotIn("ld      bc,0038h", dispatcher)
        self.assertIn("add\ta,38h", dispatcher)
        self.assertIn("ld\tc,a", dispatcher)
        self.assertGreaterEqual(dispatcher.count("add\ta,a"), 2)
        self.assertNotIn("\trla", dispatcher)
        self.assertIn("push\tix", dispatcher)
        self.assertIn("push\tiy", dispatcher)

    def test_dispatcher_passes_displaced_physical_page_in_c(self) -> None:
        source = (ROOT / "libman" / "libman_core13.asm").read_text(
            encoding="utf-8"
        )
        dispatcher = source.split("_L_CALL:", 1)[1].split(
            ";==================================================================\n;  Получить информацию",
            1,
        )[0]
        call_gate = dispatcher.split("ld      bc,lc_", 1)[1].split(
            "jp      (hl)", 1
        )[0]
        self.assertIn("push    bc", call_gate)
        self.assertIn("ld\tbc,(lc4_+1)", call_gate)

    def test_free_checks_table_occupancy_and_releases_last_page(self) -> None:
        source = (ROOT / "libman" / "libman_core13.asm").read_text(
            encoding="utf-8"
        )
        free = source.split("_L_FREE:", 1)[1].split(
            ";==================================================================\n;  Вызов процедур",
            1,
        )[0]
        scan = free.split("lf1:", 1)[1].split("lf2:", 1)[0]
        self.assertRegex(scan, r"ld\s+a,\(hl\)\s*\n\s*or\s+a")
        self.assertIn("ld      c,3Eh", free)

    def test_loader_rebuilds_relocation_pointer_after_dss_calls(self) -> None:
        source = (ROOT / "libman" / "libman_core13.asm").read_text(
            encoding="utf-8"
        )
        loader = source.split("_L_LOAD:", 1)[1].split(
            "ENDIF\t\t\t\t; !LIBMAN_RUNTIME_ONLY", 1
        )[0]
        relocation = loader.split("pop\tbc\t\t\t; новый адрес кода", 1)[1].split(
            "call\tnz,remake", 1
        )[0]
        self.assertIn("ld\thl,0C004h", relocation)
        self.assertIn("push\tde", relocation)
        self.assertIn("pop\tiy", relocation)
        self.assertIn("add     iy,de", relocation)

    def test_loader_accelerator_sections_are_guarded(self) -> None:
        source = (ROOT / "libman" / "libman_core13.asm").read_text(
            encoding="utf-8"
        )
        loader = source.split("_L_LOAD:", 1)[1].split(
            "ENDIF\t\t\t\t; !LIBMAN_RUNTIME_ONLY", 1
        )[0]
        sections = loader.split("\t; аксель\n")[1:]
        self.assertEqual(len(sections), 5)
        for section in sections:
            guarded = section.split("\tei\n", 1)[0]
            self.assertIn("\tdi\n", guarded)
            self.assertIn("\tld      d,d", guarded)
            self.assertGreaterEqual(guarded.count("\tld      b,b"), 2)
            self.assertRegex(
                guarded,
                r"ld\s+d,d[^\n]*\n(?:[A-Za-z0-9_]+:\s*\n)?\s*ld\s+a,(?:0|16)",
            )

        self.assertNotIn("ld      d,d\n\tld      a,c", loader)
        self.assertIn("ld\t(ll_copy_in_size+1),a", loader)
        self.assertIn("ld\t(ll_copy_out_size+1),a", loader)

    def test_loader_records_dss_errors_at_shared_exit_gates(self) -> None:
        source = (ROOT / "libman" / "libman_core13.asm").read_text(
            encoding="utf-8"
        )
        loader = source.split("_L_LOAD:", 1)[1].split(
            "ENDIF\t\t\t\t; !LIBMAN_RUNTIME_ONLY", 1
        )[0]
        lines = [
            line.strip()
            for line in loader.splitlines()
            if line.strip() and not line.lstrip().startswith(";")
        ]

        self.assertGreaterEqual(lines.count("rst     10h"), 15)
        self.assertTrue(
            any(line.startswith("jp      c,llerr_dss_before_path") for line in lines)
        )
        self.assertTrue(
            any(line.startswith("jp      c,llerr_dss_after_path") for line in lines)
        )
        self.assertTrue(
            any(line.startswith("jp\tc,llerr_dss_with_entry") for line in lines)
        )

        state = (ROOT / "libman" / "libman_state.inc").read_text(
            encoding="utf-8"
        )
        recorder = state.split("ll_record_dss_error:", 1)[1].split(
            "ll_record_loader_stage:", 1
        )[0]
        self.assertIn("ld      (l_dss_error),a", recorder)

    def test_loader_reloads_handle_before_first_seek(self) -> None:
        source = (ROOT / "libman" / "libman_core13.asm").read_text(
            encoding="utf-8"
        )
        after_open = source.split("ld      (llhand),a", 1)[1]
        first_seek = after_open.split("ld      bc,0215h", 1)[0]
        self.assertIn("ld\ta,(llhand)", first_seek)

    def test_loader_passes_open_file_handle_to_init(self) -> None:
        source = (ROOT / "libman" / "libman_core13.asm").read_text(
            encoding="utf-8"
        )
        init = source.split("lloldw:", 1)[1].split("call    corecall", 1)[0]
        self.assertIn("out     (0E2h),a", init)
        self.assertIn("ld\ta,(llhand)", init)

    def test_loader_stops_at_header_declared_prefix_not_physical_eof(self) -> None:
        source = (ROOT / "libman" / "libman_core13.asm").read_text(
            encoding="utf-8"
        )
        loader = source.split("_L_LOAD:", 1)[1].split(
            "ENDIF\t\t\t\t; !LIBMAN_RUNTIME_ONLY", 1
        )[0]
        source_loop = loader.split("loop:", 1)[1].split("ll4:", 1)[0]
        reloc_flag = loader.split("ll0r:", 1)[1].split("ll_reloc_ready:", 1)[0]
        self.assertIn("ld\t(llsize),de", loader)
        self.assertIn("jr\tnz,ll_reloc_ready", reloc_flag)
        self.assertIn("or\tc", reloc_flag)
        self.assertIn("sbc\thl,bc", source_loop)
        self.assertIn("ld\ta,c", source_loop)
        self.assertIn("ld\t(ll_copy_in_size+1),a", source_loop)
        self.assertIn("ld\t(ll_copy_out_size+1),a", source_loop)
        self.assertNotIn("sub     0C0h", source_loop)

    def test_loader_bounds_decoded_image_and_resets_rle_state(self) -> None:
        source = (ROOT / "libman" / "libman_core13.asm").read_text(
            encoding="utf-8"
        )
        loader = source.split("_L_LOAD:", 1)[1].split(
            "ENDIF\t\t\t\t; !LIBMAN_RUNTIME_ONLY", 1
        )[0]
        setup = loader.split("ld\ta,true", 1)[0]
        decoder = loader.split("ll2:", 1)[1].split("ll3:", 1)[0]
        completion = loader.split("jp\tnz,loop", 1)[1].split("ll4:", 1)[0]
        self.assertIn("ld\t(llzero+1),a", setup)
        self.assertIn("lloutend:", loader)
        self.assertIn("jp\tz,ll_decode_error", decoder)
        self.assertIn("jp\tnz,ll_decode_error", decoder)
        self.assertIn("ld\ta,(llzero+1)", completion)
        self.assertIn("jp\tnz,llerr_after_path", completion)

    def test_loader_accepts_physical_payload_over_64k(self) -> None:
        source = (ROOT / "libman" / "libman_core13.asm").read_text(
            encoding="utf-8"
        )
        eof = source.split("ld      bc,0215h", 1)[1].split(
            "ll_eof_size_ready:", 1
        )[0]
        self.assertIn("ld\tix,0FFFFh", eof)
        self.assertNotIn("jp      nz,llerr_after_path", eof)

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

    @unittest.skipUnless(
        shutil.which("sjasmplus") and shutil.which("z88dk-ticks"),
        "sjasmplus and z88dk-ticks are required",
    )
    def test_loader_diagnostic_vectors(self) -> None:
        assembler = shutil.which("sjasmplus")
        emulator = shutil.which("z88dk-ticks")
        assert assembler is not None
        assert emulator is not None

        fixture = ROOT / "tests" / "fixtures" / "libman_diag_vectors.asm"
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
            output = temp / "libman_diag_vectors.bin"
            symbols = temp / "libman_diag_vectors.sym"
            ram = temp / "libman_diag_vectors.ram"
            assembled = subprocess.run(
                [
                    assembler,
                    "--nologo",
                    f"--sym={symbols}",
                    f"--raw={output}",
                    str(source),
                ],
                cwd=temp,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                assembled.returncode, 0, assembled.stdout + assembled.stderr
            )

            match = re.search(
                r"^TEST_DONE:\s+EQU\s+0x([0-9A-Fa-f]+)",
                symbols.read_text(encoding="utf-8"),
                re.IGNORECASE | re.MULTILINE,
            )
            self.assertIsNotNone(match, "TEST_DONE is missing from symbol file")
            assert match is not None

            emulated = subprocess.run(
                [
                    emulator,
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
                cwd=temp,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                emulated.returncode, 0, emulated.stdout + emulated.stderr
            )
            result = ram.read_bytes()[0x7000]
            self.assertEqual(result, 0, f"diagnostic vector {result} failed")
