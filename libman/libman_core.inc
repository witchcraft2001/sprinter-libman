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

LS_NONE         EQU     0
LS_TEMP_ALLOC   EQU     1
LS_TEMP_MAP     EQU     2
LS_OPEN         EQU     3
LS_IO           EQU     4
LS_FORMAT       EQU     5
LS_COPY         EQU     6
LS_TARGET       EQU     7
LS_INIT         EQU     8
LS_CLEANUP      EQU     9

        DEFINE  LIBMAN_LOADER_ONLY
        INCLUDE "libman_core13.asm"
        UNDEFINE LIBMAN_LOADER_ONLY

        ENDMODULE

        IFDEF   LIBMAN_WIN0
        ASSERT  $ <= 4000h
        ENDIF

        ENDIF
