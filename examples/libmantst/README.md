# LMTEST

`LMTEST.EXE` is an on-target smoke test derived from the historical
`docs/libman13/TEST.ASM` and L0/L1 library examples. It verifies the current
exported libman against all three supported formats, L0/L1/L2.

## Build

Python 3.10+ and `sjasmplus` must be available:

```sh
python examples/libmantst/build.py
```

The command creates:

- `examples/libmantst/build/LMTEST.EXE`;
- `examples/libmantst/build/LMTEST2.EXE` (the same test built with
  `LIBMAN_L2_ONLY`);
- `examples/libmantst/build/LMTL0.DLL` (compressed L0 with trailing payload);
- `examples/libmantst/build/LMTL1.DLL` (uncompressed L1);
- `examples/libmantst/build/LMTL2.DLL` (uncompressed L2 -- L2 never compresses);
- `examples/libmantst/build/LMTL2BIG.DLL` (a full-page L2: `code_size` is
  exactly `4000h` and its relocation table is the largest one a page can need,
  `7FCh` bytes);
- `examples/libmantst/build/LMTBAD.DLL` (an L2 with a deliberately corrupted
  `file_size`, which must be refused);
- `examples/libmantst/build/ANTONFNT.DLL` (historical compressed L0);
- `examples/libmantst/build/TEST.DLL` (historical compressed L0).

`ANTONFNT.DLL` and `TEST.DLL` are copied byte-for-byte from `docs/LIBSHAOS`;
the second `docs/libman/TEST.DLL` is the same binary and is therefore not
duplicated. Copy the whole directory onto a Sprinter or into MAME and run
`LMTEST.EXE`. A successful run prints:

```text
Testing LMTL0.DLL ... OK
Testing LMTL1.DLL ... OK
Testing LMTL2.DLL ... OK
Testing LMTL2BIG.DLL ... OK
Rejecting LMTBAD.DLL ... OK
Testing ANTONFNT.DLL ... OK
Testing TEST.DLL ... DLL init
DLL free
OK
All libman tests passed.
```

For every DLL the program checks `l_load`, the L0/L1/L2 signature and name
returned by `l_info`, execution of `INIT`, and `l_free`. For `LMTL0.DLL`,
`LMTL1.DLL`, `LMTL2.DLL`, and `LMTL2BIG.DLL` it additionally checks
argument/result registers `A`, `DE`, `IX`, `IY` through function 2, including
handle dispatch with caller CF set. It also checks that `C` contains the
physical page displaced from WIN1 by that exact `l_call`. Their `INIT`
functions also read an appended one-byte payload through the file handle
received in `A`, checking both the handle ABI and the file position.
`build.py` and the Python test also lock their expected file sizes
(`008Bh`/`008Bh`/`008Bh`/`47FDh`) used by the on-target bundle check.
`LMTL0.DLL` is compressed, so its payload check also guards against decoding
past the declared prefix; the L2 libraries are built with `--target 1.4`,
which L2 requires.

`LMTL2BIG.DLL` is the case the format exists for: its code fills the page, so
the relocation table has to be loaded through the scratch page and applied in
chunks. Self-referencing pointers are sown one per relocation chunk plus one in
the last two bytes of the page, and the library verifies all of them from
`INIT` and again from function 2 -- a chunk that the loader skips, repeats, or
relocates against the wrong slice of the table fails the run. This is the only
place that check happens end to end: the emulator-based
`tests/fixtures/libman_l2_vectors.asm` covers the chunk loop, but not a page
whose end wraps the 16-bit address space.

`LMTBAD.DLL` declares `file_size != code_size + reloc_size`, which in L2 means
"RLE-compressed" and is therefore impossible. Both `LMTEST.EXE` builds require
`l_load` to refuse it with `l_reason = LR_LOAD`.

`LMTEST2.EXE` is the same test compiled with `DEFINE LIBMAN_L2_ONLY`. It must
load both L2 libraries and must refuse `LMTL0.DLL` and `LMTL1.DLL` on their
signature; it does not touch the historical DLLs.

`LMTEST3.EXE` is the mirror image, built with `LIBMAN_L0_L1_ONLY`: it loads
`LMTL0.DLL` and `LMTL1.DLL` and must refuse every L2 file, `LMTBAD.DLL`
included -- that one carries a deliberately broken header, so refusing it on
the signature proves the rejection happens before any header-layout check.

Public functions in the historical DLLs are not called because `ANTONFNT.DLL`
changes the video mode and draws to VRAM. On failure the program prints
`l_reason`, `l_load_stage`, `l_dss_error`, and `l_init_status`, followed by
call-trace fields.

`l_init_status` (`init=`) is the value the DLL's own INIT returned, and the
test DLLs use it to separate the two ways a load can look successful and still
be wrong:

| `init=` | meaning |
| --- | --- |
| `E1` | the library was not relocated: a relocated immediate disagrees with the address the CPU actually reached |
| `E2` | the trailing payload byte read back as zero |
| other | the byte INIT actually read, which says where the file pointer was when INIT got control |

`l2p=` names the last L2 call site the loader reached — it marks progress, not
the point of failure, so a value only rules out everything before it.
