from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile

from .errors import ToolError


ORG_PATTERN = re.compile(rb"^(?P<prefix>[ \t]*org(?:[ \t]+|\t+)).*$", re.IGNORECASE)


@dataclass(frozen=True)
class AssemblerProfile:
    name: str
    command: tuple[str, ...]
    origin_template: str
    include_arguments: tuple[str, ...]
    output_candidates: tuple[str, ...] = ("{stem}.bin", "{output}")

    def render_command(self, source: Path, output: Path, include_dirs: list[Path]) -> list[str]:
        values = {
            "source": str(source),
            "output": str(output),
            "stem": source.stem,
            "source_dir": str(include_dirs[0]) if include_dirs else "",
            "include_path": os.pathsep.join(str(path) for path in include_dirs),
        }
        include_parts = [
            part.format(include=str(include_dir))
            for include_dir in include_dirs
            for part in self.include_arguments
        ]
        command: list[str] = []
        for part in self.command:
            if part == "{include_arguments}":
                command.extend(include_parts)
            else:
                command.append(part.format(**values))
        return command


PROFILES: dict[str, AssemblerProfile] = {
    # Historical mk_dll invoked zmac without output flags; it writes <stem>.bin in cwd.
    "zmac": AssemblerProfile(
        "zmac", ("zmac", "{include_arguments}", "{source}"), "#{origin:04X}", ("-I", "{include}")
    ),
    "z80asm": AssemblerProfile(
        "z80asm",
        ("z80asm", "-b", "-o{output}", "{include_arguments}", "{source}"),
        "0x{origin:04X}",
        ("-I={include}",),
    ),
    "sjasmplus": AssemblerProfile(
        "sjasmplus",
        ("sjasmplus", "--raw={output}", "{include_arguments}", "{source}"),
        "0x{origin:04X}",
        ("-I", "{include}"),
    ),
}


def _profile(name: str, command: str | None, origin_template: str | None) -> AssemblerProfile:
    if command is not None:
        parts = tuple(shlex.split(command))
        if not parts:
            raise ToolError("--assembler-command is empty")
        if "{source}" not in command:
            raise ToolError("--assembler-command must contain {source}")
        return AssemblerProfile("custom", parts, origin_template or "0x{origin:04X}", ())
    try:
        profile = PROFILES[name]
    except KeyError as exc:
        raise ToolError(f"unknown assembler profile {name!r}") from exc
    return AssemblerProfile(
        profile.name,
        profile.command,
        origin_template or profile.origin_template,
        profile.include_arguments,
        profile.output_candidates,
    )


def _rewrite_org(source: bytes, origin: int, origin_template: str) -> bytes:
    replacement = origin_template.format(origin=origin).encode("ascii")
    lines = source.splitlines(keepends=True)
    for index, line in enumerate(lines):
        bare = line.rstrip(b"\r\n")
        match = ORG_PATTERN.match(bare)
        if match is None:
            continue
        newline = line[len(bare):]
        lines[index] = match.group("prefix") + replacement + newline
        return b"".join(lines)
    raise ToolError("source does not contain an ORG directive to rewrite")


def _find_output(workdir: Path, source: Path, requested: Path, profile: AssemblerProfile) -> Path:
    candidates = [requested]
    for template in profile.output_candidates:
        candidate = Path(template.format(stem=source.stem, output=str(requested)))
        candidates.append(candidate if candidate.is_absolute() else workdir / candidate)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    checked = ", ".join(str(candidate) for candidate in candidates)
    raise ToolError(f"assembler did not create a binary output; checked {checked}")


def assemble_two_passes(
    source_path: Path,
    *,
    assembler: str,
    assembler_command: str | None = None,
    origin_template: str | None = None,
    base_origin: int = 0,
    include_dirs: list[Path] | None = None,
) -> tuple[bytes, bytes]:
    source = source_path.read_bytes()
    profile = _profile(assembler, assembler_command, origin_template)
    resolved_include_dirs = [source_path.resolve().parent]
    for include_dir in include_dirs or []:
        resolved = include_dir.resolve()
        if resolved not in resolved_include_dirs:
            resolved_include_dirs.append(resolved)
    with tempfile.TemporaryDirectory(prefix="sprinter-mkdll-") as temp_name:
        workdir = Path(temp_name)
        outputs: list[bytes] = []
        for origin, stem in ((base_origin, "pass0"), (base_origin + 0x100, "pass100")):
            temporary_source = workdir / f"{stem}{source_path.suffix or '.asm'}"
            temporary_source.write_bytes(_rewrite_org(source, origin, profile.origin_template))
            requested = workdir / f"{stem}.bin"
            command = profile.render_command(temporary_source, requested, resolved_include_dirs)
            try:
                completed = subprocess.run(command, cwd=workdir, capture_output=True, text=True, check=False)
            except FileNotFoundError as exc:
                raise ToolError(f"assembler executable not found: {command[0]}") from exc
            if completed.returncode:
                output = (completed.stdout + completed.stderr).strip()
                raise ToolError(f"assembler pass at 0x{origin:04X} failed ({completed.returncode}):\n{output}")
            outputs.append(_find_output(workdir, temporary_source, requested, profile).read_bytes())
    return outputs[0], outputs[1]
