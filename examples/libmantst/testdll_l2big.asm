; Full-page L2 test library: code_size is exactly #4000, so the relocation
; table (2044 bytes) cannot share the page with the code.  This is the case
; L2 exists for, and the one the emulator-based tests cannot reach.
;
; The page is sown with self-referencing pointers, one per relocation chunk
; plus one in its final two bytes.  Each must read back as the address it is
; stored at, so a chunk that the loader skips, repeats, or relocates against
; the wrong slice of the table is caught by the library itself.
;
; Addresses are expressed relative to LIB_BASE because sprinter-mkdll
; assembles the source twice, at origins #0100 apart.

        org     #0000

; The tool prepends the 32-byte header, so the library starts one header
; before the assembly origin.
LIB_BASE        equ     $-#20
PAGE_SIZE       equ     #4000
MARKER_FIRST    equ     LIB_BASE+#0400
MARKER_STRIDE   equ     128
MARKER_COUNT    equ     (LIB_BASE+PAGE_SIZE-2-MARKER_FIRST)/MARKER_STRIDE
MARKER_LAST     equ     LIB_BASE+PAGE_SIZE-2

        jp      big_init
        jp      big_fini
        jp      big_test

big_init:
        call    dll_init                ; shared trailing-payload check
        ret     c
        jp      check_relocation

big_fini:
        jp      dll_fini

; l_call delivers arguments in A/C/DE/IX/IY, so the relocation sweep has to
; run without disturbing any of them.
big_test:
        push    af
        push    bc
        push    de
        push    hl
        call    check_relocation
        pop     hl
        pop     de
        pop     bc
        jr      c,big_test_failed
        pop     af
        jp      dll_test
big_test_failed:
        pop     af
        ld      a,4
        or      a                       ; a nonzero result, as dll_test reports
        ret

check_relocation:
        ld      hl,MARKER_FIRST
        ld      b,MARKER_COUNT
check_loop:
        push    bc
        call    check_marker
        pop     bc
        ret     c
        ld      de,MARKER_STRIDE
        add     hl,de
        djnz    check_loop
        ld      hl,MARKER_LAST
        call    check_marker
        ret     c
        xor     a
        ret

; The word at HL must contain HL itself.
check_marker:
        ld      a,(hl)
        ld      c,a
        inc     hl
        ld      a,(hl)
        ld      b,a
        dec     hl
        push    hl
        or      a
        sbc     hl,bc
        pop     hl
        ret     z
        ld      a,3
        scf
        ret

; The three dispatch slots at the head of the shared body are unreachable
; here; only its helpers are used.
        include "testdll_body.inc"

        assert  $ <= MARKER_FIRST
        ds      MARKER_FIRST-$,#5a

        dup     MARKER_COUNT
        dw      $
        ds      MARKER_STRIDE-2,#5a
        edup

        ds      MARKER_LAST-$,#5a
        dw      $                       ; the final two bytes of the page

        assert  $ = LIB_BASE+PAGE_SIZE
