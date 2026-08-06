; Common body for the L0 and L1 test libraries.
; The three-entry table follows the historical docs/libman13 examples:
; function 0 = INIT, function 1 = FINI, function 2 = user test.

        jp      dll_init
        jp      dll_fini
        jp      dll_test

dll_init:
; Separate the two things that can go wrong here, because l_init_status is the
; only channel back to the application:
;   #E1  the library was not relocated (a relocated immediate disagrees with
;        the address the CPU actually reached), so nothing else is meaningful;
;   #E2  the trailing payload read back as zero;
;   else the byte that was actually read, which says where the file pointer
;        really was when INIT got control.
        push    af                      ; keep the DSS handle INIT was given
        call    dll_init_here
dll_init_here:
        pop     hl                      ; address the call actually pushed
        ld      de,dll_init_here        ; the same label as a relocated immediate
        or      a
        sbc     hl,de
        jr      nz,dll_init_not_relocated
        pop     af

        ld      hl,dll_payload_byte
        ld      de,1
        ld      c,#13                   ; DSS READ, A is the INIT file handle
        rst     #10
        ret     c
        ld      a,(dll_payload_byte)
        cp      #a5
        jr      nz,dll_init_failed
        xor     a
        ret
dll_init_failed:
        or      a                       ; cp above left A = the byte read
        jr      nz,dll_init_report
        ld      a,#e2                   ; zero would look like "no failure"
dll_init_report:
        scf
        ret
dll_init_not_relocated:
        pop     af
        ld      a,#e1
        scf
        ret

dll_fini:
        xor     a
        ret

dll_test:
        cp      #a5
        jr      nz,dll_test_failed

; Verify that l_call delivered every documented argument register, then return
; deterministic values for the application to check.
        ld      a,c
        exx
        cp      c                       ; C' carries the caller's expected page
        exx
        jr      nz,dll_test_failed

        ld      a,d
        cp      #12
        jr      nz,dll_test_failed
        ld      a,e
        cp      #34
        jr      nz,dll_test_failed

        push    ix
        pop     hl
        ld      bc,#5678
        or      a
        sbc     hl,bc
        jr      nz,dll_test_failed

        push    iy
        pop     hl
        ld      bc,#9abc
        or      a
        sbc     hl,bc
        jr      nz,dll_test_failed

        ld      de,#beef
        ld      ix,#cafe
        ld      iy,#face
        xor     a
        ret

dll_test_failed:
        ld      a,1
        or      a
        ret

dll_payload_byte:
        db      0
