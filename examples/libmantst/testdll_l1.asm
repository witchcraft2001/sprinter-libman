        device  noslot64k
        org     #0000

; sprinter-mkdll supplies the external L1 header. At runtime libman places this
; body after that header, at the same +20h offset used by the L0 image.
        include "testdll_body.inc"
