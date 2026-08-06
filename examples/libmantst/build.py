from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys


EXAMPLE_DIR = Path(__file__).resolve().parent
ROOT = EXAMPLE_DIR.parents[1]
DOCS_DIR = ROOT / "docs"
EXE_HEADER_SIZE = 0x200
DLL_PAYLOAD = b"\xA5"
LMTL0_FILE_SIZE = 0x0A5
LMTL1_FILE_SIZE = 0x0A4
LMTL2_FILE_SIZE = 0x0A4
# A full page of code plus the largest bitmap it can need, plus the payload.
LMTL2BIG_FILE_SIZE = 0x4000 + 0x7FC + len(DLL_PAYLOAD)
sys.path.insert(0, str(ROOT / "src"))

from sprinter_mkdll.cli import main as mkdll_main  # noqa: E402
from sprinter_mkdll.errors import ToolError  # noqa: E402
from sprinter_mkdll.format import decode_library  # noqa: E402
from sprinter_mkdll.model import LibraryFormat  # noqa: E402


def build_dll(
    source: str,
    output: Path,
    library_format: LibraryFormat,
    *,
    compress: bool,
    name: str,
    target: str = "1.3",
) -> None:
    arguments = [
        "build",
        str(EXAMPLE_DIR / source),
        "--format",
        library_format.value,
        "--target",
        target,
        "--assembler",
        "sjasmplus",
        "--name",
        name,
        "--version",
        "1.0",
        "--date",
        "2026-07-28",
        "--compress" if compress else "--no-compress",
        "-o",
        str(output),
    ]
    if mkdll_main(arguments):
        raise SystemExit(f"failed to build {output.name}")


def validate_dll(
    path: Path,
    expected_format: LibraryFormat,
    expected_name: str,
    expected_size: int | None = None,
    expected_payload: bytes | None = None,
) -> None:
    contents = path.read_bytes()
    if expected_size is not None and len(contents) != expected_size:
        raise SystemExit(
            f"{path.name}: expected {expected_size} bytes, got {len(contents)}"
        )
    library = decode_library(contents)
    if library.header.format is not expected_format:
        raise SystemExit(f"{path.name}: expected {expected_format.value.upper()}")
    if library.header.display_name() != expected_name:
        raise SystemExit(f"{path.name}: unexpected library name")
    if not library.relocation_count:
        raise SystemExit(f"{path.name}: test DLL has no relocation entries")
    if expected_payload is not None and library.trailing_data != expected_payload:
        raise SystemExit(f"{path.name}: unexpected trailing payload")


def write_corrupted_l2(source: Path, output: Path) -> None:
    """Write an L2 whose file_size claims RLE compression, which L2 never uses.

    The tool cannot produce this, so the bad header is written by hand: it is
    the input the loader's file_size == code_size + reloc_size check exists to
    turn away.
    """
    data = bytearray(source.read_bytes())
    library = decode_library(bytes(data))
    corrupted = library.header.code_size + library.header.reloc_size - 1
    data[2:4] = corrupted.to_bytes(2, "little")
    output.write_bytes(bytes(data))
    try:
        decode_library(bytes(data))
    except ToolError:
        return
    raise SystemExit(f"{output.name}: the tool still accepts the corrupted header")


def copy_documented_dll(
    source: Path, output: Path, expected_name: str
) -> None:
    validate_dll(source, LibraryFormat.L0, expected_name)
    shutil.copyfile(source, output)
    validate_dll(output, LibraryFormat.L0, expected_name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the libman L0/L1 target test")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=EXAMPLE_DIR / "build",
        help="artifact directory (default: examples/libmantst/build)",
    )
    args = parser.parse_args(argv)

    assembler = shutil.which("sjasmplus")
    if assembler is None:
        parser.error("sjasmplus is required")

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    for legacy_name in ("TSTL0.DLL", "TSTL1.DLL"):
        (output / legacy_name).unlink(missing_ok=True)
    l0_path = output / "LMTL0.DLL"
    l1_path = output / "LMTL1.DLL"
    l2_path = output / "LMTL2.DLL"
    l2big_path = output / "LMTL2BIG.DLL"
    l2bad_path = output / "LMTBAD.DLL"
    antonfnt_path = output / "ANTONFNT.DLL"
    sample_path = output / "TEST.DLL"
    exe_path = output / "LMTEST.EXE"
    l2only_exe_path = output / "LMTEST2.EXE"
    l0l1_exe_path = output / "LMTEST3.EXE"

    build_dll(
        "testdll_l0.asm",
        l0_path,
        LibraryFormat.L0,
        compress=True,
        name="LIBMAN TEST L0",
    )
    build_dll(
        "testdll_l1.asm",
        l1_path,
        LibraryFormat.L1,
        compress=False,
        name="LIBMAN TEST L1",
    )
    build_dll(
        "testdll_l2.asm",
        l2_path,
        LibraryFormat.L2,
        compress=False,
        name="LIBMAN TEST L2",
        target="1.4",
    )
    build_dll(
        "testdll_l2big.asm",
        l2big_path,
        LibraryFormat.L2,
        compress=False,
        name="LIBMAN TEST BIG",
        target="1.4",
    )
    for path in (l0_path, l1_path, l2_path, l2big_path):
        path.write_bytes(path.read_bytes() + DLL_PAYLOAD)
    write_corrupted_l2(l2_path, l2bad_path)
    validate_dll(
        l0_path,
        LibraryFormat.L0,
        "LIBMAN TEST L0",
        LMTL0_FILE_SIZE,
        DLL_PAYLOAD,
    )
    validate_dll(
        l1_path,
        LibraryFormat.L1,
        "LIBMAN TEST L1",
        LMTL1_FILE_SIZE,
        DLL_PAYLOAD,
    )
    validate_dll(
        l2_path,
        LibraryFormat.L2,
        "LIBMAN TEST L2",
        LMTL2_FILE_SIZE,
        DLL_PAYLOAD,
    )
    validate_dll(
        l2big_path,
        LibraryFormat.L2,
        "LIBMAN TEST BIG",
        LMTL2BIG_FILE_SIZE,
        DLL_PAYLOAD,
    )
    big = decode_library(l2big_path.read_bytes())
    if big.header.code_size != 0x4000:
        raise SystemExit(
            f"{l2big_path.name}: code must fill the page exactly, got "
            f"{big.header.code_size} bytes"
        )
    copy_documented_dll(
        DOCS_DIR / "LIBSHAOS" / "ANTONFNT.DLL",
        antonfnt_path,
        "Anton Enin Font",
    )
    copy_documented_dll(
        DOCS_DIR / "LIBSHAOS" / "TEST.DLL",
        sample_path,
        "Sample Library",
    )

    for executable, source in (
        (exe_path, "libmantst.asm"),
        (l2only_exe_path, "libmantst_l2only.asm"),
        (l0l1_exe_path, "libmantst_l0l1.asm"),
    ):
        subprocess.run(
            [
                assembler,
                "--nologo",
                "--fullpath",
                f"--raw={executable}",
                str(EXAMPLE_DIR / source),
            ],
            cwd=EXAMPLE_DIR,
            check=True,
        )
        header = executable.read_bytes()[:EXE_HEADER_SIZE]
        if header[:4] != b"EXE\x01" or int.from_bytes(header[4:8], "little") != 0x200:
            raise SystemExit(f"{executable.name} has an invalid DSS header")

    for artifact in (
        exe_path,
        l2only_exe_path,
        l0l1_exe_path,
        l0_path,
        l1_path,
        l2_path,
        l2big_path,
        l2bad_path,
        antonfnt_path,
        sample_path,
    ):
        print(artifact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
