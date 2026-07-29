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
LMTL0_FILE_SIZE = 0x085
LMTL1_FILE_SIZE = 0x084
sys.path.insert(0, str(ROOT / "src"))

from sprinter_mkdll.cli import main as mkdll_main  # noqa: E402
from sprinter_mkdll.format import decode_library  # noqa: E402
from sprinter_mkdll.model import LibraryFormat  # noqa: E402


def build_dll(
    source: str,
    output: Path,
    library_format: LibraryFormat,
    *,
    compress: bool,
    name: str,
) -> None:
    arguments = [
        "build",
        str(EXAMPLE_DIR / source),
        "--format",
        library_format.value,
        "--target",
        "1.3",
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
    antonfnt_path = output / "ANTONFNT.DLL"
    sample_path = output / "TEST.DLL"
    exe_path = output / "LMTEST.EXE"

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
    for path in (l0_path, l1_path):
        path.write_bytes(path.read_bytes() + DLL_PAYLOAD)
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

    subprocess.run(
        [
            assembler,
            "--nologo",
            "--fullpath",
            f"--raw={exe_path}",
            str(EXAMPLE_DIR / "libmantst.asm"),
        ],
        cwd=EXAMPLE_DIR,
        check=True,
    )
    header = exe_path.read_bytes()[:EXE_HEADER_SIZE]
    if header[:4] != b"EXE\x01" or int.from_bytes(header[4:8], "little") != 0x200:
        raise SystemExit("LMTEST.EXE has an invalid DSS header")

    for artifact in (
        exe_path,
        l0_path,
        l1_path,
        antonfnt_path,
        sample_path,
    ):
        print(artifact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
