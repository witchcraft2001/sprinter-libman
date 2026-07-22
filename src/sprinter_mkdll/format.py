from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .errors import ToolError
from .model import HEADER_SIZE, Header, LibraryFormat, LibmanTarget, encode_name, validate_target

MAX_LOADED_SIZE = 0x4000


@dataclass(frozen=True)
class DecodedLibrary:
    header: Header
    image: bytes
    compressed: bool
    trailing_data: bytes = b""

    @property
    def bitmap(self) -> bytes:
        return self.image[self.header.code_size:self.header.code_size + self.header.reloc_size]

    @property
    def relocation_bits(self) -> int:
        return self.header.code_size if self.header.format is LibraryFormat.L0 else self.header.code_size - HEADER_SIZE

    @property
    def relocation_count(self) -> int:
        return sum(byte.bit_count() for byte in self.bitmap)


def _expected_bitmap_size(header: Header) -> int:
    bits = header.code_size if header.format is LibraryFormat.L0 else header.code_size - HEADER_SIZE
    return (bits + 7) // 8


def checksum(image: bytes) -> int:
    return sum(image[16:]) & 0xFFFF


def decode_library(raw: bytes, *, verify: bool = True) -> DecodedLibrary:
    if len(raw) < 16:
        raise ToolError("DLL is shorter than the uncompressed 16-byte header prefix")
    # Bytes 16..31 may themselves be RLE-compressed, so only the fixed prefix
    # is authoritative until the loaded image has been decoded.
    partial_header = Header.parse(raw[:16] + b"\0" * 16)
    if partial_header.file_size < 16:
        raise ToolError("header loaded-size field is smaller than 16 bytes")
    if partial_header.file_size > len(raw):
        raise ToolError(
            f"header loaded size is {partial_header.file_size}, but file contains only {len(raw)} bytes"
        )
    loaded_data = raw[:partial_header.file_size]
    trailing_data = raw[partial_header.file_size:]
    expected_size = partial_header.code_size + partial_header.reloc_size
    if partial_header.code_size < HEADER_SIZE:
        raise ToolError("header code size is smaller than the 32-byte DLL header")
    if expected_size < HEADER_SIZE:
        raise ToolError("header code/table sizes are smaller than the DLL header")
    compressed = partial_header.file_size != expected_size
    if compressed:
        image = loaded_data[:16] + decompress_zero_rle(loaded_data[16:], expected_size - 16)
    else:
        image = loaded_data
    if len(image) != expected_size:
        raise ToolError("decoded DLL length does not match header sizes")
    header = Header.parse(image[:HEADER_SIZE])
    if header.file_size != partial_header.file_size:
        raise ToolError("encoded header changed while decoding")
    decoded = DecodedLibrary(
        header=header,
        image=image,
        compressed=compressed,
        trailing_data=trailing_data,
    )
    if verify:
        validate_decoded(decoded)
    return decoded


def validate_decoded(library: DecodedLibrary, target: LibmanTarget | None = None) -> None:
    header = library.header
    if target is not None:
        validate_target(header.format, target)
    if len(library.image) > MAX_LOADED_SIZE:
        raise ToolError(
            f"uncompressed code and relocation table occupy {len(library.image)} bytes; "
            f"libman limit is {MAX_LOADED_SIZE}"
        )
    if header.file_size > MAX_LOADED_SIZE:
        raise ToolError(f"loaded file prefix is {header.file_size} bytes; libman limit is {MAX_LOADED_SIZE}")
    expected = _expected_bitmap_size(header)
    if header.reloc_size not in (0, expected):
        raise ToolError(
            f"{header.format.value.upper()} relocation table has {header.reloc_size} bytes; expected {expected} or 0"
        )
    if header.format is LibraryFormat.L0 and header.reloc_size and library.bitmap[:4] != b"\0\0\0\0":
        raise ToolError("L0 relocation bitmap must start with four zero bytes for the 32-byte header")
    if header.reloc_size and header.reloc_size >> 8 == header.reloc_size & 0xFF:
        raise ToolError(
            f"relocation table size 0x{header.reloc_size:04X} triggers a libman loader bug "
            "that disables relocation"
        )
    used_bits = library.relocation_bits
    if header.reloc_size and used_bits % 8:
        unused_mask = (1 << (8 - used_bits % 8)) - 1
        if library.bitmap[-1] & unused_mask:
            raise ToolError("unused low bits in the last relocation bitmap byte must be zero")
    calculated = checksum(library.image)
    if calculated != header.checksum:
        raise ToolError(f"checksum mismatch: header {header.checksum:04X}, calculated {calculated:04X}")


def decompress_zero_rle(payload: bytes, expected_length: int) -> bytes:
    out = bytearray()
    position = 0
    while position < len(payload):
        value = payload[position]
        position += 1
        if value:
            out.append(value)
            continue
        if position == len(payload):
            raise ToolError("truncated zero-RLE sequence")
        count = payload[position] or 256
        position += 1
        out.extend(b"\0" * count)
        if len(out) > expected_length:
            raise ToolError("zero-RLE sequence expands past the header-declared DLL size")
    if len(out) != expected_length:
        raise ToolError(f"zero-RLE expands to {len(out)} bytes; expected {expected_length}")
    return bytes(out)


def compress_zero_rle(image: bytes) -> bytes:
    if len(image) < HEADER_SIZE:
        raise ToolError("cannot compress a truncated DLL")
    out = bytearray(image[:16])
    position = 16
    while position < len(image):
        value = image[position]
        if value:
            out.append(value)
            position += 1
            continue
        run_end = position
        while run_end < len(image) and image[run_end] == 0 and run_end - position < 256:
            run_end += 1
        count = run_end - position
        out.extend((0, count & 0xFF))
        position = run_end
    return bytes(out)


def encode_library(image: bytes, *, compress: bool, trailing_data: bytes = b"") -> bytes:
    if len(image) < HEADER_SIZE:
        raise ToolError("cannot encode a truncated DLL")
    header = Header.parse(image[:HEADER_SIZE])
    if len(image) != header.code_size + header.reloc_size:
        raise ToolError("canonical DLL length does not match header code/table sizes")
    if len(image) > MAX_LOADED_SIZE:
        raise ToolError(
            f"uncompressed code and relocation table occupy {len(image)} bytes; "
            f"libman limit is {MAX_LOADED_SIZE}"
        )
    mutable = bytearray(image)
    # The file-size word is in the uncompressed prefix, so updating it cannot alter
    # the RLE layout.  Set a provisional value before compression for clarity.
    header.file_size = len(image)
    mutable[:HEADER_SIZE] = header.pack()
    if compress:
        encoded = compress_zero_rle(bytes(mutable))
        # Equality is not representable: libman uses size inequality as the
        # compression flag.  Keeping only smaller RLE also avoids overflowing
        # the 16 KiB input page on data with many isolated zeroes.
        if len(encoded) < len(image):
            header.file_size = len(encoded)
            mutable[:HEADER_SIZE] = header.pack()
            encoded = bytes(mutable[:16]) + encoded[16:]
            return encoded + trailing_data
    return bytes(mutable) + trailing_data


def _set_header_and_checksum(image: bytearray, header: Header) -> None:
    header.checksum = 0
    image[:HEADER_SIZE] = header.pack()
    header.checksum = checksum(image)
    image[:HEADER_SIZE] = header.pack()


def _set_relocation_bit(bitmap: bytearray, position: int) -> None:
    bitmap[position // 8] |= 0x80 >> (position % 8)


def _relocation_bitmap(first: bytes, second: bytes) -> bytes:
    if len(first) != len(second):
        raise ToolError(f"two assembler passes have different sizes: {len(first)} and {len(second)} bytes")
    bitmap = bytearray((len(first) + 7) // 8)
    for index, (low, high) in enumerate(zip(first, second)):
        if low == high:
            continue
        if high != (low + 1) & 0xFF:
            raise ToolError(
                f"assembler passes differ unexpectedly at offset 0x{index:04X}: "
                f"0x{low:02X} -> 0x{high:02X}; expected an address high byte increment"
            )
        _set_relocation_bit(bitmap, index)
    return bytes(bitmap)


def _align_256(value: int) -> int:
    return (value + 0xFF) & ~0xFF


def _pad_l1_around_loader_size_bug(first: bytes, second: bytes) -> tuple[bytes, bytes, bytes]:
    while True:
        bitmap = _relocation_bitmap(first, second)
        size = len(bitmap)
        if not size or size >> 8 != size & 0xFF:
            return first, second, bitmap
        remainder = len(first) % 8
        padding = 1 if remainder == 0 else 9 - remainder
        first += b"\0" * padding
        second += b"\0" * padding


def _pad_converted_image_around_loader_size_bug(
    code: bytes, bitmap: bytes, output_format: LibraryFormat
) -> tuple[bytes, bytes]:
    size = len(bitmap)
    if not size or size >> 8 != size & 0xFF:
        return code, bitmap
    relevant_bits = len(code) if output_format is LibraryFormat.L0 else len(code) - HEADER_SIZE
    padding = size * 8 + 1 - relevant_bits
    if not 1 <= padding <= 8:
        raise ToolError("internal error while padding a loader-sensitive relocation table")
    return code + b"\0" * padding, bitmap + b"\0"


def build_library_from_binaries(
    first_pass: bytes,
    second_pass: bytes,
    *,
    library_format: LibraryFormat,
    compress: bool,
    name: str | None = None,
    version: int | None = None,
    build_date: date | None = None,
    encoding: str = "ascii",
) -> bytes:
    """Build an L0/L1 DLL from images whose assembly origins differ by 0x100."""
    if library_format is LibraryFormat.L0:
        if len(first_pass) < HEADER_SIZE:
            raise ToolError("L0 source did not produce the mandatory 32-byte header")
        header = Header.parse(first_pass[:HEADER_SIZE])
        if header.format is not LibraryFormat.L0:
            raise ToolError("L0 source must begin with the literal header signature L0")
        if name is not None:
            header.name_bytes = encode_name(name, encoding)
        if version is not None:
            header.version = version
        if build_date is not None:
            header.day, header.month, header.year = build_date.day, build_date.month, build_date.year
        code_size = _align_256(len(first_pass))
        code = first_pass + b"\0" * (code_size - len(first_pass))
        relocated = second_pass + b"\0" * (code_size - len(second_pass))
        bitmap = _relocation_bitmap(code, relocated)
        if bitmap[:4] != b"\0\0\0\0":
            raise ToolError("L0 header changed between assembler passes; its relocation bits must be zero")
    else:
        if len(first_pass) + HEADER_SIZE > 0xFFFF:
            raise ToolError("L1 code is too large for the 16-bit DLL header")
        header = Header.create(
            LibraryFormat.L1,
            name=name if name is not None else "library",
            version=0x0100 if version is None else version,
            build_date=build_date,
            encoding=encoding,
        )
        first_pass, second_pass, bitmap = _pad_l1_around_loader_size_bug(first_pass, second_pass)
        code_size = HEADER_SIZE + len(first_pass)
        code = b"\0" * HEADER_SIZE + first_pass
    header.code_size = code_size
    header.reloc_size = len(bitmap)
    image = bytearray(code + bitmap)
    _set_header_and_checksum(image, header)
    encoded = encode_library(bytes(image), compress=compress)
    # Ensure fields set by encode_library are reflected in a fully validated object.
    decode_library(encoded)
    return encoded


def convert_library(raw: bytes, output_format: LibraryFormat, *, compress: bool | None = None) -> bytes:
    source = decode_library(raw)
    if source.header.format is output_format:
        return encode_library(
            source.image,
            compress=source.compressed if compress is None else compress,
            trailing_data=source.trailing_data,
        )
    header = source.header
    old_bitmap = source.bitmap
    if header.reloc_size == 0:
        new_bitmap = b""
    elif output_format is LibraryFormat.L1:
        if len(old_bitmap) < 4 or old_bitmap[:4] != b"\0\0\0\0":
            raise ToolError("cannot convert L0: its header relocation bits are not zero")
        new_bitmap = old_bitmap[4:]
    else:
        new_bitmap = b"\0\0\0\0" + old_bitmap
    code, new_bitmap = _pad_converted_image_around_loader_size_bug(
        source.image[:source.header.code_size], new_bitmap, output_format
    )
    header.format = output_format
    header.code_size = len(code)
    header.reloc_size = len(new_bitmap)
    image = bytearray(code + new_bitmap)
    _set_header_and_checksum(image, header)
    return encode_library(
        bytes(image),
        compress=source.compressed if compress is None else compress,
        trailing_data=source.trailing_data,
    )


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
