from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
import struct

from .errors import ToolError

HEADER_SIZE = 32


class LibraryFormat(str, Enum):
    L0 = "l0"
    L1 = "l1"
    L2 = "l2"

    @property
    def signature(self) -> bytes:
        return self.value.upper().encode("ascii")

    @classmethod
    def from_signature(cls, value: bytes) -> "LibraryFormat":
        try:
            return cls(value.decode("ascii").lower())
        except (UnicodeDecodeError, ValueError) as exc:
            raise ToolError(f"unsupported library signature {value!r}; expected L0, L1 or L2") from exc


class LibmanTarget(str, Enum):
    V12 = "1.2"
    V13 = "1.3"
    V14 = "1.4"


@dataclass
class Header:
    format: LibraryFormat
    file_size: int
    code_size: int
    reloc_size: int
    checksum: int
    day: int
    month: int
    year: int
    version: int
    name_bytes: bytes

    @classmethod
    def parse(cls, raw: bytes) -> "Header":
        if len(raw) < HEADER_SIZE:
            raise ToolError("DLL is shorter than its 32-byte header")
        return cls(
            format=LibraryFormat.from_signature(raw[:2]),
            file_size=struct.unpack_from("<H", raw, 2)[0],
            code_size=struct.unpack_from("<H", raw, 4)[0],
            reloc_size=struct.unpack_from("<H", raw, 6)[0],
            checksum=struct.unpack_from("<H", raw, 8)[0],
            day=raw[10],
            month=raw[11],
            year=struct.unpack_from("<H", raw, 12)[0],
            version=struct.unpack_from("<H", raw, 14)[0],
            name_bytes=bytes(raw[16:32]),
        )

    @classmethod
    def create(
        cls,
        library_format: LibraryFormat,
        *,
        name: str,
        version: int = 0x0100,
        build_date: date | None = None,
        encoding: str = "ascii",
    ) -> "Header":
        when = build_date or date.today()
        return cls(
            format=library_format,
            file_size=0,
            code_size=0,
            reloc_size=0,
            checksum=0,
            day=when.day,
            month=when.month,
            year=when.year,
            version=version,
            name_bytes=encode_name(name, encoding),
        )

    @property
    def name(self) -> bytes:
        return self.name_bytes.split(b"\0", 1)[0]

    @property
    def version_text(self) -> str:
        return f"{self.version >> 8}.{self.version & 0xFF}"

    def display_name(self, encoding: str = "ascii") -> str:
        return self.name.decode(encoding, errors="replace")

    def pack(self) -> bytes:
        if not all(0 <= field <= 0xFFFF for field in (self.file_size, self.code_size, self.reloc_size, self.checksum, self.year, self.version)):
            raise ToolError("a DLL header word is outside the 0..65535 range")
        if not 0 <= self.day <= 31 or not 0 <= self.month <= 12:
            raise ToolError("invalid library date in header")
        if len(self.name_bytes) != 16:
            raise ToolError("library name field must be exactly 16 bytes")
        return b"".join(
            (
                self.format.signature,
                struct.pack("<HHHH", self.file_size, self.code_size, self.reloc_size, self.checksum),
                bytes((self.day, self.month)),
                struct.pack("<HH", self.year, self.version),
                self.name_bytes,
            )
        )


def encode_name(value: str, encoding: str) -> bytes:
    try:
        encoded = value.encode(encoding)
    except UnicodeEncodeError as exc:
        raise ToolError(f"library name cannot be encoded as {encoding}: {value!r}") from exc
    if b"\0" in encoded:
        raise ToolError("library name must not contain NUL")
    if len(encoded) > 15:
        raise ToolError("library name is limited to 15 encoded bytes")
    return encoded + b"\0" * (16 - len(encoded))


def parse_version(value: str) -> int:
    try:
        major_text, minor_text = value.split(".", 1)
        major, minor = int(major_text, 10), int(minor_text, 10)
    except ValueError as exc:
        raise ToolError("version must have the form MAJOR.MINOR") from exc
    if not 0 <= major <= 0xFF or not 0 <= minor <= 0xFF:
        raise ToolError("version components must be in 0..255")
    return (major << 8) | minor


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ToolError("date must have the form YYYY-MM-DD") from exc


def validate_target(library_format: LibraryFormat, target: LibmanTarget) -> None:
    if library_format is LibraryFormat.L2 and target is not LibmanTarget.V14:
        raise ToolError("L2 requires --target 1.4")
    if target is LibmanTarget.V12 and library_format is LibraryFormat.L1:
        raise ToolError("libman 1.2 supports L0 only; select --format l0 or --target 1.3/1.4")
