from __future__ import annotations

import io
import re
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from sprinter_mkdll.cli import main as mkdll_main
from sprinter_mkdll.format import decode_library
from sprinter_mkdll.model import LibraryFormat


ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    ROOT / "tests" / "fixtures" / "libman_smoke.asm",
    ROOT / "tests" / "fixtures" / "libman_win0_smoke.asm",
    ROOT / "tests" / "fixtures" / "libman_l2only_smoke.asm",
    ROOT / "tests" / "fixtures" / "libman_l0l1_smoke.asm",
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

    def test_l2_signature_dispatches_before_l0_l1_parsing(self) -> None:
        source = (ROOT / "libman" / "libman_core13.asm").read_text(
            encoding="utf-8"
        )
        loader = source.split("_L_LOAD:", 1)[1].split(
            "ENDIF\t\t\t\t; !LIBMAN_RUNTIME_ONLY", 1
        )[0]
        signature_check = loader.split('cp\t"L"', 1)[1].split("ll_l2_entry:", 1)[0]
        self.assertIn('cp\t"2"', signature_check)
        self.assertIn("jp\tz,ll_l2_entry", signature_check)
        # The "2" check must run before the "1"/"0" branch commits to the
        # L0/L1 header layout.
        self.assertLess(
            signature_check.index('cp\t"2"'), signature_check.index('cp\t"1"')
        )

    def test_l2_only_build_rejects_l0_and_l1_signatures(self) -> None:
        source = (ROOT / "libman" / "libman_core13.asm").read_text(
            encoding="utf-8"
        )
        loader = source.split("_L_LOAD:", 1)[1].split(
            "ENDIF\t\t\t\t; !LIBMAN_RUNTIME_ONLY", 1
        )[0]
        signature_check = loader.split('cp\t"L"', 1)[1].split("ll_l2_entry:", 1)[0]
        l2_only_branch = signature_check.split("IFDEF\tLIBMAN_L2_ONLY", 1)[1].split(
            "ELSE", 1
        )[0]
        self.assertIn("jp\tllerr_after_path", l2_only_branch)
        self.assertNotIn('cp\t"1"', l2_only_branch)
        self.assertNotIn('cp\t"0"', l2_only_branch)

    def test_l2_tail_is_unconditional_but_l0_l1_tail_is_guarded(self) -> None:
        source = (ROOT / "libman" / "libman_core13.asm").read_text(
            encoding="utf-8"
        )
        # ll_l2_finish must be reachable from both the full build and
        # LIBMAN_L2_ONLY, so its own label must not sit inside an IFNDEF
        # LIBMAN_L2_ONLY guard.
        before_finish = source.split("ll_l2_finish:", 1)[0]
        last_directive = None
        for token in ("IFNDEF\tLIBMAN_L2_ONLY", "IFDEF\tLIBMAN_L2_ONLY", "ENDIF"):
            pos = before_finish.rfind(token)
            if pos > (last_directive[1] if last_directive else -1):
                last_directive = (token, pos)
        self.assertIsNotNone(last_directive)
        self.assertEqual(last_directive[0], "ENDIF")

    def test_non_relocatable_l0_l1_branch_still_falls_through_to_ll4a(self) -> None:
        # libman 1.3 reaches ll4a by falling off the end of the "no relocation
        # table" branch.  Anything placed between that branch and ll4a is
        # executed by every non-relocatable L0/L1 load, so the L2 entry block
        # must not live there -- the emulator fixture cannot cover the L0/L1
        # path, because it moves bytes through the block accelerator.
        source = (ROOT / "libman" / "libman_core13.asm").read_text(
            encoding="utf-8"
        )
        sentinel = "\tld\thl,3FFFh\t\t; макс. размер не перемещ. библы"
        self.assertIn(sentinel, source)
        between = source.split(sentinel, 1)[1].split("ll4a:", 1)[0]
        instructions = [
            line.split(";", 1)[0].strip()
            for line in between.splitlines()
            if line.strip() and not line.lstrip().startswith(";")
        ]
        self.assertEqual(instructions, ["ENDIF", "ll_fr:\tld\ta,true"])

    def test_ll10_copy_loop_has_a_wraparound_guard(self) -> None:
        # ll10's exit test compares only the high byte of the destination
        # pointer, which wraps through 0 for a library ending exactly on the
        # page's last byte (or a non-relocatable one, given the 3FFFh
        # sentinel below).  Without a guard the loop never terminates and
        # overwrites RAM in 16-byte steps until it crashes.
        source = (ROOT / "libman" / "libman_core13.asm").read_text(
            encoding="utf-8"
        )
        loop = source.split("ll10:\t", 1)[1].split("ll10_end:", 1)[0]
        self.assertIn("ld      a,(ix+3)", loop)
        self.assertIn("jr      nc,ll10", loop)
        guard = loop.split("ld      a,(ix+3)", 1)[0]
        self.assertIn("ld\ta,d", guard)
        self.assertIn("or\ta", guard)
        self.assertIn("jr\tz,ll10_end", guard)

    def test_non_relocatable_sentinel_is_inclusive_page_end(self) -> None:
        # 4000h would wrap (ix+3) through 100h when a non-relocatable library
        # claims a fresh page outright, which combined with the ll10 guard
        # above would make the copy loop exit on its very first check instead
        # of running.  3FFFh is the loader's only correct choice once that
        # guard exists.
        source = (ROOT / "libman" / "libman_core13.asm").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("hl,4000h\t\t; макс. размер не перемещ. библы", source)
        self.assertIn("hl,3FFFh\t\t; макс. размер не перемещ. библы", source)

    def test_l2_page_limit_check_reports_through_carry(self) -> None:
        # The check is reached by CALL from sites that hold their own stack
        # entries, and llerr_after_path unwinds _L_LOAD's frame by count, so a
        # branch straight to the handler would leave the frame desynchronized.
        source = (ROOT / "libman" / "libman_core13.asm").read_text(
            encoding="utf-8"
        )
        body = source.split("ll2_check_page_limit:", 1)[1].split("ll_l2_entry:", 1)[0]
        self.assertNotIn("llerr", body)
        self.assertIn("sbc\thl,de", body)
        entry = source.split("ll_l2_entry:", 1)[1].split("ll4a:", 1)[0]
        calls = entry.count("call\tll2_check_page_limit")
        self.assertEqual(calls, 2)
        for tail in entry.split("call\tll2_check_page_limit")[1:]:
            following = [
                line.split(";", 1)[0].strip()
                for line in tail.splitlines()
                if line.strip() and not line.lstrip().startswith(";")
            ]
            # Only a flag-preserving POP may intervene before the verdict.
            self.assertTrue(
                following[0] == "jp\tc,llerr_after_path"
                or (
                    following[0].startswith("pop\t")
                    and following[1] == "jp\tc,llerr_after_path"
                ),
                following[:2],
            )

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

    @unittest.skipUnless(shutil.which("sjasmplus"), "sjasmplus is required")
    def test_l0_l1_only_build_omits_the_l2_reader(self) -> None:
        """The point of the option is that the L2 code is gone, not skipped."""
        assembler = shutil.which("sjasmplus")
        assert assembler is not None

        l2_symbols = ("ll_l2_entry", "ll_l2_finish", "ll2_chunk", "ll2_left")
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            shutil.copytree(ROOT / "libman", temp / "libman")
            source = temp / "smoke.asm"
            source.write_text(
                (ROOT / "tests" / "fixtures" / "libman_l0l1_smoke.asm")
                .read_text(encoding="utf-8")
                .replace("../../libman/", "libman/"),
                encoding="utf-8",
            )

            symbols: dict[str, str] = {}
            for build in ("full", "LIBMAN_L0_L1_ONLY"):
                symbol_file = temp / f"{build}.sym"
                command = [
                    assembler,
                    "--nologo",
                    f"--sym={symbol_file}",
                    f"--raw={temp / build}.bin",
                ]
                if build == "full":
                    # The same fixture without the define, so the comparison
                    # below cannot pass just because a name was misspelt.
                    text = source.read_text(encoding="utf-8")
                    text = text.replace("DEFINE  LIBMAN_L0_L1_ONLY", "")
                    text = text.replace("= 1861", "= 2191")
                    text = text.replace(
                        "LIBMAN.FORMAT_L0|LIBMAN.FORMAT_L1",
                        "LIBMAN.FORMAT_L0|LIBMAN.FORMAT_L1|LIBMAN.FORMAT_L2",
                    )
                    plain = temp / "plain.asm"
                    plain.write_text(text, encoding="utf-8")
                    command.append(str(plain))
                else:
                    command.append(str(source))
                result = subprocess.run(
                    command, cwd=temp, capture_output=True, text=True, check=False
                )
                self.assertEqual(
                    result.returncode, 0, result.stdout + result.stderr
                )
                symbols[build] = symbol_file.read_text(encoding="utf-8")

        for name in l2_symbols:
            with self.subTest(symbol=name):
                self.assertIn(name, symbols["full"])
                self.assertNotIn(name, symbols["LIBMAN_L0_L1_ONLY"])

    @unittest.skipUnless(
        shutil.which("sjasmplus") and shutil.which("z88dk-ticks"),
        "sjasmplus and z88dk-ticks are required",
    )
    def test_l2_loader_vectors(self) -> None:
        assembler = shutil.which("sjasmplus")
        emulator = shutil.which("z88dk-ticks")
        assert assembler is not None
        assert emulator is not None

        fixtures = ROOT / "tests" / "fixtures"
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            shutil.copytree(ROOT / "libman", temp / "libman")

            # The relocatable vector library is produced by the real tool, so
            # the bitmap the loader consumes is the one sprinter-mkdll emits.
            with redirect_stdout(io.StringIO()):
                built = mkdll_main(
                    [
                        "build",
                        str(fixtures / "l2_vector_lib.asm"),
                        "--format",
                        "l2",
                        "--target",
                        "1.4",
                        "--assembler",
                        "sjasmplus",
                        "--name",
                        "L2 VECTOR",
                        "-o",
                        str(temp / "l2_vector_lib.dll"),
                    ]
                )
            self.assertEqual(built, 0)
            library = decode_library((temp / "l2_vector_lib.dll").read_bytes())
            self.assertIs(library.header.format, LibraryFormat.L2)
            self.assertFalse(library.compressed)
            # The fixture is only meaningful while the body spans several
            # relocation chunks, with the last one partial.
            body = library.header.code_size - 32
            self.assertGreater(body, 2 * 128)
            self.assertNotEqual(body % 128, 0)
            self.assertGreater(library.relocation_count, 0)

            source = temp / "libman_l2_vectors.asm"
            source.write_text(
                (fixtures / "libman_l2_vectors.asm")
                .read_text(encoding="utf-8")
                .replace("../../libman/", "libman/"),
                encoding="utf-8",
            )

            # Both configurations run the same L2 path and must agree, which
            # also covers LIBMAN_L2_ONLY allocating a single scratch page.
            sizes: dict[str, int] = {}
            for build in ("full", "LIBMAN_L2_ONLY"):
                with self.subTest(build=build):
                    output = temp / f"libman_l2_vectors_{build}.bin"
                    symbols = temp / f"libman_l2_vectors_{build}.sym"
                    ram = temp / f"libman_l2_vectors_{build}.ram"
                    command = [
                        assembler,
                        "--nologo",
                        f"--sym={symbols}",
                        f"--raw={output}",
                    ]
                    if build != "full":
                        command.append(f"-D{build}")
                    command.append(str(source))
                    assembled = subprocess.run(
                        command,
                        cwd=temp,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(
                        assembled.returncode,
                        0,
                        assembled.stdout + assembled.stderr,
                    )

                    match = re.search(
                        r"^TEST_DONE:\s+EQU\s+0x([0-9A-Fa-f]+)",
                        symbols.read_text(encoding="utf-8"),
                        re.IGNORECASE | re.MULTILINE,
                    )
                    self.assertIsNotNone(
                        match, "TEST_DONE is missing from symbol file"
                    )
                    assert match is not None

                    emulated = subprocess.run(
                        [
                            emulator,
                            # Vector 2 claims a full page, so ll10 copies 16 KiB
                            # through a stub that shadows the page on every
                            # switch; the run is ~190M emulated cycles.
                            "-counter",
                            "900000000",
                            "-l",
                            "0",
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
                        # A loader bug can put the emulated Z80 somewhere the
                        # cycle budget never retires; fail the test instead of
                        # hanging the suite.
                        timeout=120,
                    )
                    self.assertEqual(
                        emulated.returncode, 0, emulated.stdout + emulated.stderr
                    )
                    result = ram.read_bytes()[0x7000]
                    self.assertEqual(
                        result, 0, f"L2 loader vector {result} failed"
                    )
                    sizes[build] = output.stat().st_size

            # Proves the -D actually reached the assembler, so the second run
            # exercised a different build and not the first one twice.
            self.assertLess(sizes["LIBMAN_L2_ONLY"], sizes["full"])
