        device  noslot64k

TEST_RESULT     equ     #7000
DSS_CALLS       equ     #7001
TEST_FAIL_STAGE equ     #7002
DSS_MODE        equ     #7003

        define  LIBMAN_PATH_CAPACITY 272
        define  LIBMAN_DIAGNOSTICS
        define  LIBMAN_TEST_LOAD_FAILURE_HOOK diag_failure_hook

        org     #0010

; The public l_load checks below only need a deterministic missing-file error.
dss_stub:
        push    af
        ld      a,(DSS_CALLS)
        inc     a
        ld      (DSS_CALLS),a
        pop     af
        ld      a,(DSS_MODE)
        or      a
        jr      z,dss_missing
        cp      2
        jr      z,dss_setwin_failure
        cp      3
        jr      z,dss_setwin_success
        jr      dss_success
dss_missing:
        ld      a,c
        cp      #3d                     ; DSS ALLOC
        jr      z,dss_alloc_ok
        cp      #3b                     ; DSS SETWIN3
        jr      z,dss_simple_ok
        cp      #3e                     ; DSS FREE
        jr      z,dss_simple_ok
        cp      #11                     ; DSS OPEN
        jr      nz,dss_bad_call
        ld      a,#21
        scf
        ret
dss_alloc_ok:
        ld      a,7
        or      a
        ret
dss_simple_ok:
        xor     a
        ret
dss_success:
        ld      a,c
        cp      #11
        jr      z,dss_open_ok
        cp      #12
        jr      nz,dss_bad_call
        xor     a
        ret
dss_open_ok:
        ld      a,5
        or      a
        ret
dss_setwin_failure:
        ld      a,c
        cp      #39                     ; explicit SETWIN1
        jr      nz,dss_bad_call
        ld      a,#1f
        scf
        ret
dss_setwin_success:
        ld      a,c
        cp      #3e                     ; FREEMEM after l_free
        jr      z,dss_simple_ok
        cp      #39                     ; explicit SETWIN1
        jr      nz,dss_bad_call
        ld      ix,#1111                ; DSS may clobber public DLL arguments
        ld      iy,#2222
        xor     a
        ret
dss_bad_call:
        ld      a,#7f
        scf
        ret

        assert  $ < #0100
        ds      #0100-$,0

test_start:
        ld      sp,#3ff0
        xor     a
        ld      (TEST_RESULT),a
        ld      (DSS_CALLS),a
        ld      (TEST_FAIL_STAGE),a
        ld      (DSS_MODE),a

; A real path probe must publish LR_OPEN, LS_OPEN and the raw DSS status.
        ld      hl,missing_path
        ld      a,3
        call    LIBMAN.l_load
        jp      nc,failed_1
        cp      #ff
        jp      nz,failed_1
        ld      a,(LIBMAN.l_reason)
        cp      LIBMAN.LR_OPEN
        jp      nz,failed_1
        ld      a,(LIBMAN.l_load_stage)
        cp      LIBMAN.LS_OPEN
        jp      nz,failed_1
        ld      a,(LIBMAN.l_dss_error)
        cp      #21
        jp      nz,failed_1
        ld      a,(LIBMAN.l_init_status)
        or      a
        jp      nz,failed_1

; Every selected path is staged before OPEN.  An overlong explicit path is
; rejected without OPEN; only scratch allocation/mapping/cleanup reach DSS.
        xor     a
        ld      (DSS_CALLS),a
        ld      hl,overflow_path
        ld      a,3
        call    LIBMAN.l_load
        jp      nc,failed_2
        ld      a,(LIBMAN.l_reason)
        cp      LIBMAN.LR_OPEN
        jp      nz,failed_2
        ld      a,(LIBMAN.l_load_stage)
        cp      LIBMAN.LS_OPEN
        jp      nz,failed_2
        ld      a,(LIBMAN.l_dss_error)
        or      a
        jp      nz,failed_2
        ld      a,(DSS_CALLS)
        cp      3                       ; ALLOC, SETWIN3, FREE
        jp      nz,failed_2

; Invalid caller input has no loader stage and never calls DSS.
        ld      hl,missing_path
        xor     a
        call    LIBMAN.l_load
        jp      nc,failed_3
        ld      a,(LIBMAN.l_reason)
        cp      LIBMAN.LR_WINDOW
        jp      nz,failed_3
        ld      a,(LIBMAN.l_load_stage)
        or      a
        jp      nz,failed_3
        ld      a,(LIBMAN.l_dss_error)
        or      a
        jp      nz,failed_3

; Inject one primary failure per stage through the production _L_LOAD unwind.
; Stage 5 represents an internal format error; stage 8 is a DLL INIT rejection;
; the remaining stages represent a DSS CF with a raw status in A.
        ld      a,1
        ld      (DSS_MODE),a
        ld      b,LIBMAN.LS_TEMP_ALLOC
stage_loop:
        ld      a,b
        ld      (TEST_FAIL_STAGE),a
        ld      hl,load_path
        ld      a,3
        call    LIBMAN.l_load
        jp      nc,failed_4
        cp      #ff
        jp      nz,failed_4
        ld      a,(LIBMAN.l_reason)
        cp      LIBMAN.LR_LOAD
        jp      nz,failed_4
        ld      a,(TEST_FAIL_STAGE)
        ld      b,a
        ld      a,(LIBMAN.l_load_stage)
        cp      b
        jp      nz,failed_4
        ld      a,b
        cp      LIBMAN.LS_FORMAT
        jr      z,stage_internal
        cp      LIBMAN.LS_INIT
        jr      z,stage_init
        ld      a,b
        add     a,#40
        ld      c,a
        ld      a,(LIBMAN.l_dss_error)
        cp      c
        jp      nz,failed_4
        ld      a,(LIBMAN.l_init_status)
        or      a
        jp      nz,failed_4
        jr      stage_next
stage_internal:
        ld      a,(LIBMAN.l_dss_error)
        or      a
        jp      nz,failed_4
        ld      a,(LIBMAN.l_init_status)
        or      a
        jp      nz,failed_4
        jr      stage_next
stage_init:
        ld      a,(LIBMAN.l_dss_error)
        or      a
        jp      nz,failed_4
        ld      a,(LIBMAN.l_init_status)
        cp      #48
        jp      nz,failed_4
stage_next:
        inc     b
        ld      a,b
        cp      LIBMAN.LS_CLEANUP+1
        jr      c,stage_loop
        xor     a
        ld      (TEST_FAIL_STAGE),a

; Best-effort cleanup must not replace an already recorded primary failure.
        xor     a
        ld      (LIBMAN.l_load_stage),a
        ld      a,LIBMAN.LS_INIT
        ld      (LIBMAN.ll_load_stage_active),a
        ld      a,#48
        scf
        call    c,LIBMAN.ll_record_dss_error
        ld      a,LIBMAN.LS_CLEANUP
        ld      (LIBMAN.ll_load_stage_active),a
        ld      a,#49
        scf
        call    c,LIBMAN.ll_record_dss_error
        ld      a,(LIBMAN.l_load_stage)
        cp      LIBMAN.LS_INIT
        jp      nz,failed_5
        ld      a,(LIBMAN.l_dss_error)
        cp      #48
        jp      nz,failed_5

; A DLL INIT rejection is not a DSS error.
        xor     a
        ld      (LIBMAN.l_load_stage),a
        ld      (LIBMAN.l_dss_error),a
        ld      (LIBMAN.l_init_status),a
        ld      (LIBMAN.lcflag),a
        ld      a,#5a
        scf
        call    c,LIBMAN.ll_record_init_failure
        jp      nc,failed_6
        cp      #5a
        jp      nz,failed_6
        ld      a,(LIBMAN.l_load_stage)
        cp      LIBMAN.LS_INIT
        jp      nz,failed_6
        ld      a,(LIBMAN.l_dss_error)
        or      a
        jp      nz,failed_6
        ld      a,(LIBMAN.l_init_status)
        cp      #5a
        jp      nz,failed_6

; A real DSS SETWIN failure inside INIT dispatch is not an INIT rejection.
        xor     a
        ld      (LIBMAN.l_load_stage),a
        ld      (LIBMAN.l_dss_error),a
        ld      (LIBMAN.l_init_status),a
        ld      hl,LIBMAN.lib_table
        ld      (hl),1
        inc     hl
        ld      (hl),7
        inc     hl
        ld      (hl),#40
        inc     hl
        ld      (hl),#41
        ld      a,2
        ld      (DSS_MODE),a
        ld      hl,0
        ld      b,0
        ld      a,#8c
        call    LIBMAN.l_call
        call    c,LIBMAN.ll_record_init_failure
        jp      nc,failed_7
        cp      #8c
        jp      nz,failed_7
        ld      a,(LIBMAN.l_load_stage)
        cp      LIBMAN.LS_INIT
        jp      nz,failed_7
        ld      a,(LIBMAN.l_dss_error)
        cp      #1f
        jp      nz,failed_7
        ld      a,(LIBMAN.l_init_status)
        or      a
        jp      nz,failed_7

; Current Estex-DSS has a broken generic SETWIN #38 implementation for WIN1.
; The dispatcher must select SETWIN1 #39 and restore IX/IY after DSS.
        ld      a,3
        ld      (DSS_MODE),a
        ld      ix,#1234
        ld      iy,#5678
        in      a,(#a2)
        exx
        ld      c,a                     ; expected displaced page in C'
        exx
        ld      hl,0
        ld      b,0
        ld      a,#8c
        scf                             ; handle lookup must ignore caller CF
        call    LIBMAN.l_call
        jp      c,failed_8
        or      a
        jp      nz,failed_8

; l_free must also ignore caller CF and release the page after clearing the
; last table entry.  The DSS trace contains SETWIN1 followed by FREEMEM.
        xor     a
        ld      (DSS_CALLS),a
        ld      hl,0
        scf
        call    LIBMAN.l_free
        jp      c,failed_9
        ld      a,(LIBMAN.lib_table)
        or      a
        jp      nz,failed_9
        ld      a,(DSS_CALLS)
        cp      2
        jp      nz,failed_9
        jp      test_done

failed_1:
        ld      a,1
        jr      failed
failed_2:
        ld      a,2
        jr      failed
failed_3:
        ld      a,3
        jr      failed
failed_4:
        ld      a,4
        jr      failed
failed_5:
        ld      a,5
        jr      failed
failed_6:
        ld      a,6
        jr      failed
failed_7:
        ld      a,7
        jr      failed
failed_8:
        ld      a,8
        jr      failed
failed_9:
        ld      a,9
failed:
        ld      (TEST_RESULT),a
test_done:
        halt

; Called only by the test build at the beginning of _L_LOAD.
diag_failure_hook:
        ld      a,(TEST_FAIL_STAGE)
        or      a
        ret     z
        ld      (LIBMAN.ll_load_stage_active),a
        cp      LIBMAN.LS_FORMAT
        jr      z,diag_internal_failure
        cp      LIBMAN.LS_INIT
        jr      z,diag_init_failure
        add     a,#40
        scf
        call    c,LIBMAN.ll_record_dss_error
        ret
diag_internal_failure:
        scf
        ret
diag_init_failure:
        xor     a
        ld      (LIBMAN.lcflag),a
        ld      a,#48
        scf
        call    c,LIBMAN.ll_record_init_failure
        ret

missing_path:
        db      "X:\\MISSING.DLL",0
load_path:
        db      "X:\\TEST.DLL",0
overflow_path:
        db      "X:\\"
        ds      LIBMAN_PATH_CAPACITY,'A'
        db      0

        assert  $ < #4020
        ds      #4020-$,0
test_dll_table:
        jp      test_dll_init
        jp      test_dll_init
        jp      test_dll_init
test_dll_init:
        ld      a,c
        exx
        cp      c
        exx
        jr      nz,test_dll_bad_args
        push    ix
        pop     hl
        ld      de,#1234
        or      a
        sbc     hl,de
        jr      nz,test_dll_bad_args
        push    iy
        pop     hl
        ld      de,#5678
        or      a
        sbc     hl,de
        jr      nz,test_dll_bad_args
        xor     a
        ret
test_dll_bad_args:
        ld      a,#66
        scf
        ret

        assert  $ < #8000
        ds      #8000-$,0
        include "../../libman/libman.asm"

        assert  LIBMAN.LS_NONE = 0
        assert  LIBMAN.LS_TEMP_ALLOC = 1
        assert  LIBMAN.LS_TEMP_MAP = 2
        assert  LIBMAN.LS_OPEN = 3
        assert  LIBMAN.LS_IO = 4
        assert  LIBMAN.LS_FORMAT = 5
        assert  LIBMAN.LS_COPY = 6
        assert  LIBMAN.LS_TARGET = 7
        assert  LIBMAN.LS_INIT = 8
        assert  LIBMAN.LS_CLEANUP = 9

        end     test_start
