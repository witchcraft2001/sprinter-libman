        device  noslot64k
        org     #0000

; L0 keeps its 32-byte header inside the relocatable image.
        db      "L0"
        dw      0                       ; encoded file size
        dw      0                       ; code size
        dw      0                       ; relocation bitmap size
        dw      0                       ; checksum
        db      28,7
        dw      2026
        dw      #0100
l0_name:
        db      "LIBMAN TEST L0",0
        ds      16-($-l0_name),0

        include "testdll_body.inc"
