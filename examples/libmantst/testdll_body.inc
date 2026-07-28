; Common body for the L0 and L1 test libraries.
; The three-entry table follows the historical docs/libman13 examples:
; function 0 = INIT, function 1 = FINI, function 2 = user test.

        jp      dll_init
        jp      dll_fini
        jp      dll_test

dll_init:
        xor     a
        ret

dll_fini:
        xor     a
        ret

dll_test:
        cp      #a5
        jr      nz,dll_test_failed

; Verify that l_call delivered every documented argument register, then return
; deterministic values for the application to check.
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
