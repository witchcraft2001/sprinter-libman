; LMTEST2.EXE - the same on-target test built against LIBMAN_L2_ONLY.
;
; That configuration drops the L0/L1 branches and the RLE decompressor, so it
; must still load both L2 libraries and must refuse L0/L1 by signature.

        define  LIBMAN_L2_ONLY
        include "libmantst.asm"
