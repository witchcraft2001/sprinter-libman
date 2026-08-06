; ============================================================================
; LMTEST.EXE - on-target smoke test for current libman with L0 and L1 DLLs.
;
; Derived from docs/libman13/TEST.ASM and its L0/L1 LIB.ASM examples.
; The program runs from WIN2, loads each DLL into WIN1, checks l_info, calls
; function 2 with A/DE/IX/IY arguments and the displaced page in C, validates
; its results and unloads it.
; ============================================================================

        device  noslot64k

EXE_HEADER_SIZE         equ     #0200
EXE_LOAD_ADDRESS        equ     #8100
STACK_TOP               equ     #bff0

DSS                     equ     #10
DSS_EXIT                equ     #41
DSS_PCHARS              equ     #5c
LMTL0_FILE_SIZE         equ     #00a5
LMTL1_FILE_SIZE         equ     #00a4
LMTL2_FILE_SIZE         equ     #00a4
LMTL2BIG_FILE_SIZE      equ     #47fd

        define  LIBMAN_MAX_LIBS 1
        define  LIBMAN_NO_LEGACY_API
        define  LIBMAN_DIAGNOSTICS
        define  LIBMAN_CALL_TRACE

        org     EXE_LOAD_ADDRESS-EXE_HEADER_SIZE
exe_header:
        db      "EXE",1
        dd      EXE_HEADER_SIZE
        dw      0                       ; no primary loader
        ds      6,0
        dw      start
        dw      start
        dw      STACK_TOP
        db      0
        ds      EXE_HEADER_SIZE-($-exe_header),0

        assert  $ = EXE_LOAD_ADDRESS

start:
        ld      hl,msg_banner
        call    puts

        IFNDEF  LIBMAN_L2_ONLY
        ld      hl,file_l0
        ld      de,name_l0
        ld      ix,LMTL0_FILE_SIZE
        ld      a,'0'
        ld      c,1
        call    test_library
        jr      c,test_failed

        ld      hl,file_l1
        ld      de,name_l1
        ld      ix,LMTL1_FILE_SIZE
        ld      a,'1'
        ld      c,1
        call    test_library
        jr      c,test_failed
        ELSE
; This build understands only L2, so the historical formats must be turned
; away on their signature, before the loader commits to any header layout.
        ld      hl,file_l0
        call    test_library_rejected
        jr      c,test_failed

        ld      hl,file_l1
        call    test_library_rejected
        jr      c,test_failed
        ENDIF

        IFNDEF  LIBMAN_L0_L1_ONLY
        ld      hl,file_l2
        ld      de,name_l2
        ld      ix,LMTL2_FILE_SIZE
        ld      a,'2'
        ld      c,1
        call    test_library
        jr      c,test_failed

; The case L2 exists for: code fills the page and the relocation table is
; loaded separately.  The library checks its own relocation from INIT and
; again from function 2.
        ld      hl,file_l2big
        ld      de,name_l2big
        ld      ix,LMTL2BIG_FILE_SIZE
        ld      a,'2'
        ld      c,1
        call    test_library
        jr      c,test_failed

; An L2 whose file_size does not equal code_size + reloc_size claims to be
; RLE-compressed, which L2 never is.  It must be refused, not decoded.
        ld      hl,file_l2bad
        call    test_library_rejected
        jr      c,test_failed
        ELSE
; This build keeps the formats libman 1.3 understood, so every L2 file must be
; turned away on its signature -- including the one with the broken header,
; which must not reach any header-layout check.
        ld      hl,file_l2
        call    test_library_rejected
        jr      c,test_failed

        ld      hl,file_l2big
        call    test_library_rejected
        jr      c,test_failed

        ld      hl,file_l2bad
        call    test_library_rejected
        jr      c,test_failed
        ENDIF

        IFNDEF  LIBMAN_L2_ONLY
        ld      hl,file_antonfnt
        ld      de,name_antonfnt
        ld      ix,#1803
        ld      a,'0'
        ld      c,0
        call    test_library
        jr      c,test_failed

        ld      hl,file_sample
        ld      de,name_sample
        ld      ix,#006f
        ld      a,'0'
        ld      c,0
        call    test_library
        jr      c,test_failed
        ENDIF

        ld      hl,msg_all_ok
        call    puts
        ld      b,0
        jp      exit_to_dss

test_failed:
        ld      hl,msg_failed
        call    puts
        ld      hl,(error_message)
        call    puts
        ld      hl,msg_reason
        call    puts
        ld      a,(LIBMAN.l_reason)
        call    print_hex8
        ld      hl,msg_stage
        call    puts
        ld      a,(LIBMAN.l_load_stage)
        call    print_hex8
        ld      hl,msg_dss
        call    puts
        ld      a,(LIBMAN.l_dss_error)
        call    print_hex8
        ld      hl,msg_init
        call    puts
        ld      a,(LIBMAN.l_init_status)
        call    print_hex8
        ld      hl,msg_trace_relocated
        call    puts
        ld      a,(LIBMAN.l_trace_relocated+0)
        call    print_hex8
        ld      a,(LIBMAN.l_trace_relocated+1)
        call    print_hex8
        ld      a,(LIBMAN.l_trace_relocated+2)
        call    print_hex8
        ld      hl,msg_trace_mapped
        call    puts
        ld      a,(LIBMAN.l_trace_mapped+0)
        call    print_hex8
        ld      a,(LIBMAN.l_trace_mapped+1)
        call    print_hex8
        ld      a,(LIBMAN.l_trace_mapped+2)
        call    print_hex8
        ld      hl,msg_trace_function
        call    puts
        ld      a,(LIBMAN.l_trace_function)
        call    print_hex8
        ld      hl,msg_trace_flag
        call    puts
        ld      a,(LIBMAN.l_trace_reloc_flag)
        call    print_hex8
        ld      a,(LIBMAN.l_trace_reloc_base)
        call    print_hex8
        ld      hl,msg_trace_bitmap
        call    puts
        ld      a,(LIBMAN.l_trace_bitmap_raw)
        call    print_hex8
        ld      a,(LIBMAN.l_trace_bitmap_staged)
        call    print_hex8
        ld      a,(LIBMAN.l_trace_bitmap)
        call    print_hex8
        ld      hl,msg_trace_size
        call    puts
        ld      hl,(LIBMAN.l_trace_load_size)
        call    print_hex16
        ld      hl,msg_trace_source_end
        call    puts
        ld      hl,(LIBMAN.l_trace_copy_source_end)
        call    print_hex16
        ld      hl,msg_trace_dest_end
        call    puts
        ld      hl,(LIBMAN.l_trace_copy_dest_end)
        call    print_hex16
        ld      hl,msg_trace_l2_point
        call    puts
        ld      a,(LIBMAN.l_trace_l2_point)
        call    print_hex8
        ld      hl,msg_trace_l2_a
        call    puts
        ld      a,(LIBMAN.l_trace_l2_a)
        call    print_hex8
        ld      hl,msg_newline
        call    puts
        ld      b,1

exit_to_dss:
        ld      c,DSS_EXIT
        rst     DSS
        ret

; In: HL=DLL filename, DE=expected info name, IX=expected file size, A='0'/'1',
;     C=1 to exercise the private register-test function 2, C=0 otherwise.
; Out: CF=0 on success; otherwise error_message describes the failed check.
test_library:
        ld      (expected_format),a
        ld      a,c
        ld      (call_test_enabled),a
        ld      (expected_name),de
        ld      (selected_file),hl
        ld      (expected_file_size),ix
        xor     a
        ld      (dll_loaded),a

        ld      hl,msg_testing
        call    puts
        ld      hl,(selected_file)
        call    puts
        ld      hl,msg_separator
        call    puts

        ld      hl,(selected_file)
        xor     a
        ld      (LIBMAN.l_trace_load_size+0),a
        ld      (LIBMAN.l_trace_load_size+1),a
        ld      a,1                     ; DLL occupies WIN1
        call    LIBMAN.l_load
        jp      c,fail_load
        ld      (dll_handle),hl
        ld      a,1
        ld      (dll_loaded),a
        call    test_file_size_mismatch
        jp      c,fail_bundle_loaded

        ld      hl,(dll_handle)
        ld      de,dll_info
        call    LIBMAN.l_info
        jp      c,fail_info

        ld      a,(dll_info)
        cp      'L'
        jp      nz,fail_info_format
        ld      a,(expected_format)
        ld      b,a
        ld      a,(dll_info+1)
        cp      b
        jp      nz,fail_info_format

        ld      hl,(expected_name)
        ld      de,dll_info+16
        call    strings_equal
        jr      nz,fail_info_name

        ld      a,(call_test_enabled)
        or      a
        jp      z,test_library_free

        in      a,(#a2)
        exx
        ld      c,a                     ; expected displaced WIN1 page in C'
        exx
        ld      a,#a5
        ld      de,#1234
        ld      ix,#5678
        ld      iy,#9abc
        ld      hl,(dll_handle)
        ld      b,2
        scf                             ; handle lookup must ignore caller CF
        call    LIBMAN.l_call
        jr      c,fail_call
        or      a
        jr      nz,fail_result

        ld      a,d
        cp      #be
        jr      nz,fail_result
        ld      a,e
        cp      #ef
        jr      nz,fail_result
        push    ix
        pop     hl
        ld      de,#cafe
        or      a
        sbc     hl,de
        jr      nz,fail_result
        push    iy
        pop     hl
        ld      de,#face
        or      a
        sbc     hl,de
        jr      nz,fail_result

test_library_free:
        ld      hl,(dll_handle)
        scf                             ; l_free/corecall must ignore caller CF
        call    LIBMAN.l_free
        jr      c,fail_free
        xor     a
        ld      (dll_loaded),a
        ld      hl,msg_ok
        call    puts
        or      a
        ret

fail_load:
        call    test_file_size_mismatch
        jr      c,fail_bundle
        ld      hl,msg_load
        jr      fail
fail_bundle:
        ld      hl,msg_bundle
        jr      fail
fail_bundle_loaded:
        ld      hl,msg_bundle
        jr      fail_with_cleanup
fail_info:
        ld      hl,msg_info
        jr      fail_with_cleanup
fail_info_format:
        ld      hl,msg_info_format
        jr      fail_with_cleanup
fail_info_name:
        ld      hl,msg_info_name
        jr      fail_with_cleanup
fail_call:
        ld      hl,msg_call
        jr      fail_with_cleanup
fail_result:
        ld      hl,msg_result
        jr      fail_with_cleanup
fail_free:
        xor     a
        ld      (dll_loaded),a
        ld      hl,msg_free
        jr      fail

fail_with_cleanup:
        push    hl
        call    cleanup_library
        pop     hl
fail:
        ld      (error_message),hl
        scf
        ret

cleanup_library:
        ld      a,(dll_loaded)
        or      a
        ret     z
        ld      hl,(dll_handle)
        call    LIBMAN.l_free
        xor     a
        ld      (dll_loaded),a
        ret

; In: HL=DLL filename that this build must refuse.
; Out: CF=0 when l_load rejected it and blamed the load itself.
test_library_rejected:
        ld      (selected_file),hl
        xor     a
        ld      (dll_loaded),a

        ld      hl,msg_rejecting
        call    puts
        ld      hl,(selected_file)
        call    puts
        ld      hl,msg_separator
        call    puts

        ld      hl,(selected_file)
        ld      a,1                     ; the same window a real load would use
        call    LIBMAN.l_load
        jr      nc,fail_not_rejected
        ld      a,(LIBMAN.l_reason)
        cp      LIBMAN.LR_LOAD
        jr      nz,fail_wrong_reason
        ld      hl,msg_ok
        call    puts
        or      a
        ret

fail_not_rejected:
        ld      (dll_handle),hl
        ld      a,1
        ld      (dll_loaded),a
        ld      hl,msg_not_rejected
        jr      fail_with_cleanup
fail_wrong_reason:
        ld      hl,msg_wrong_reason
        jr      fail

; CF=1 if the opened file is from a different LMTEST build.
test_file_size_mismatch:
        ld      hl,(LIBMAN.l_trace_load_size)
        ld      a,h
        or      l
        ret     z
        ld      de,(expected_file_size)
        or      a
        sbc     hl,de
        ret     z
        scf
        ret

; Compare ASCIIZ strings HL and DE. ZF=1 means equal.
strings_equal:
        ld      a,(de)
        cp      (hl)
        ret     nz
        or      a
        ret     z
        inc     hl
        inc     de
        jr      strings_equal

; DSS string output, preserving all registers used by the test.
puts:
        push    af
        push    bc
        push    de
        push    hl
        ld      c,DSS_PCHARS
        rst     DSS
        pop     hl
        pop     de
        pop     bc
        pop     af
        ret

print_hex8:
        push    af
        rrca
        rrca
        rrca
        rrca
        call    print_hex_nibble
        pop     af
print_hex_nibble:
        and     #0f
        add     a,'0'
        cp      '9'+1
        jr      c,print_hex_digit
        add     a,'A'-'9'-1
print_hex_digit:
        ld      (hex_buffer),a
        ld      hl,hex_buffer
        jp      puts

; print_hex8 ends in print_hex_nibble, which loads HL with the output buffer.
; Without saving HL the low byte printed here was the low byte of hex_buffer,
; so every 16-bit field above reported a correct high byte and a constant lie
; for the low one.
print_hex16:
        push    af
        push    hl
        ld      a,h
        call    print_hex8
        pop     hl
        push    hl
        ld      a,l
        call    print_hex8
        pop     hl
        pop     af
        ret

dll_handle:
        dw      0
selected_file:
        dw      0
expected_name:
        dw      0
expected_file_size:
        dw      0
error_message:
        dw      msg_load
expected_format:
        db      0
call_test_enabled:
        db      0
dll_loaded:
        db      0
dll_info:
        ds      32,0
hex_buffer:
        db      0,0

msg_banner:
        IFDEF   LIBMAN_L2_ONLY
        db      13,10,"libman L2-only test",13,10,0
        ELSE
        IFDEF   LIBMAN_L0_L1_ONLY
        db      13,10,"libman L0/L1-only test",13,10,0
        ELSE
        db      13,10,"libman L0/L1/L2 test",13,10,0
        ENDIF
        ENDIF
msg_testing:
        db      "Testing ",0
msg_rejecting:
        db      "Rejecting ",0
msg_separator:
        db      " ... ",0
msg_ok:
        db      "OK",13,10,0
msg_all_ok:
        db      "All libman tests passed.",13,10,0
msg_failed:
        db      "FAILED: ",0
msg_reason:
        db      " reason=",0
msg_stage:
        db      " stage=",0
msg_dss:
        db      " dss=",0
msg_init:
        db      " init=",0
msg_trace_relocated:
        db      " rel=",0
msg_trace_mapped:
        db      " map=",0
msg_trace_function:
        db      " fn=",0
msg_trace_flag:
        db      " rb=",0
msg_trace_bitmap:
        db      " bm=",0
msg_trace_size:
        db      " sz=",0
msg_trace_source_end:
        db      " sh=",0
msg_trace_dest_end:
        db      " de=",0
msg_trace_l2_point:
        db      " l2p=",0
msg_trace_l2_a:
        db      " l2a=",0
msg_newline:
        db      13,10,0

msg_load:
        db      "l_load",0
msg_bundle:
        db      "replace DLLs with current test build",0
msg_info:
        db      "l_info",0
msg_info_format:
        db      "wrong L0/L1 signature",0
msg_info_name:
        db      "wrong library name",0
msg_call:
        db      "l_call dispatcher",0
msg_result:
        db      "DLL arguments/results",0
msg_free:
        db      "l_free",0
msg_not_rejected:
        db      "l_load accepted a DLL it must refuse",0
msg_wrong_reason:
        db      "rejected with the wrong l_reason",0

file_l0:
        db      "LMTL0.DLL",0
file_l1:
        db      "LMTL1.DLL",0
file_l2:
        db      "LMTL2.DLL",0
file_l2big:
        db      "LMTL2BIG.DLL",0
file_l2bad:
        db      "LMTBAD.DLL",0
file_antonfnt:
        db      "ANTONFNT.DLL",0
file_sample:
        db      "TEST.DLL",0
name_l0:
        db      "LIBMAN TEST L0",0
name_l1:
        db      "LIBMAN TEST L1",0
name_l2:
        db      "LIBMAN TEST L2",0
name_l2big:
        db      "LIBMAN TEST BIG",0
name_antonfnt:
        db      "Anton Enin Font",0
name_sample:
        db      "Sample Library",0

        include "../../libman/libman.asm"

program_end:
        assert  program_end < STACK_TOP
        end     start
