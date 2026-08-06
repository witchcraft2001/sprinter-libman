from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .assembler import PROFILES, assemble_two_passes
from .errors import ToolError
from .format import build_library_from_binaries, convert_library, decode_library, encode_library, write_bytes
from .model import LibmanTarget, LibraryFormat, parse_date, parse_version, validate_target


def _library_format(value: str) -> LibraryFormat:
    try:
        return LibraryFormat(value.lower())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("format must be l0, l1 or l2") from exc


def _target(value: str) -> LibmanTarget:
    try:
        return LibmanTarget(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("target must be 1.2, 1.3 or 1.4") from exc


def _version(value: str) -> int:
    try:
        return parse_version(value)
    except ToolError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _date(value: str):
    try:
        return parse_date(value)
    except ToolError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _compression_group(parser: argparse.ArgumentParser, *, default: bool | None) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--compress",
        dest="compress",
        action="store_true",
        help="enable historical zero-RLE compression (L0/L1 only; L2 never compresses)",
    )
    group.add_argument("--no-compress", dest="compress", action="store_false", help="write an uncompressed DLL")
    parser.set_defaults(compress=default)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sprinter-mkdll", description="Build and inspect Sprinter libman DLLs")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subcommands = parser.add_subparsers(dest="command", required=True)

    build = subcommands.add_parser("build", help="assemble source twice and build a DLL")
    build.add_argument("source", type=Path)
    build.add_argument("-o", "--output", type=Path)
    build.add_argument("--format", type=_library_format, default=LibraryFormat.L1)
    build.add_argument("--target", type=_target, default=LibmanTarget.V13)
    build.add_argument("--assembler", choices=sorted(PROFILES), default="zmac")
    build.add_argument("--assembler-command", help="custom command template containing {source}; {output} is optional")
    build.add_argument("--origin-template", help="e.g. '#{origin:04X}' or '0x{origin:04X}'")
    build.add_argument("-I", "--include-dir", action="append", default=[], type=Path, help="additional assembler include directory")
    build.add_argument("--name", help="L1 name, or override the L0 header name")
    build.add_argument("--version", type=_version, help="L1 version, or override the L0 header version")
    build.add_argument("--date", type=_date, help="L1 date, or override the L0 header date")
    build.add_argument("--encoding", choices=("ascii", "cp866"), default="ascii")
    _compression_group(build, default=None)

    inspect = subcommands.add_parser("inspect", help="print DLL metadata and layout")
    inspect.add_argument("file", type=Path)
    inspect.add_argument("--encoding", choices=("ascii", "cp866"), default="ascii")
    inspect.add_argument("--json", action="store_true")

    verify = subcommands.add_parser("verify", help="validate DLL structure and compatibility")
    verify.add_argument("file", type=Path)
    verify.add_argument("--target", type=_target)

    decompress = subcommands.add_parser("decompress", help="write canonical uncompressed DLL bytes")
    decompress.add_argument("input", type=Path)
    decompress.add_argument("-o", "--output", required=True, type=Path)

    convert = subcommands.add_parser("convert", help="convert between L0, L1 and L2")
    convert.add_argument("input", type=Path)
    convert.add_argument("-o", "--output", required=True, type=Path)
    convert.add_argument("--format", required=True, type=_library_format)
    convert.add_argument("--target", type=_target, default=LibmanTarget.V13)
    _compression_group(convert, default=None)
    return parser


def _inspect_data(raw: bytes, encoding: str) -> dict[str, object]:
    library = decode_library(raw)
    header = library.header
    return {
        "format": header.format.value.upper(),
        "file_size": header.file_size,
        "physical_size": len(raw),
        "trailing_size": len(library.trailing_data),
        "code_size": header.code_size,
        "reloc_size": header.reloc_size,
        "checksum": f"{header.checksum:04X}",
        "date": f"{header.year:04d}-{header.month:02d}-{header.day:02d}",
        "version": header.version_text,
        "name": header.display_name(encoding),
        "compressed": library.compressed,
        "relocation_count": library.relocation_count,
    }


def run(args: argparse.Namespace) -> int:
    if args.command == "build":
        validate_target(args.format, args.target)
        first, second = assemble_two_passes(
            args.source,
            assembler=args.assembler,
            assembler_command=args.assembler_command,
            origin_template=args.origin_template,
            base_origin=0 if args.format is LibraryFormat.L0 else 0x20,
            include_dirs=args.include_dir,
        )
        output = args.output or args.source.with_suffix(".dll")
        # --compress/--no-compress default to the historical L0/L1 behavior
        # (compressed) unless the user overrides it; L2 defaults to
        # uncompressed since it never supports RLE.
        compress = args.compress
        if compress is None:
            compress = args.format is not LibraryFormat.L2
        data = build_library_from_binaries(
            first,
            second,
            library_format=args.format,
            compress=compress,
            name=(
                args.name
                if args.name is not None
                else args.source.stem if args.format in (LibraryFormat.L1, LibraryFormat.L2) else None
            ),
            version=args.version,
            build_date=args.date,
            encoding=args.encoding,
        )
        write_bytes(output, data)
        info = _inspect_data(data, args.encoding)
        print(f"created {output}: {info['format']}, {info['file_size']} bytes, {info['relocation_count']} relocations")
        return 0
    if args.command == "inspect":
        data = _inspect_data(args.file.read_bytes(), args.encoding)
        if args.json:
            print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            for key, value in data.items():
                print(f"{key}: {value}")
        return 0
    if args.command == "verify":
        library = decode_library(args.file.read_bytes())
        if args.target is not None:
            validate_target(library.header.format, args.target)
        print(f"ok: {args.file} ({library.header.format.value.upper()}, {'compressed' if library.compressed else 'uncompressed'})")
        return 0
    if args.command == "decompress":
        library = decode_library(args.input.read_bytes())
        data = encode_library(library.image, compress=False, trailing_data=library.trailing_data)
        write_bytes(args.output, data)
        print(f"wrote {args.output}: {len(data)} uncompressed bytes")
        return 0
    if args.command == "convert":
        validate_target(args.format, args.target)
        data = convert_library(args.input.read_bytes(), args.format, compress=args.compress)
        write_bytes(args.output, data)
        print(f"wrote {args.output}: {_inspect_data(data, 'ascii')['format']}")
        return 0
    raise AssertionError(f"unhandled command {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        return run(parser.parse_args(argv))
    except ToolError as exc:
        print(f"sprinter-mkdll: error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"sprinter-mkdll: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
