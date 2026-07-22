from __future__ import annotations

import unittest

from pathlib import Path

from sprinter_mkdll.assembler import PROFILES, _rewrite_org
from sprinter_mkdll.errors import ToolError


class AssemblerTests(unittest.TestCase):
    def test_rewrite_first_org_preserves_the_rest_of_source(self) -> None:
        source = b"; comment\r\n\tORG #0000\r\norg #2222\r\n"
        rewritten = _rewrite_org(source, 0x100, "#{origin:04X}")
        self.assertEqual(rewritten, b"; comment\r\n\tORG #0100\r\norg #2222\r\n")

    def test_rewrite_org_requires_directive(self) -> None:
        with self.assertRaisesRegex(ToolError, "ORG"):
            _rewrite_org(b"db 0\n", 0, "0x{origin:04X}")

    def test_builtin_profile_adds_include_directories(self) -> None:
        command = PROFILES["sjasmplus"].render_command(
            Path("/tmp/pass0.asm"),
            Path("/tmp/pass0.bin"),
            [Path("/project/source"), Path("/project/include")],
        )
        self.assertIn("/project/source", command)
        self.assertIn("/project/include", command)
