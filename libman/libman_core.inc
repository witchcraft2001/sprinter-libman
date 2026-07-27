; ============================================================================
; Sprinter libman: loader part.
;
; This part may be placed in WIN0.  It is active only while l_load is running;
; all persistent state and callable runtime code are emitted by
; libman_state.inc and must stay mapped.
; ============================================================================

        IFNDEF  _LIBMAN_CORE_INCLUDE
        DEFINE  _LIBMAN_CORE_INCLUDE

        IFDEF   LIBMAN_WIN0
        ASSERT  $ < 4000h
        ENDIF

        MODULE  LIBMAN

        DEFINE  LIBMAN_LOADER_ONLY
        INCLUDE "libman_core13.asm"
        UNDEFINE LIBMAN_LOADER_ONLY

        ENDMODULE

        IFDEF   LIBMAN_WIN0
        ASSERT  $ <= 4000h
        ENDIF

        ENDIF
