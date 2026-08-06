; LMTEST3.EXE - the same on-target test built against LIBMAN_L0_L1_ONLY.
;
; That configuration keeps the DLL formats libman 1.3 understood, on the 1.4
; codebase: it must still load both historical formats and must refuse every
; L2 file by signature, before any header-layout check can run.

        define  LIBMAN_L0_L1_ONLY
        include "libmantst.asm"
