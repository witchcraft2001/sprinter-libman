	ORG	8100h-512

;EXE-file header:
        dw 5845h     ; EXE Signature
        db 45h       ; Reserved (EXE type)
        db 00h       ; Version of EXE file
        dw 0200h     ; Code offset
	dw 0000h
        dw 0000h     ; Primary loader size or 0 (no primary loader)
        dw 0000h     ; Reserved
	dw 0000h     ; Reserved
        dw 0000h     ; Reserved
        dw START     ; Loading address
        dw START     ; Starting address (register PC)
        dw 0C000h    ; Stack address (register SP)
        ds 490       ; Reserved 

;code of program

	include	"antonfnt.inc"

START:

; Write welcome message

	ld	hl,msg
	ld	c,5ch
	rst	10h

; Load library

	ld	hl,filenam
	ld	a,3
	call	l_load
	jp	c,error
	ld	(handle),hl 

; Copy library info

	ld	hl,(handle)
	ld	de,buf
	call	l_info
	jp	c,error

	ld	c, #51			; save previos vmode
	rst	#10
	ld	(vmode), a
	ld	a, b
	ld	(vscrn), a
	ld	bc, #0050		; set 640x256x16
	ld	a, #82
	rst	#10
	
; Make FN style graphics and palette

	ld	hl,(handle)
	ld	b,ANTONFNT_FNSTYLE
	call	L_CALL

; Write name of library

	ld	de,buf+16	; text string
	ld	ix,0		; x position
	ld	iy,32		; y position
	ld	a,#70		; background|foreground
	ld	hl,(handle)
	ld	b,ANTONFNT_APRINT
	call	L_CALL
	jp	c,error1

; Draw string 1

	ld	de,str1		; text string
	ld	ix,#0020	; x position
	ld	iy,#0000	; y position
	ld	a,#02		; background|foreground
	ld	hl,(handle)
	ld	b,3
	call	L_CALL
	jp	c,error1

; Draw string 2

	ld	de,str2		; text string
	ld	ix,#0020	; x position
	ld	iy,#0008	; y position
	ld	a,#1F		; background|foreground
	ld	hl,(handle)
	ld	b,3
	call	L_CALL
	jp	c,error1

; Wait keypress

	ld	c,30h
	rst	10h

; Close library

	ld	hl,(handle)
	call	l_free
	jp	c,error1

error1:
	ld	a,(vscrn)
	ld	b,a
	ld	a,(vmode)
	ld	c, #50
	rst	#10			; set previos vmode

error:


; Exit from program

	ld	bc,0041h 
	rst	10h      

handle	dw	0
msg	db	"LIBMAN Test",13,10,0
str1:	db	"Color print with acceleration.", 0
str2:	db	"Written by Enin Anton. (c) Copyright 2002 R-lab", 0
buf	ds	32
filenam db	"antonfnt.dll",0
vmode	db	0
vscrn	db	0

	include "libman.a"
