        device  noslot64k
        org     #8100

        ; The formats libman 1.3 understood, on the 1.4 codebase: every fix
        ; and the bounded path search stay, the L2 reader is left out.
        DEFINE  LIBMAN_L0_L1_ONLY

start:
        ld      hl,dll_name
        ld      a,3
        call    LIBMAN.l_load
        ret     c
        ld      (dll_handle),hl
        ld      b,2
        call    LIBMAN.l_call
        ld      hl,(dll_handle)
        call    LIBMAN.l_free
        ret

dll_name:
        db      "TEST.DLL",0
dll_handle:
        dw      0

libman_start:
        include "../../libman/libman.asm"
libman_end:

        ASSERT  libman_end-libman_start = 1861

        ; One version across every configuration; only the format set moves.
        ASSERT  LIBMAN.VERSION = #0104
        ASSERT  LIBMAN.FORMATS = LIBMAN.FORMAT_L0|LIBMAN.FORMAT_L1

        ASSERT  l_load = LIBMAN.l_load
        ASSERT  l_free = LIBMAN.l_free
        ASSERT  l_call = LIBMAN.l_call
        ASSERT  l_info = LIBMAN.l_info
