; Executable vectors for the L2 loader path, driven through the public
; LIBMAN.l_load against a stubbed DSS and an in-RAM "file".
;
; The DSS stub emulates window-3 paging by shadowing the mapped page, which is
; what makes the interesting case testable: L2 reads code into the target page
; and the relocation table into the scratch page, then relocates in chunks by
; switching between the two.  Aliasing those pages, as a no-op SETWIN would,
; hides exactly the bugs this fixture is here to catch.  (An earlier stub did
; alias them -- the dispatch clobbered the descriptor in A and the swap
; clobbered the slot number in C -- and a loader that ran its first remake
; with the scratch page still mapped sailed through: the reads all landed in
; one flat page whose merged bytes happened to execute as a successful INIT.
; Hence the sentinel in TEST_RESULT, the HALT fill in low memory, and vector
; 9, which loads at a nonzero page offset so relocation visibly changes bytes.)
;
; Only L2 is covered.  The L0/L1 RLE decode loop still moves its bytes through
; the Sprinter block accelerator, which the emulator executes as a plain
; single-byte LD, so that stage cannot be reproduced here; L0/L1 keeps its
; structural coverage in test_libman_include.py instead.

        device  noslot64k

TEST_RESULT     equ     #7000           ; 0 = all vectors passed, #EE = never finished
FILE_BASE       equ     #7002           ; dw: image of the file under test
FILE_LEN        equ     #7004           ; dw: physical length reported by DSS
FILE_POS        equ     #7006           ; dw: read cursor
SP_BEFORE       equ     #7008           ; dw
SP_AFTER        equ     #700a           ; dw
CUR_SLOT        equ     #700c           ; db: page currently in window 3
NEXT_DESC       equ     #700d           ; db: next descriptor handed out by ALLOC
DSS_A           equ     #700e           ; db: caller's A, saved before dispatch

WINDOW          equ     #c000           ; window 3
SHADOW_SIZE     equ     #400            ; per-page backing store
SHADOW_BASE     equ     #a000           ; slot n at SHADOW_BASE + n*SHADOW_SIZE
FIRST_DESC      equ     #55
NO_SLOT         equ     #ff

        define  LIBMAN_MAX_LIBS 2
        define  LIBMAN_NO_EXE_DIR
        define  LIBMAN_PATH_BUFFER #6000
        define  LIBMAN_PATH_CAPACITY 64
        ; L2 now hands its relocated image to the shared ll10 copy loop, whose
        ; 16-byte transfers go through the Sprinter block accelerator.  An
        ; emulator runs that idiom as a one-byte LD, so without this the target
        ; page would receive 1 byte in 16 and every check below would be
        ; reading rubbish.  It swaps only the copy primitive; the paging,
        ; sequencing and relocation under test are the shipped code.
        define  LIBMAN_TEST_NO_ACCELERATOR

; Low memory is filled with #FF (RST #38): a jump through an unrelocated
; pointer lands here whatever its alignment and is turned into a diagnosed
; stop, instead of wandering back into the test and fabricating a pass.  It
; must not be a HALT fill -- the emulator spins on HALT with interrupts off
; without retiring its cycle budget, so a caught bug would hang the run
; rather than fail it.
        org     #0000
        ds      #0010,#ff
        jp      dss_stub
        ds      #0038-$,#ff
        jp      stray_execution
        ds      #0100-$,#ff

; ---------------------------------------------------------------------------
        org     #0100
test_start:
        ld      sp,#3ff0
        ld      a,#ee                   ; cleared only when every vector ran
        ld      (TEST_RESULT),a

; 1. A relocatable L2 whose body spans three relocation chunks, two full and
;    one partial.  Its INIT walks every relocated pointer, so a chunk that is
;    skipped, repeated or fed the wrong slice of the table fails the load.
        ld      hl,file_l2_reloc
        ld      de,file_l2_reloc_end-file_l2_reloc+1   ; payload included
        call    select_file
        call    load_ok
        jp      c,failed_1
        ld      b,2                     ; function 2 re-checks a stored pointer
        ld      hl,0
        call    LIBMAN.l_call
        jp      c,failed_1
        or      a
        jp      nz,failed_1
; Postconditions of the chunk loop, which pin its arithmetic even where a
; wrong count would relocate against a bitmap of zeros and go unnoticed: the
; loop must consume the body exactly once and stop on the last code byte.
        ld      hl,(LIBMAN.ll2_left)
        ld      a,h
        or      l
        jp      nz,failed_1
        ld      hl,(file_l2_reloc+4)    ; code_size, header included
        ld      de,WINDOW
        add     hl,de
        ex      de,hl
        ld      hl,(LIBMAN.ll2_code_addr)
        or      a
        sbc     hl,de
        jp      nz,failed_1
        ld      hl,0
        call    LIBMAN.l_free
        jp      c,failed_1

; 2. A non-relocatable L2 claims its page outright.  ll5 must be able to read
;    back a high-water mark of #40, which needs an inclusive #FF end byte and
;    not a #00 wrapped through #100 -- otherwise the next library is placed on
;    top of this one.
        ld      hl,file_l2_plain
        ld      de,file_l2_plain_end-file_l2_plain
        call    select_file
        call    load_ok
        jp      c,failed_2
        ld      a,l
        or      h
        jp      nz,failed_2             ; the first handle is 0
        ld      a,(LIBMAN.lib_table+0)
        cp      1
        jp      nz,failed_2
        ld      a,(LIBMAN.lib_table+2)
        cp      #c0
        jp      nz,failed_2
        ld      a,(LIBMAN.lib_table+3)
        cp      #ff
        jp      nz,failed_2
        ld      a,(WINDOW+#20)          ; code landed at the page start
        cp      #af                     ; XOR A
        jp      nz,failed_2
        ld      hl,0
        call    LIBMAN.l_free
        jp      c,failed_2

; 3. code_size above a full page.  Before the page check returned its verdict
;    in CF this left its own return address on the stack, and _L_LOAD returned
;    through it after llerr_after_path unwound four words by count.
        ld      hl,file_l2_big_code
        ld      de,file_l2_big_code_end-file_l2_big_code
        call    select_file
        call    load_fails
        jp      c,failed_3

; 4. reloc_size above a full page: the same leak plus a pushed code_size.
        ld      hl,file_l2_big_table
        ld      de,file_l2_big_table_end-file_l2_big_table
        call    select_file
        call    load_fails
        jp      c,failed_4

; 5. file_size != code_size + reloc_size, i.e. a would-be compressed L2.
        ld      hl,file_l2_packed
        ld      de,file_l2_packed_end-file_l2_packed
        call    select_file
        call    load_fails
        jp      c,failed_5

; 6. code_size below the 32-byte header.
        ld      hl,file_l2_tiny
        ld      de,file_l2_tiny_end-file_l2_tiny
        call    select_file
        call    load_fails
        jp      c,failed_6

; 7. A physically truncated prefix.
        ld      hl,file_l2_plain
        ld      de,#20
        call    select_file
        call    load_fails
        jp      c,failed_7

; 8. Every rejection above must leave the table clean for the next load.
        ld      hl,file_l2_plain
        ld      de,file_l2_plain_end-file_l2_plain
        call    select_file
        call    load_ok
        jp      c,failed_8
        ld      a,l
        or      h
        jp      nz,failed_8             ; still the first slot
        ld      hl,0
        call    LIBMAN.l_free
        jp      c,failed_8

; 9. The chunked library again, but loaded behind a smaller one so it shares
;    the page at offset #100.  Only here does relocation change any bytes
;    (vector 1 loads at the page start, where the delta equals the assembly
;    base), so only here does a remake applied to the wrong page, or fed a
;    scribbled-over table, change what INIT and function 2 observe.
        ld      hl,file_l2_small
        ld      de,file_l2_small_end-file_l2_small
        call    select_file
        call    load_ok
        jp      c,failed_9
        ld      hl,file_l2_reloc
        ld      de,file_l2_reloc_end-file_l2_reloc+1   ; payload included
        call    select_file_keep
        call    load_ok
        jp      c,failed_9
        ld      a,l
        dec     a
        or      h
        jp      nz,failed_9             ; the second slot
        ld      a,(LIBMAN.lib_table+4+2)
        cp      #c1                     ; shared page, offset #100
        jp      nz,failed_9
        ld      b,2
        ld      hl,1
        call    LIBMAN.l_call
        jp      c,failed_9
        or      a
        jp      nz,failed_9
        ld      hl,1
        call    LIBMAN.l_free
        jp      c,failed_9
        ld      hl,0
        call    LIBMAN.l_free
        jp      c,failed_9

        xor     a                       ; every vector ran: clear the sentinel
        ld      (TEST_RESULT),a
        jp      test_done

; ---------------------------------------------------------------------------
; Helpers
; ---------------------------------------------------------------------------
; HL = image, DE = physical length.  Also returns the machine to the state a
; fresh l_load sees: no page mapped, descriptors unissued, pages zeroed.
select_file:
        call    select_file_keep
        ld      a,NO_SLOT
        ld      (CUR_SLOT),a
        ld      a,FIRST_DESC
        ld      (NEXT_DESC),a
        ld      hl,SHADOW_BASE
        ld      de,SHADOW_BASE+1
        ld      bc,3*SHADOW_SIZE-1
        ld      (hl),0
        ldir
        ld      hl,WINDOW
        ld      de,WINDOW+1
        ld      bc,SHADOW_SIZE-1
        ld      (hl),0
        ldir
        ret

; The file-only half of select_file: window, shadows and descriptors carry
; over, which is what lets a second library land in the first one's page.
select_file_keep:
        ld      (FILE_BASE),hl
        ex      de,hl
        ld      (FILE_LEN),hl
        ld      hl,0
        ld      (FILE_POS),hl
        ret

; Expect CF=0 from l_load.  Returns CF=1 on a failure.
load_ok:
        call    run_load
        ret     c
        or      a
        ret

; Expect CF=1 from l_load with A=#FF.  Returns CF=0 when the rejection was
; clean, CF=1 otherwise.
load_fails:
        call    run_load
        jr      nc,load_fails_bad
        cp      #ff
        jr      nz,load_fails_bad
        or      a
        ret
load_fails_bad:
        scf
        ret

; Runs one l_load and validates the stack balance, propagating l_load's CF.
; A corrupted SP always reports as a failure.
run_load:
        ld      hl,dummy_path
        ld      (SP_BEFORE),sp
        ld      a,3
        call    LIBMAN.l_load
        ld      (SP_AFTER),sp
        push    af
        push    hl
        ld      hl,(SP_BEFORE)
        ld      de,(SP_AFTER)
        or      a
        sbc     hl,de
        jr      nz,run_load_unbalanced
        pop     hl
        pop     af
        ret
run_load_unbalanced:
        ld      sp,#3ff0                ; do not carry the damage forward
        ld      a,#ee
        scf
        ret

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
        jr      failed
; Reached only by executing the #FF fill in low memory, i.e. after a jump
; through a pointer relocation should have fixed up.
stray_execution:
        ld      a,#ea
        jr      failed
failed:
        ld      (TEST_RESULT),a
        ld      sp,#3ff0                ; the stray path arrives on any stack
test_done:
        halt

; ---------------------------------------------------------------------------
; DSS stub.  Estex-DSS makes no promise about HL/DE/IY across a call, so the
; stub destroys them after every transfer: the loader must carry nothing
; across RST #10 in those registers.
;
; READ destroys IX as well.  The historical loader never noticed because it
; copies every header field it needs into registers before its one big read
; and only then points IX at the buffer; code that reads (ix+n) after a READ
; gets rubbish, which on hardware showed up as a bogus byte count and a file
; pointer left past EOF.  SETWIN3 does preserve IX -- the copy loop depends
; on it and works on hardware -- so only READ clobbers it here.
; ---------------------------------------------------------------------------
dss_stub:
        ld      (DSS_A),a               ; descriptors and handles arrive in A
        ld      a,c
        cp      #3d                     ; ALLOC
        jr      z,dss_alloc
        cp      #3b                     ; SETWIN3
        jr      z,dss_setwin
        cp      #3e                     ; FREE
        jr      z,dss_ok
        cp      #11                     ; OPEN
        jr      z,dss_open
        cp      #12                     ; CLOSE
        jr      z,dss_ok
        cp      #15                     ; MOVE_FP
        jr      z,dss_seek
        cp      #13                     ; READ
        jr      z,dss_read
        ld      a,#7f
        scf
        ret
dss_alloc:
        ld      a,(NEXT_DESC)
        inc     a
        ld      (NEXT_DESC),a
        dec     a
        or      a
        ret
dss_open:
        ld      a,#33
        or      a
        ret
dss_ok:
        xor     a
        ret

; A = block descriptor, B = page index inside the block.  Swap the window
; contents through the per-page shadows so the caller really does see a
; different page.
dss_setwin:
        ld      a,(DSS_A)               ; the dispatch above replaced A with C
        sub     FIRST_DESC
        add     a,a
        add     a,b                     ; a = requested slot
        ld      c,a
        ld      a,(CUR_SLOT)
        cp      c
        jr      z,dss_setwin_done
        cp      NO_SLOT
        jr      z,dss_setwin_load
        call    slot_address            ; save the outgoing page
        ex      de,hl
        ld      hl,WINDOW
        push    bc                      ; c = incoming slot, consumed below
        ld      bc,SHADOW_SIZE
        ldir
        pop     bc
dss_setwin_load:
        ld      a,c
        ld      (CUR_SLOT),a
        call    slot_address
        ld      de,WINDOW
        ld      bc,SHADOW_SIZE
        ldir
dss_setwin_done:
        ld      iy,#dead
        xor     a
        ret

; A = slot -> HL = its shadow address.  C is preserved for the caller.
slot_address:
        push    bc
        add     a,a
        add     a,a
        add     a,SHADOW_BASE>>8
        ld      h,a
        ld      l,0
        pop     bc
        ret

; B=2 seeks to the end, anything else to the absolute offset in HL:IX.  The
; position comes back as HL:IX.  The offset really is honoured: the loader
; used to seek only to zero, and a stub that assumed so turned the seek onto
; the trailing payload into a seek back to the header.
dss_seek:
        ld      a,b
        cp      2
        jr      z,dss_seek_end
        push    ix
        pop     hl                      ; low word of the requested position
        jr      dss_seek_set
dss_seek_end:
        ld      hl,(FILE_LEN)
dss_seek_set:
        ld      (FILE_POS),hl
        push    hl
        pop     ix
        ld      hl,0                    ; high word of the position
        xor     a
        ret

; A = handle, HL = destination, DE = count.
;
dss_read:
        ld      a,d
        or      e
        jr      z,dss_ok
        push    hl                      ; destination
        push    de                      ; count
        ld      hl,(FILE_LEN)
        ld      bc,(FILE_POS)
        or      a
        sbc     hl,bc                   ; bytes still available
        or      a
        sbc     hl,de
        pop     de
        pop     hl
        jr      c,dss_read_short
        ex      de,hl                   ; hl = count, de = destination
        ld      b,h
        ld      c,l
        ld      hl,(FILE_BASE)
        push    de
        ld      de,(FILE_POS)
        add     hl,de                   ; hl = source
        pop     de
        ldir
        ld      de,(FILE_BASE)
        or      a
        sbc     hl,de                   ; ldir left hl past the last source byte
        ld      (FILE_POS),hl
        ld      hl,#dead
        ld      de,#beef
        ld      iy,#face
        ld      ix,#6d21                ; the value real DSS left behind
        xor     a
        ret
dss_read_short:
        ld      a,#1a
        scf
        ret

dummy_path:
        db      "TEST.DLL",0

; ---------------------------------------------------------------------------
; Files under test.  The relocatable one is built by the test with the real
; sprinter-mkdll; the rest are hand-written headers, since the loader rejects
; them before it reads anything past the first sixteen bytes.
; ---------------------------------------------------------------------------
file_l2_reloc:
        incbin  "l2_vector_lib.dll"
file_l2_reloc_end:
        db      #a5                     ; trailing payload, outside the prefix

        macro   DLLHEAD sig?, fsize?, csize?, rsize?
        db      sig?
        dw      fsize?
        dw      csize?
        dw      rsize?
        dw      0                       ; checksum, which the loader never reads
        db      1, 1
        dw      2026
        dw      #0100
        db      "VECTOR"
        ds      10,0
        endm

file_l2_plain:
        DLLHEAD "L2", #0030, #0030, #0000
        xor     a                       ; function 0: INIT
        ret
        nop
        xor     a                       ; function 1: FINI
        ret
        nop
        xor     a                       ; function 2
        ret
        ds      file_l2_plain+#30-$,#5a
file_l2_plain_end:
        db      #a5

; Relocatable but with an all-zero bitmap: takes the chunked path, occupies
; only the first #100-byte unit of its page, and leaves the rest for vector 9.
file_l2_small:
        DLLHEAD "L2", #0032, #0030, #0002
        xor     a                       ; function 0: INIT
        ret
        nop
        xor     a                       ; function 1: FINI
        ret
        nop
        xor     a                       ; function 2
        ret
        ds      file_l2_small+#30-$,#5a
        db      0,0                     ; bitmap: nothing to relocate
file_l2_small_end:

file_l2_big_code:
        DLLHEAD "L2", #4001, #4001, #0000
file_l2_big_code_end:

file_l2_big_table:
        DLLHEAD "L2", #4031, #0030, #4001
file_l2_big_table_end:

file_l2_packed:
        DLLHEAD "L2", #0035, #0030, #0010
file_l2_packed_end:

file_l2_tiny:
        DLLHEAD "L2", #0010, #0010, #0000
file_l2_tiny_end:

        assert  $ < #6000
        ds      #8000-$,0
        include "../../libman/libman.asm"

        assert  $ < SHADOW_BASE
        end     test_start
