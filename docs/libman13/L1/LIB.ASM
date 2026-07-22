	org	0


	jp	init
	jp	free
	jp	user

;N0
init:
	ld	hl,_init
	ld	c,5Ch
	rst	10h
	xor	a			; for LIBMAN
	ret
;N1
free:
	ld	hl,_free
	ld	c,5Ch
	rst	10h
	ret
;N2
user:
	ld	hl,_user
	ld	c,5Ch
	rst	10h
	ret


_init:	db	"DLL init",0Dh,0Ah,0
_free:	db	"DLL free",0Dh,0Ah,0
_user:	db	"DLL user",0Dh,0Ah,0
