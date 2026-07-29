# LMTEST

`LMTEST.EXE` is an on-target smoke test derived from the historical
`docs/libman13/TEST.ASM` and L0/L1 library examples. It verifies the current
exported libman against both supported formats.

## Build

Python 3.10+ and `sjasmplus` must be available:

```sh
python examples/libmantst/build.py
```

The command creates:

- `examples/libmantst/build/LMTEST.EXE`;
- `examples/libmantst/build/LMTL0.DLL` (compressed L0 with trailing payload);
- `examples/libmantst/build/LMTL1.DLL` (uncompressed L1).
- `examples/libmantst/build/ANTONFNT.DLL` (historical compressed L0);
- `examples/libmantst/build/TEST.DLL` (historical compressed L0).

`ANTONFNT.DLL` and `TEST.DLL` are copied byte-for-byte from `docs/LIBSHAOS`;
the second `docs/libman/TEST.DLL` is the same binary and is therefore not
duplicated. Copy all five files into one DSS directory and run `LMTEST.EXE` on a
Sprinter or in MAME. A successful run prints:

```text
Testing LMTL0.DLL ... OK
Testing LMTL1.DLL ... OK
Testing ANTONFNT.DLL ... OK
Testing TEST.DLL ... DLL init
DLL free
OK
All libman tests passed.
```

For every DLL the program checks `l_load`, the L0/L1 signature and name returned
by `l_info`, execution of `INIT`, and `l_free`. For `LMTL0.DLL` and
`LMTL1.DLL` it additionally checks argument/result registers `A`, `DE`, `IX`,
`IY` through function 2, including handle dispatch with caller CF set. It also
checks that `C` contains the physical page displaced from WIN1 by that exact
`l_call`. Their `INIT` functions also read an appended one-byte payload through
the file handle received in `A`, checking both the handle ABI and the file
position.
`build.py` and the Python test also lock their expected file sizes
(`008Bh`/`008Bh`) used by the on-target bundle check. `LMTL0.DLL` is compressed,
so its payload check also guards against decoding past the declared prefix.
Public functions in the
historical DLLs are not called
because `ANTONFNT.DLL` changes the video mode and draws to VRAM. On failure the
program prints `l_reason`, `l_load_stage`, `l_dss_error`, and `l_init_status`.
