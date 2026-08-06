; ============================================================================
; Sprinter libman 1.4 monolithic include.
;
; Public API:
;   LIBMAN.l_load  HL=ASCIIZ filename, A=window (1..3)
;                  -> HL=handle, CF=0; CF=1 on error
;   LIBMAN.l_free  HL=handle
;   LIBMAN.l_call  HL=handle, B=function number
;   LIBMAN.l_info  HL=handle, DE=32-byte destination
;
; Compact l_load diagnostics:
;   LIBMAN.l_reason and LIBMAN.l_dss_error
; DEFINE LIBMAN_DIAGNOSTICS for active stage/init detail:
;   LIBMAN.l_load_stage and LIBMAN.l_init_status
;
; Supported DLL formats are a build option, reported by LIBMAN.FORMATS:
;   (default)          L0, L1 and L2
;   LIBMAN_L0_L1_ONLY  L0 and L1 only -- the formats libman 1.3 understood
;   LIBMAN_L2_ONLY     L2 only
; LIBMAN.VERSION is 0104h in every configuration.
;
; For a SprEd-style split layout include libman_core.inc in WIN0 and
; libman_state.inc in a permanently mapped window instead of this file.
; ============================================================================

        IFNDEF  _LIBMAN_INCLUDE
        DEFINE  _LIBMAN_INCLUDE

        INCLUDE "libman_core.inc"
        INCLUDE "libman_state.inc"

        ENDIF
