        device  noslot64k

        DEFINE  LIBMAN_WIN0
        DEFINE  LIBMAN_MAX_LIBS 8
        DEFINE  LIBMAN_APP_DIR app_exe_dir
        DEFINE  LIBMAN_PATH_CAPACITY 272

        ; Current SprEd WIN0 ends at #3BA0 and must remain below #4000.
        org     #3BA0
win0_libman_start:
        include "../../libman/libman_core.inc"
win0_libman_end:
        ASSERT  win0_libman_end-win0_libman_start = 971
        ASSERT  win0_libman_end <= #4000

        ; Current SprEd WIN1 ends at #7453; its stack starts at #7FF0.
        org     #7453
win1_libman_start:
        include "../../libman/libman_state.inc"
app_exe_dir:
        ASSERT  app_exe_dir-win1_libman_start = 644
        db      "C:\\SPRED\\",0
win1_libman_end:
        ASSERT  win1_libman_end <= #7FF0

        org     win1_libman_end
smoke_call:
        ld      hl,dll_name
        ld      a,3
        call    LIBMAN.l_load
        ret     c
        ld      b,2
        call    LIBMAN.l_call
        ret

dll_name:
        db      "TEST.DLL",0
