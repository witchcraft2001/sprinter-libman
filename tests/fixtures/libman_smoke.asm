        device  noslot64k
        org     #8100

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
        include "../../libman/libman13.asm" ; compatibility name + guard
libman_end:

        ASSERT  libman_end-libman_start = 1847

        ASSERT  l_load = LIBMAN.l_load
        ASSERT  l_free = LIBMAN.l_free
        ASSERT  l_call = LIBMAN.l_call
        ASSERT  l_info = LIBMAN.l_info
