from __future__ import annotations

from pathlib import Path
import unittest

from sprinter_mkdll.errors import ToolError
from sprinter_mkdll.format import (
    build_library_from_binaries,
    checksum,
    compress_zero_rle,
    convert_library,
    decode_library,
    decompress_zero_rle,
    encode_library,
)
from sprinter_mkdll.model import HEADER_SIZE, Header, LibraryFormat


ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DLLS = (ROOT / "docs/libman/TEST.DLL", ROOT / "docs/LIBSHAOS/ANTONFNT.DLL")


class FormatTests(unittest.TestCase):
    def test_historical_l0_round_trip_is_byte_exact(self) -> None:
        for path in GOLDEN_DLLS:
            with self.subTest(path=path):
                original = path.read_bytes()
                decoded = decode_library(original)
                self.assertIs(decoded.header.format, LibraryFormat.L0)
                self.assertTrue(decoded.compressed)
                self.assertEqual(encode_library(decoded.image, compress=True), original)

    def test_l0_l1_conversion_round_trip(self) -> None:
        for path in GOLDEN_DLLS:
            with self.subTest(path=path):
                original = path.read_bytes()
                l1 = convert_library(original, LibraryFormat.L1)
                decoded_l1 = decode_library(l1)
                self.assertIs(decoded_l1.header.format, LibraryFormat.L1)
                self.assertEqual(decoded_l1.header.reloc_size, decode_library(original).header.reloc_size - 4)
                self.assertEqual(convert_library(l1, LibraryFormat.L0), original)

    def test_appended_payload_is_accepted_and_preserved(self) -> None:
        original = (ROOT / "docs/libman/TEST.DLL").read_bytes()
        with_payload = original + b"EXTRA DATA"
        decoded = decode_library(with_payload)
        self.assertEqual(decoded.trailing_data, b"EXTRA DATA")
        converted = convert_library(with_payload, LibraryFormat.L1)
        self.assertTrue(converted.endswith(b"EXTRA DATA"))
        self.assertEqual(decode_library(converted).trailing_data, b"EXTRA DATA")

    def test_payload_can_extend_physical_file_past_64k(self) -> None:
        original = (ROOT / "docs/libman/TEST.DLL").read_bytes()
        payload = b"\xA5" * 0x10000
        with_payload = original + payload
        self.assertGreater(len(with_payload), 0xFFFF)
        self.assertEqual(decode_library(with_payload).trailing_data, payload)

    def test_zero_rle_supports_a_256_byte_run(self) -> None:
        payload = b"header-prefix-16" + b"\0" * 256 + b"\x01" + b"\0" * 2
        self.assertEqual(len(payload[:16]), 16)
        encoded = compress_zero_rle(payload)
        self.assertEqual(encoded[16:18], b"\0\0")
        self.assertEqual(decompress_zero_rle(encoded[16:], len(payload) - 16), payload[16:])

    def test_uncompressed_reencoding_updates_file_size(self) -> None:
        compressed = (ROOT / "docs/libman/TEST.DLL").read_bytes()
        canonical = decode_library(compressed).image
        uncompressed = encode_library(canonical, compress=False)
        decoded = decode_library(uncompressed)
        self.assertFalse(decoded.compressed)
        self.assertEqual(decoded.header.file_size, len(uncompressed))

    def test_compression_falls_back_when_rle_is_not_smaller(self) -> None:
        header = Header.create(LibraryFormat.L1, name="123456789012345")
        header.code_size = HEADER_SIZE + 4
        image = bytearray(header.pack() + b"\x01\0\0\0")
        header.checksum = checksum(image)
        image[:HEADER_SIZE] = header.pack()
        encoded = encode_library(bytes(image), compress=True)
        decoded = decode_library(encoded)
        self.assertFalse(decoded.compressed)
        self.assertEqual(len(encoded), len(image))

    def test_build_l1_marks_only_changed_high_bytes(self) -> None:
        first = bytes((0xC3, 0x34, 0x12, 0xC9))
        second = bytes((0xC3, 0x34, 0x13, 0xC9))
        raw = build_library_from_binaries(first, second, library_format=LibraryFormat.L1, name="test", version=0x0102, compress=False)
        library = decode_library(raw)
        self.assertEqual(library.header.code_size, HEADER_SIZE + len(first))
        self.assertEqual(library.bitmap, b"\x20")
        self.assertEqual(library.image[HEADER_SIZE:HEADER_SIZE + len(first)], first)
        self.assertEqual(library.relocation_count, 1)

    def test_build_l0_uses_256_byte_image_and_header_bitmap_padding(self) -> None:
        header = Header.create(LibraryFormat.L0, name="legacy")
        first = header.pack() + bytes((0xC3, 0x34, 0x12, 0xC9))
        second = header.pack() + bytes((0xC3, 0x34, 0x13, 0xC9))
        raw = build_library_from_binaries(first, second, library_format=LibraryFormat.L0, compress=False)
        library = decode_library(raw)
        self.assertEqual(library.header.code_size, 0x100)
        self.assertEqual(library.header.reloc_size, 0x20)
        self.assertEqual(library.bitmap[:4], b"\0" * 4)
        self.assertEqual(library.bitmap[4], 0x20)

    def test_build_rejects_difference_that_is_not_a_relocation(self) -> None:
        with self.assertRaisesRegex(ToolError, "differ unexpectedly"):
            build_library_from_binaries(b"\x00", b"\x02", library_format=LibraryFormat.L1, name="test", compress=False)

    def test_build_rejects_total_image_over_16k(self) -> None:
        body = b"\x01" * 14550
        with self.assertRaisesRegex(ToolError, "code and relocation table"):
            build_library_from_binaries(body, body, library_format=LibraryFormat.L1, name="large", compress=False)

    def test_l1_padding_avoids_relocation_size_loader_bug(self) -> None:
        first = bytearray(b"\x01" * 2049)
        second = bytearray(first)
        first[2], second[2] = 0x12, 0x13
        raw = build_library_from_binaries(
            bytes(first), bytes(second), library_format=LibraryFormat.L1, name="map258", compress=False
        )
        library = decode_library(raw)
        self.assertEqual(library.header.reloc_size, 0x0102)
        self.assertEqual(library.header.code_size - HEADER_SIZE, 2057)

    def test_l1_to_l0_conversion_avoids_relocation_size_loader_bug(self) -> None:
        body = b"\x01" * 2017
        l1 = build_library_from_binaries(
            body, body, library_format=LibraryFormat.L1, name="convert", compress=False
        )
        self.assertEqual(decode_library(l1).header.reloc_size, 0x00FD)
        l0 = decode_library(convert_library(l1, LibraryFormat.L0))
        self.assertEqual(l0.header.reloc_size, 0x0102)

    def test_verify_rejects_set_unused_bitmap_bits(self) -> None:
        raw = build_library_from_binaries(
            b"\x01", b"\x01", library_format=LibraryFormat.L1, name="unused", compress=False
        )
        damaged = bytearray(raw)
        damaged[-1] |= 0x01
        header = Header.parse(damaged)
        header.checksum = checksum(damaged)
        damaged[:HEADER_SIZE] = header.pack()
        with self.assertRaisesRegex(ToolError, "unused low bits"):
            decode_library(bytes(damaged))
