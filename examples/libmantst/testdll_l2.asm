        device  noslot64k
        org     #0000

; sprinter-mkdll supplies the external L2 header (same layout as L1's, but
; the code+table are never RLE-compressed). At runtime libman places this
; body after that header, at the same +20h offset used by the L0/L1 images.
        include "testdll_body.inc"
