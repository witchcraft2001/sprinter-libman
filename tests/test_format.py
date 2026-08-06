from __future__ import annotations

from pathlib import Path
import unittest

from sprinter_mkdll.errors import ToolError
from sprinter_mkdll.format import (
    MAX_L2_CODE_SIZE,
    build_library_from_binaries,
    checksum,
    compress_zero_rle,
    convert_library,
    decode_library,
    decompress_zero_rle,
    encode_library,
)
from sprinter_mkdll.model import HEADER_SIZE, Header, LibmanTarget, LibraryFormat, validate_target


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

    def test_validate_target_requires_1_4_for_l2(self) -> None:
        with self.assertRaisesRegex(ToolError, "requires --target 1.4"):
            validate_target(LibraryFormat.L2, LibmanTarget.V13)
        validate_target(LibraryFormat.L2, LibmanTarget.V14)

    def test_build_l2_marks_only_changed_high_bytes(self) -> None:
        first = bytes((0xC3, 0x34, 0x12, 0xC9))
        second = bytes((0xC3, 0x34, 0x13, 0xC9))
        raw = build_library_from_binaries(
            first, second, library_format=LibraryFormat.L2, name="test", version=0x0102, compress=False
        )
        library = decode_library(raw)
        self.assertIs(library.header.format, LibraryFormat.L2)
        self.assertFalse(library.compressed)
        self.assertEqual(library.header.code_size, HEADER_SIZE + len(first))
        self.assertEqual(library.header.file_size, library.header.code_size + library.header.reloc_size)
        self.assertEqual(library.bitmap, b"\x20")
        self.assertEqual(library.image[HEADER_SIZE:HEADER_SIZE + len(first)], first)
        self.assertEqual(library.relocation_count, 1)

    def test_l2_rejects_compression(self) -> None:
        with self.assertRaisesRegex(ToolError, "does not support RLE compression"):
            build_library_from_binaries(b"\x00", b"\x00", library_format=LibraryFormat.L2, name="test", compress=True)

    def test_l2_decode_rejects_a_file_size_that_implies_compression(self) -> None:
        header = Header.create(LibraryFormat.L2, name="x")
        header.code_size = HEADER_SIZE + 4
        header.reloc_size = 0
        image = bytearray(header.pack() + b"\x01\0\0\0")
        header.checksum = checksum(image)
        header.file_size = len(image) - 1
        image[:HEADER_SIZE] = header.pack()
        with self.assertRaisesRegex(ToolError, "L2 does not support RLE compression"):
            decode_library(bytes(image))

    def test_build_l2_accepts_a_full_page_of_code(self) -> None:
        body = b"\x01" * (MAX_L2_CODE_SIZE - HEADER_SIZE)
        raw = build_library_from_binaries(body, body, library_format=LibraryFormat.L2, name="full", compress=False)
        library = decode_library(raw)
        self.assertEqual(library.header.code_size, MAX_L2_CODE_SIZE)
        self.assertEqual(library.header.reloc_size, 0x7FC)
        self.assertEqual(len(library.image), MAX_L2_CODE_SIZE + 0x7FC)
        self.assertEqual(library.relocation_count, 0)

    def test_build_rejects_l2_code_over_a_full_page(self) -> None:
        body = b"\x01" * (MAX_L2_CODE_SIZE - HEADER_SIZE + 1)
        with self.assertRaisesRegex(ToolError, "L2 code"):
            build_library_from_binaries(body, body, library_format=LibraryFormat.L2, name="over", compress=False)

    def test_l2_allows_relocation_size_that_would_trigger_the_l1_loader_bug(self) -> None:
        # 2056 code bytes -> a 257-byte (0x0101) bitmap, whose high and low
        # bytes are equal: this disables relocation in the historical L0/L1
        # loader path, so mkdll pads L1 around it. L2 uses a different
        # loading path that is not affected, so no padding is introduced.
        body = b"\x01" * 2056
        raw = build_library_from_binaries(body, body, library_format=LibraryFormat.L2, name="bug", compress=False)
        library = decode_library(raw)
        self.assertEqual(library.header.reloc_size, 0x0101)
        self.assertEqual(library.header.code_size, HEADER_SIZE + 2056)

    def test_l1_l2_conversion_round_trip_is_byte_exact(self) -> None:
        first = bytes((0xC3, 0x34, 0x12, 0xC9))
        second = bytes((0xC3, 0x34, 0x13, 0xC9))
        l1 = build_library_from_binaries(first, second, library_format=LibraryFormat.L1, name="conv", compress=False)
        l2 = convert_library(l1, LibraryFormat.L2)
        decoded_l1 = decode_library(l1)
        decoded_l2 = decode_library(l2)
        self.assertIs(decoded_l2.header.format, LibraryFormat.L2)
        self.assertFalse(decoded_l2.compressed)
        self.assertEqual(decoded_l2.header.code_size, decoded_l1.header.code_size)
        self.assertEqual(decoded_l2.header.reloc_size, decoded_l1.header.reloc_size)
        self.assertEqual(decoded_l2.header.checksum, decoded_l1.header.checksum)
        # The signature is the only byte that may legitimately differ.
        self.assertEqual(decoded_l2.image[2:], decoded_l1.image[2:])
        self.assertEqual(convert_library(l2, LibraryFormat.L1), l1)

    def test_l0_l2_conversion_round_trip(self) -> None:
        for path in GOLDEN_DLLS:
            with self.subTest(path=path):
                original = path.read_bytes()
                decoded_l0 = decode_library(original)
                l2 = convert_library(original, LibraryFormat.L2)
                decoded_l2 = decode_library(l2)
                self.assertIs(decoded_l2.header.format, LibraryFormat.L2)
                self.assertFalse(decoded_l2.compressed)
                self.assertEqual(decoded_l2.header.reloc_size, decoded_l0.header.reloc_size - 4)
                self.assertEqual(convert_library(l2, LibraryFormat.L0, compress=True), original)

    def test_l2_to_l1_conversion_rejects_an_oversized_image(self) -> None:
        body = b"\x01" * (MAX_L2_CODE_SIZE - HEADER_SIZE)
        l2 = build_library_from_binaries(body, body, library_format=LibraryFormat.L2, name="huge", compress=False)
        with self.assertRaisesRegex(ToolError, "code and relocation table"):
            convert_library(l2, LibraryFormat.L1)
