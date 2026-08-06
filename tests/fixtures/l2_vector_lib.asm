; Relocatable library used by libman_l2_vectors.asm to exercise the L2 chunked
; relocation loop.  The test builds it with --format l2 --target 1.4, so it is
; assembled twice at the tool's L1/L2 base and every absolute word below ends
; up carrying a relocation bit.
;
; The layout is chosen so that ptr_table straddles the loader's 128-byte
; relocation chunks: a chunk that is skipped, applied twice, or fed the wrong
; slice of the table leaves at least one word away from its relocated value.
;
; Every check is written against the library's own relocated words rather than
; a hard-coded #C0 base, so the same file loads correctly at any offset inside
; a shared page (the fixture loads it both at offset 0 and behind another
; library).  The anchor comparison against the run-time PC catches the case
; where nothing was relocated at all, which self-consistent comparisons alone
; would miss.

        org     #0000

PTR_COUNT       equ     64
PAD             equ     126

        jp      fn_init                 ; function 0
        jp      fn_fini                 ; function 1
        jp      fn_test                 ; function 2

; INIT first pins the load base: the relocated immediate must equal the
; address the call actually pushed.  Then it walks the whole pointer table
; against another relocated immediate.  libman reports a nonzero INIT result
; as a failed l_load, so a mis-relocated word fails the vector directly.
fn_init:
; A still holds the DSS handle of the open DLL, and libman promises the file
; pointer sits on the first trailing-payload byte.  Read it before anything
; else clobbers A: this is the only check in the suite that pins where the
; loader's reads left the file.
        ld      hl,payload_byte
        ld      de,1
        ld      c,#13                   ; DSS READ
        rst     #10
        jr      c,fn_init_bad
        ld      a,(payload_byte)
        cp      #a5
        jr      nz,fn_init_bad
        call    fn_init_pc
fn_init_pc:
        pop     hl                      ; hl = run-time address of fn_init_pc
        ld      de,fn_init_pc           ; relocated immediate of the same label
        or      a
        sbc     hl,de
        jr      nz,fn_init_bad
        ld      hl,ptr_table
        ld      b,PTR_COUNT
fn_init_loop:
        ld      e,(hl)
        inc     hl
        ld      d,(hl)                  ; de = a relocated table entry
        inc     hl
        push    hl
        ld      hl,fn_init              ; relocated immediate; entries store it
        or      a
        sbc     hl,de
        pop     hl
        jr      nz,fn_init_bad
        djnz    fn_init_loop
        xor     a
        ret
fn_init_bad:
        ld      a,#e1
        scf
        ret

fn_fini:
        xor     a
        ret

; Relocation must also preserve the low bytes: compare a stored pointer with
; the address the same label resolves to at run time.
fn_test:
        ld      hl,(ptr_table)
        ld      de,fn_init
        or      a
        sbc     hl,de
        jr      nz,fn_test_bad
        xor     a
        ret
fn_test_bad:
        ld      a,#e2
        scf
        ret

        ds      PAD,#5a

ptr_table:
        dup     PTR_COUNT
        dw      fn_init
        edup

payload_byte:
        db      0
