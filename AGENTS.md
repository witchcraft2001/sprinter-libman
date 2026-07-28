# Repository Guidelines

## Project Structure & Module Organization

The Python package lives in `src/sprinter_mkdll/`. `cli.py` defines the
command-line interface, `format.py` handles L0/L1 encoding and validation,
`assembler.py` runs supported Z80 assemblers, and `model.py` contains shared
types. The exportable Sprinter runtime is in `libman/`; keep
`libman_core.inc`, `libman_state.inc`, and their internal ASM implementation
consistent. Historical sources and golden DLLs are under `docs/`. Tests live
in `tests/`, with assembler inputs in `tests/fixtures/`. Standalone packaging
helpers are in `scripts/`.

Do not commit generated `build/`, `dist/`, `__pycache__/`, `.egg-info/`, or
local virtual-environment contents.

## Build, Test, and Development Commands

```sh
python -m pip install .
python -m unittest discover -s tests -v
sprinter-mkdll verify docs/libman/TEST.DLL --target 1.3
sprinter-mkdll inspect docs/libman/TEST.DLL
```

The full test suite uses Python's `unittest`. Tests involving exported ASM
automatically skip when `sjasmplus` is unavailable. To build and smoke-test a
native executable:

```sh
python -m pip install '.[standalone]'
python scripts/build_standalone.py
python scripts/smoke_standalone.py
```

## Coding Style & Naming Conventions

Use Python 3.10+ syntax, four-space indentation, type annotations, and
`from __future__ import annotations` in new modules. Follow existing naming:
`snake_case` for functions and variables, `PascalCase` for classes, and
uppercase constants. Keep CLI errors actionable and raise `ToolError` for
expected user-facing failures. No formatter or linter is configured; match
the surrounding code and run `git diff --check`.

For SjASMPlus sources, preserve established labels and public
`LIBMAN.*` symbols. Treat L0/L1 binary layout and legacy entry points as
compatibility contracts.

## Testing Guidelines

Name test files `test_*.py`, classes `*Tests`, and methods `test_*`. Add focused
unit tests for format edge cases and fixture-based assembly tests for runtime
changes. Preserve byte-exact golden-file assertions where applicable.

## Commit & Pull Request Guidelines

History uses concise Conventional Commit subjects, such as
`feat(libman): ...` and `fix(libman): ...`. Keep commits scoped and
imperative. Pull requests should explain behavior and compatibility impact,
list commands run, mention required external assemblers, and link related
issues when available. Include CLI output or binary-size changes when they
help reviewers verify the result.
